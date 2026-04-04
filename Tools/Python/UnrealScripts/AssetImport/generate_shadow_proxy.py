import unreal
import path_util
import os
from AssetImport import asset_import_utils
from AssetOperations import static_mesh_utils

import importlib
importlib.reload(path_util)

TEMP_STORE_FBX_FOLDER = "ShadowProxy"
SHADOW_MATERIAL_PATH = "/Game/Art/Materials/M_Base_Shadow"

editor_util_lib = unreal.EditorUtilityLibrary()
editor_dialog = unreal.EditorDialog()


def get_export_folder_path():
    export_folder = path_util.tool_output_temp_folder()
    export_folder = os.path.join(export_folder, TEMP_STORE_FBX_FOLDER)
    if not os.path.isdir(export_folder):
        os.makedirs(export_folder)
    return export_folder
    
    
def export_selected_fbx(asset_to_export: unreal.Object, export_file_path):
    task = unreal.AssetExportTask()
    task.set_editor_property('filename', export_file_path)
    task.set_editor_property('automated', True)
    # this will cause export error... not sure why. we can let engine decide the output type
    # task.set_editor_property('exporter', unreal.ExporterFBX())
    print(asset_to_export)
    task.set_editor_property('object', asset_to_export)

    fbx_options = unreal.FbxExportOption()
    fbx_options.set_editor_property('collision', False)
    fbx_options.set_editor_property('force_front_x_axis', False)
    fbx_options.set_editor_property('level_of_detail', False)
    task.set_editor_property('options', fbx_options)
    
    with unreal.ScopedSlowTask(1, "Exporting FBX for {}...".format(asset_to_export.get_name())) as slow_task:
        # display the dialog
        slow_task.make_dialog(True)
        result = unreal.Exporter.run_asset_export_task(task)
        
    print('[Auto Shadow Proxy] Export {} Result: {}'.format(asset_to_export.get_name(), result))
    
    if not result:
        editor_dialog.show_message("Shadow Proxy Error", 
                                   "Fail to export shadow mesh for {}".format(asset_to_export.get_name()), 
                                   unreal.AppMsgType.OK)
        

def reimport_shadow_proxy_mesh(fbx_path, package_path, asset_name):
    import_option = asset_import_utils.build_staticmesh_import_options()
    import_task = asset_import_utils.build_input_task_simple(fbx_path, package_path, asset_name, import_option)
    import_result = asset_import_utils.execute_import_tasks([import_task])
    return import_result


def setup_shadow_mesh_asset(shadow_mesh: unreal.StaticMesh):
    lod_reduction_settings = [
        unreal.StaticMeshReductionSettings(1.0, 1.0),
        unreal.StaticMeshReductionSettings(0.8, 0.75),
        unreal.StaticMeshReductionSettings(0.4, 0.25),
        unreal.StaticMeshReductionSettings(0.1, 0.05)
    ]
    static_mesh_utils.apply_lods(shadow_mesh, lod_reduction_settings)

    body = shadow_mesh.get_editor_property('body_setup')
    body.set_editor_property('collision_trace_flag', unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
    
    body_instance = body.get_editor_property('default_instance')
    body_instance.set_editor_property('collision_profile_name', 'NoCollision')
    body.set_editor_property('default_instance', body_instance)
    
    shadow_mesh.set_editor_property('body_setup', body)
    
    shadow_material = unreal.load_asset(SHADOW_MATERIAL_PATH)
    for index in range(0, len(shadow_mesh.static_materials)):
        shadow_mesh.set_material(index, shadow_material)
        
    unreal.EditorAssetLibrary.save_loaded_asset(shadow_mesh)


if __name__ == "__main__":
    export_folder = get_export_folder_path()
    selected_assets = editor_util_lib.get_selected_asset_data()
    for selected_asset_data in selected_assets:
        is_nanite = selected_asset_data.get_tag_value("NaniteEnabled")
        if is_nanite == "False":
            editor_dialog.show_message("Shadow Proxy Warning",
                                       "Asset {} is not nanite. You don't need the shadow proxy".format(selected_asset_data.asset_name),
                                       unreal.AppMsgType.OK)
        
        # tag_values = unreal.EditorAssetLibrary.get_tag_values(selected_asset_data.package_name)
        # print(tag_values)
        
        export_fbx_name = "{}/{}_PSM.fbx".format(export_folder, selected_asset_data.asset_name)
        export_selected_fbx(selected_asset_data.get_asset(), export_fbx_name)
        
        shadow_proxy_asset_name = "{}_PSM".format(selected_asset_data.asset_name)
        imported_assets = reimport_shadow_proxy_mesh(export_fbx_name, selected_asset_data.package_path, shadow_proxy_asset_name)
        
        if len(imported_assets) == 0 or imported_assets[0] is None:
            editor_dialog.show_message("Shadow Proxy Error",
                                       "Fail to import shadow proxy: {}".format(
                                           export_fbx_name),
                                       unreal.AppMsgType.OK)
        
        shadow_proxy_asset_path = imported_assets[0]
        shadow_proxy_asset = unreal.load_asset(shadow_proxy_asset_path)
        setup_shadow_mesh_asset(shadow_proxy_asset)

    # editor_dialog.show_message("Shadow Proxy Message",
    #                            "Finish Generating Shadow Proxy",
    #                            unreal.AppMsgType.OK)