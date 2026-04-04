import unreal

editor_util_lib = unreal.EditorUtilityLibrary()
system_lib = unreal.SystemLibrary()

if __name__ == "__main__":
    selected_assets = editor_util_lib.get_selected_asset_data()
    for selected_asset_data in selected_assets:
        editor_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        system_lib.execute_console_command(editor_world, "py AssetImport/mesh_import_setting_UI.py {}".format(selected_asset_data.package_name))