import maya.cmds as cmds

def rebind_skin_clean(selected_only=True):
    """
    Rebind skin to rig, removing weights from deleted bones.
    This will unbind and rebind the skin with currently existing joints only.
    
    Args:
        selected_only (bool): If True, only process selected meshes. 
                              If False, process all skinned meshes in scene.
    """
    
    # Get meshes to process
    if selected_only:
        selection = cmds.ls(selection=True, long=True)
        if not selection:
            cmds.warning("No objects selected. Please select meshes to rebind.")
            return
        
        # Get mesh transforms
        meshes = []
        for obj in selection:
            shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
            for shape in shapes:
                if cmds.nodeType(shape) == 'mesh':
                    meshes.append(obj)
                    break
        
        if not meshes:
            cmds.warning("No mesh objects found in selection.")
            return
    else:
        # Get all skinned meshes in scene
        all_skin_clusters = cmds.ls(type='skinCluster')
        if not all_skin_clusters:
            cmds.warning("No skinned meshes found in scene.")
            return
        
        meshes = []
        for sc in all_skin_clusters:
            mesh_shapes = cmds.skinCluster(sc, query=True, geometry=True)
            if mesh_shapes:
                for shape in mesh_shapes:
                    transform = cmds.listRelatives(shape, parent=True, fullPath=True)
                    if transform:
                        meshes.append(transform[0])
        
        meshes = list(set(meshes))  # Remove duplicates
    
    if not meshes:
        cmds.warning("No meshes to process.")
        return
    
    print(f"\n{'='*60}")
    print(f"Rebinding {len(meshes)} mesh(es)...")
    print(f"{'='*60}\n")
    
    rebind_count = 0
    failed_meshes = []
    
    for mesh in meshes:
        try:
            # Find skinCluster
            skin_cluster = None
            history = cmds.listHistory(mesh, pruneDagObjects=True)
            for node in history:
                if cmds.nodeType(node) == 'skinCluster':
                    skin_cluster = node
                    break
            
            if not skin_cluster:
                print(f"Skipping {mesh}: No skinCluster found")
                continue
            
            print(f"\nProcessing: {mesh}")
            print(f"  SkinCluster: {skin_cluster}")
            
            # Get current influences (joints)
            influences = cmds.skinCluster(skin_cluster, query=True, influence=True)
            
            # Filter out deleted or non-existent joints
            valid_influences = []
            deleted_count = 0
            for inf in influences:
                if cmds.objExists(inf):
                    valid_influences.append(inf)
                else:
                    deleted_count += 1
                    print(f"  Found deleted influence: {inf}")
            
            if deleted_count > 0:
                print(f"  Found {deleted_count} deleted bone(s)")
            
            if not valid_influences:
                print(f"  ERROR: No valid influences found!")
                failed_meshes.append(mesh)
                continue
            
            print(f"  Valid influences: {len(valid_influences)}")
            
            # Get skinCluster settings
            max_influences = cmds.skinCluster(skin_cluster, query=True, maximumInfluences=True)
            skinning_method = cmds.getAttr(f"{skin_cluster}.skinningMethod")
            normalize_weights = cmds.getAttr(f"{skin_cluster}.normalizeWeights")
            
            # Unbind skin
            print(f"  Unbinding skin...")
            cmds.skinCluster(skin_cluster, edit=True, unbind=True)
            
            # Rebind with valid influences only
            print(f"  Rebinding with {len(valid_influences)} joints...")
            new_skin_cluster = cmds.skinCluster(
                valid_influences, 
                mesh,
                toSelectedBones=True,
                maximumInfluences=max_influences,
                skinMethod=skinning_method,
                normalizeWeights=normalize_weights,
                name=skin_cluster  # Try to keep same name
            )[0]
            
            print(f"  SUCCESS: Created new skinCluster: {new_skin_cluster}")
            rebind_count += 1
            
        except Exception as e:
            print(f"  ERROR processing {mesh}: {str(e)}")
            failed_meshes.append(mesh)
            continue
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Rebind Complete!")
    print(f"{'='*60}")
    print(f"Successfully rebound: {rebind_count}/{len(meshes)} meshes")
    
    if failed_meshes:
        print(f"\nFailed meshes:")
        for mesh in failed_meshes:
            print(f"  - {mesh}")
    
    print("")


def rebind_selected():
    """
    Rebind selected meshes only.
    """
    rebind_skin_clean(selected_only=True)


def rebind_all():
    """
    Rebind all skinned meshes in the scene.
    """
    rebind_skin_clean(selected_only=False)


# Main execution
if __name__ == "__main__":
    # By default, rebind selected meshes
    # To rebind all meshes in scene, use: rebind_all()
    rebind_selected()
