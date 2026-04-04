import unreal
from typing import List
from typing import Dict
from typing import Set

asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
editor_asset_subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    

def object_path_to_package_path(object_path: str):
    if "'" in object_path:
        object_path = object_path[object_path.index("'") + 1: len(object_path) - 1]
    return object_path.split('.', 1)[0]


def package_path_to_object_path(package_path: str):
    return "{}.{}".format(package_path, package_path[package_path.rfind('/') + 1:])


def get_asset_data_from_obj(obj):
    asset = editor_asset_subsystem.find_asset_data(obj.get_package().get_path_name())
    return asset


def get_assets_data_in_folder_by_class(search_folder, unreal_static_class) -> Dict[unreal.AssetData, List[str]]:
    """
    :param search_folder: 
    :param unreal_static_class: exp.unreal.StaticMesh.static_class()
    :return: 
    """
    filtered_assets_data = asset_registry.get_assets_by_path(search_folder, True)
    filter = unreal.ARFilter()
    filter.class_paths.append(unreal.BlueprintLibrary.get_class_path_name(unreal_static_class))
    filtered_assets_data = asset_registry.run_assets_through_filter(filtered_assets_data, filter)
    
    return filtered_assets_data


def get_asset_referencers_recursively(asset_path, already_checked_assets: Set, search_end_class=[], search_depth=20, max_depth=20):
    if asset_path in already_checked_assets:
        return set()
    already_checked_assets.add(asset_path)
    
    all_referencers = set(editor_asset_subsystem.find_package_referencers_for_asset(asset_path))
    referencers = set()
    end_referencers = set()
    for ref in all_referencers:
        # if str(ref).startswith("/Script/") and not str(ref).startswith("/Engine/"):
        #     continue
        if get_asset_data_class(ref) in search_end_class:
            end_referencers.add(ref)
            continue
        referencers.add(ref)
    
    if len(referencers) <= 0:
        return end_referencers
    
    if search_depth > 0:
        child_referencers = set()
        for referencer in referencers:
            recursive_referencers = get_asset_referencers_recursively(referencer, already_checked_assets, search_end_class, search_depth - 1, max_depth)
            child_referencers.update(recursive_referencers)
        referencers.update(child_referencers)
    else:
        if max_depth != 0:
            pass
            # unreal.log_warning("Exceed max search depth when finding asset referencers. Last: {}".format(asset_path))
    
    referencers.update(end_referencers)
    return referencers


def get_asset_dependencies_recursively(asset_path, already_checked_assets: Set, search_end_class=[], search_depth=20, max_depth=20):
    if asset_path in already_checked_assets:
        return set()
    already_checked_assets.add(asset_path)

    option = unreal.AssetRegistryDependencyOptions()
    option.include_soft_package_references = False
    all_dependencies = set(asset_registry.get_dependencies(asset_path, option))
    dependencies = set()
    for dep in all_dependencies:
        if str(dep).startswith("/Script/") and not str(dep).startswith("/Engine/"):
            continue
        if get_asset_data_class(dep) in search_end_class:
            continue
        dependencies.add(dep)

    if len(dependencies) <= 0:
        return set()

    if search_depth > 0:
        child_dependencies = set()
        for referencer in dependencies:
            recursive_dependencies = get_asset_dependencies_recursively(referencer, already_checked_assets, search_end_class,
                                                                      search_depth - 1, max_depth)
            child_dependencies.update(recursive_dependencies)
        dependencies.update(child_dependencies)
    else:
        if max_depth != 0:
            pass
            # unreal.log_warning("Exceed max search depth when finding asset dependencies. Last: {}".format(asset_path))

    return dependencies
    

def get_assets_ref_by(search_folder, ref_asset_list: List[str], search_depth=-1, filter_class=None) -> Dict[unreal.AssetData, Set[str]]:
    with unreal.ScopedSlowTask(1, "Finding Assets in {}:".format(search_folder)) as slow_task:
        slow_task.make_dialog(True)
        if filter_class is None:
            asset_data_list = asset_registry.get_assets_by_path(search_folder, True)
        else:
            asset_data_list = get_assets_data_in_folder_by_class(search_folder, filter_class)
    
    result_dir = {}
    
    with unreal.ScopedSlowTask(len(asset_data_list), "Search referencers for assets") as slow_task:
        # display the dialog
        slow_task.make_dialog(True)
        for asset_data in asset_data_list:
            if slow_task.should_cancel():
                break
            slow_task.enter_progress_frame(1, asset_data.package_name)
            
            all_refs = get_asset_ref_by(asset_data.package_name, ref_asset_list, search_depth)
    
            if len(all_refs) > 0:
                result_dir[asset_data] = all_refs
    return result_dir


def get_asset_ref_by(asset_path, ref_asset_list: List[str], search_depth=-1, search_end_class=[]) -> Set[str]:
    """
    
    :param asset_path: 
    :param ref_asset_list: 
    :param search_depth: value -1 means get all chained referencers(has a default max depth).
                         value 0 means only get referencers directly reference to this asset
                         value >= 1 
    :return: 
    """
    
    search_end_class_name = []
    for search_class in search_end_class:
        search_end_class_name.append(unreal.BlueprintLibrary.get_class_path_name(search_class).asset_name)
    
    already_checked_assets = set()
    if search_depth == -1:
        refs = get_asset_referencers_recursively(asset_path, already_checked_assets, search_end_class_name)
    else:
        refs = get_asset_referencers_recursively(asset_path, already_checked_assets, search_end_class_name, search_depth, search_depth)

    all_refs = set()
    if len(refs) > 0:
        for r in refs:
            for ref_asset in ref_asset_list:
                if ref_asset == r:
                    all_refs.add(str(r))
                    break

    return all_refs


