"""
Loop-bake an animation cycle in place, N times, with accumulating offset.

Why this exists
---------------
When checking synthesised root motion (see ``convert_inplace_to_rootmotion``),
the most revealing test is to play the cycle many times in a row.  If the
per-cycle root travel does not match the real stride, the planted foot creeps a
little further every loop -- the error *accumulates*, so a drift that is almost
invisible in one cycle becomes obvious after five or six.

So this tool repeats the clip back-to-back as real baked keyframes, and -- this
is the important part -- offsets each successive copy so the motion keeps going
instead of snapping back to the origin every loop (Maya's "Cycle with Offset",
baked to keys).

How the offset works (fully general, no per-channel special-casing)
-------------------------------------------------------------------
For every animated channel, copy ``c`` of the cycle is value-shifted by::

    c * (value_at_end - value_at_start)

* A channel that returns to its start value over the cycle (foot rotations,
  spine sway, the root's vertical bob, etc.) has delta ~= 0, so it simply
  repeats -- a clean loop.
* The root's ground-plane translation and yaw have a real per-cycle delta, so
  they accumulate and the character keeps walking / turning forward.

Adding the offset numerically also sidesteps the +/-180 Euler wrap that a
rotation channel would otherwise hit.  Tangents are preserved via copyKey /
pasteKey.

Assumptions
-----------
* The source range is one full cycle: the pose at ``end`` equals the pose at
  ``start`` (standard looping clip).  The seam key merges cleanly.
* "In place" here means *on the current skeleton* -- this edits the existing
  animation.  Save / duplicate first if you want to keep the single-cycle clip.

Usage
-----
    import loop_bake_animation as lb
    lb.show_ui()

or scripted::

    lb.loop_bake(root="root", cycles=6, start=None, end=None)
"""

import maya.cmds as cmds


# ---------------------------------------------------------------------------
# helpers
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


def _gather_nodes(root):
    """The root plus every descendant transform/joint under it."""
    nodes = [root]
    kids = cmds.listRelatives(root, allDescendents=True, fullPath=False) or []
    nodes.extend(kids)
    # de-dup while preserving order
    seen = set()
    out = []
    for n in nodes:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _animated_attrs(node):
    """Keyable attrs on ``node`` that actually carry keyframes."""
    attrs = cmds.listAttr(node, keyable=True) or []
    out = []
    for a in attrs:
        plug = "{0}.{1}".format(node, a)
        if not cmds.objExists(plug):
            continue
        if cmds.keyframe(plug, q=True, keyframeCount=True):
            out.append(a)
    return out


# ---------------------------------------------------------------------------
# core
# ---------------------------------------------------------------------------

def loop_bake(root, cycles, start=None, end=None, extend_range=True):
    """Repeat the cycle ``cycles`` times in place, with accumulating offset.

    Parameters
    ----------
    root : str
        Root of the skeleton to loop (its whole hierarchy is processed).
    cycles : int
        Total number of cycles after baking (>= 2). ``cycles=1`` is a no-op.
    start, end : int or None
        The single-cycle range. ``None`` uses the playback range.
    extend_range : bool
        Extend the timeline / playback range to cover all baked cycles.
    """
    if not cmds.objExists(root):
        raise ValueError("Node does not exist: '{0}'".format(root))
    cycles = int(cycles)
    if cycles < 2:
        cmds.warning("cycles < 2 -- nothing to loop.")
        return

    start, end = _frame_range(start, end)
    period = end - start
    if period < 1:
        raise ValueError("Source range is too short to be a cycle.")

    nodes = _gather_nodes(root)

    # Collect (node, attr, delta) up front.  delta is sampled by scrubbing to
    # the two cycle boundaries exactly once each, rather than per channel.
    restore_time = cmds.currentTime(q=True)
    plugs = []  # (plug, attr, node)
    for node in nodes:
        for attr in _animated_attrs(node):
            plugs.append(("{0}.{1}".format(node, attr), attr, node))

    if not plugs:
        cmds.warning("No animated channels found under '{0}'.".format(root))
        return

    try:
        cmds.currentTime(start, edit=True)
        v_start = {p[0]: cmds.getAttr(p[0]) for p in plugs}
        cmds.currentTime(end, edit=True)
        v_end = {p[0]: cmds.getAttr(p[0]) for p in plugs}

        for plug, attr, node in plugs:
            delta = v_end[plug] - v_start[plug]
            # copy the single source cycle for this channel to the clipboard
            copied = cmds.copyKey(node, attribute=attr, time=(start, end))
            if not copied:
                continue
            for c in range(1, cycles):
                cmds.pasteKey(
                    node, attribute=attr,
                    time=(start + c * period,),
                    option="merge",
                    valueOffset=c * delta)
    finally:
        cmds.currentTime(restore_time, edit=True)

    if extend_range:
        new_end = start + cycles * period
        cmds.playbackOptions(edit=True, min=start, max=new_end,
                             animationStartTime=start, animationEndTime=new_end)

    cmds.inViewMessage(
        amg="Looped <hl>{0}</hl> cycles (period {1}) on <hl>{2}</hl> "
            "channels.".format(cycles, period, len(plugs)),
        pos="midCenter", fade=True)


