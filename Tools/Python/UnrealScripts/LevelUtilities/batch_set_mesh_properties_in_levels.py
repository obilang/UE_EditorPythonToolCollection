import unreal
from AssetOperations import asset_utils
from LevelUtilities import level_utils
from Materials import material_utils
from AssetImport import mesh_import_setting
from typing import List

import importlib

importlib.reload(asset_utils)

editor_asset_subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
level_editor_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def LOG_SETTING(log_str):
    unreal.log("[Set Mesh Properties]: {}".format(log_str))


def find_mesh_component_owns_static_mesh(mesh_obj: unreal.StaticMesh):
    mesh_components = []
    mesh_obj_path = mesh_obj.get_package().get_path_name()
    all_components_in_level = level_utils.get_meshes_components_from_current_level()
    for sm_path, mcs in all_components_in_level.items():
        sm_path = asset_utils.object_path_to_package_path(sm_path)
        if sm_path == mesh_obj_path:
            for mc in mcs:
                if isinstance(mc, unreal.InstancedStaticMeshComponent):
                    if mc.get_instance_count() > 0:
                        mesh_components.append(mc)
                else:
                    mesh_components.append(mc)
            break

    return mesh_components


def update_property_for_static_mesh_in_current_level(mesh_obj: unreal.StaticMesh):
    related_mesh_components = find_mesh_component_owns_static_mesh(mesh_obj)

    LOG_SETTING(" related mesh components: {}".format(related_mesh_components))
    return update_property_for_components_in_current_level(related_mesh_components)


def update_property_for_components_in_current_level(related_mesh_components: List[unreal.StaticMeshComponent]):
    should_save = False
    for related_mc in related_mesh_components:
        b_receive_decals = related_mc.receives_decals
        if not b_receive_decals:
            related_mc.set_receives_decals(True)
            should_save = True

    return should_save


def update_property_for_static_mesh_in_all_levels(mesh_asset: unreal.AssetData):
    # cs_maps = asset_utils.get_all_cs_maps()
    in_game_maps = asset_utils.get_all_game_maps()

    all_map = set()
    # for cs_map in cs_maps:
    #     cs_map = str(cs_map)
    #     sp = cs_map.split('/')
    #     name = sp[-1]
    #     folder_name = sp[-2]
    #     folder_name_2 = sp[-3]
    #     if name != folder_name and name != folder_name_2:
    #         all_map.add(cs_map)
    for in_game_map in in_game_maps:
        all_map.add(in_game_map)

    all_ref_levels = asset_utils.get_asset_ref_by(mesh_asset.package_name, list(all_map), -1, [unreal.World])
    mesh_obj = editor_asset_subsystem.load_asset(mesh_asset.package_name)
    changed_mats = set()
    failed_to_save_levels = []
    print(all_ref_levels)
    for level in all_ref_levels:
        level_editor_subsystem.load_level(level)
        should_save = update_property_for_static_mesh_in_current_level(mesh_obj)

        if should_save:
            LOG_SETTING(" Saving changed level: {}".format(level))
            save_result = editor_asset_subsystem.save_asset(level, False)
            if not save_result:
                LOG_SETTING(" Failed to save changed level: {}".format(level))
                failed_to_save_levels.append(level)

    if len(failed_to_save_levels) > 0:
        unreal.EditorDialog.show_message("Fail to save level", failed_to_save_levels, unreal.AppMsgType.OK)


if __name__ == "__main__":
    selected_asset_data = unreal.EditorUtilityLibrary.get_selected_asset_data()
    for asset_data in selected_asset_data:
        # mesh_obj = unreal.load_asset(asset_data.package_name)
        update_property_for_static_mesh_in_all_levels(asset_data)

