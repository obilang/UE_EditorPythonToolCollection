"""
Convert an in-place locomotion cycle (walk / run) into a root-motion animation.

The idea
--------
A true in-place cycle has no world translation to *extract* -- it has to be
*synthesized* from the feet.  During a foot's stance (contact) phase the planted
foot slides backwards relative to the (static) body; that backward slide is
exactly how far the character would have travelled forward if the foot had been
gripping the ground.

So instead of measuring root motion, we *pin the support foot to the ground* and
let that decide where the root must go:

    we want   foot_world_new(f)  ==  foot_world_new(f-1)        (foot does not move)

Because the whole skeleton hangs under a currently-static root, changing the
root post-multiplies every descendant's world matrix (Maya row-vector
convention)::

    descendant_world_new = descendant_world_old * D(f)

where ``D(f)`` is the accumulated world-space root delta we are solving for.
Plugging the pin condition in for the foot gives the recurrence::

    foot(f) * D(f) == foot(f-1) * D(f-1)
    =>  D(f) = foot(f)^-1 * foot(f-1) * D(f-1)
    =>  D(f) =        delta(f)        * D(f-1) ,   D(0) = I

Each foot matrix is first projected to a ground-plane rigid motion -- horizontal
translation (Y is up) plus yaw only -- so the accumulated motion is a clean
SE(2) trajectory: forward translation *and* turning, with no vertical bob or
pitch/roll leaking into the root.

Several *pin points* are tracked -- both ankles, plus (by default) both toe /
ball joints.  Per frame we compute each point's own delta, then blend them by a
soft "how planted is this point" contact weight (low + slow == planted).  The
planted point dominates, and at handoff the deltas blend smoothly instead of
popping.

The toes matter at the foot switch.  During toe-off the back ankle is lifting
and rotating, so it scores as unplanted -- while the front foot is still
landing and also scores unplanted.  With ankles alone neither wins that window:
the blend cancels or falls below the contact floor and coasts, so the root
barely advances and the back foot visibly slides.  The toe is the point that is
genuinely gripping the ground and driving the body forward there, so including
it gives a confident pin exactly where the ankles are ambiguous.  Because a toe
sits systematically lower than an ankle, the contact height gate is normalized
per *tier* (ankles against ankles, toes against toes) rather than globally.

Finally the root's world transform per frame becomes ``R0 * D(f)`` (``R0`` = the
root's original, static world matrix) and is keyed onto the root joint.  The body
rides forward with it and the feet stop sliding.

Assumptions (chosen for the current walk/run in-place cycles)
------------------------------------------------------------
* Y-up scene (ground = XZ plane).
* A dedicated, currently-static root joint that is an ancestor of the feet.
* Translation + yaw are synthesised; pitch / roll / vertical of the root are
  left untouched.

Usage
-----
In Maya's script editor (Python)::

    import convert_inplace_to_rootmotion as cv
    cv.show_ui()

or headless / scripted::

    cv.convert(
        root="root",
        foot_l="ankle_l",       # the ankle joints (or foot locators)
        foot_r="ankle_r",
        start=None, end=None,   # None -> playback range
        use_toes=True,          # also pin the toes; auto-found under each foot
    )
"""

import math

import maya.cmds as cmds
import maya.api.OpenMaya as om


# ---------------------------------------------------------------------------
# tuning
# ---------------------------------------------------------------------------

# Soft contact-detection scales, expressed as fractions of the clip's vertical
# foot travel and per-frame horizontal foot travel.  They only shape the *blend*
# between the two feet, so the exact values are forgiving.
_HEIGHT_SOFTNESS = 0.5      # smaller -> only the very lowest foot counts as planted
_SPEED_SOFTNESS = 0.5       # smaller -> only a very slow foot counts as planted
# A truly planted foot is also not moving VERTICALLY. A foot about to land is
# low and (easing in) slow, which fools the height+speed gates into handing it
# weight while it is still creeping forward -> the root slides backward at the
# handoff. Gating on vertical motion rejects the incoming foot until it settles
# (and the lift-off frames too). Apex of the swing also has dy~=0 but is high,
# so the height gate keeps it out.
_VSPEED_SOFTNESS = 0.5      # smaller -> a foot must be more vertically still to count
# How sharply the planted foot wins the blend. With soft weighting the
# forward-moving SWING foot bleeds in and partially cancels the planted foot's
# backward slide, so the root under-travels (~half speed at sharpness 1). The
# exponent pushes the blend towards winner-take-all while keeping a brief soft
# transition at foot-handoff (no pop). 8 reaches ~98% of true stride travel.
_CONTACT_SHARPNESS = 8.0
# Below this combined planted-ness confidence we treat the frame as "no foot
# planted" (e.g. a run's flight phase) and coast on the previous delta instead
# of pinning a fast-moving swing foot.
_CONTACT_FLOOR = 0.15
_EPS = 1e-8


# ---------------------------------------------------------------------------
# small math helpers (everything in Maya row-vector convention: p_world = p*M)
# ---------------------------------------------------------------------------