# ---------------------------------------------------------------------------
# cmds UI
# ---------------------------------------------------------------------------

_WIN = "loopBakeAnimationWin"
_FIELDS = {}


def _set_from_selection(*_):
    sel = cmds.ls(selection=True, long=False)
    if not sel:
        cmds.warning("Nothing selected.")
        return
    cmds.textField(_FIELDS["root"], edit=True, text=sel[0])


def _on_bake(*_):
    root = cmds.textField(_FIELDS["root"], q=True, text=True).strip()
    cycles = cmds.intField(_FIELDS["cycles"], q=True, value=True)
    use_range = cmds.checkBox(_FIELDS["use_range"], q=True, value=True)
    extend = cmds.checkBox(_FIELDS["extend"], q=True, value=True)

    start = end = None
    if use_range:
        start = cmds.intField(_FIELDS["start"], q=True, value=True)
        end = cmds.intField(_FIELDS["end"], q=True, value=True)

    if not root:
        cmds.warning("Please fill in the skeleton root.")
        return

    try:
        loop_bake(root, cycles, start=start, end=end, extend_range=extend)
    except Exception as exc:
        cmds.confirmDialog(title="Loop bake failed", message=str(exc),
                           button=["OK"])
        raise


def _toggle_range(value):
    cmds.intField(_FIELDS["start"], edit=True, enable=value)
    cmds.intField(_FIELDS["end"], edit=True, enable=value)


def show_ui():
    """Open the loop-bake window."""
    if cmds.window(_WIN, exists=True):
        cmds.deleteUI(_WIN)

    cmds.window(_WIN, title="Loop-Bake Animation", widthHeight=(380, 280),
                sizeable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6,
                      columnOffset=("both", 8))
    cmds.text(label="")
    cmds.text(label="Repeat the cycle N times in place, root motion "
                    "accumulating.", align="left")
    cmds.text(label="Edits the current animation -- duplicate first to keep "
                    "the original.", align="left")
    cmds.separator(style="in", height=8)

    cmds.rowLayout(numberOfColumns=3, columnWidth3=(70, 200, 90),
                   adjustableColumn=2, columnAlign=(1, "right"))
    cmds.text(label="Root:")
    _FIELDS["root"] = cmds.textField()
    cmds.button(label="<- Sel", command=_set_from_selection)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(70, 90),
                   columnAlign=(1, "right"))
    cmds.text(label="Cycles:")
    _FIELDS["cycles"] = cmds.intField(value=6, minValue=2)
    cmds.setParent("..")

    cmds.separator(style="in", height=8)

    _FIELDS["use_range"] = cmds.checkBox(
        label="Use custom cycle range (off = playback range)", value=False,
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

    _FIELDS["extend"] = cmds.checkBox(
        label="Extend playback range to cover all cycles", value=True)

    cmds.separator(style="in", height=8)
    cmds.button(label="Loop Bake", height=36, command=_on_bake)
    cmds.setParent("..")
    cmds.showWindow(_WIN)


if __name__ == "__main__":
    show_ui()
