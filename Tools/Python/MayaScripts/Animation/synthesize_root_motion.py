"""
Synthesize SE(2) root motion (translateX, translateZ, rotateY) from a pivot
bone and two foot joints, then bake it onto a root joint.

The approach
------------
The character's turn is already authored into the body bones, so each foot
already sweeps through world space along the true path.  We therefore:

1. For each frame, weight each foot by how planted it is (low + horizontally
   slow).
2. Pin the planted foot in *world* space: the root translates by the negative
   of the planted foot's world XZ displacement.  We do NOT re-rotate by the
   body heading -- that would double-count the turn the body already performs
   (which is what sent an earlier left-walk down the wrong axis).
3. Key translateX, translateZ onto the root joint.  ``rotateY`` is keyed only
   when ``bake_rotation=True`` (i.e. when the body should hand its turn to the
   root rather than keep it).  All keyed translations are multiplied by
   ``trans_scale`` (default 0.01 for rigs where the root joint carries
   scale=100).

This script also exposes ``bake_data()``, which keys a pre-computed
``(frame, rotY_deg, world_tx, world_tz)`` list directly -- handy when you have
already solved the motion externally and just need to drive it into the scene.

Usage
-----
    import synthesize_root_motion as sr
    sr.show_ui()

or headless::

    sr.synthesize_root_motion(
        root="root",
        center="n_center",
        foot_l="j_leg_03_l",
        foot_r="j_leg_03_r",
        trans_scale=0.01,
    )

    # -- or bake pre-solved data directly --
    sr.bake_data("root", SR_DATA, trans_scale=0.01)
"""

import math
import maya.cmds as cmds

# ---------------------------------------------------------------------------
# tuning
# ---------------------------------------------------------------------------
_HEIGHT_SOFTNESS = 0.50   # height gate: smaller -> only very-low foot is planted
_SPEED_SOFTNESS  = 0.60   # speed gate:  smaller -> only very-slow foot is planted
_SHARPNESS       = 6.0    # winner-take-all bias (>1); raise if feet still slide
_EPS             = 1e-8


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _frame_range(start, end):
    if start is None:
        start = cmds.playbackOptions(q=True, min=True)
    if end is None:
        end = cmds.playbackOptions(q=True, max=True)
    return int(round(start)), int(round(end))


def _smooth(seq, half_win):
    """Simple box-smooth."""
    n, out = len(seq), []
    for i in range(n):
        lo = max(0, i - half_win); hi = min(n, i + half_win + 1)
        out.append(sum(seq[lo:hi]) / (hi - lo))
    return out


def _sample_positions(node, frames):
    """World XYZ of *node* at each frame.  Returns list of (x, y, z)."""
    restore = cmds.currentTime(q=True)
    out = []
    try:
        for f in frames:
            cmds.currentTime(f, edit=True)
            m = cmds.getAttr("{}.worldMatrix[0]".format(node))
            out.append((m[12], m[13], m[14]))
    finally:
        cmds.currentTime(restore, edit=True)
    return out


def _sample_yaw(node, frames):
    """World Y-axis yaw (degrees) of *node* at each frame via the +Z world axis."""
    restore = cmds.currentTime(q=True)
    out = []
    try:
        for f in frames:
            cmds.currentTime(f, edit=True)
            m = cmds.getAttr("{}.worldMatrix[0]".format(node))
            # row-vector convention: row 2 is the +Z world axis
            out.append(math.degrees(math.atan2(m[8], m[10])))
    finally:
        cmds.currentTime(restore, edit=True)
    return out


def _h_speed(pos_seq, i):
    """Horizontal foot speed at index i (central difference)."""
    n = len(pos_seq)
    lo = max(i - 1, 0); hi = min(i + 1, n - 1); span = max(hi - lo, 1)
    return math.hypot((pos_seq[hi][0] - pos_seq[lo][0]) / span,
                      (pos_seq[hi][2] - pos_seq[lo][2]) / span)


# ---------------------------------------------------------------------------
# core: compute from scene
# ---------------------------------------------------------------------------

