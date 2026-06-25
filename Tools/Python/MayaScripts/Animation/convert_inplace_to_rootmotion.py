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

Two feet are tracked.  Per frame we compute each foot's own delta, then blend
the two by a soft "how planted is this foot" contact weight (low + slow ==
planted).  The planted foot dominates, and at foot-handoff the two deltas blend
smoothly instead of popping.

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
        foot_l="ball_l",        # use the ball / toe joint or a foot locator
        foot_r="ball_r",
        start=None, end=None,   # None -> playback range
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


def _sample_feet(foot_l, foot_r, start, end):
    """Step through every frame and record each foot's world matrix.

    Returns ``frames, ground_l, ground_r, raw_y_l, raw_y_r`` where the ground_*
    lists hold clean SE(2) matrices and the raw_y_* lists hold the un-projected
    world Y of each foot (used for contact height).
    """
    frames = list(range(start, end + 1))
    ground_l, ground_r = [], []
    raw_y_l, raw_y_r = [], []

    restore_time = cmds.currentTime(q=True)
    try:
        for f in frames:
            cmds.currentTime(f, edit=True)
            ml = _world_matrix(foot_l)
            mr = _world_matrix(foot_r)

            ground_l.append(_ground_matrix(_yaw_from_matrix(ml), ml[12], ml[14]))
            ground_r.append(_ground_matrix(_yaw_from_matrix(mr), mr[12], mr[14]))
            raw_y_l.append(ml[13])
            raw_y_r.append(mr[13])
    finally:
        cmds.currentTime(restore_time, edit=True)

    return frames, ground_l, ground_r, raw_y_l, raw_y_r


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


def _contact_weights(ground_l, ground_r, raw_y_l, raw_y_r,
                     sharpness=_CONTACT_SHARPNESS):
    """Soft per-frame planted-ness weights.

    Returns a list of ``(wl, wr, confidence)`` per frame, where ``wl + wr == 1``
    (normalized blend between the two feet) and ``confidence`` in ``[0, 1]`` is
    the *un-normalized* planted-ness -- low when neither foot is on the ground
    (e.g. a flight phase), used downstream to decide whether to pin at all.

    ``sharpness`` (>= 1) biases the blend towards the more-planted foot; higher
    values approach winner-take-all and recover more of the true stride speed.
    """
    n = len(ground_l)

    all_y = raw_y_l + raw_y_r
    y_min = min(all_y)
    y_max = max(all_y)
    y_span = max(y_max - y_min, _EPS)

    speeds_l = [_horizontal_speed(ground_l, i) for i in range(n)]
    speeds_r = [_horizontal_speed(ground_r, i) for i in range(n)]
    speed_ref = max(max(speeds_l + speeds_r), _EPS)

    vspeeds_l = [_vertical_speed(raw_y_l, i) for i in range(n)]
    vspeeds_r = [_vertical_speed(raw_y_r, i) for i in range(n)]
    vspeed_ref = max(max(vspeeds_l + vspeeds_r), _EPS)

    h_scale = max(y_span * _HEIGHT_SOFTNESS, _EPS)
    s_scale = max(speed_ref * _SPEED_SOFTNESS, _EPS)
    v_scale = max(vspeed_ref * _VSPEED_SOFTNESS, _EPS)

    def planted(raw_y_i, spd, vspd):
        h = raw_y_i - y_min
        # low + horizontally slow + vertically still == planted
        return (math.exp(-h / h_scale)
                * math.exp(-spd / s_scale)
                * math.exp(-vspd / v_scale))

    weights = []
    for i in range(n):
        wl = planted(raw_y_l[i], speeds_l[i], vspeeds_l[i])
        wr = planted(raw_y_r[i], speeds_r[i], vspeeds_r[i])
        confidence = max(wl, wr)         # how planted the *best* foot is
        total = wl + wr
        if total < _EPS:
            wl = wr = 0.5
        else:
            wl /= total
            wr /= total
            # Sharpen towards winner-take-all so the swing foot's forward motion
            # doesn't cancel the planted foot's slide (which halves root speed).
            wl = wl ** sharpness
            wr = wr ** sharpness
            s = wl + wr
            wl /= s
            wr /= s
        weights.append((wl, wr, confidence))
    return weights


# ---------------------------------------------------------------------------
# trajectory synthesis
# ---------------------------------------------------------------------------

def _circular_blend(yl, yr, wl, wr):
    """Weighted circular mean of two angles -- safe across the +/-pi branch cut."""
    return math.atan2(wl * math.sin(yl) + wr * math.sin(yr),
                      wl * math.cos(yl) + wr * math.cos(yr))


