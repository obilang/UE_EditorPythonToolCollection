if __name__ == "__main__":
    import unreal
    from Materials import material_utils
    # import path_util
    mat = unreal.EditorUtilityLibrary.get_selected_asset_data()[0]
    base_mat = material_utils.get_base_material(mat)
    mat_obj = unreal.load_asset(base_mat.package_name)
    # real_path = unreal.SystemLibrary().get_system_path(mat_obj)
    # path_util.make_writable(real_path)
    unreal.MaterialEditingLibrary().recompile_material(mat_obj)
    # unreal.EditorAssetLibrary.save_asset(base_mat.package_name)