def synthesize_root_motion(root, center, foot_l, foot_r,
                           start=None, end=None,
                           trans_scale=0.01, bake_rotation=False, yaw_smooth=2,
                           clear_existing=True):
    """Compute and bake world-space root translation (+ optional yaw).

    The character's turn is already authored into the body bones, so the feet
    already sweep through world space along the true path.  We therefore pin the
    planted foot in *world* space and let that drive the root translation -- we
    do NOT re-rotate the deltas by the body heading (that would double-count the
    turn the body already performs, sending a left-walk down the wrong axis).

    Parameters
    ----------
    root : str
        The (currently static) joint to receive the baked keys.
    center : str
        Pivot / hip bone (only used for ``bake_rotation``; e.g. n_center).
    foot_l, foot_r : str
        Left / right foot drivers (ball or knee joints both work).
    trans_scale : float
        Scale factor applied to all keyed translations.
        Use 0.01 when the root joint carries scale=100.
    bake_rotation : bool
        Default ``False``.  When ``False`` only translateX/Z are keyed and the
        body keeps providing the turn (correct when the source already turns
        in-body).  Set ``True`` only if you also need the heading on the root.
    yaw_smooth : int
        Half-window (frames) for heading-curve smoothing.  0 = off.
    clear_existing : bool
        Delete existing translateX / translateZ (+ rotateY) keys on root first.
    """
    for node in (root, center, foot_l, foot_r):
        if not cmds.objExists(node):
            raise ValueError("Node does not exist: '{}'".format(node))

    start, end = _frame_range(start, end)
    frames = list(range(start, end + 1))
    N = len(frames)

    # -- sample --
    cmds.progressWindow(title="Synthesizing root motion",
                        maxValue=N, status="Sampling frames...",
                        isInterruptable=False)
    try:
        pos_l   = _sample_positions(foot_l, frames)
        pos_r   = _sample_positions(foot_r, frames)
        raw_yaw = _sample_yaw(center, frames) if bake_rotation else None
    finally:
        cmds.progressWindow(endProgress=True)

    # -- optional heading curve (only baked when bake_rotation) --
    if bake_rotation:
        yaw_s = _smooth(raw_yaw, yaw_smooth) if yaw_smooth > 0 else raw_yaw[:]
        theta = [yaw_s[i] - yaw_s[0] for i in range(N)]   # degrees, rel frame 0
    else:
        theta = [0.0] * N

    # -- planted weights --
    all_y   = [p[1] for p in pos_l] + [p[1] for p in pos_r]
    y_min   = min(all_y)
    y_span  = max(max(all_y) - y_min, _EPS)
    spd_l   = [_h_speed(pos_l, i) for i in range(N)]
    spd_r   = [_h_speed(pos_r, i) for i in range(N)]
    spd_ref = max(max(spd_l + spd_r), _EPS)

    def _planted(y, spd):
        w = (math.exp(-(y - y_min) / max(_HEIGHT_SOFTNESS * y_span, _EPS))
             * math.exp(-spd / max(_SPEED_SOFTNESS * spd_ref, _EPS)))
        return w ** _SHARPNESS

    # -- world-space weighted-pin solve --
    # The planted foot must not move in the world, so the body (root) translates
    # by the negative of the planted foot's world displacement.  No heading
    # rotation: the body already carries the turn, the feet already follow it.
    Tx = [0.0] * N
    Tz = [0.0] * N
    for i in range(1, N):
        wl = _planted(pos_l[i][1], spd_l[i]) + _planted(pos_l[i-1][1], spd_l[i-1])
        wr = _planted(pos_r[i][1], spd_r[i]) + _planted(pos_r[i-1][1], spd_r[i-1])
        s = wl + wr
        if s < _EPS:
            wl = wr = 0.5
        else:
            wl /= s; wr /= s

        d_x = wl * (pos_l[i][0] - pos_l[i-1][0]) + wr * (pos_r[i][0] - pos_r[i-1][0])
        d_z = wl * (pos_l[i][2] - pos_l[i-1][2]) + wr * (pos_r[i][2] - pos_r[i-1][2])

        Tx[i] = Tx[i-1] - d_x
        Tz[i] = Tz[i-1] - d_z

    # -- bake --
    restore = cmds.currentTime(q=True)
    try:
        cmds.currentTime(start, edit=True)
        base_tx = cmds.getAttr("{}.translateX".format(root))
        base_tz = cmds.getAttr("{}.translateZ".format(root))
        base_ry = cmds.getAttr("{}.rotateY".format(root))

        if clear_existing:
            attrs = ["translateX", "translateZ"]
            if bake_rotation:
                attrs.append("rotateY")
            for attr in attrs:
                plug = "{}.{}".format(root, attr)
                if cmds.keyframe(plug, q=True, keyframeCount=True):
                    cmds.cutKey(plug, clear=True)

        for i, f in enumerate(frames):
            cmds.currentTime(f, edit=True)
            cmds.setKeyframe(root, attribute="translateX",
                             value=base_tx + Tx[i] * trans_scale)
            cmds.setKeyframe(root, attribute="translateZ",
                             value=base_tz + Tz[i] * trans_scale)
            if bake_rotation:
                cmds.setKeyframe(root, attribute="rotateY",
                                 value=base_ry + theta[i])
    finally:
        cmds.currentTime(restore, edit=True)

    cmds.inViewMessage(
        amg="Root motion baked: <hl>{0}</hl> frames, travel "
            "<hl>{1:.2f}</hl> units.".format(
                N, math.hypot(Tx[-1], Tz[-1]) * trans_scale),
        pos="midCenter", fade=True)

    return [(f, theta[i], Tx[i] * trans_scale, Tz[i] * trans_scale)
            for i, f in enumerate(frames)]


