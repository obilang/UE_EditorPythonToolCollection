import unreal
import sys
from typing import List
import math

editor_actor_subsystem = unreal.EditorActorSubsystem()


def center_pivot(actor: unreal.Actor):
    editor_actor_subsystem.set_actor_selection_state(actor, False)
    bounding_box = actor.get_actor_bounds(False)
    box_center = bounding_box[0]
    box_extent = bounding_box[1]
    new_pivot = unreal.Vector(box_center.x, box_center.y, box_center.z - box_extent.z)
    transform = unreal.Transform(new_pivot)
    pivot_offset = transform.make_relative(actor.get_actor_transform())
    actor.set_editor_property("pivot_offset", pivot_offset.translation)
    editor_actor_subsystem.set_actor_selection_state(actor, True)


def reorder_actor_by_bounding_size(actors: List[unreal.Actor]):
    sorted_actors = []
    for actor in actors:
        bounding_box_size = actor.get_actor_bounds(False)[1]
        max_size = max([bounding_box_size.x, bounding_box_size.y])
        # print(approx_size)
        sorted_actors.append({'Path': actor, 'Size': max_size * 2})

    sorted_actors.sort(key=lambda x: x.get('Size'))
    
    row_count = math.floor(int(math.sqrt(len(sorted_actors)))) + 1

    index = 0
    first_item_size = 0
    for item in sorted_actors:
        row = int(index / row_count)
        column = int(math.fmod(index, row_count))

        if column == 0:
            first_item_size = item['Size']

        location = unreal.Vector(row * first_item_size, column * item['Size'], 0)
        actor = item['Path']
        pivot_offset = actor.pivot_offset
        actor.set_actor_location(location - pivot_offset, False, False)
        index = index + 1


if __name__ == "__main__":
    selected_actors = editor_actor_subsystem.get_selected_level_actors()
    operation_type = sys.argv[1]
    
    for selected_actor in selected_actors:
        if operation_type == "ForceDelete":
            editor_actor_subsystem.destroy_actor(selected_actor)
        elif operation_type == "CenterPivots":
            center_pivot(selected_actor)
            
    if operation_type == "ReOrderByBounds":
        reorder_actor_by_bounding_size(selected_actors)
