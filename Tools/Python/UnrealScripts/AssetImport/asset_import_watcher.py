import unreal
import global_state
import global_config

import_subsystem = None
system_lib = unreal.SystemLibrary
g_is_reimporting = False


def LOG_WATCHER(log_str):
    unreal.log("[Import Watcher]: {}".format(log_str))


def start_import_watcher():
    if global_config.GLOBAL_CONFIG.enable_import_hook:
        global import_subsystem
        LOG_WATCHER("Start watching new imports.")
        import_subsystem = unreal.get_editor_subsystem(unreal.ImportSubsystem)
        if import_subsystem:
            import_subsystem.on_asset_pre_import.add_callable_unique(_on_pre_import)
            import_subsystem.on_asset_post_import.add_callable_unique(_on_post_import)
            import_subsystem.on_asset_reimport.add_callable_unique(_on_reimport)


# def stop_import_watcher():
#     LOG_WATCHER("Stop watching new imports.")
#     import_subsystem = unreal.get_editor_subsystem(unreal.ImportSubsystem)
#     if import_subsystem and import_subsystem.on_asset_pre_import.contains_callable(_on_pre_import):
#         import_subsystem.on_asset_pre_import.remove_callable(_on_pre_import)
#         import_subsystem.on_asset_post_import.remove_callable(_on_post_import)
#         import_subsystem.on_asset_post_import.remove_callable(_on_reimport)


def _on_pre_import(factory, objClass, parentObj, name, aa):
    LOG_WATCHER("Pre Import: {}|{}|{}|{}|{}".format(factory, objClass, parentObj, name, aa))


def _on_post_import(fact, obj):
    if global_state.g_is_tool_importing_asset:
        LOG_WATCHER("g_is_tool_importing_asset: {}".format(global_state.g_is_tool_importing_asset))
        return 
    
    LOG_WATCHER("Import: {}|{}|{}|{}|{}".format(fact, obj, obj, obj, obj))
    LOG_WATCHER(obj.get_path_name())

    global g_is_reimporting
    if g_is_reimporting:
        LOG_WATCHER("is reimporting asset: {}".format(g_is_reimporting))
        g_is_reimporting = False
        return
    
    editor_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if isinstance(obj, unreal.Texture2D):
        system_lib.execute_console_command(editor_world,
                                           "py AssetImport/texture_import_setting_UI.py {}".format(obj.get_path_name()))
    elif isinstance(obj, unreal.StaticMesh):
        system_lib.execute_console_command(editor_world,
                                           "py AssetImport/mesh_import_setting_UI.py {}".format(
                                               obj.get_path_name()))
    
    
def _on_reimport(obj):
    LOG_WATCHER("Reimport: ")
    global g_is_reimporting
    g_is_reimporting = True
    
    # static mesh reimport do not call the post import event
    editor_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if isinstance(obj, unreal.StaticMesh):
        system_lib.execute_console_command(editor_world,
                                           "py AssetImport/mesh_import_setting_UI.py {}".format(obj.get_path_name()))


# if __name__ == "__main__":
#     if global_config.GLOBAL_CONFIG.enable_import_hook:
#         start_import_watcher()
