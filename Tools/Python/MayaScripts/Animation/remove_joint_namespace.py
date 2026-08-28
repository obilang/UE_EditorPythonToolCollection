import maya.cmds as cmds

def remove_joint_namespaces():
    """
    Strip namespaces from all joints in the scene.
    e.g. 'run_f_lp:n_root' -> 'n_root'
    """
    all_joints = cmds.ls(type='joint', long=True)

    if not all_joints:
        print("No joints found in the scene.")
        return

    namespaced_joints = [jnt for jnt in all_joints if ':' in jnt.split('|')[-1]]

    if not namespaced_joints:
        print("No namespaced joints found in the scene.")
        return

    # Track by uuid so renaming a parent doesn't invalidate the long-name
    # path we captured for its children.
    joint_uuids = [cmds.ls(jnt, uuid=True)[0] for jnt in namespaced_joints]

    renamed_count = 0
    for uuid in joint_uuids:
        current_path = cmds.ls(uuid, long=True)[0]
        short_name = current_path.split('|')[-1]
        new_name = short_name.split(':')[-1]
        try:
            cmds.rename(current_path, new_name)
            print(f"Renamed: {short_name} -> {new_name}")
            renamed_count += 1
        except Exception as e:
            print(f"Error renaming {short_name}: {str(e)}")

    print(f"\nTotal joints renamed: {renamed_count}")

# Execute the function
if __name__ == "__main__":
    remove_joint_namespaces()