def _world_matrix(node, attr="worldMatrix"):
    """Current world matrix of ``node`` as an MMatrix (sample after setting time)."""
    vals = cmds.getAttr("{0}.{1}[0]".format(node, attr))
    return om.MMatrix(vals)


def _toe_candidates(foot):
    """Joint children of ``foot``, paired with horizontal distance from it.

    Sorted furthest-first.  Rigs often carry twist or helper joints directly
    under the ankle, so "first child" guesses wrong often; the real toe is the
    one that extends *forward* along the foot, so the furthest child is a much
    better guess.  The caller prints the whole scored list, so when the guess is
    wrong it is obvious *and* the right joint's name is right there to paste
    into ``toe_l`` / ``toe_r``.
    """
    children = cmds.listRelatives(foot, children=True, type="joint",
                                  fullPath=True) or []
    origin = _world_matrix(foot)
    scored = []
    for child in children:
        m = _world_matrix(child)
        scored.append(
            (child, math.hypot(m[12] - origin[12], m[14] - origin[14])))
    scored.sort(key=lambda cd: -cd[1])
    return scored


def _find_toe(foot):
    """Best-guess toe / ball joint under ``foot``, or ``None`` if it has none."""
    scored = _toe_candidates(foot)
    return scored[0][0] if scored else None


def _yaw_from_matrix(m):
    """Extract the Y (yaw) Euler angle, in radians, from world matrix ``m``.

    Uses the matrix's local +Z axis projected onto the ground plane, which is
    robust to whatever pitch/roll the foot carries during the stride.
    """
    # row 2 (indices 8,9,10) is the node's world +Z axis under row-vector convention
    zx = m[8]
    zz = m[10]
    return math.atan2(zx, zz)


def _ground_matrix(yaw, x, z):
    """Build a clean ground-plane SE(2) matrix: yaw about Y, translate in XZ."""
    c = math.cos(yaw)
    s = math.sin(yaw)
    # rotateY then translate, row-vector layout
    return om.MMatrix([
        c,    0.0, -s,   0.0,
        0.0,  1.0,  0.0, 0.0,
        s,    0.0,  c,   0.0,
        x,    0.0,  z,   1.0,
    ])


def _delta_to_yaw_dxz(delta):
    """Decompose a small SE(2) delta matrix into (d_yaw, dx, dz) for blending."""
    d_yaw = _yaw_from_matrix(delta)
    return d_yaw, delta[12], delta[14]


def _project_onto_axis(dx, dz, axis_deg):
    """Project a (dx, dz) vector onto the world heading ``axis_deg``.

    Uses the same convention as ``_yaw_from_matrix`` (0deg = +Z, 90deg = +X),
    so a locked axis lines up with the yaw the tool already reports.
    """
    rad = math.radians(axis_deg)
    ux, uz = math.sin(rad), math.cos(rad)
    proj = dx * ux + dz * uz
    return proj * ux, proj * uz


# ---------------------------------------------------------------------------
# sampling
# ---------------------------------------------------------------------------

def _frame_range(start, end):
    if start is None:
        start = cmds.playbackOptions(q=True, min=True)
    if end is None:
        end = cmds.playbackOptions(q=True, max=True)
    start = int(round(start))
    end = int(round(end))
    if end < start:
        start, end = end, start
    return start, end


