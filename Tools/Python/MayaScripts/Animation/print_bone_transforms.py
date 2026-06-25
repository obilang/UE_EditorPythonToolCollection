"""
Print the world-space location and rotation of target bones at every frame.

Usage
-----
In Maya's Script Editor (Python)::

    import print_bone_transforms as pb
    pb.show_ui()

or headless / scripted::

    pb.print_transforms(
        bones=["root", "hand_l", "hand_r"],
        start=None, end=None,   # None -> playback range
        world_space=True,
    )
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om


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


def _get_transform(node, world_space):
    """Return (tx, ty, tz, rx, ry, rz) for ``node`` in the requested space."""
    if world_space:
        vals = cmds.getAttr("{0}.worldMatrix[0]".format(node))
        m = om.MMatrix(vals)
        t = om.MTransformationMatrix(m)
        tx, ty, tz = t.translation(om.MSpace.kWorld)
        rx, ry, rz = [
            v * (180.0 / 3.14159265358979323846)
            for v in t.rotation(asQuaternion=False)
        ]
    else:
        tx = cmds.getAttr("{0}.translateX".format(node))
        ty = cmds.getAttr("{0}.translateY".format(node))
        tz = cmds.getAttr("{0}.translateZ".format(node))
        rx = cmds.getAttr("{0}.rotateX".format(node))
        ry = cmds.getAttr("{0}.rotateY".format(node))
        rz = cmds.getAttr("{0}.rotateZ".format(node))
    return tx, ty, tz, rx, ry, rz


# ---------------------------------------------------------------------------
# core
# ---------------------------------------------------------------------------

def print_transforms(bones, start=None, end=None, world_space=True):
    """Print location and rotation for each bone at every frame.

    Parameters
    ----------
    bones : list[str]
        Node names to sample.
    start, end : int or None
        Frame range; ``None`` uses the playback range.
    world_space : bool
        ``True`` = world-space; ``False`` = local (object) space.
    """
    missing = [b for b in bones if not cmds.objExists(b)]
    if missing:
        raise ValueError("Nodes do not exist: {0}".format(", ".join(missing)))

    start, end = _frame_range(start, end)
    space_label = "world" if world_space else "local"

    print("=" * 72)
    print("Bone transforms ({0} space)  frames {1}-{2}".format(
        space_label, start, end))
    print("=" * 72)

    restore_time = cmds.currentTime(q=True)
    try:
        for f in range(start, end + 1):
            cmds.currentTime(f, edit=True)
            print("--- frame {0} ---".format(f))
            for bone in bones:
                tx, ty, tz, rx, ry, rz = _get_transform(bone, world_space)
                print("  {name:<30}  "
                      "loc=({tx:10.4f}, {ty:10.4f}, {tz:10.4f})  "
                      "rot=({rx:10.4f}, {ry:10.4f}, {rz:10.4f})".format(
                          name=bone,
                          tx=tx, ty=ty, tz=tz,
                          rx=rx, ry=ry, rz=rz))
    finally:
        cmds.currentTime(restore_time, edit=True)

    print("=" * 72)
    print("Done. Sampled {0} bone(s) over {1} frame(s).".format(
        len(bones), end - start + 1))


# ---------------------------------------------------------------------------
# cmds UI
# ---------------------------------------------------------------------------

_WIN = "printBoneTransformsWin"
_FIELDS = {}


def _add_bone(*_):
    sel = cmds.ls(selection=True, long=False)
    if not sel:
        cmds.warning("Select at least one node first.")
        return
    existing = cmds.textScrollList(_FIELDS["bones"], q=True, allItems=True) or []
    for node in sel:
        if node not in existing:
            cmds.textScrollList(_FIELDS["bones"], edit=True, append=node)


def _remove_bone(*_):
    sel = cmds.textScrollList(_FIELDS["bones"], q=True, selectItem=True) or []
    for item in sel:
        cmds.textScrollList(_FIELDS["bones"], edit=True, removeItem=item)


def _toggle_range(value):
    cmds.intField(_FIELDS["start"], edit=True, enable=value)
    cmds.intField(_FIELDS["end"], edit=True, enable=value)


def _on_print(*_):
    bones = cmds.textScrollList(_FIELDS["bones"], q=True, allItems=True) or []
    if not bones:
        cmds.warning("Add at least one bone to the list.")
        return

    use_range = cmds.checkBox(_FIELDS["use_range"], q=True, value=True)
    world_space = cmds.checkBox(_FIELDS["world_space"], q=True, value=True)

    start = end = None
    if use_range:
        start = cmds.intField(_FIELDS["start"], q=True, value=True)
        end = cmds.intField(_FIELDS["end"], q=True, value=True)

    try:
        print_transforms(bones, start=start, end=end, world_space=world_space)
    except Exception as exc:
        cmds.confirmDialog(title="Print failed", message=str(exc), button=["OK"])
        raise


def show_ui():
    """Open the print-bone-transforms window."""
    if cmds.window(_WIN, exists=True):
        cmds.deleteUI(_WIN)

    cmds.window(_WIN, title="Print Bone Transforms", widthHeight=(420, 380),
                sizeable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6,
                      columnOffset=("both", 8))
    cmds.text(label="")
    cmds.text(label="Print world/local location and rotation of bones "
                    "at every frame.", align="left")
    cmds.text(label="Output goes to the Script Editor history.", align="left")
    cmds.separator(style="in", height=8)

    cmds.text(label="Bones:", align="left")
    _FIELDS["bones"] = cmds.textScrollList(
        height=140, allowMultiSelection=True)

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 200),
                   adjustableColumn=1)
    cmds.button(label="<- Add Selected", command=_add_bone)
    cmds.button(label="Remove Selected", command=_remove_bone)
    cmds.setParent("..")

    cmds.separator(style="in", height=8)

    _FIELDS["world_space"] = cmds.checkBox(
        label="World space (off = local / object space)", value=True)

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
    cmds.button(label="Print Transforms", height=36, command=_on_print)
    cmds.setParent("..")
    cmds.showWindow(_WIN)


if __name__ == "__main__":
    show_ui()
