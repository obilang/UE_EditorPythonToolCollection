import maya.cmds as cmds

def extract_root_bone_cleanly():
    sel = cmds.ls(selection=True, type='joint')
    if not sel:
        cmds.warning("Please select your root bone (joint) first.")
        return
    
    root_bone = sel[0]
    
    # Find the parent transform node
    parent_node = cmds.listRelatives(root_bone, parent=True, fullPath=True)
    if not parent_node:
        cmds.warning("The selected joint is already at the scene root.")
        return
    parent_node = parent_node[0]
    
    # 1. Store the exact world matrix BEFORE we unparent
    # This matrix contains the exact world scale, rotation, and translation
    world_matrix = cmds.xform(root_bone, query=True, worldSpace=True, matrix=True)
    
    # 2. Turn off Segment Scale Compensate for all joints.
    # We must do this before moving scale to the root, so the children scale with it.
    all_joints = cmds.listRelatives(root_bone, allDescendents=True, type='joint', fullPath=True) or []
    all_joints.append(root_bone)
    
    for jnt in all_joints:
        if cmds.attributeQuery('segmentScaleCompensate', node=jnt, exists=True):
            cmds.setAttr(f"{jnt}.segmentScaleCompensate", 0)

    # 3. Unlock transform attributes on the root bone just in case they are locked
    for attr in ['tx','ty','tz','rx','ry','rz','sx','sy','sz']:
        cmds.setAttr(f"{root_bone}.{attr}", lock=False)
            
    # 4. UNPARENT RELATIVE
    # This is the magic fix! By unparenting "relatively", Maya drops it to the root 
    # WITHOUT trying to preserve its visual size, which STOPS it from creating that 
    # annoying dummy transform node.
    root_bone = cmds.parent(root_bone, world=True, relative=True)[0]
    
    # 5. Snap it back into place
    # Now that the joint is cleanly at the scene root with no parent, we force it 
    # to absorb the scale/translation/rotation natively by giving its matrix back.
    cmds.xform(root_bone, worldSpace=True, matrix=world_matrix)
    
    # 6. Clean up: Delete the original parent if it is now empty
    remaining_children = cmds.listRelatives(parent_node, children=True)
    if not remaining_children:
        cmds.delete(parent_node)
        print(f"Success! '{root_bone}' cleanly moved to root. Scale applied to bone and '{parent_node}' deleted.")
    else:
        print(f"Success! '{root_bone}' cleanly moved to root. '{parent_node}' was kept because it has other objects.")

# Run the script
extract_root_bone_cleanly()