def _parse_frame_ranges(text):
    """Parse comma-separated frame numbers/ranges, e.g. "12-18, 30-34, 40".

    Returns a list of (start, end) int tuples (inclusive, start <= end).
    Raises ValueError with the offending chunk on malformed input.
    """
    ranges = []
    for chunk in (text or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            if "-" in chunk:
                a, b = chunk.split("-", 1)
                start, end = int(a), int(b)
            else:
                start = end = int(chunk)
        except ValueError:
            raise ValueError("Invalid frame range '{0}'".format(chunk))
        if end < start:
            start, end = end, start
        ranges.append((start, end))
    return ranges


def _sample_points(nodes, start, end):
    """Step through every frame and record each pin point's world matrix.

    Returns ``frames, grounds, raw_ys`` where ``grounds[j]`` is point ``j``'s
    per-frame list of clean SE(2) matrices and ``raw_ys[j]`` its per-frame
    un-projected world Y (used for contact height).
    """
    frames = list(range(start, end + 1))
    grounds = [[] for _ in nodes]
    raw_ys = [[] for _ in nodes]

    restore_time = cmds.currentTime(q=True)
    try:
        for f in frames:
            cmds.currentTime(f, edit=True)
            for j, node in enumerate(nodes):
                m = _world_matrix(node)
                grounds[j].append(
                    _ground_matrix(_yaw_from_matrix(m), m[12], m[14]))
                raw_ys[j].append(m[13])
    finally:
        cmds.currentTime(restore_time, edit=True)

    return frames, grounds, raw_ys


# ---------------------------------------------------------------------------
# contact weighting
# ---------------------------------------------------------------------------

def _horizontal_speed(ground_seq, i):
    """Per-frame horizontal foot travel at index ``i`` (centered, ends clamped)."""
    n = len(ground_seq)
    if n < 2:
        return 0.0
    lo = max(i - 1, 0)
    hi = min(i + 1, n - 1)
    a, b = ground_seq[lo], ground_seq[hi]
    span = max(hi - lo, 1)
    dx = (b[12] - a[12]) / span
    dz = (b[14] - a[14]) / span
    return math.hypot(dx, dz)


def _vertical_speed(y_seq, i):
    """Per-frame absolute vertical foot motion at index ``i`` (centered)."""
    n = len(y_seq)
    if n < 2:
        return 0.0
    lo = max(i - 1, 0)
    hi = min(i + 1, n - 1)
    span = max(hi - lo, 1)
    return abs((y_seq[hi] - y_seq[lo]) / span)


def _contact_weights(grounds, raw_ys, tiers, sharpness=_CONTACT_SHARPNESS):
    """Soft per-frame planted-ness weights across N pin points.

    Returns a list of ``(weights, confidence)`` per frame, where ``weights`` is
    a list summing to 1 (normalized blend across all points) and ``confidence``
    in ``[0, 1]`` is the *un-normalized* planted-ness of the best point -- low
    when nothing is on the ground (e.g. a flight phase), used downstream to
    decide whether to pin at all.

    ``tiers[j]`` names point ``j``'s kind ("ankle" / "toe").  The height gate is
    normalized *per tier*: ankles sit systematically higher off the ground than
    toes, so one shared reference would make every ankle look permanently "high"
    and never planted.  Speed references stay global -- those magnitudes are
    comparable across tiers, and a global reference avoids amplifying tiny toe
    jitter into "fast".

    ``sharpness`` (>= 1) biases the blend towards the most-planted point; higher
    values approach winner-take-all and recover more of the true stride speed.
    """
    n = len(grounds[0])
    npts = len(grounds)

    speeds = [[_horizontal_speed(grounds[j], i) for i in range(n)]
              for j in range(npts)]
    vspeeds = [[_vertical_speed(raw_ys[j], i) for i in range(n)]
               for j in range(npts)]

    speed_ref = max(max(max(s) for s in speeds), _EPS)
    vspeed_ref = max(max(max(v) for v in vspeeds), _EPS)
    s_scale = max(speed_ref * _SPEED_SOFTNESS, _EPS)
    v_scale = max(vspeed_ref * _VSPEED_SOFTNESS, _EPS)

    # Per-tier ground reference + height softness scale.
    tier_ref = {}
    for tier in set(tiers):
        tier_y = [y for j in range(npts) if tiers[j] == tier for y in raw_ys[j]]
        y_min = min(tier_y)
        y_span = max(max(tier_y) - y_min, _EPS)
        tier_ref[tier] = (y_min, max(y_span * _HEIGHT_SOFTNESS, _EPS))

    def planted(tier, raw_y_i, spd, vspd):
        y_min, h_scale = tier_ref[tier]
        h = raw_y_i - y_min
        # low (for its own kind) + horizontally slow + vertically still
        return (math.exp(-h / h_scale)
                * math.exp(-spd / s_scale)
                * math.exp(-vspd / v_scale))

    weights = []
    for i in range(n):
        w = [planted(tiers[j], raw_ys[j][i], speeds[j][i], vspeeds[j][i])
             for j in range(npts)]
        confidence = max(w)             # how planted the *best* point is
        total = sum(w)
        if total < _EPS:
            w = [1.0 / npts] * npts
        else:
            # Sharpen towards winner-take-all so a swing point's forward motion
            # doesn't cancel the planted point's slide (which halves root speed).
            w = [(x / total) ** sharpness for x in w]
            s = sum(w)
            w = [x / s for x in w]
        weights.append((w, confidence))
    return weights


def _apply_pin_overrides(frames, weights, sides, pin_l_ranges, pin_r_ranges):
    """Force specific frames to pin to one side of the body.

    ``pin_l_ranges`` / ``pin_r_ranges`` are lists of (start, end) frame-number
    tuples (inclusive).  A pinned frame keeps only that side's points -- the
    other side is zeroed and the survivors are renormalized, so the automatic
    ankle-vs-toe split *within* the side is preserved (that split is what
    handles the roll-through at toe-off).  Confidence becomes 1 so the frame
    never coasts.  Raises ValueError if a frame is pinned to both sides at once
    (ambiguous).
    """
    def _expand(ranges):
        s = set()
        for start, end in ranges or []:
            s.update(range(start, end + 1))
        return s

    l_frames = _expand(pin_l_ranges)
    r_frames = _expand(pin_r_ranges)
    overlap = l_frames & r_frames
    if overlap:
        raise ValueError(
            "Frame(s) {0} are pinned to both the left and right foot -- "
            "fix the overlapping ranges.".format(sorted(overlap)))

    out = list(weights)
    for i, f in enumerate(frames):
        if f in l_frames:
            side = "L"
        elif f in r_frames:
            side = "R"
        else:
            continue

        w, _ = weights[i]
        keep = [w[j] if sides[j] == side else 0.0 for j in range(len(w))]
        total = sum(keep)
        if total < _EPS:
            # That side had no planted-ness at all: split evenly across it
            # rather than dividing by zero.
            members = [j for j in range(len(w)) if sides[j] == side]
            keep = [1.0 / len(members) if j in members else 0.0
                    for j in range(len(w))]
        else:
            keep = [x / total for x in keep]
        out[i] = (keep, 1.0)
    return out


# ---------------------------------------------------------------------------
# trajectory synthesis
# ---------------------------------------------------------------------------

def _circular_blend(yaws, weights):
    """Weighted circular mean of N angles -- safe across the +/-pi branch cut."""
    return math.atan2(
        sum(w * math.sin(y) for y, w in zip(yaws, weights)),
        sum(w * math.cos(y) for y, w in zip(yaws, weights)))


def _accumulate_root_deltas(grounds, weights, lock_axis=None):
    """Build the accumulated world-space root delta D(f) for every frame.

    Returns a list of MMatrix, one per frame, with D(0) = identity.  Frames with
    no convincingly-planted point (e.g. a flight phase) coast on the previous
    delta rather than pinning a fast-moving swing point.  The keyed rotation
    curve is Euler-unwrapped afterwards in ``_apply_root``.

    ``lock_axis``, if not ``None``, is a heading in degrees expressed relative
    to the body's *current* facing (same convention as yaw: 0 = forward,
    90 = side).  Each frame's blended *local* travel step -- before it gets
    rotated into world space by the accumulated heading -- is projected onto
    that direction, forcing the predicted travel to always point the chosen
    way relative to however the body is currently facing (e.g. "always
    forward, never sideways") instead of whatever direction the noisy foot
    blend produces.  Locking pre-rotation like this means the root still
    curves naturally through world space if the clip turns; it only removes
    drift relative to the body's own heading.  Yaw itself is never affected.
    """
    n = len(grounds[0])
    npts = len(grounds)
    d = om.MMatrix()  # identity
    deltas = [om.MMatrix(d)]
    prev_blended = None

    for i in range(1, n):
        w, confidence = weights[i]

        if confidence < _CONTACT_FLOOR and prev_blended is not None:
            # Nothing is convincingly planted: coast on the last good delta.
            blended = prev_blended
        else:
            # each point's own pin delta: point(f)^-1 * point(f-1)
            yaws, dxs, dzs = [], [], []
            for j in range(npts):
                yaw, dx, dz = _delta_to_yaw_dxz(
                    grounds[j][i].inverse() * grounds[j][i - 1])
                yaws.append(yaw)
                dxs.append(dx)
                dzs.append(dz)

            d_yaw = _circular_blend(yaws, w)
            b_x = sum(w[j] * dxs[j] for j in range(npts))
            b_z = sum(w[j] * dzs[j] for j in range(npts))

            if lock_axis is not None:
                proj_x, proj_z = _project_onto_axis(b_x, b_z, lock_axis)
                print("[axis_lock] i={} lock_axis={} local_step=({:.5f},{:.5f}) "
                      "projected=({:.5f},{:.5f})".format(
                          i, lock_axis, b_x, b_z, proj_x, proj_z))
                b_x, b_z = proj_x, proj_z

            blended = _ground_matrix(d_yaw, b_x, b_z)
            prev_blended = blended

        d = blended * d            # D(f) = delta(f) * D(f-1)
        deltas.append(om.MMatrix(d))

    return deltas


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------

def _coast_flags(weights):
    """Per-frame "this frame reused the previous delta" flags.

    Mirrors the exact condition in ``_accumulate_root_deltas`` (including that
    there is nothing to coast *on* until the first confidently-pinned frame),
    so the report cannot disagree with what was actually baked.
    """
    flags = [False]
    prev_ok = False
    for i in range(1, len(weights)):
        coast = weights[i][1] < _CONTACT_FLOOR and prev_ok
        flags.append(coast)
        if not coast:
            prev_ok = True
    return flags


def _report_pins(frames, nodes, sides, tiers, grounds, raw_ys, weights, deltas):
    """Print which pin point drives each frame, so a bad pick is visible.

    Two independent things go wrong in practice, and this report separates them:

    * **Wrong joint resolved.**  Check the legend.  A real ball/toe joint hugs
      the ground, so its ``Y min`` should be clearly *lower* than its ankle's
      and its ``dist`` from the ankle should be a believable foot length.  A
      twist/helper joint gives away by sitting at ~the same height as the ankle
      with ``dist`` near 0.
    * **Wrong point leading.**  Check the ``leader`` column against what the
      foot is actually doing on that frame.  During toe-off the toe should lead;
      through mid-stance the ankle is fine.  ``*`` marks frames where nothing
      scored as planted at all, so the root just reused the previous delta --
      a run of those is what shows up as a dense cluster of root keys.
    """
    npts = len(nodes)
    n = len(frames)

    # Same-side ankle for each point, to report a meaningful separation.
    ankle_of = {}
    for j in range(npts):
        if tiers[j] == "ankle":
            ankle_of[sides[j]] = j

    print("")
    print("[pins] resolved pin points:")
    for j in range(npts):
        ys = raw_ys[j]
        a = ankle_of.get(sides[j])
        if a is None or a == j:
            dist = "     -"
        else:
            dist = "{0:>6.3f}".format(math.hypot(
                grounds[j][0][12] - grounds[a][0][12],
                grounds[j][0][14] - grounds[a][0][14]))
        print("  [{0}] {1} {2:<5}  Y min {3:>9.3f}  max {4:>9.3f}  "
              "dist-to-ankle {5}  {6}".format(
                  j, sides[j], tiers[j], min(ys), max(ys), dist, nodes[j]))

    speeds = [[_horizontal_speed(grounds[j], i) for i in range(n)]
              for j in range(npts)]
    vspeeds = [[_vertical_speed(raw_ys[j], i) for i in range(n)]
               for j in range(npts)]
    tier_min = {}
    for tier in set(tiers):
        tier_min[tier] = min(y for j in range(npts) if tiers[j] == tier
                             for y in raw_ys[j])

    coast = _coast_flags(weights)

    print("")
    print("[pins] per-frame decision  ('*' = nothing planted, reused previous "
          "delta):")
    print("  frame  leader        weight   conf  height   hspd   vspd"
          "  | travelX   travelZ  headY")
    led = [0] * npts
    for i in range(n):
        w, conf = weights[i]
        j = max(range(npts), key=lambda k: w[k])
        led[j] += 1
        d = deltas[i]
        print("  {0:>5}{1} [{2}] {3} {4:<5} {5:>6.3f} {6:>6.3f} {7:>7.3f} "
              "{8:>6.3f} {9:>6.3f} | {10:>8.3f} {11:>9.3f} {12:>6.1f}".format(
                  frames[i], "*" if coast[i] else " ", j, sides[j], tiers[j],
                  w[j], conf, raw_ys[j][i] - tier_min[tiers[j]],
                  speeds[j][i], vspeeds[j][i],
                  d[12], d[14], math.degrees(_yaw_from_matrix(d))))

    print("")
    print("[pins] frames led: {0}".format(", ".join(
        "[{0}] {1} {2} = {3}".format(j, sides[j], tiers[j], led[j])
        for j in range(npts))))
    print("[pins] reused-previous-delta frames: {0} of {1} "
          "(confidence below the {2} contact floor)".format(
              sum(coast), n - 1, _CONTACT_FLOOR))


# ---------------------------------------------------------------------------
# applying to the root joint
# ---------------------------------------------------------------------------

def _clear_root_keys(root):
    """Remove any translate/rotate keys baked onto ``root``."""
    for attr in ("translateX", "translateY", "translateZ",
                 "rotateX", "rotateY", "rotateZ"):
        plug = "{0}.{1}".format(root, attr)
        if cmds.keyframe(plug, q=True, keyframeCount=True):
            cmds.cutKey(plug, clear=True)


def _apply_root(root, frames, deltas, clear_existing=True):
    """Key ``R0 * D(f)`` onto the root for every frame."""
    rot_plugs = ["{0}.rotate{1}".format(root, ax) for ax in ("X", "Y", "Z")]
    restore_time = cmds.currentTime(q=True)
    try:
        # R0 = root's original (static) world matrix, sampled once at frames[0].
        cmds.currentTime(frames[0], edit=True)
        r0 = _world_matrix(root)

        if clear_existing:
            _clear_root_keys(root)

        for f, d in zip(frames, deltas):
            cmds.currentTime(f, edit=True)
            world = list(r0 * d)
            cmds.xform(root, worldSpace=True, matrix=world)
            cmds.setKeyframe(root, attribute=("translate", "rotate"))

        # Unwrap Euler discontinuities so accumulated yaw past +/-180 doesn't
        # interpolate as a ~360-degree spin between adjacent keys.
        existing = [p for p in rot_plugs
                    if cmds.keyframe(p, q=True, keyframeCount=True)]
        if existing:
            cmds.filterCurve(existing, filter="euler")
    finally:
        cmds.currentTime(restore_time, edit=True)


# ---------------------------------------------------------------------------
# public entry point
# ---------------------------------------------------------------------------

def convert(root, foot_l, foot_r, start=None, end=None, clear_existing=True,
            sharpness=_CONTACT_SHARPNESS, lock_axis=None,
            pin_l_ranges=None, pin_r_ranges=None,
            use_toes=True, toe_l=None, toe_r=None):
    """Synthesise root motion for an in-place cycle and key it onto ``root``.

    Parameters
    ----------
    root : str
        The static root joint that is an ancestor of both feet.
    foot_l, foot_r : str
        Left / right foot drivers -- normally the ankle joints.
    start, end : int or None
        Frame range; ``None`` uses the timeline playback range.
    clear_existing : bool
        Remove any pre-existing translate/rotate keys on the root first.
    sharpness : float
        Contact-blend sharpness (>= 1). Raise it if the feet still slide (root
        too slow); lower it towards 1 if the root motion looks jittery. ~8 is a
        good default; 1 is the original soft blend (~half speed).
    lock_axis : float or None
        Heading in degrees, relative to the body's current facing, to
        manually pin the predicted travel direction to (same convention as
        yaw: 0 = forward, 90 = side). ``None`` (default) leaves the
        direction free, as computed from the foot blend. Use this when the
        foot-blend prediction drifts sideways relative to how the body is
        actually facing (e.g. a walk that should track straight ahead with
        zero strafe) -- each frame's local travel step is projected onto this
        axis, relative to the current heading, before being rotated into
        world space and accumulated. Because the lock tracks the body's own
        turning, the root still curves naturally through a clip that turns;
        only drift relative to the heading is removed. Rotation (yaw) is
        never affected.
    pin_l_ranges, pin_r_ranges : list of (start, end) or None
        Frame ranges (inclusive) where the left / right *side* should be
        pinned, overriding whatever ``_contact_weights`` computed. The
        ankle-vs-toe choice within the pinned side stays automatic. Use
        this when the automatic heuristic picks the wrong foot over some
        stretch of the clip. A frame may not appear in both -- that is
        ambiguous and raises ``ValueError``.
    use_toes : bool
        Also track each foot's toe / ball joint as a pin candidate. This
        matters at the foot switch: during toe-off the ankle is lifting and
        rotating so it scores as unplanted, while the toe is still gripping
        and driving the body forward. Without the toes neither foot wins
        that window, the root stalls and the back foot slides. Default on.
    toe_l, toe_r : str or None
        Explicit toe joints. ``None`` (default) auto-detects via
        ``_find_toe`` -- the furthest joint child of each foot. Only used
        when ``use_toes`` is true.
    """
    for n in (root, foot_l, foot_r):
        if not cmds.objExists(n):
            raise ValueError("Node does not exist: '{0}'".format(n))

    # Pin points: each foot's ankle, plus optionally its toe. Tiers keep the
    # contact height gate honest (ankles sit higher than toes); sides let the
    # manual pin ranges restrict to one leg.
    nodes = [foot_l, foot_r]
    sides = ["L", "R"]
    tiers = ["ankle", "ankle"]

    if use_toes:
        for foot, explicit, side in ((foot_l, toe_l, "L"), (foot_r, toe_r, "R")):
            if explicit:
                toe = explicit
                print("[pin_points] {0} toe set explicitly to '{1}'".format(
                    side, toe))
            else:
                # Print every candidate, not just the winner: auto-detection is
                # a guess, and this is what makes a wrong guess visible (and
                # the right joint's name easy to copy into toe_l / toe_r).
                scored = _toe_candidates(foot)
                if scored:
                    print("[pin_points] {0} toe candidates under '{1}': "
                          "{2}".format(side, foot.split("|")[-1], ", ".join(
                              "{0} (dist {1:.3f})".format(c.split("|")[-1], dd)
                              for c, dd in scored)))
                toe = scored[0][0] if scored else None
                if toe is not None:
                    print("[pin_points] {0} toe auto-detected as '{1}' -- if "
                          "that is not the ball/toe joint, set it explicitly "
                          "in the UI.".format(side, toe.split("|")[-1]))
            if toe is None:
                cmds.warning(
                    "No joint child found under '{0}'; using the ankle alone "
                    "for that side. Root motion may stall at toe-off.".format(
                        foot))
                continue
            if not cmds.objExists(toe):
                raise ValueError("Node does not exist: '{0}'".format(toe))
            nodes.append(toe)
            sides.append(side)
            tiers.append("toe")

    up = cmds.upAxis(q=True, axis=True)
    if up != "y":
        cmds.warning(
            "Scene up-axis is '{0}'; this tool assumes Y-up. Results may be "
            "wrong on the ground plane.".format(up))

    start, end = _frame_range(start, end)
    if end - start < 1:
        raise ValueError("Need at least two frames to synthesise motion.")

    # R0 is sampled at the first frame; if the root is already animated, that
    # one pose gets baked into every synthesised frame. Warn rather than guess.
    for attr in ("translate", "rotate"):
        plug = "{0}.{1}".format(root, attr)
        if cmds.keyframe(plug, q=True, keyframeCount=True):
            cmds.warning(
                "Root '{0}' already has {1} keys; the tool assumes a static "
                "root. R0 will be taken from frame {2}.".format(
                    root, attr, start))
            break

    frames, grounds, raw_ys = _sample_points(nodes, start, end)
    weights = _contact_weights(grounds, raw_ys, tiers, sharpness=sharpness)
    if pin_l_ranges or pin_r_ranges:
        weights = _apply_pin_overrides(frames, weights, sides,
                                       pin_l_ranges, pin_r_ranges)
    deltas = _accumulate_root_deltas(grounds, weights, lock_axis=lock_axis)
    _report_pins(frames, nodes, sides, tiers, grounds, raw_ys, weights, deltas)
    _apply_root(root, frames, deltas, clear_existing=clear_existing)

    total = list(deltas[-1])
    dist = math.hypot(total[12], total[14])
    cmds.inViewMessage(
        amg="Root motion baked: <hl>{0}</hl> frames, travel <hl>{1:.2f}</hl> "
            "units.".format(len(frames), dist),
        pos="midCenter", fade=True)
    return dist


# ---------------------------------------------------------------------------
# cmds UI (version-robust; no PySide dependency)
# ---------------------------------------------------------------------------

_WIN = "inplaceToRootMotionWin"
_FIELDS = {}


def _set_from_selection(field):
    sel = cmds.ls(selection=True, long=False)
    if not sel:
        cmds.warning("Nothing selected.")
        return
    cmds.textField(_FIELDS[field], edit=True, text=sel[0])


_AXIS_LOCK_ITEMS = ("Free (no lock)", "Forward / Back", "Left / Right (strafe)",
                    "Custom angle...")
_AXIS_LOCK_DEGREES = {
    "Free (no lock)": None,
    "Forward / Back": 0.0,
    "Left / Right (strafe)": 90.0,
}


def _resolve_lock_axis():
    choice = cmds.optionMenu(_FIELDS["axis_lock_menu"], q=True, value=True)
    if choice == "Custom angle...":
        return cmds.floatField(_FIELDS["axis_lock_angle"], q=True, value=True)
    return _AXIS_LOCK_DEGREES[choice]


def _toggle_axis_angle(*_):
    choice = cmds.optionMenu(_FIELDS["axis_lock_menu"], q=True, value=True)
    cmds.floatField(_FIELDS["axis_lock_angle"], edit=True,
                    enable=(choice == "Custom angle..."))


def _toggle_toes(value):
    for key in ("toe_l", "toe_r"):
        cmds.textField(_FIELDS[key], edit=True, enable=value)


def _on_delete_baked(*_):
    root = cmds.textField(_FIELDS["root"], q=True, text=True).strip()
    if not root:
        cmds.warning("Please fill in root.")
        return
    if not cmds.objExists(root):
        cmds.warning("Node does not exist: '{0}'".format(root))
        return
    _clear_root_keys(root)
    cmds.inViewMessage(
        amg="Baked root motion deleted on <hl>{0}</hl>.".format(root),
        pos="midCenter", fade=True)


def _on_convert(*_):
    root = cmds.textField(_FIELDS["root"], q=True, text=True).strip()
    foot_l = cmds.textField(_FIELDS["foot_l"], q=True, text=True).strip()
    foot_r = cmds.textField(_FIELDS["foot_r"], q=True, text=True).strip()
    use_range = cmds.checkBox(_FIELDS["use_range"], q=True, value=True)
    clear = cmds.checkBox(_FIELDS["clear"], q=True, value=True)
    sharpness = cmds.floatField(_FIELDS["sharpness"], q=True, value=True)
    use_toes = cmds.checkBox(_FIELDS["use_toes"], q=True, value=True)
    toe_l = cmds.textField(_FIELDS["toe_l"], q=True, text=True).strip() or None
    toe_r = cmds.textField(_FIELDS["toe_r"], q=True, text=True).strip() or None
    lock_axis = _resolve_lock_axis()
    print("[axis_lock] resolved lock_axis from UI = {}".format(lock_axis))

    start = end = None
    if use_range:
        start = cmds.intField(_FIELDS["start"], q=True, value=True)
        end = cmds.intField(_FIELDS["end"], q=True, value=True)

    if not (root and foot_l and foot_r):
        cmds.warning("Please fill in root, left foot and right foot.")
        return

    try:
        pin_l_ranges = _parse_frame_ranges(cmds.textField(_FIELDS["pin_l"], q=True, text=True))
        pin_r_ranges = _parse_frame_ranges(cmds.textField(_FIELDS["pin_r"], q=True, text=True))
    except ValueError as exc:
        cmds.confirmDialog(title="Invalid frame range", message=str(exc), button=["OK"])
        return

    try:
        convert(root, foot_l, foot_r, start=start, end=end, clear_existing=clear,
                sharpness=sharpness, lock_axis=lock_axis,
                pin_l_ranges=pin_l_ranges, pin_r_ranges=pin_r_ranges,
                use_toes=use_toes, toe_l=toe_l, toe_r=toe_r)
    except Exception as exc:  # surface the error to the user, not just the log
        cmds.confirmDialog(title="Convert failed", message=str(exc), button=["OK"])
        raise


def _node_row(label, key, annotation=""):
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(70, 200, 90),
                   adjustableColumn=2, columnAlign=(1, "right"))
    cmds.text(label=label)
    _FIELDS[key] = cmds.textField(annotation=annotation)
    cmds.button(label="<- Sel", command=lambda *_: _set_from_selection(key))
    cmds.setParent("..")


