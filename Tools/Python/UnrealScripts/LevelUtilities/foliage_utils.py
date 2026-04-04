import unreal
from scipy.spatial import KDTree


editor_level_lib = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def check_overlapping_instances(trans_list):
    pos_list = []
    for trans in trans_list:
        pos = trans.translation
        pos_list.append((pos.x, pos.y, pos.z))

    kd_tree = KDTree(pos_list)
    pairs = kd_tree.query_pairs(r=0.0001)
    total_overlapping_count = len(pairs)

    return total_overlapping_count


def get_no_overlapping_pos(in_pos_list, picked_index, search_depth):
    pos_list = []
    origin_index = []

    for i in picked_index:
        pos_list.append(in_pos_list[i])
        origin_index.append(i)

    # print(pos_list)
    kd_tree = KDTree(pos_list)
    pairs = kd_tree.query_pairs(r=0.0001)
    print("pairs length: {}".format(len(pairs)))

    if len(pairs) == 0:
        return picked_index

    if search_depth >= 10:
        unreal.log_warning("Foliage overlapping check exceed max search depth")
        return

    new_picked_index = set()
    for (i, j) in pairs:
        new_picked_index.add(origin_index[i])
    new_picked_index = picked_index - new_picked_index

    print(len(new_picked_index))
    return get_no_overlapping_pos(in_pos_list, new_picked_index, search_depth + 1)


def find_overlapping_foliages(foliage_component: unreal.FoliageInstancedStaticMeshComponent):
    n_inst = foliage_component.get_instance_count()
    result = 0
    if n_inst > 0:
        trans_list = []
        for i in range(n_inst):
            trans_inst = foliage_component.get_instance_transform(i, True)
            trans_list.append(trans_inst)
        result = check_overlapping_instances(trans_list)
            
    return result