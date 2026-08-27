import maya.cmds as cmds

def normalize_skeleton_with_animation(root_bone=None, target_scale=1.0, bone_radius=3.0):
    """
    Normalize root bone scale from 100 to 1 while preserving all animations
    Works on skeletons without skinned meshes

    Args:
        root_bone (str): Name of the root bone. If None, will try to find it automatically
        target_scale (float): Target scale value (default: 1.0)
        bone_radius (float): Joint display radius applied after normalizing (default: 3.0)
    """
    
    # Find root bone
    if root_bone is None:
        all_joints = cmds.ls(type='joint')
        if not all_joints:
            print("No joints found in scene")
            return
        
        root_joints = []
        for joint in all_joints:
            parent = cmds.listRelatives(joint, parent=True, type='joint')
            if not parent:
                root_joints.append(joint)
        
        if not root_joints:
            print("No root joint found")
            return
        elif len(root_joints) > 1:
            print(f"Multiple root joints found: {root_joints}")
            print("Please specify which one to use")
            return
        
        root_bone = root_joints[0]
        print(f"Found root bone: {root_bone}")
    
    # Get current scale
    current_scale = cmds.getAttr(f"{root_bone}.scaleX")
    print(f"Current root bone scale: {current_scale}")
    
    if abs(current_scale - target_scale) < 0.001:
        print(f"Root bone is already at scale {target_scale}")
        # Still enforce the uniform joint radius
        children = cmds.listRelatives(root_bone, allDescendents=True, type='transform') or []
        for joint in [root_bone] + [c for c in children if cmds.nodeType(c) == 'joint']:
            try:
                cmds.setAttr(f"{joint}.radius", bone_radius)
            except:
                pass
        print(f"Set radius to {bone_radius} on all joints")
        return

    # Calculate scale factor
    scale_factor = current_scale / target_scale
    
    # Get all children
    all_children = cmds.listRelatives(root_bone, allDescendents=True, type='transform') or []
    all_joints = [root_bone] + [child for child in all_children if cmds.nodeType(child) == 'joint']
    
    print(f"Found {len(all_joints)} joints in hierarchy")
    
    # Get time range for animation
    start_time = cmds.playbackOptions(query=True, minTime=True)
    end_time = cmds.playbackOptions(query=True, maxTime=True)
    
    print(f"Animation range: {start_time} to {end_time}")
    
    # Store current time
    current_time = cmds.currentTime(query=True)
    
    # Check if there are keyframes on the skeleton
    has_animation = False
    for joint in all_joints:
        connections = cmds.listConnections(joint, type='animCurve') or []
        if connections:
            has_animation = True
            break
    
    if has_animation:
        print("Animation detected on skeleton")
    else:
        print("No animation curves found")
    
    # Set root bone scale to target value
    cmds.setAttr(f"{root_bone}.scaleX", target_scale)
    cmds.setAttr(f"{root_bone}.scaleY", target_scale)
    cmds.setAttr(f"{root_bone}.scaleZ", target_scale)
    
    print(f"Set root bone scale to {target_scale}")
    
    # Scale all child joints' translate values
    joints_scaled = 0
    for child in all_children:
        if cmds.nodeType(child) == 'joint':
            # Check if translate attributes have animation
            has_tx_anim = cmds.listConnections(f"{child}.translateX", type='animCurve')
            has_ty_anim = cmds.listConnections(f"{child}.translateY", type='animCurve')
            has_tz_anim = cmds.listConnections(f"{child}.translateZ", type='animCurve')
            
            if has_tx_anim or has_ty_anim or has_tz_anim:
                # Has animation - need to scale keyframes
                print(f"Scaling animated translate values for {child}")
                
                # Get all keyframe times
                all_keys = set()
                if has_tx_anim:
                    all_keys.update(cmds.keyframe(f"{child}.translateX", query=True, timeChange=True) or [])
                if has_ty_anim:
                    all_keys.update(cmds.keyframe(f"{child}.translateY", query=True, timeChange=True) or [])
                if has_tz_anim:
                    all_keys.update(cmds.keyframe(f"{child}.translateZ", query=True, timeChange=True) or [])
                
                # Scale values at each keyframe
                for key_time in all_keys:
                    cmds.currentTime(key_time)
                    
                    tx = cmds.getAttr(f"{child}.translateX")
                    ty = cmds.getAttr(f"{child}.translateY")
                    tz = cmds.getAttr(f"{child}.translateZ")
                    
                    cmds.setKeyframe(f"{child}.translateX", value=tx * scale_factor, time=key_time)
                    cmds.setKeyframe(f"{child}.translateY", value=ty * scale_factor, time=key_time)
                    cmds.setKeyframe(f"{child}.translateZ", value=tz * scale_factor, time=key_time)
            else:
                # No animation - just scale the static values
                tx = cmds.getAttr(f"{child}.translateX")
                ty = cmds.getAttr(f"{child}.translateY")
                tz = cmds.getAttr(f"{child}.translateZ")
                
                cmds.setAttr(f"{child}.translateX", tx * scale_factor)
                cmds.setAttr(f"{child}.translateY", ty * scale_factor)
                cmds.setAttr(f"{child}.translateZ", tz * scale_factor)
            
            joints_scaled += 1

    # Restore original time
    cmds.currentTime(current_time)

    # Set a uniform joint display radius after normalizing
    radius_set = 0
    for joint in all_joints:
        try:
            cmds.setAttr(f"{joint}.radius", bone_radius)
            radius_set += 1
        except:
            pass

    print(f"\n=== Summary ===")
    print(f"- Normalized root bone to scale {target_scale}")
    print(f"- Scaled {joints_scaled} child joints")
    print(f"- Set radius to {bone_radius} on {radius_set} joints")
    print(f"- Scale factor applied: {scale_factor}")
    if has_animation:
        print("- Animation keyframes preserved and scaled")
    print("Done!")

# Execute the function
if __name__ == "__main__":
    normalize_skeleton_with_animation()
    
    # Or specify a specific root bone:
    # normalize_skeleton_with_animation(root_bone="root")