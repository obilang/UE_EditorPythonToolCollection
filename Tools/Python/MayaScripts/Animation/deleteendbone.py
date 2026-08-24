import maya.cmds as cmds

def remove_bones_with_end_suffix():
    """
    Remove all bones (joints) in the scene with names ending in '_end'
    """
    # Get all joints in the scene
    all_joints = cmds.ls(type='joint')
    
    if not all_joints:
        print("No joints found in the scene.")
        return
    
    # Filter joints that end with '_end'
    end_joints = [joint for joint in all_joints if joint.endswith('_end')]
    
    if not end_joints:
        print("No joints ending with '_end' found in the scene.")
        return
    
    # Delete the filtered joints
    deleted_count = 0
    for joint in end_joints:
        try:
            cmds.delete(joint)
            print(f"Deleted: {joint}")
            deleted_count += 1
        except Exception as e:
            print(f"Error deleting {joint}: {str(e)}")
    
    print(f"\nTotal joints deleted: {deleted_count}")

# Execute the function
if __name__ == "__main__":
    remove_bones_with_end_suffix()