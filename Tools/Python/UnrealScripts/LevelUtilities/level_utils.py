import unreal
from typing import List
from typing import Dict
from typing import Set

editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor_filter_lib = unreal.EditorFilterLibrary()
editor_level_lib = unreal.EditorLevelLibrary()
system_lib = unreal.SystemLibrary()
editor_level_utils = unreal.EditorLevelUtils()
editor_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def spawn_actor_from_class(actor_class, location=[0, 0, 0], actor_label='', actor_folder='') -> unreal.Actor:
    actor = editor_level_lib.spawn_actor_from_class(actor_class, location)
    if actor is not None:
        actor.set_actor_location_and_rotation(location, [0, 0, 0], False, False)
        if actor_label != '':
            actor.set_actor_label(actor_label)
        if actor_folder != '':
            actor.set_folder_path(actor_folder)
    return actor


def get_mesh_asset_from_actor(sm_actor: unreal.StaticMeshActor) -> unreal.StaticMesh:
    smc = sm_actor.static_mesh_component
    sm = smc.get_editor_property("static_mesh")
    return sm


def get_meshes_from_current_level() -> Dict[str, List[unreal.StaticMeshActor]]:
    mesh_dict = {}
    all_actors = editor_actor_subsystem.get_all_level_actors()
    smas = editor_filter_lib.by_class(all_actors, unreal.StaticMeshActor)
    for sma in smas:
        smc = sma.static_mesh_component
        sm = smc.get_editor_property("static_mesh")
        if sm is None:
            continue
        sm_path = str(sm).split("'")[1]
        if sm_path not in mesh_dict:
            mesh_dict[sm_path] = []
        if sma not in mesh_dict[sm_path]:
            mesh_dict[sm_path].append(sma)
    return mesh_dict


def get_meshes_components_from_current_level(selected_only=False) -> Dict[str, List[unreal.StaticMeshComponent]]:
    """
    this includes the mesh components inside blueprint
    :return: 
    """
    mesh_dict = {}
    all_components = editor_actor_subsystem.get_all_level_actors_components()
    smcs = editor_filter_lib.by_class(all_components, unreal.StaticMeshComponent)
    if selected_only:
        all_selected_actors = editor_actor_subsystem.get_selected_level_actors()
    for smc in smcs:
        if selected_only and smc.get_owner() not in all_selected_actors:
            continue
        
        sm = smc.get_editor_property("static_mesh")
        if sm is None:
            continue
    
        sm_path = sm.get_package().get_path_name()
        if sm_path not in mesh_dict:
            mesh_dict[sm_path] = []
        if smc not in mesh_dict[sm_path]:
            mesh_dict[sm_path].append(smc)
    return mesh_dict


def get_bps_from_current_level():
    bp_dict = {}
    all_actors = editor_level_lib.get_all_level_actors()

    for bp_actor in all_actors:
        if bp_actor.get_class().get_class().get_name() == "BlueprintGeneratedClass":
            bp_actor_class = unreal.SystemLibrary.get_class_display_name(bp_actor.get_class())
            if bp_actor_class not in bp_dict:
                bp_dict[bp_actor_class] = []
            if bp_actor not in bp_dict[bp_actor_class]:
                bp_dict[bp_actor_class].append(bp_actor)
    return bp_dict


def get_mesh_physic_materials(mesh_component: unreal.StaticMeshComponent) -> List[unreal.PhysicalMaterial]:
    body_instance = mesh_component.get_editor_property("body_instance")
    phy_mat_override = body_instance.get_editor_property("phys_material_override")
    if phy_mat_override is not None:
        result = [phy_mat_override]
    else:
        result = []
        materials = mesh_component.get_materials()
        for element in materials:
            phy_mat = element.get_physical_material()
            if phy_mat is not None:
                result.append(phy_mat)
    return result


def get_mesh_collision_trace_block_channels(mesh_component: unreal.StaticMeshComponent):
    body_instance = mesh_component.get_editor_property("body_instance")
    collision_responses = body_instance.get_editor_property("collision_responses")

    result = []
    for res_channel in collision_responses.get_editor_property("response_array"):
        channel_name = res_channel.get_editor_property("channel")
        response = res_channel.get_editor_property("response")
        if response == unreal.CollisionResponseType.ECR_BLOCK:
            result.append(str(channel_name))
    return result


def get_visible_sub_levels() -> Set[unreal.Level]:
    """
    very slow method
    :return: 
    """
    it = unreal.ObjectIterator()
    visible_levels = set()
    for x in it:
        if isinstance(x, unreal.LevelStreaming):
            if x.get_loaded_level() and x.is_level_visible():
                visible_levels.add(x.get_loaded_level())
    return visible_levels