# ---------------------------------------------------------------------------
# core: bake pre-computed data
# ---------------------------------------------------------------------------

def bake_data(root, data, trans_scale=0.01, clear_existing=True):
    """Key pre-computed root-motion data onto *root*.

    Parameters
    ----------
    root : str
        The joint to receive the baked keys.
    data : list of (frame, rotY_deg, world_tx, world_tz)
        Per-frame values.  rotY_deg is a *delta* from the frame-0 heading.
        world_tx / world_tz are world-space translations; they will be
        multiplied by *trans_scale* before keying.
    trans_scale : float
        Scale factor for translations (0.01 when root has scale=100).
    clear_existing : bool
        Delete existing translateX / translateZ / rotateY keys on root first.
    """
    if not cmds.objExists(root):
        raise ValueError("Node does not exist: '{}'".format(root))
    if not data:
        cmds.warning("bake_data: data list is empty.")
        return

    restore = cmds.currentTime(q=True)
    try:
        first_frame = data[0][0]
        cmds.currentTime(first_frame, edit=True)
        base_tx = cmds.getAttr("{}.translateX".format(root))
        base_tz = cmds.getAttr("{}.translateZ".format(root))
        base_ry = cmds.getAttr("{}.rotateY".format(root))

        if clear_existing:
            for attr in ("translateX", "translateZ", "rotateY"):
                plug = "{}.{}".format(root, attr)
                if cmds.keyframe(plug, q=True, keyframeCount=True):
                    cmds.cutKey(plug, clear=True)

        for (f, rot_y, tx, tz) in data:
            cmds.currentTime(f, edit=True)
            cmds.setKeyframe(root, attribute="translateX",
                             value=base_tx + tx * trans_scale)
            cmds.setKeyframe(root, attribute="translateZ",
                             value=base_tz + tz * trans_scale)
            cmds.setKeyframe(root, attribute="rotateY",
                             value=base_ry + rot_y)
    finally:
        cmds.currentTime(restore, edit=True)

    last = data[-1]
    cmds.inViewMessage(
        amg="Root motion baked: <hl>{0}</hl> frames, yaw <hl>{1:.1f}°</hl>, "
            "travel <hl>{2:.2f}</hl> units.".format(
                len(data), last[1],
                math.hypot(last[2], last[3]) * trans_scale),
        pos="midCenter", fade=True)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

_WIN    = "synthesizeRootMotionWin"
_FIELDS = {}


def _set_from_sel(key, *_):
    sel = cmds.ls(selection=True, long=False)
    if not sel:
        cmds.warning("Nothing selected.")
        return
    cmds.textField(_FIELDS[key], edit=True, text=sel[0])


