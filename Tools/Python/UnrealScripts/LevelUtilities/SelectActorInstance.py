import unreal
from LevelUtilities import level_utils

editor_level_lib = unreal.EditorActorSubsystem()
editor_filter_lib = unreal.EditorFilterLibrary()
sys_lib = unreal.SystemLibrary


def get_same_meshes_from_current_level(base_mesh_actor):
    base_mesh_component = base_mesh_actor.static_mesh_component
    base_static_mesh = base_mesh_component.get_editor_property("static_mesh")
    
    mesh_list = []
    all_actors = editor_level_lib.get_all_level_actors()
    smas = editor_filter_lib.by_class(all_actors, unreal.StaticMeshActor)
    for sma in smas:
        smc = sma.static_mesh_component
        sm = smc.get_editor_property("static_mesh")
        if sm is None:
            continue
        if sm == base_static_mesh:
            mesh_list.append(sma)
        # sm_path = str(sm).split("'")[1]

    return mesh_list


def get_bps_from_current_level(base_bp_actor):
    bp_dict = level_utils.get_bps_from_current_level()
    bp_actor_class = unreal.SystemLibrary.get_class_display_name(base_bp_actor.get_class())
    for bp_class, bp_actors in bp_dict.items():
        if bp_class == bp_actor_class:
            return bp_actors

    return []


def get_all_actor_instance_with_same_type():
    actor_list = editor_level_lib.get_selected_level_actors()
    selected_actor = actor_list[0]
    actor_class = sys_lib.get_class_display_name(selected_actor.static_class())
    print(actor_class)
    if actor_class == "StaticMeshActor":
        mesh_actors = get_same_meshes_from_current_level(selected_actor)
        editor_level_lib.clear_actor_selection_set()
        for mesh_actor in mesh_actors:
            editor_level_lib.set_actor_selection_state(mesh_actor, True)
    if selected_actor.get_class().get_class().get_name() == "BlueprintGeneratedClass":
        bp_actors = get_bps_from_current_level(selected_actor)
        editor_level_lib.clear_actor_selection_set()
        for bp_actor in bp_actors:
            editor_level_lib.set_actor_selection_state(bp_actor, True)
    
    
if __name__ == "__main__":
    get_all_actor_instance_with_same_type()