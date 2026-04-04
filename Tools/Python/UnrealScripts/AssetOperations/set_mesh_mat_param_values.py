import unreal
from Materials import material_utils

# import importlib
# importlib.reload(material_utils)

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


def get_root_materials(mesh: unreal.StaticMesh):
    all_materials = mesh.static_materials
    mats = []
    for mat in all_materials:
        mi = mat.material_interface
        if not isinstance(mi, unreal.MaterialInstanceConstant):
            continue
        is_root = True
        for other_mat in all_materials:
            other_mi = other_mat.material_interface
            if mi.get_editor_property("parent") == other_mi:
                is_root = False
                break
        
        if is_root:
            mats.append(mi)
    
    return mats


def set_mat_scalar_param_for_mesh(mesh: unreal.StaticMesh, param_pair):
    mats = get_root_materials(mesh)
    print(mats)
    has_value_changed = False
    for mat in mats:
        for key, value in param_pair.items():
            unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mat, key, value)
        #     value_changed = material_utils.set_material_scalar_param_value(
        #         mat, key, value
        #     )
        #     if value_changed:
        #         has_value_changed = True
        # if has_value_changed:
        #     unreal.PythonFunctionLibrary.force_refresh_material_instance(mat)
        unreal.MaterialEditingLibrary.update_material_instance(mat)

    editor_asset_sub.save_loaded_assets(mats, False)
        

if __name__ == "__main__":
    selected_asset_data = unreal.EditorUtilityLibrary.get_selected_asset_data()[0]
    
    param_pair = {
        "Camera Fade Near Distance": 50,
        "Camera Fade Far Distance": 200
    }
    
    set_mat_scalar_param_for_mesh(editor_asset_sub.load_asset(selected_asset_data.package_name),
                                  param_pair)