def _toggle_range(value):
    cmds.intField(_FIELDS["start"], edit=True, enable=value)
    cmds.intField(_FIELDS["end"],   edit=True, enable=value)


def _node_row(label, key):
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(80, 190, 90),
                   adjustableColumn=2, columnAlign=(1, "right"))
    cmds.text(label=label)
    _FIELDS[key] = cmds.textField()
    cmds.button(label="<- Sel", command=lambda *a: _set_from_sel(key))
    cmds.setParent("..")


def _on_compute(*_):
    root   = cmds.textField(_FIELDS["root"],   q=True, text=True).strip()
    center = cmds.textField(_FIELDS["center"], q=True, text=True).strip()
    foot_l = cmds.textField(_FIELDS["foot_l"], q=True, text=True).strip()
    foot_r = cmds.textField(_FIELDS["foot_r"], q=True, text=True).strip()

    if not all((root, center, foot_l, foot_r)):
        cmds.warning("Please fill in all four node fields.")
        return

    ts      = cmds.floatField(_FIELDS["trans_scale"], q=True, value=True)
    smooth  = cmds.intField(  _FIELDS["yaw_smooth"],  q=True, value=True)
    bake_r  = cmds.checkBox(  _FIELDS["bake_rotation"], q=True, value=True)
    clear   = cmds.checkBox(  _FIELDS["clear"],        q=True, value=True)
    use_rng = cmds.checkBox(  _FIELDS["use_range"],    q=True, value=True)

    start = end = None
    if use_rng:
        start = cmds.intField(_FIELDS["start"], q=True, value=True)
        end   = cmds.intField(_FIELDS["end"],   q=True, value=True)

    try:
        synthesize_root_motion(root, center, foot_l, foot_r,
                               start=start, end=end,
                               trans_scale=ts, bake_rotation=bake_r,
                               yaw_smooth=smooth, clear_existing=clear)
    except Exception as exc:
        cmds.confirmDialog(title="Synthesize failed", message=str(exc),
                           button=["OK"])
        raise


def show_ui():
    """Open the Synthesize Root Motion window."""
    if cmds.window(_WIN, exists=True):
        cmds.deleteUI(_WIN)

    cmds.window(_WIN, title="Synthesize Root Motion", widthHeight=(420, 400),
                sizeable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6,
                      columnOffset=("both", 8))
    cmds.text(label="")
    cmds.text(label="Pin the planted foot in world space to drive root travel.",
              align="left")
    cmds.text(label="Keys translateX / translateZ on the root joint.",
              align="left")
    cmds.separator(style="in", height=8)

    _node_row("Root:",        "root")
    _node_row("Center/Hip:",  "center")
    _node_row("Left foot:",   "foot_l")
    _node_row("Right foot:",  "foot_r")

    cmds.separator(style="in", height=8)

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(160, 80),
                   columnAlign=(1, "right"))
    cmds.text(label="Translation scale:")
    _FIELDS["trans_scale"] = cmds.floatField(
        value=0.01, precision=4, minValue=0.0001,
        annotation="Multiply all translations by this. 0.01 for scale=100 rigs.")
    cmds.setParent("..")

    _FIELDS["bake_rotation"] = cmds.checkBox(
        label="Also bake rotateY (only if body should NOT keep the turn)",
        value=False,
        annotation="Off: body keeps the turn, root gets translation only "
                   "(correct when the source already turns in-body). "
                   "On: also key the heading onto the root.")

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(160, 80),
                   columnAlign=(1, "right"))
    cmds.text(label="Heading smooth (frames):")
    _FIELDS["yaw_smooth"] = cmds.intField(
        value=2, minValue=0,
        annotation="Half-window for heading smoothing (only when baking "
                   "rotateY). 0 = off.")
    cmds.setParent("..")

    _FIELDS["clear"] = cmds.checkBox(
        label="Clear existing translateX / translateZ (+ rotateY) keys",
        value=True)

    cmds.separator(style="in", height=8)

    _FIELDS["use_range"] = cmds.checkBox(
        label="Use custom frame range (off = playback range)", value=False,
        changeCommand=_toggle_range)

    cmds.rowLayout(numberOfColumns=4, columnWidth4=(60, 80, 60, 80),
                   columnAlign=(1, "right"))
    cmds.text(label="Start:")
    _FIELDS["start"] = cmds.intField(
        value=int(cmds.playbackOptions(q=True, min=True)), enable=False)
    cmds.text(label="End:")
    _FIELDS["end"] = cmds.intField(
        value=int(cmds.playbackOptions(q=True, max=True)), enable=False)
    cmds.setParent("..")

    cmds.separator(style="in", height=8)
    cmds.button(label="Synthesize Root Motion", height=36, command=_on_compute)
    cmds.setParent("..")
    cmds.showWindow(_WIN)


