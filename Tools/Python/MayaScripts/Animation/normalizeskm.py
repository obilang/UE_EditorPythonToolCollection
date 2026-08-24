import maya.cmds as cmds
import os

def normalize_root_freeze_100(root_bone=None, target_scale=1.0):
    """
    Normalize root bone scale: unbind, set mesh to scale 100, freeze, rebind with weights
    
    Args:
        root_bone (str): Name of the root bone
        target_scale (float): Target scale value (default: 1.0)
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
    
    scale_factor = current_scale / target_scale
    
    # Get all children
    all_children = cmds.listRelatives(root_bone, allDescendents=True, type='transform') or []
    all_joints = [root_bone] + [child for child in all_children if cmds.nodeType(child) == 'joint']
    
    # Find skinned meshes and store skin cluster info
    skin_info = []
    processed_clusters = set()
    
    for joint in all_joints:
        skin_clusters = cmds.listConnections(joint, type='skinCluster') or []
        for skin_cluster in skin_clusters:
            if skin_cluster in processed_clusters:
                continue
            
            processed_clusters.add(skin_cluster)
            
            geometry = cmds.skinCluster(skin_cluster, query=True, geometry=True)
            if geometry:
                for geo in geometry:
                    mesh_transform = cmds.listRelatives(geo, parent=True, type='transform')[0]
                    influences = cmds.skinCluster(skin_cluster, query=True, influence=True)
                    
                    # Get skinCluster settings
                    skin_method = cmds.getAttr(f"{skin_cluster}.skinningMethod")
                    normalize_weights = cmds.getAttr(f"{skin_cluster}.normalizeWeights")
                    max_influences = cmds.getAttr(f"{skin_cluster}.maxInfluences")
                    
                    skin_info.append({
                        'mesh': mesh_transform,
                        'skin_cluster': skin_cluster,
                        'influences': influences,
                        'skin_method': skin_method,
                        'normalize_weights': normalize_weights,
                        'max_influences': max_influences,
                        'mesh_scale': [
                            cmds.getAttr(f"{mesh_transform}.scaleX"),
                            cmds.getAttr(f"{mesh_transform}.scaleY"),
                            cmds.getAttr(f"{mesh_transform}.scaleZ")
                        ]
                    })
                    
                    print(f"Found skin cluster: {skin_cluster} on {mesh_transform}")
    
    # Get temp directory
    temp_dir = cmds.internalVar(userTmpDir=True)
    
    # Export skin weights using Maya's deformer weights
    print("\nExporting skin weights...")
    weight_files = {}
    for info in skin_info:
        skin_cluster = info['skin_cluster']
        mesh = info['mesh']
        
        # Create weight file name
        weight_file_name = f"{skin_cluster}_weights.xml"
        
        # Export weights to temp directory
        cmds.deformerWeights(weight_file_name,
                            export=True,
                            deformer=skin_cluster,
                            path=temp_dir)
        
        weight_files[skin_cluster] = weight_file_name
        print(f"Exported weights for {skin_cluster}")
    
    # Unbind all skin clusters
    print("\nUnbinding skin clusters...")
    for info in skin_info:
        cmds.skinCluster(info['mesh'], edit=True, unbind=True)
        print(f"Unbound {info['mesh']}")
    
    # After unbinding, mesh scales will be at 10000 (100 * 100)
    # Set them to 100 instead
    print("\nSetting mesh scales to 100...")
    for info in skin_info:
        mesh = info['mesh']
        
        # Check current scale after unbind
        current_mesh_scale = cmds.getAttr(f"{mesh}.scaleX")
        print(f"Mesh {mesh} current scale: {current_mesh_scale}")
        
        # Set to 100
        cmds.setAttr(f"{mesh}.scaleX", 100)
        cmds.setAttr(f"{mesh}.scaleY", 100)
        cmds.setAttr(f"{mesh}.scaleZ", 100)
        
        print(f"Set {mesh} scale to 100")
    
    # Freeze transforms on meshes (bake scale 100 into vertices, scale becomes 1)
    print("\nFreezing transforms on meshes...")
    for info in skin_info:
        mesh = info['mesh']
        
        try:
            cmds.makeIdentity(mesh, apply=True, translate=True, rotate=True, scale=True, normal=False)
            print(f"Froze transforms on {mesh}")
        except Exception as e:
            print(f"Error freezing {mesh}: {e}")
    
    # Adjust skeleton
    print("\nAdjusting skeleton...")
    cmds.setAttr(f"{root_bone}.scaleX", target_scale)
    cmds.setAttr(f"{root_bone}.scaleY", target_scale)
    cmds.setAttr(f"{root_bone}.scaleZ", target_scale)
    
    joints_scaled = 0
    for child in all_children:
        if cmds.nodeType(child) == 'joint':
            tx = cmds.getAttr(f"{child}.translateX")
            ty = cmds.getAttr(f"{child}.translateY")
            tz = cmds.getAttr(f"{child}.translateZ")
            
            cmds.setAttr(f"{child}.translateX", tx * scale_factor)
            cmds.setAttr(f"{child}.translateY", ty * scale_factor)
            cmds.setAttr(f"{child}.translateZ", tz * scale_factor)
            
            try:
                radius = cmds.getAttr(f"{child}.radius")
                cmds.setAttr(f"{child}.radius", radius * scale_factor)
            except:
                pass
            
            joints_scaled += 1
    
    print(f"Scaled {joints_scaled} child joints")
    
    # Rebind skin with original weights
    print("\nRebinding skin clusters...")
    for info in skin_info:
        mesh = info['mesh']
        influences = info['influences']
        old_skin_cluster = info['skin_cluster']
        
        # Create new skin cluster with same settings
        new_skin = cmds.skinCluster(influences, mesh,
                                     toSelectedBones=True,
                                     skinMethod=info['skin_method'],
                                     normalizeWeights=info['normalize_weights'],
                                     maximumInfluences=info['max_influences'],
                                     name=old_skin_cluster)[0]
        
        print(f"Created new skin cluster {new_skin} on {mesh}")
        
        # Import weights from file
        weight_file = weight_files[old_skin_cluster]
        try:
            cmds.deformerWeights(weight_file,
                                im=True,
                                deformer=new_skin,
                                path=temp_dir)
            print(f"Imported weights for {mesh}")
        except Exception as e:
            print(f"Error importing weights for {mesh}: {e}")
    
    # Clean up temp files
    print("\nCleaning up temp files...")
    for weight_file in weight_files.values():
        try:
            full_path = os.path.join(temp_dir, weight_file)
            if os.path.exists(full_path):
                os.remove(full_path)
                print(f"Deleted {full_path}")
        except Exception as e:
            print(f"Could not delete temp file: {e}")
    
    print(f"\n=== Summary ===")
    print(f"- Normalized root bone to scale {target_scale}")
    print(f"- Scaled {joints_scaled} child joints")
    print(f"- Froze {len(skin_info)} mesh(es) at scale 100")
    print(f"- Rebound {len(skin_info)} mesh(es) with original weights")
    print("Done! Meshes now at scale 1, skeleton at scale 1, weights preserved!")

# Execute
if __name__ == "__main__":
    normalize_root_freeze_100()