"""
Center each selected mesh's pivot, move it to the world origin, then freeze transforms.

Steps applied to every selected mesh
--------------------------------------
1. Set the rotate and scale pivot to the mesh's bounding box centre.
2. Translate the mesh so that pivot lands exactly at the world origin (0, 0, 0).
3. Freeze transforms (makeIdentity -- translate, rotate, scale) so the
   resulting pose becomes the new zero state.

Usage
-----
    import set_pivot_to_center as spc
    spc.show_ui()

or headless::

    spc.apply_to_selection()
"""

import maya.cmds as cmds


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _mesh_transforms_from_selection():
    """Return transform nodes that directly own a mesh shape from the selection."""
    sel = cmds.ls(selection=True, long=True) or []
    out = []
    for node in sel:
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
        if any(cmds.nodeType(s) == "mesh" for s in shapes):
            out.append(node)
    return out


def _set_pivot_to_bbox_center(node):
    """Move the rotate and scale pivot to the bounding box centre in world space."""
    # exactWorldBoundingBox returns [xmin, ymin, zmin, xmax, ymax, zmax]
    bb = cmds.exactWorldBoundingBox(node)
    cx = (bb[0] + bb[3]) / 2.0
    cy = (bb[1] + bb[4]) / 2.0
    cz = (bb[2] + bb[5]) / 2.0
    cmds.xform(node, worldSpace=True, pivots=(cx, cy, cz))


# ---------------------------------------------------------------------------
# core
# ---------------------------------------------------------------------------

def center_and_freeze(node):
    """Apply all three steps to a single mesh transform node.

    Parameters
    ----------
    node : str
        Full path to a mesh transform.
    """
    _set_pivot_to_bbox_center(node)
    # rotatePivotRelative: translates the object so the rotate pivot ends up
    # at the given world-space position without touching the pivot offsets.
    cmds.move(0, 0, 0, node, worldSpace=True, rotatePivotRelative=True)
    cmds.makeIdentity(node, apply=True,
                      translate=True, rotate=True, scale=True, normal=False)


def apply_to_selection():
    """Run center_and_freeze on every selected mesh transform.

    Returns
    -------
    int
        Number of meshes processed.
    """
    meshes = _mesh_transforms_from_selection()
    if not meshes:
        cmds.warning("No mesh transforms selected.")
        return 0

    for node in meshes:
        center_and_freeze(node)

    cmds.inViewMessage(
        amg="Pivot centred, moved to origin, and frozen on "
            "<hl>{0}</hl> mesh(es).".format(len(meshes)),
        pos="midCenter", fade=True)
    return len(meshes)


# ---------------------------------------------------------------------------
# cmds UI
# ---------------------------------------------------------------------------

_WIN = "setPivotToCenterWin"


def _on_apply(*_):
    try:
        count = apply_to_selection()
        if count == 0:
            cmds.confirmDialog(
                title="Nothing to do",
                message="Select one or more mesh objects first.",
                button=["OK"])
    except Exception as exc:
        cmds.confirmDialog(title="Operation failed", message=str(exc),
                           button=["OK"])
        raise


def show_ui():
    """Open the Set Pivot to Center window."""
    if cmds.window(_WIN, exists=True):
        cmds.deleteUI(_WIN)

    cmds.window(_WIN, title="Set Pivot to Center", widthHeight=(320, 200),
                sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6,
                      columnOffset=("both", 8))
    cmds.text(label="")
    cmds.text(label="Applied to every selected mesh:", align="left")
    cmds.text(label="  1. Set pivot to bounding box centre.", align="left")
    cmds.text(label="  2. Move mesh so pivot is at world origin.", align="left")
    cmds.text(label="  3. Freeze transforms.", align="left")
    cmds.separator(style="in", height=8)
    cmds.button(label="Apply to Selection", height=36, command=_on_apply)
    cmds.setParent("..")
    cmds.showWindow(_WIN)


if __name__ == "__main__":
    show_ui()