if __name__ == "__main__":
    show_ui()

# import synthesize_root_motion as sr

# (frame, rotY_deg, world_tx, world_tz)
# world_tx / world_tz are in world units; bake_data() multiplies by trans_scale=0.01
# SR_DATA = [
#     ( 0,   0.000,     0.000,     0.000),
#     ( 1,   0.000,   -15.551,     0.112),
#     ( 2,   0.000,   -17.362,    -1.405),
#     ( 3,   0.000,   -25.700,    -0.700),
#     ( 4,   0.000,   -29.990,     0.268),
#     ( 5,   0.000,   -34.667,     0.076),
#     ( 6,   0.000,   -37.394,     0.054),
#     ( 7,   0.000,   -37.731,     0.119),
#     ( 8,   0.000,   -36.711,     0.159),
#     ( 9,   0.000,   -34.630,     0.421),
#     (10,   0.000,   -31.405,     0.499),
#     (11,   0.000,   -27.054,     0.456),
#     (12,   0.000,   -21.521,     0.333),
#     (13,   0.000,   -16.360,    -0.534),
#     (14,   0.000,   -10.498,    -1.557),
#     (15,   0.000,    -6.650,    -2.333),
#     (16,   0.000,    -2.642,    -2.887),
#     (17,   0.000,     1.631,    -3.256),
#     (18,   0.000,     5.985,    -3.596),
#     (19,   0.000,    10.415,    -3.884),
#     (20,   0.000,    14.903,    -4.159),
#     (21,   0.000,    19.505,    -4.494),
#     (22,   0.000,    24.200,    -4.881),
#     (23,   0.000,    28.959,    -5.381),
#     (24,   0.000,    33.763,    -5.903),
#     (25,   0.000,    38.628,    -6.465),
#     (26,   0.000,    43.375,    -6.842),
#     (27,   0.000,    47.272,    -6.486),
#     (28,   0.000,    49.966,    -4.579),
#     (29,   0.000,    52.623,    -4.879),
#     (30,   0.000,    56.430,    -5.572),
#     (31,   0.000,    60.822,    -5.899),
#     (32,   0.000,    65.923,    -6.236),
#     (33,   0.000,    71.102,    -6.498),
#     (34,   0.000,    76.373,    -6.725),
#     (35,   0.000,    81.697,    -6.944),
#     (36,   0.000,    87.073,    -7.186),
#     (37,   0.000,    92.410,    -7.413),
#     (38,   0.000,    97.649,    -7.605),
#     (39,   0.000,   102.645,    -7.791),
#     (40,   0.000,   107.305,    -7.959),
#     (41,   0.000,   111.776,    -8.138),
#     (42,   0.000,   115.580,    -8.315),
#     (43,   0.000,   119.355,    -8.340),
#     (44,   0.000,   123.009,    -8.272),
#     (45,   0.000,   126.894,    -8.743),
#     (46,   0.000,   131.233,    -9.064),
#     (47,   0.000,   136.086,    -9.215),
#     (48,   0.000,   141.155,    -9.326),
#     (49,   0.000,   146.226,    -9.366),
#     (50,   0.000,   151.255,    -9.310),
#     (51,   0.000,   155.700,    -9.205),
#     (52,   0.000,   165.009,     0.691),
# ]

# bake_data("root", SR_DATA, trans_scale=0.01)