def show_ui():
    """Open the converter window."""
    if cmds.window(_WIN, exists=True):
        cmds.deleteUI(_WIN)

    cmds.window(_WIN, title="In-Place -> Root Motion", widthHeight=(380, 470),
                sizeable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6,
                      columnOffset=("both", 8))
    cmds.text(label="")
    cmds.text(label="Pin the support foot to synthesise root translation + yaw.",
              align="left")
    cmds.separator(style="in", height=8)

    _node_row("Root:", "root")
    _node_row("Left foot:", "foot_l")
    _node_row("Right foot:", "foot_r")

    cmds.separator(style="in", height=8)

    _FIELDS["use_range"] = cmds.checkBox(
        label="Use custom frame range (off = playback range)", value=False,
        changeCommand=lambda v: _toggle_range(v))

    cmds.rowLayout(numberOfColumns=4, columnWidth4=(60, 80, 60, 80),
                   columnAlign=(1, "right"))
    cmds.text(label="Start:")
    _FIELDS["start"] = cmds.intField(
        value=int(cmds.playbackOptions(q=True, min=True)), enable=False)
    cmds.text(label="End:")
    _FIELDS["end"] = cmds.intField(
        value=int(cmds.playbackOptions(q=True, max=True)), enable=False)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(160, 90),
                   columnAlign=(1, "right"))
    cmds.text(label="Contact sharpness:")
    _FIELDS["sharpness"] = cmds.floatField(
        value=_CONTACT_SHARPNESS, minValue=1.0, precision=1,
        annotation="Raise if feet still slide (root too slow); lower towards 1 "
                   "if root motion is jittery.")
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(160, 150),
                   columnAlign=(1, "right"))
    cmds.text(label="Axis lock:")
    _FIELDS["axis_lock_menu"] = cmds.optionMenu(
        changeCommand=_toggle_axis_angle,
        annotation="Pin the predicted travel direction relative to the "
                   "body's current facing instead of letting the foot blend "
                   "pick it (kills side-to-side drift/strafe). The root "
                   "still curves naturally through a turn. Rotation is "
                   "never affected.")
    for item in _AXIS_LOCK_ITEMS:
        cmds.menuItem(label=item)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(160, 90),
                   columnAlign=(1, "right"))
    cmds.text(label="Custom angle (deg):")
    _FIELDS["axis_lock_angle"] = cmds.floatField(
        value=0.0, precision=1, enable=False,
        annotation="Heading in degrees relative to the body's current "
                   "facing (0 = forward, 90 = side), same convention as "
                   "the tool's yaw.")
    cmds.setParent("..")

    _FIELDS["use_toes"] = cmds.checkBox(
        label="Also pin the toe", value=True, changeCommand=_toggle_toes,
        annotation="Track each foot's toe/ball joint as well as the ankle. At "
                   "the foot switch the ankle is lifting and rotating while "
                   "the toe is still driving the body forward -- without the "
                   "toe the root stalls there and the back foot slides.")

    _toe_hint = ("Leave blank to auto-detect (the furthest joint child of the "
                 "foot). Auto-detection is only a guess -- the Script Editor "
                 "lists every candidate it considered, so if it picked a "
                 "twist/helper joint instead of the ball, name the right one "
                 "here.")
    _node_row("Left toe:", "toe_l", annotation=_toe_hint)
    _node_row("Right toe:", "toe_r", annotation=_toe_hint)

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(160, 220),
                   columnAlign=(1, "right"))
    cmds.text(label="Left foot pinned frames:")
    _FIELDS["pin_l"] = cmds.textField(
        annotation="Comma-separated frame ranges (e.g. \"12-18, 30-34\") "
                   "where the left foot should be forced fully planted, "
                   "overriding automatic contact detection. Leave blank "
                   "for none.")
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(160, 220),
                   columnAlign=(1, "right"))
    cmds.text(label="Right foot pinned frames:")
    _FIELDS["pin_r"] = cmds.textField(
        annotation="Comma-separated frame ranges for the right foot. A "
                   "frame cannot be pinned to both feet.")
    cmds.setParent("..")

    _FIELDS["clear"] = cmds.checkBox(
        label="Clear existing root keys first", value=True)

    cmds.separator(style="in", height=8)
    cmds.button(label="Convert", height=36, command=_on_convert)
    cmds.button(label="Delete Baked Root Motion", height=24,
                command=_on_delete_baked,
                annotation="Remove the translate/rotate keys baked onto "
                           "Root, so you can tweak settings and re-run "
                           "Convert without stacking on the previous bake.")
    cmds.setParent("..")
    cmds.showWindow(_WIN)


def _toggle_range(value):
    cmds.intField(_FIELDS["start"], edit=True, enable=value)
    cmds.intField(_FIELDS["end"], edit=True, enable=value)


if __name__ == "__main__":
    show_ui()
