import unreal
import sys


editor_actor_subsystem = unreal.EditorActorSubsystem()
editor_asset_subsystem = unreal.EditorAssetSubsystem()
SHADOW_PROXY_MATERIAL = "/Game/Art/Materials/Environmental_Material/Base_Master_Material/M_Base_Shadow"
CAMERA_BLOCKER_MATERIAL = "/Game/Art/Materials/Environmental_Material/Base_Master_Material/M_Collision"

TOOL_TAG_LIST = [
    "ShadowProxy",
    "ShadowMesh",
    "CameraBlocker"
]


def remove_tool_tags(mesh_actor: unreal.StaticMeshActor):
    for tag in TOOL_TAG_LIST:
        if mesh_actor.static_mesh_component.component_has_tag(tag):
            mesh_actor.static_mesh_component.get_editor_property("component_tags").remove(tag)
        if str(mesh_actor.get_actor_label()).endswith(tag):
            mesh_actor.set_actor_label(str(mesh_actor.get_actor_label()).replace('_' + tag, ''))
    if str(mesh_actor.get_actor_label()).endswith("_PSM"):
        mesh_actor.set_actor_label(str(mesh_actor.get_actor_label()).replace('_PSM', ''))


def setting_shadow_proxy_actor(mesh_actor: unreal.StaticMeshActor):
    mesh_actor.static_mesh_component.set_editor_property("render_in_main_pass", False)
    mesh_actor.static_mesh_component.set_editor_property("render_in_depth_pass", False)
    mesh_actor.static_mesh_component.set_editor_property("receives_decals", False)
    mesh_actor.static_mesh_component.set_editor_property("visible_in_ray_tracing", False)
    mesh_actor.static_mesh_component.set_editor_property("visible_in_real_time_sky_captures", False)
    mesh_actor.static_mesh_component.set_editor_property("visible_in_reflection_captures", False)
    mesh_actor.static_mesh_component.set_editor_property("use_as_occluder", False)
    mesh_actor.static_mesh_component.set_editor_property("affect_distance_field_lighting", False)
    mesh_actor.static_mesh_component.set_editor_property("visible_in_ray_tracing", False)
    mesh_actor.static_mesh_component.set_collision_profile_name("NoCollision")
    mesh_actor.static_mesh_component.set_editor_property("cast_hidden_shadow", False)


    target_material = editor_asset_subsystem.load_asset(SHADOW_PROXY_MATERIAL)
    for index in range(len(mesh_actor.static_mesh_component.get_materials())):
        mesh_actor.static_mesh_component.set_material(index, target_material)
        
    remove_tool_tags(mesh_actor)
    if not mesh_actor.static_mesh_component.component_has_tag("ShadowProxy"):
        mesh_actor.static_mesh_component.component_tags.append("ShadowProxy")
    mesh_actor.set_actor_label("{}_{}".format(mesh_actor.get_actor_label(), "PSM"))


def setting_shadow_mesh_actor(mesh_actor: unreal.StaticMeshActor, should_change_mat = True):
    mesh_actor.static_mesh_component.set_editor_property("render_in_main_pass", True)
    mesh_actor.static_mesh_component.set_editor_property("affect_distance_field_lighting", True)
    mesh_actor.static_mesh_component.set_editor_property("hidden_in_game", True)
    mesh_actor.static_mesh_component.set_editor_property("cast_hidden_shadow", True)
    mesh_actor.static_mesh_component.set_editor_property("visible_in_ray_tracing", False)
    mesh_actor.static_mesh_component.set_collision_profile_name("NoCollision")

    if should_change_mat:
        target_material = editor_asset_subsystem.load_asset(SHADOW_PROXY_MATERIAL)
        for index in range(len(mesh_actor.static_mesh_component.get_materials())):
            mesh_actor.static_mesh_component.set_material(index, target_material)
    
    remove_tool_tags(mesh_actor)
    if not mesh_actor.static_mesh_component.component_has_tag("ShadowMesh"):
        mesh_actor.static_mesh_component.component_tags.append("ShadowMesh")
    mesh_actor.set_actor_label("{}_{}".format(mesh_actor.get_actor_label(), "ShadowMesh"))


def setting_camera_blocker_actor(mesh_actor: unreal.StaticMeshActor):
    mesh_actor.static_mesh_component.set_editor_property("visible", False)
    mesh_actor.static_mesh_component.set_editor_property("hidden_in_game", True)
    mesh_actor.static_mesh_component.set_collision_profile_name("CameraBlocker")
    
    target_material = editor_asset_subsystem.load_asset(CAMERA_BLOCKER_MATERIAL)
    for index in range(len(mesh_actor.static_mesh_component.get_materials())):
        mesh_actor.static_mesh_component.set_material(index, target_material)

    remove_tool_tags(mesh_actor)
    if not mesh_actor.static_mesh_component.component_has_tag("CameraBlocker"):
        mesh_actor.static_mesh_component.component_tags.append("CameraBlocker")
    mesh_actor.set_actor_label("{}_{}".format(mesh_actor.get_actor_label(), "CameraBlocker"))


if __name__ == "__main__":
    selected_actors = editor_actor_subsystem.get_selected_level_actors()
    actor_type = sys.argv[1]

    for selected_actor in selected_actors:
        if actor_type == "ShadowProxy":
            setting_shadow_proxy_actor(selected_actor)
        elif actor_type == "CameraBlocker":
            setting_camera_blocker_actor(selected_actor)
        elif actor_type == "ShadowMesh":
            setting_shadow_mesh_actor(selected_actor)
        elif actor_type == "ShadowMesh_NoChangeMat":
            setting_shadow_mesh_actor(selected_actor, False)