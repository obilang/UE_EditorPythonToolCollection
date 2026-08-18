import unreal

editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor_filter_lib = unreal.EditorFilterLibrary()


def _get_hlod_layer(mesh_actor: unreal.StaticMeshActor):
    # Property name can differ by engine branch/customizations.
    for property_name in ("hlod_layer", "HLODLayer"):
        try:
            return mesh_actor.get_editor_property(property_name)
        except Exception:
            continue
    return None


def _has_hlod_layer(mesh_actor: unreal.StaticMeshActor) -> bool:
    return _get_hlod_layer(mesh_actor) is not None


def find_mesh_actors_with_hlod_layer():
    all_actors = editor_actor_subsystem.get_all_level_actors()
    static_mesh_actors = editor_filter_lib.by_class(all_actors, unreal.StaticMeshActor)

    actor_by_path = {}
    for static_mesh_actor in static_mesh_actors:
        if not _has_hlod_layer(static_mesh_actor):
            continue

        actor_by_path[static_mesh_actor.get_path_name()] = static_mesh_actor

    return list(actor_by_path.values())


def select_mesh_actors_with_component_hlod_layer():
    target_actors = find_mesh_actors_with_hlod_layer()

    try:
        editor_actor_subsystem.set_selected_level_actors(target_actors)
    except Exception:
        # Fallback for branches where bulk selection API is unavailable.
        editor_actor_subsystem.clear_actor_selection_set()
        for actor in target_actors:
            editor_actor_subsystem.set_actor_selection_state(actor, True)

    unreal.log(
        "[select_mesh_actors_with_component_hlod_layer] Selected {0} StaticMeshActor(s).".format(
            len(target_actors)
        )
    )


if __name__ == "__main__":
    select_mesh_actors_with_component_hlod_layer()
