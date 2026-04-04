import unreal
from LevelUtilities import level_utils
from LevelUtilities import auto_setting_actor_properties

import importlib
importlib.reload(level_utils)

editor_actor_subsystem = unreal.EditorActorSubsystem()
editor_asset_lib = unreal.EditorAssetLibrary()
editor_dialog = unreal.EditorDialog()


def get_shadow_mesh_package_path(origin_mesh_path):
    double_name_index = origin_mesh_path.rindex(".")
    first_part = origin_mesh_path[0: double_name_index]
    second_part = origin_mesh_path[double_name_index + 1:]
    shadow_mesh_path = "{}_PSM.{}_PSM".format(first_part, second_part)
    return shadow_mesh_path


if __name__ == "__main__":
    mesh = editor_actor_subsystem.get_selected_level_actors()[0]
    static_mesh = level_utils.get_mesh_asset_from_actor(mesh)
    shadow_mesh_path = get_shadow_mesh_package_path(static_mesh.get_path_name())
    is_exist = editor_asset_lib.does_asset_exist(shadow_mesh_path)
    
    if is_exist: 
        shadow_mesh_obj = editor_asset_lib.load_asset(shadow_mesh_path)
        shadow_mesh_actor = editor_actor_subsystem.spawn_actor_from_object(shadow_mesh_obj, [0, 0, 0])
        shadow_mesh_actor.attach_to_actor(mesh, "", 
                                          unreal.AttachmentRule.KEEP_RELATIVE, 
                                          unreal.AttachmentRule.KEEP_RELATIVE, 
                                          unreal.AttachmentRule.KEEP_RELATIVE)
        
        mesh.static_mesh_component.set_editor_property("cast_shadow", False)
        auto_setting_actor_properties.setting_shadow_proxy_actor(shadow_mesh_actor)
    else:
        editor_dialog.show_message("Shadow Proxy Error",
                                   "Fail to find shadow proxy: {} \n Please create one first".format(
                                       shadow_mesh_path),
                                   unreal.AppMsgType.OK)