def _accumulate_root_deltas(ground_l, ground_r, weights):
    """Build the accumulated world-space root delta D(f) for every frame.

    Returns a list of MMatrix, one per frame, with D(0) = identity.  Frames with
    no convincingly-planted foot (e.g. a flight phase) coast on the previous
    delta rather than pinning a fast-moving swing foot.  The keyed rotation curve
    is Euler-unwrapped afterwards in ``_apply_root``.
    """
    n = len(ground_l)
    d = om.MMatrix()  # identity
    deltas = [om.MMatrix(d)]
    prev_blended = None

    for i in range(1, n):
        wl, wr, confidence = weights[i]

        if confidence < _CONTACT_FLOOR and prev_blended is not None:
            # No foot is convincingly planted: coast on the last good delta.
            blended = prev_blended
        else:
            # each foot's own pin delta: foot(f)^-1 * foot(f-1)
            delta_l = ground_l[i].inverse() * ground_l[i - 1]
            delta_r = ground_r[i].inverse() * ground_r[i - 1]

            yl, lx, lz = _delta_to_yaw_dxz(delta_l)
            yr, rx, rz = _delta_to_yaw_dxz(delta_r)

            d_yaw = _circular_blend(yl, yr, wl, wr)
            b_x = wl * lx + wr * rx
            b_z = wl * lz + wr * rz
            blended = _ground_matrix(d_yaw, b_x, b_z)
            prev_blended = blended

        d = blended * d            # D(f) = delta(f) * D(f-1)
        deltas.append(om.MMatrix(d))

    return deltas


# ---------------------------------------------------------------------------
# applying to the root joint
# ---------------------------------------------------------------------------

def _apply_root(root, frames, deltas, clear_existing=True):
    """Key ``R0 * D(f)`` onto the root for every frame."""
    rot_plugs = ["{0}.rotate{1}".format(root, ax) for ax in ("X", "Y", "Z")]
    restore_time = cmds.currentTime(q=True)
    try:
        # R0 = root's original (static) world matrix, sampled once at frames[0].
        cmds.currentTime(frames[0], edit=True)
        r0 = _world_matrix(root)

        if clear_existing:
            for attr in ("translateX", "translateY", "translateZ",
                         "rotateX", "rotateY", "rotateZ"):
                plug = "{0}.{1}".format(root, attr)
                if cmds.keyframe(plug, q=True, keyframeCount=True):
                    cmds.cutKey(plug, clear=True)

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
            sharpness=_CONTACT_SHARPNESS):
    """Synthesise root motion for an in-place cycle and key it onto ``root``.

    Parameters
    ----------
    root : str
        The static root joint that is an ancestor of both feet.
    foot_l, foot_r : str
        Left / right foot drivers -- use the ball/toe joints or foot locators.
    start, end : int or None
        Frame range; ``None`` uses the timeline playback range.
    clear_existing : bool
        Remove any pre-existing translate/rotate keys on the root first.
    sharpness : float
        Contact-blend sharpness (>= 1). Raise it if the feet still slide (root
        too slow); lower it towards 1 if the root motion looks jittery. ~8 is a
        good default; 1 is the original soft blend (~half speed).
    """
    for n in (root, foot_l, foot_r):
        if not cmds.objExists(n):
            raise ValueError("Node does not exist: '{0}'".format(n))

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

    frames, gl, gr, yl, yr = _sample_feet(foot_l, foot_r, start, end)
    weights = _contact_weights(gl, gr, yl, yr, sharpness=sharpness)
    deltas = _accumulate_root_deltas(gl, gr, weights)
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


def _on_convert(*_):
    root = cmds.textField(_FIELDS["root"], q=True, text=True).strip()
    foot_l = cmds.textField(_FIELDS["foot_l"], q=True, text=True).strip()
    foot_r = cmds.textField(_FIELDS["foot_r"], q=True, text=True).strip()
    use_range = cmds.checkBox(_FIELDS["use_range"], q=True, value=True)
    clear = cmds.checkBox(_FIELDS["clear"], q=True, value=True)
    sharpness = cmds.floatField(_FIELDS["sharpness"], q=True, value=True)

    start = end = None
    if use_range:
        start = cmds.intField(_FIELDS["start"], q=True, value=True)
        end = cmds.intField(_FIELDS["end"], q=True, value=True)

    if not (root and foot_l and foot_r):
        cmds.warning("Please fill in root, left foot and right foot.")
        return

    try:
        convert(root, foot_l, foot_r, start=start, end=end, clear_existing=clear,
                sharpness=sharpness)
    except Exception as exc:  # surface the error to the user, not just the log
        cmds.confirmDialog(title="Convert failed", message=str(exc), button=["OK"])
        raise


def _node_row(label, key):
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(70, 200, 90),
                   adjustableColumn=2, columnAlign=(1, "right"))
    cmds.text(label=label)
    _FIELDS[key] = cmds.textField()
    cmds.button(label="<- Sel", command=lambda *_: _set_from_selection(key))
    cmds.setParent("..")


def show_ui():
    """Open the converter window."""
    if cmds.window(_WIN, exists=True):
        cmds.deleteUI(_WIN)

    cmds.window(_WIN, title="In-Place -> Root Motion", widthHeight=(380, 360),
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

    _FIELDS["clear"] = cmds.checkBox(
        label="Clear existing root keys first", value=True)

    cmds.separator(style="in", height=8)
    cmds.button(label="Convert", height=36, command=_on_convert)
    cmds.setParent("..")
    cmds.showWindow(_WIN)


def _toggle_range(value):
    cmds.intField(_FIELDS["start"], edit=True, enable=value)
    cmds.intField(_FIELDS["end"], edit=True, enable=value)


if __name__ == "__main__":
    show_ui()
