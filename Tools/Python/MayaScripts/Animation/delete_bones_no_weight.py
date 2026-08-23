import maya.cmds as cmds


def get_all_descendants(joint):
    """
    Get all descendant joints of a given joint.
    """
    descendants = []
    children = cmds.listRelatives(joint, children=True, type='joint') or []
    for child in children:
        descendants.append(child)
        descendants.extend(get_all_descendants(child))
    return descendants


def delete_bones_without_skin_weights():
    """
    Deletes all joints/bones that don't have any skin weights,
    but preserves joints that have child bones with weights.
    This ensures the hierarchy is maintained for weighted bones.
    """
    # Get all joints in the scene
    all_joints = cmds.ls(type='joint')
    
    if not all_joints:
        cmds.warning("No joints found in the scene.")
        return
    
    # Get all skinClusters in the scene
    all_skin_clusters = cmds.ls(type='skinCluster')
    
    if not all_skin_clusters:
        cmds.warning("No skinClusters found in the scene.")
        return
    
    # Set to store joints that have actual non-zero weights
    joints_with_weights = set()
    
    # Check each skinCluster
    for skin_cluster in all_skin_clusters:
        # Get the geometry affected by this skinCluster
        geometry = cmds.skinCluster(skin_cluster, query=True, geometry=True)
        
        if not geometry:
            continue
        
        # Get all influence objects (joints) for this skinCluster
        influences = cmds.skinCluster(skin_cluster, query=True, influence=True)
        
        if not influences:
            continue
        
        # Get all vertices of the geometry
        shape = geometry[0]
        vertices = cmds.ls(f"{shape}.vtx[*]", flatten=True)
        
        # For each influence, check if it has any non-zero weights
        for influence in influences:
            has_weight = False
            
            # Check weight values on vertices
            for vtx in vertices:
                try:
                    # Get the weight value for this influence on this vertex
                    weight_value = cmds.skinPercent(
                        skin_cluster,
                        vtx,
                        transform=influence,
                        query=True
                    )
                    
                    # If weight is greater than 0, this joint is being used
                    if weight_value > 0.0001:  # Use small threshold for floating point
                        has_weight = True
                        joints_with_weights.add(influence)
                        break  # No need to check other vertices for this influence
                except:
                    pass
            
            if has_weight:
                continue
    
    # Find joints without any skin weights
    joints_without_weights = [j for j in all_joints if j not in joints_with_weights]
    
    # Filter out joints that have children with weights
    joints_to_delete = []
    joints_to_keep = []
    
    for joint in joints_without_weights:
        # Get all descendant joints
        descendants = get_all_descendants(joint)
        
        # Check if any descendant has weights
        has_weighted_descendant = any(desc in joints_with_weights for desc in descendants)
        
        if has_weighted_descendant:
            joints_to_keep.append(joint)
        else:
            joints_to_delete.append(joint)
    
    # Delete the joints
    if joints_to_delete:
        cmds.delete(joints_to_delete)
        print(f"Deleted {len(joints_to_delete)} joints without skin weights:")
        for joint in joints_to_delete:
            print(f"  - {joint}")
    else:
        print("No joints to delete.")
    
    if joints_to_keep:
        print(f"\nKept {len(joints_to_keep)} joints without weights (have weighted children):")
        for joint in joints_to_keep:
            print(f"  - {joint}")
    
    # Print summary
    print(f"\nSummary:")
    print(f"  Total joints: {len(all_joints)}")
    print(f"  Joints with weights: {len(joints_with_weights)}")
    print(f"  Joints without weights: {len(joints_without_weights)}")
    print(f"  Joints kept (weighted children): {len(joints_to_keep)}")
    print(f"  Joints deleted: {len(joints_to_delete)}")
    print(f"  SkinClusters checked: {len(all_skin_clusters)}")


# Run the function
if __name__ == "__main__":
    delete_bones_without_skin_weights()
