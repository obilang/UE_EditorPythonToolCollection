import unreal


def find_level_instances_in_current_level():
    """
    Find all LevelInstance actors in the current level and print their world asset paths.
    """
    editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    all_actors = editor_actor_subsystem.get_all_level_actors()

    level_instances = [actor for actor in all_actors if isinstance(actor, unreal.LevelInstance)]

    if not level_instances:
        print("No LevelInstance actors found in the current level.")
        return

    path_counts = {}
    for li in level_instances:
        world_asset = li.get_editor_property("world_asset")
        if world_asset is not None:
            path = world_asset.get_package().get_path_name()
        else:
            path = "<no world asset>"
        path_counts[path] = path_counts.get(path, 0) + 1

    print(f"Found {len(level_instances)} LevelInstance actor(s), {len(path_counts)} unique path(s):")
    for path, count in sorted(path_counts.items()):
        print(f"  {path} [{count}]")


if __name__ == "__main__":
    find_level_instances_in_current_level()
