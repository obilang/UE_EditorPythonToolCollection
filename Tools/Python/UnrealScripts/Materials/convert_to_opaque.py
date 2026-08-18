import unreal

editor_util_lib = unreal.EditorUtilityLibrary()
selected_assets = editor_util_lib.get_selected_asset_data()


for mesh_data in selected_assets:
    mat_obj = unreal.EditorAssetLibrary.load_asset(mesh_data.package_name) 
    blend_mode = mat_obj.get_blend_mode()
    if blend_mode != unreal.BlendMode.BLEND_OPAQUE:
        if blend_mode == unreal.BlendMode.BLEND_MASKED:
            base_property_overrides = mat_obj.get_editor_property("base_property_overrides")
            base_property_overrides.set_editor_property("override_blend_mode", True)
            base_property_overrides.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
            mat_obj.set_editor_property("base_property_overrides", base_property_overrides)
            unreal.ExtraPythonFunctionLibrary.force_refresh_material_instance(mat_obj)
            unreal.EditorAssetLibrary.save_loaded_asset(mat_obj)
            print(f"Changed {mat_obj.get_name()} to Opaque")