def get_assets_depend_on(asset_path, search_depth=-1, filter_class=None, search_end_class=[]) -> Set[str]:
    if filter_class is not None:
        filter_class_name = unreal.BlueprintLibrary.get_class_path_name(filter_class).asset_name
    search_end_class_name = []
    for search_class in search_end_class:
        search_end_class_name.append(unreal.BlueprintLibrary.get_class_path_name(search_class).asset_name)
        
    already_checked_assets = set()
    if search_depth == -1:
        depends = get_asset_dependencies_recursively(asset_path, already_checked_assets, search_end_class_name)
    else:
        depends = get_asset_dependencies_recursively(asset_path, already_checked_assets, search_end_class_name, search_depth, search_depth)

    all_depends = set()
    if len(depends) > 0:
        for d in depends:
            if filter_class is not None:
                if get_asset_data_class(d) == filter_class_name:
                    all_depends.add(d)
            else:
                all_depends.add(d)
    
    return all_depends


def get_base_material(material_instance_data):
    parent = material_instance_data.get_tag_value("parent")
    if parent is None or str(parent) == "None":
        return None

    parent = object_path_to_package_path(parent)
    if parent is None or str(parent) == "None" or not editor_asset_subsystem.does_asset_exist(parent):
        return None

    parent_data = editor_asset_subsystem.find_asset_data(parent)
    if parent_data.asset_class_path.asset_name == "Material":
        return parent_data
    else:
        return get_base_material(parent_data)


def get_texture_in_game_size(texture: unreal.Texture):
    x = texture.blueprint_get_size_x()
    y = texture.blueprint_get_size_y()
    max_size = max(x, y)
    lod_bias = texture.lod_bias
    max_in_game_size = max_size / pow(2, lod_bias)
    return int(max_in_game_size)


def get_texture_in_game_width(texture: unreal.Texture):
    x = texture.blueprint_get_size_x()
    lod_bias = texture.lod_bias
    max_in_game_size = x / pow(2, lod_bias)
    return int(max_in_game_size)


def get_texture_in_game_height(texture: unreal.Texture):
    y = texture.blueprint_get_size_y()
    lod_bias = texture.lod_bias
    max_in_game_size = y / pow(2, lod_bias)
    return int(max_in_game_size)


def get_texture_approximate_memory_size(texture: unreal.Texture):
    BC1_2K_MEMORY_SIZE_KB = 2731

    base_line_size = BC1_2K_MEMORY_SIZE_KB
    if texture.compression_settings == unreal.TextureCompressionSettings.TC_NORMALMAP:
        base_line_size = base_line_size * 2

    x = texture.blueprint_get_size_x()
    y = texture.blueprint_get_size_y()
    max_size = max(x, y)
    lod_bias = texture.lod_bias
    max_in_game_size = max_size / pow(2, lod_bias)

    approximate_memory_size = pow(max_in_game_size, 2) / pow(2048, 2) * base_line_size
    return approximate_memory_size


def get_asset_data_class(asset_path):
    asset_data = editor_asset_subsystem.find_asset_data(asset_path)
    return asset_data.asset_class_path.asset_name


def mesh_has_simple_collision(mesh: unreal.StaticMesh):
    body = mesh.get_editor_property('body_setup')
    
    collision_trace = body.get_editor_property('collision_trace_flag')
    if collision_trace == unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE:
        return True
    
    agg_geom = body.get_editor_property("agg_geom")
    for geo_type in ["box_elems", "convex_elems", "level_set_elems", "sphere_elems", "sphyl_elems", "tapered_capsule_elems"]:
        elems = agg_geom.get_editor_property(geo_type)
        if len(elems) > 0:
            return True
    return False


def get_all_game_maps():
    all_maps = []
    level_relation_data = unreal.LevelRelationData.create_level_relation_data()
    if not level_relation_data:
        unreal.log_warning("cannot find level relation data")
        return all_maps

    level_relation_data.load_data()
    for maps in level_relation_data.get_editor_property("all_level_data").values():
        for map in maps.remaster_level_list:
            all_maps.append(map.path)
    return all_maps


def get_all_cs_maps():
    all_maps = []

    cutscene_data = unreal.CutsceneDataAsset.create_cutscene_data_asset()
    if not cutscene_data:
        unreal.log_warning("can not find cutscene relation data")
        return all_maps
    
    cutscene_data.load_data()
    for entrie in cutscene_data.get_editor_property("cutscene_entries").values():
        for cs_entrie in entrie.entries:
            for map in cs_entrie.maps_path:
                all_maps.append(map)
    return all_maps


def get_blueprint_asset_components(bp_asset: unreal.AssetData):
    bp_cdo_path = "{}.{}_c".format(bp_asset.package_name, bp_asset.asset_name)
    bp_obj = unreal.load_object(None, bp_cdo_path)
    bp_cdo = unreal.get_default_object(bp_obj)
    components = unreal.PythonFunctionLibrary.get_cdo_node_components(bp_cdo)
    return components