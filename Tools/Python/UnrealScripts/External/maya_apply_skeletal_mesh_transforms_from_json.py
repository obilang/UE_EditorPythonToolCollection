import json
import os

import maya.cmds as cmds

try:
    from PySide2 import QtCore, QtWidgets
except ImportError:
    from PySide6 import QtCore, QtWidgets


TOOL_VERSION = "1.0.0"


def _get_entry(data, actor_name=None):
    actors = data.get("actors", [])
    if not actors:
        raise RuntimeError("JSON has no actors data.")

    if actor_name is None:
        return actors[0]

    for actor in actors:
        if actor.get("actor_name") == actor_name:
            return actor

    raise RuntimeError("Actor '{0}' not found in JSON.".format(actor_name))


def _get_component_entry(actor_entry, component_name=None, component_index=0):
    components = actor_entry.get("skeletal_mesh_components", [])
    if not components:
        raise RuntimeError("Actor has no skeletal mesh components in JSON.")

    if component_name is not None:
        for comp in components:
            if comp.get("component_name") == component_name:
                return comp
        raise RuntimeError("Component '{0}' not found in actor data.".format(component_name))

    if component_index < 0 or component_index >= len(components):
        raise RuntimeError(
            "component_index out of range. Got {0}, available 0..{1}.".format(
                component_index,
                len(components) - 1,
            )
        )

    return components[component_index]


def _full_node_name(node_name, namespace=""):
    if not namespace:
        return node_name
    return "{0}:{1}".format(namespace, node_name)


def _resolve_scene_node(node_name, namespace="", search_scope_root=None):
    # 1) Exact path/name with optional namespace override.
    preferred_name = _full_node_name(node_name, namespace=namespace)
    if cmds.objExists(preferred_name):
        return preferred_name, None

    # 1.5) If scope root is provided, only search under this hierarchy.
    if search_scope_root and cmds.objExists(search_scope_root):
        scoped_transforms = cmds.listRelatives(
            search_scope_root,
            allDescendents=True,
            fullPath=True,
            type="transform",
        ) or []

        scoped_candidates = []
        for transform in scoped_transforms:
            short_name = transform.split("|")[-1]
            if short_name == preferred_name or short_name.endswith(":" + node_name):
                scoped_candidates.append(transform)

        if len(scoped_candidates) == 1:
            return scoped_candidates[0], None
        if len(scoped_candidates) > 1:
            return None, "ambiguous"

    # 2) If no namespace was provided, try to resolve by suffix.
    if not namespace:
        candidates = []

        ns_candidates = cmds.ls("*:{0}".format(node_name), long=True) or []
        for candidate in ns_candidates:
            if candidate not in candidates:
                candidates.append(candidate)

        path_candidates = cmds.ls("*|{0}".format(node_name), long=True) or []
        for candidate in path_candidates:
            if candidate not in candidates:
                candidates.append(candidate)

        if len(candidates) == 1:
            return candidates[0], None
        if len(candidates) > 1:
            return None, "ambiguous"

    return None, "missing"


def _convert_unreal_rotation_to_maya_euler(rotation_data):
    roll = float(rotation_data.get("roll", 0.0))
    pitch = float(rotation_data.get("pitch", 0.0))
    yaw = float(rotation_data.get("yaw", 0.0))

    # Proven mapping from manual Unreal FBX export to Maya.
    # rotation_x_unreal = rotation_x_maya
    # rotation_y_unreal = -rotation_y_maya
    # rotation_z_unreal = -rotation_z_maya
    # => maya = (roll, -pitch, -yaw)
    return roll, -pitch, -yaw


def _set_world_transform(node, transform_data, apply_scale=False):
    location = transform_data.get("location", {})
    rotation = transform_data.get("rotation", {})
    scale = transform_data.get("scale", {})

    tx = float(location.get("x", 0.0))
    # unreal_translation_y = -maya_translation_y  =>  maya_y = -unreal_y
    ty = -float(location.get("y", 0.0))
    tz = float(location.get("z", 0.0))

    rx, ry, rz = _convert_unreal_rotation_to_maya_euler(rotation)

    cmds.xform(node, ws=True, t=(tx, ty, tz))
    cmds.xform(node, ws=True, ro=(rx, ry, rz))

    if apply_scale:
        sx = float(scale.get("x", 1.0))
        sy = float(scale.get("y", 1.0))
        sz = float(scale.get("z", 1.0))
        cmds.setAttr(node + ".scale", sx, sy, sz, type="double3")


def apply_skeletal_mesh_transforms_from_json(
    json_file_path,
    actor_name=None,
    component_name=None,
    component_index=0,
    pelvis_bone_name="pelvis",
    namespace="",
    apply_scale=False,
    search_scope_root=None,
):
    if not os.path.isfile(json_file_path):
        raise RuntimeError("File not found: {0}".format(json_file_path))

    with open(json_file_path, "r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)

    actor_entry = _get_entry(data, actor_name=actor_name)
    component_entry = _get_component_entry(
        actor_entry,
        component_name=component_name,
        component_index=component_index,
    )

    missing_nodes = []
    ambiguous_nodes = []
    updated_nodes = []

    # Per request, actor transform is applied to the pelvis joint.
    pelvis_node, pelvis_reason = _resolve_scene_node(
        pelvis_bone_name,
        namespace=namespace,
        search_scope_root=search_scope_root,
    )
    if pelvis_node:
        _set_world_transform(
            pelvis_node,
            actor_entry.get("actor_transform", {}),
            apply_scale=apply_scale,
        )
        updated_nodes.append(pelvis_node)
    else:
        if pelvis_reason == "ambiguous":
            ambiguous_nodes.append(pelvis_bone_name)
        else:
            missing_nodes.append(pelvis_bone_name)

    for bone_entry in component_entry.get("bones", []):
        bone_name = bone_entry.get("bone_name")
        if not bone_name:
            continue

        if bone_name == pelvis_bone_name:
            # Keep pelvis from actor transform rather than bone transform.
            continue

        target_node, reason = _resolve_scene_node(
            bone_name,
            namespace=namespace,
            search_scope_root=search_scope_root,
        )
        if not target_node:
            if reason == "ambiguous":
                ambiguous_nodes.append(bone_name)
            else:
                missing_nodes.append(bone_name)
            continue

        _set_world_transform(
            target_node,
            bone_entry.get("transform", {}),
            apply_scale=apply_scale,
        )
        updated_nodes.append(target_node)

    print("[apply_skeletal_mesh_transforms_from_json] Updated {0} node(s).".format(len(updated_nodes)))
    if missing_nodes:
        print(
            "[apply_skeletal_mesh_transforms_from_json] Missing {0} node(s):".format(
                len(missing_nodes)
            )
        )
        for node_name in missing_nodes:
            print("  - {0}".format(node_name))
    if ambiguous_nodes:
        print(
            "[apply_skeletal_mesh_transforms_from_json] Ambiguous {0} node(s), provide namespace to disambiguate:".format(
                len(ambiguous_nodes)
            )
        )
        for node_name in ambiguous_nodes:
            print("  - {0}".format(node_name))

    return {
        "updated_nodes": updated_nodes,
        "missing_nodes": missing_nodes,
        "ambiguous_nodes": ambiguous_nodes,
        "search_scope_root": search_scope_root,
        "actor_name": actor_entry.get("actor_name"),
        "actor_path": actor_entry.get("actor_path"),
        "component_name": component_entry.get("component_name"),
    }


def _find_actor_scope_roots(actor_entry):
    actor_path = actor_entry.get("actor_path", "")
    actor_name = actor_entry.get("actor_name", "")

    matched = []

    if actor_path:
        for node in cmds.ls(type="transform", long=True) or []:
            if not cmds.attributeQuery("ue_actor_path", node=node, exists=True):
                continue
            try:
                if cmds.getAttr(node + ".ue_actor_path") == actor_path:
                    matched.append(node)
            except Exception:
                continue
        if matched:
            return matched

    if actor_name:
        for node in cmds.ls(type="transform", long=True) or []:
            if not cmds.attributeQuery("ue_actor_name", node=node, exists=True):
                continue
            try:
                if cmds.getAttr(node + ".ue_actor_name") == actor_name:
                    matched.append(node)
            except Exception:
                continue

    return matched


def apply_all_skeletal_mesh_transforms_from_json(
    json_file_path,
    pelvis_bone_name="pelvis",
    namespace="",
    apply_scale=False,
):
    data = _load_json_data(json_file_path)
    actors = data.get("actors", [])
    if not actors:
        raise RuntimeError("JSON has no actors data.")

    all_updated = []
    all_missing = []
    all_ambiguous = []
    actors_without_scope = []
    actors_applied = 0

    for actor_entry in actors:
        scope_roots = _find_actor_scope_roots(actor_entry)
        if not scope_roots:
            actors_without_scope.append(actor_entry.get("actor_name", "<unknown>"))
            continue

        if len(scope_roots) > 1:
            all_ambiguous.append("{0} (multiple actor roots)".format(actor_entry.get("actor_name", "<unknown>")))
            continue

        result = apply_skeletal_mesh_transforms_from_json(
            json_file_path=json_file_path,
            actor_name=actor_entry.get("actor_name"),
            component_name=None,
            component_index=0,
            pelvis_bone_name=pelvis_bone_name,
            namespace=namespace,
            apply_scale=apply_scale,
            search_scope_root=scope_roots[0],
        )

        all_updated.extend(result.get("updated_nodes", []))
        all_missing.extend(result.get("missing_nodes", []))
        all_ambiguous.extend(result.get("ambiguous_nodes", []))
        actors_applied += 1

    return {
        "updated_nodes": all_updated,
        "missing_nodes": all_missing,
        "ambiguous_nodes": all_ambiguous,
        "actors_applied": actors_applied,
        "actors_total": len(actors),
        "actors_without_scope": actors_without_scope,
    }


def apply_skeletal_mesh_transforms_from_json_dialog(**kwargs):
    selected = cmds.fileDialog2(
        fileMode=1,
        caption="Select Skeletal Mesh Transform JSON",
        fileFilter="JSON Files (*.json)",
    )
    if not selected:
        cmds.warning("No JSON file selected.")
        return None

    return apply_skeletal_mesh_transforms_from_json(selected[0], **kwargs)


def get_total_actor_num_from_json(json_file_path):
    if not os.path.isfile(json_file_path):
        return 0

    with open(json_file_path, "r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)

    if "actor_count" in data:
        try:
            return int(data.get("actor_count", 0))
        except Exception:
            pass

    return len(data.get("actors", []))


def _load_json_data(json_file_path):
    if not os.path.isfile(json_file_path):
        raise RuntimeError("File not found: {0}".format(json_file_path))

    with open(json_file_path, "r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def get_unique_skeletal_mesh_assets_from_json(json_file_path):
    data = _load_json_data(json_file_path)
    unique_assets = []
    seen = set()

    for actor in data.get("actors", []):
        components = actor.get("skeletal_mesh_components", [])
        for component in components:
            asset_path = component.get("skeletal_mesh_asset_path", "")
            if not asset_path or asset_path in seen:
                continue
            seen.add(asset_path)
            unique_assets.append(asset_path)

    return unique_assets


def _sanitize_name(value):
    sanitized = value.replace("|", "_").replace(":", "_").replace(" ", "_")
    sanitized = sanitized.replace("/", "_").replace("\\", "_").replace(".", "_")
    return sanitized or "item"


def _make_unique_name(base_name):
    candidate = _sanitize_name(base_name)
    if not cmds.objExists(candidate):
        return candidate

    index = 1
    while cmds.objExists("{0}_{1}".format(candidate, index)):
        index += 1
    return "{0}_{1}".format(candidate, index)


def _make_unique_namespace(base_name):
    candidate = _sanitize_name(base_name)
    if not cmds.namespace(exists=candidate):
        return candidate

    index = 1
    while cmds.namespace(exists="{0}_{1}".format(candidate, index)):
        index += 1
    return "{0}_{1}".format(candidate, index)


def _find_top_level_transforms(new_nodes):
    top_transforms = []
    for node in new_nodes:
        if cmds.nodeType(node) != "transform":
            continue
        parent = cmds.listRelatives(node, parent=True, fullPath=True)
        if parent:
            continue
        if node not in top_transforms:
            top_transforms.append(node)
    return top_transforms


def import_actors_as_referenced_fbx_instances(
    json_file_path,
    asset_to_fbx_path,
    root_group_name="UE_ActorInstances",
    apply_actor_scale=False,
):
    data = _load_json_data(json_file_path)
    actors = data.get("actors", [])
    if not actors:
        raise RuntimeError("JSON has no actors data.")

    if not cmds.objExists(root_group_name):
        root_group = cmds.group(empty=True, name=root_group_name)
    else:
        root_group = root_group_name

    reference_cache = {}
    created_actor_groups = []
    skipped_actors = []
    missing_asset_mappings = set()

    for actor in actors:
        components = actor.get("skeletal_mesh_components", [])
        if not components:
            skipped_actors.append(actor.get("actor_name", "<unknown>"))
            continue

        component = components[0]
        asset_path = component.get("skeletal_mesh_asset_path", "")
        if not asset_path:
            skipped_actors.append(actor.get("actor_name", "<unknown>"))
            continue

        fbx_path = asset_to_fbx_path.get(asset_path, "").strip()
        if not fbx_path:
            missing_asset_mappings.add(asset_path)
            skipped_actors.append(actor.get("actor_name", "<unknown>"))
            continue
        if not os.path.isfile(fbx_path):
            raise RuntimeError("FBX file not found for asset '{0}': {1}".format(asset_path, fbx_path))

        if asset_path not in reference_cache:
            namespace = _make_unique_namespace(asset_path.split("/")[-1])
            new_nodes = cmds.file(
                fbx_path,
                reference=True,
                namespace=namespace,
                returnNewNodes=True,
            )

            top_transforms = _find_top_level_transforms(new_nodes)
            if not top_transforms:
                top_transforms = cmds.ls(namespace + ":*", assemblies=True, long=True) or []
            if not top_transforms:
                raise RuntimeError("Could not find top-level transforms in reference: {0}".format(fbx_path))

            reference_cache[asset_path] = {
                "namespace": namespace,
                "top_transforms": top_transforms,
            }

        actor_name = actor.get("actor_name", "UEActor")
        actor_group_name = _make_unique_name("{0}_grp".format(actor_name))
        actor_group = cmds.group(empty=True, name=actor_group_name)
        cmds.parent(actor_group, root_group)

        if not cmds.attributeQuery("ue_actor_name", node=actor_group, exists=True):
            cmds.addAttr(actor_group, longName="ue_actor_name", dataType="string")
        if not cmds.attributeQuery("ue_actor_path", node=actor_group, exists=True):
            cmds.addAttr(actor_group, longName="ue_actor_path", dataType="string")
        if not cmds.attributeQuery("ue_skeletal_mesh_asset_path", node=actor_group, exists=True):
            cmds.addAttr(actor_group, longName="ue_skeletal_mesh_asset_path", dataType="string")

        cmds.setAttr(actor_group + ".ue_actor_name", actor_name, type="string")
        cmds.setAttr(actor_group + ".ue_actor_path", actor.get("actor_path", ""), type="string")
        cmds.setAttr(actor_group + ".ue_skeletal_mesh_asset_path", asset_path, type="string")

        for top_transform in reference_cache[asset_path]["top_transforms"]:
            instance_name = _make_unique_name("{0}_inst".format(top_transform.split("|")[-1]))
            instanced = cmds.instance(top_transform, name=instance_name)
            if not instanced:
                continue
            cmds.parent(instanced[0], actor_group)

        _set_world_transform(
            actor_group,
            actor.get("actor_transform", {}),
            apply_scale=apply_actor_scale,
        )
        created_actor_groups.append(actor_group)

    if created_actor_groups:
        cmds.select(created_actor_groups, replace=True)

    return {
        "created_actor_groups": created_actor_groups,
        "skipped_actors": skipped_actors,
        "missing_asset_mappings": sorted(list(missing_asset_mappings)),
    }


def _get_selected_mesh_transforms():
    selected_transforms = cmds.ls(selection=True, long=True, type="transform") or []
    mesh_transforms = []
    for transform in selected_transforms:
        mesh_shapes = cmds.listRelatives(transform, shapes=True, noIntermediate=True, type="mesh") or []
        if mesh_shapes:
            mesh_transforms.append(transform)
    return mesh_transforms


def create_static_mesh_from_current_pose(target_mesh_transforms=None, suffix="_static"):
    mesh_transforms = target_mesh_transforms or _get_selected_mesh_transforms()
    if not mesh_transforms:
        raise RuntimeError("Select at least one skinned mesh transform.")

    created_meshes = []
    for mesh_transform in mesh_transforms:
        base_name = mesh_transform.split("|")[-1]
        new_name = "{0}{1}".format(base_name, suffix)

        # Duplicate preserves evaluated (current) deformation. Deleting history bakes it into static mesh.
        duplicated = cmds.duplicate(mesh_transform, rr=True, name=new_name)
        if not duplicated:
            continue

        duplicated_transform = duplicated[0]
        cmds.delete(duplicated_transform, ch=True)
        created_meshes.append(duplicated_transform)

    if created_meshes:
        cmds.select(created_meshes, replace=True)

    return created_meshes


def import_and_convert_actors_to_static_meshes(
    json_file_path,
    asset_to_fbx_path,
    pelvis_bone_name="root",
    root_group_name="UE_StaticMeshes",
    apply_actor_scale=False,
):
    """
    Simplified workflow: For each actor in JSON:
    1. Import FBX (regular import, not reference)
    2. Apply bone transforms from JSON
    3. Duplicate mesh and delete history to create static mesh
    4. Delete skeleton/joints
    5. Keep only the static mesh properly named
    
    Returns dict with:
        - created_meshes: list of static mesh transform node names
        - skipped_actors: list of actor names that were skipped
    """
    with open(json_file_path, "r") as file:
        data = json.load(file)

    actors = data.get("actors", [])
    if not actors:
        raise RuntimeError("JSON has no actors data.")

    # Create root group for all static meshes
    root_group = None
    if cmds.objExists(root_group_name):
        root_group = root_group_name
    else:
        root_group = cmds.group(empty=True, name=root_group_name)

    created_meshes = []
    skipped_actors = []

    for actor in actors:
        actor_name = actor.get("actor_name", "UnnamedActor")
        actor_transform = actor.get("actor_transform", {})
        components = actor.get("skeletal_mesh_components", [])

        if not components:
            print("[import_and_convert] Actor '{0}' has no skeletal mesh components, skipping.".format(actor_name))
            skipped_actors.append(actor_name)
            continue

        # Use first component (typically there's one per actor)
        component = components[0]
        skeletal_mesh_asset_path = component.get("skeletal_mesh_asset_path", "")

        if not skeletal_mesh_asset_path:
            print("[import_and_convert] Actor '{0}' has no skeletal_mesh_asset_path, skipping.".format(actor_name))
            skipped_actors.append(actor_name)
            continue

        fbx_path = asset_to_fbx_path.get(skeletal_mesh_asset_path)
        if not fbx_path or not os.path.isfile(fbx_path):
            print("[import_and_convert] Actor '{0}': FBX path not mapped or file not found, skipping.".format(actor_name))
            skipped_actors.append(actor_name)
            continue

        print("[import_and_convert] Processing actor '{0}' with FBX: {1}".format(actor_name, fbx_path))

        # Step 1: Import FBX (regular import)
        before_import = set(cmds.ls(assemblies=True) or [])
        try:
            cmds.file(fbx_path, i=True, type="FBX", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=actor_name)
        except Exception as e:
            print("[import_and_convert] Failed to import FBX for actor '{0}': {1}".format(actor_name, e))
            skipped_actors.append(actor_name)
            continue
        
        after_import = set(cmds.ls(assemblies=True) or [])
        new_nodes = list(after_import - before_import)

        if not new_nodes:
            print("[import_and_convert] No new nodes created after FBX import for '{0}', skipping.".format(actor_name))
            skipped_actors.append(actor_name)
            continue

        # FBX may import multiple hierarchies (e.g., skeleton and mesh groups)
        # Track all imported root nodes
        print("[import_and_convert] Imported {0} root nodes: {1}".format(len(new_nodes), new_nodes))
        
        # Find the skeleton root (usually named 'root' or has joints underneath)
        fbx_root = None
        for node in new_nodes:
            # Check if this node or its children contain joints
            descendants = cmds.listRelatives(node, allDescendents=True, type="joint", fullPath=True) or []
            if descendants:
                fbx_root = node
                print("[import_and_convert] Skeleton root: {0}".format(fbx_root))
                break
        
        # Fallback to first node if no skeleton found
        if not fbx_root:
            fbx_root = new_nodes[0]
            print("[import_and_convert] No skeleton found, using first root: {0}".format(fbx_root))

        # Step 2: Apply bone transforms from JSON
        # Build a lookup of all joints/transforms under the skeleton hierarchy
        all_descendants = cmds.listRelatives(fbx_root, allDescendents=True, fullPath=True) or []
        
        # Debug: print how many descendants found
        print("[import_and_convert] Found {0} descendant nodes under FBX root.".format(len(all_descendants)))
        
        bone_name_to_node = {}
        for node in all_descendants:
            node_type = cmds.nodeType(node)
            if node_type in ["joint", "transform"]:
                # Get short name (without path and namespace)
                short_name = node.split("|")[-1].split(":")[-1]
                # Store full path for this bone name
                if short_name not in bone_name_to_node:
                    bone_name_to_node[short_name] = node

        print("[import_and_convert] Built bone lookup with {0} entries.".format(len(bone_name_to_node)))

        bones = component.get("bones", [])
        applied_count = 0
        for bone_data in bones:
            bone_name = bone_data.get("bone_name", "")
            if not bone_name:
                continue  # Skip empty bone names

            # Look up bone in our hierarchy
            bone_node = bone_name_to_node.get(bone_name)
            if not bone_node:
                continue

            try:
                _set_world_transform(bone_node, bone_data.get('transform', {}), apply_scale=apply_actor_scale)
                applied_count += 1
            except Exception as e:
                print("[import_and_convert] Failed to set transform for bone '{0}': {1}".format(bone_name, e))

        print("[import_and_convert] Applied transforms to {0} bones for actor '{1}'.".format(applied_count, actor_name))
        # If no bones were applied (static mesh FBX), apply actor transform to root instead
        if applied_count == 0 and cmds.objExists(fbx_root):
            print("[import_and_convert] No bones found, applying actor transform to FBX root: {0}".format(fbx_root))
            try:
                _set_world_transform(fbx_root, actor_transform, apply_scale=apply_actor_scale)
                print("[import_and_convert] Applied actor transform to root successfully.")
            except Exception as e:
                print("[import_and_convert] Failed to apply actor transform to root: {0}".format(e))

        # Step 3: Find mesh and create static mesh
        # Search for meshes across ALL imported root nodes (not just skeleton root)
        all_mesh_transforms = []
        for imported_root in new_nodes:
            # Check the root itself
            shapes = cmds.listRelatives(imported_root, shapes=True, noIntermediate=True, fullPath=True) or []
            for shape in shapes:
                if cmds.nodeType(shape) == "mesh":
                    all_mesh_transforms.append(imported_root)
                    break
            
            # Check all descendants
            descendants = cmds.listRelatives(imported_root, allDescendents=True, fullPath=True) or []
            for node in descendants:
                node_type = cmds.nodeType(node)
                if node_type == "transform":
                    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True, fullPath=True) or []
                    for shape in shapes:
                        if cmds.nodeType(shape) == "mesh":
                            all_mesh_transforms.append(node)
                            break
        
        print("[import_and_convert] Found {0} mesh transforms.".format(len(all_mesh_transforms)))

        # Prioritize skinned meshes, fall back to any mesh
        skinned_meshes = []
        for mesh_transform in all_mesh_transforms:
            shapes = cmds.listRelatives(mesh_transform, shapes=True, noIntermediate=True, fullPath=True) or []
            for shape in shapes:
                if cmds.nodeType(shape) == "mesh":
                    history = cmds.listHistory(shape, pruneDagObjects=True) or []
                    if any(cmds.nodeType(node) == "skinCluster" for node in history):
                        skinned_meshes.append(mesh_transform)
                        break

        target_mesh = None
        if skinned_meshes:
            target_mesh = skinned_meshes[0]
            print("[import_and_convert] Found skinned mesh: {0}".format(target_mesh))
        elif all_mesh_transforms:
            target_mesh = all_mesh_transforms[0]
            print("[import_and_convert] Found static mesh (no skin): {0}".format(target_mesh))

        if not target_mesh:
            print("[import_and_convert] No meshes found for actor '{0}', keeping FBX hierarchy as-is.".format(actor_name))
            # Just parent first imported node to our group
            if new_nodes and cmds.objExists(new_nodes[0]):
                try:
                    cmds.parent(new_nodes[0], root_group)
                    created_meshes.append(new_nodes[0])
                except:
                    pass
            continue

        # Duplicate mesh preserving current pose and create static mesh
        static_mesh_name = "{0}_static".format(actor_name)
        try:
            duplicated = cmds.duplicate(target_mesh, rr=True, name=static_mesh_name)
            if not duplicated:
                print("[import_and_convert] Failed to duplicate mesh for actor '{0}'.".format(actor_name))
                skipped_actors.append(actor_name)
                continue

            static_mesh_transform = duplicated[0]
            
            # Delete history to bake deformation and remove skin cluster
            cmds.delete(static_mesh_transform, ch=True)
            
            # Parent to root group
            cmds.parent(static_mesh_transform, root_group)
            
            created_meshes.append(static_mesh_transform)
            print("[import_and_convert] Created static mesh: {0}".format(static_mesh_transform))

        except Exception as e:
            print("[import_and_convert] Failed to create static mesh for actor '{0}': {1}".format(actor_name, e))
            skipped_actors.append(actor_name)
            continue

        # Step 4: Delete ALL original imported FBX hierarchies (skeleton, meshes, etc.)
        for imported_node in new_nodes:
            try:
                if cmds.objExists(imported_node):
                    cmds.delete(imported_node)
            except Exception as e:
                print("[import_and_convert] Failed to delete imported node '{0}': {1}".format(imported_node, e))
        
        print("[import_and_convert] Deleted {0} imported FBX hierarchies for actor '{1}'.".format(len(new_nodes), actor_name))

    print("[import_and_convert] Summary: Created {0} static meshes, skipped {1} actors.".format(
        len(created_meshes), len(skipped_actors)))

    return {
        "created_meshes": created_meshes,
        "skipped_actors": skipped_actors,
        "root_group": root_group,
    }


class ApplySkeletalMeshTransformsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(ApplySkeletalMeshTransformsDialog, self).__init__(parent)
        self.setWindowTitle("Apply UE Skeletal Transform JSON v{0}".format(TOOL_VERSION))
        self.setMinimumWidth(800)
        self.setMinimumHeight(700)
        self._build_ui()

    def _build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        path_layout = QtWidgets.QHBoxLayout()
        path_label = QtWidgets.QLabel("JSON File")
        self.json_path_edit = QtWidgets.QLineEdit()
        self.json_path_edit.setPlaceholderText("Select exported JSON file...")
        browse_btn = QtWidgets.QPushButton("Browse")
        browse_btn.clicked.connect(self._on_browse)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.json_path_edit)
        path_layout.addWidget(browse_btn)
        main_layout.addLayout(path_layout)

        form_layout = QtWidgets.QFormLayout()
        self.total_actor_num_label = QtWidgets.QLabel("0")
        form_layout.addRow("Total Actor Num", self.total_actor_num_label)

        self.pelvis_bone_edit = QtWidgets.QLineEdit("root")
        form_layout.addRow("Pelvis Bone", self.pelvis_bone_edit)

        self.namespace_edit = QtWidgets.QLineEdit()
        self.namespace_edit.setPlaceholderText("Optional namespace, e.g. CHR_Rig")
        form_layout.addRow("Namespace", self.namespace_edit)

        self.apply_scale_checkbox = QtWidgets.QCheckBox("Apply Scale")
        self.apply_scale_checkbox.setChecked(False)
        form_layout.addRow("", self.apply_scale_checkbox)

        # main_layout.addLayout(form_layout)

        mapping_group = QtWidgets.QGroupBox("FBX Mapping Per Skeletal Mesh Asset")
        mapping_layout = QtWidgets.QVBoxLayout(mapping_group)
        self.asset_mapping_scroll = QtWidgets.QScrollArea()
        self.asset_mapping_scroll.setWidgetResizable(True)
        self.asset_mapping_widget = QtWidgets.QWidget()
        self.asset_mapping_rows_layout = QtWidgets.QVBoxLayout(self.asset_mapping_widget)
        self.asset_mapping_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.asset_mapping_scroll.setWidget(self.asset_mapping_widget)
        mapping_layout.addWidget(self.asset_mapping_scroll)
        main_layout.addWidget(mapping_group)

        self.asset_path_to_edit = {}

        self.result_label = QtWidgets.QLabel("")
        self.result_label.setWordWrap(True)
        main_layout.addWidget(self.result_label)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch(1)
        import_convert_btn = QtWidgets.QPushButton("Import & Convert to Static")
        import_convert_btn.clicked.connect(self._on_import_and_convert)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(import_convert_btn)
        button_layout.addWidget(close_btn)
        main_layout.addLayout(button_layout)

    def _clear_asset_mapping_rows(self):
        while self.asset_mapping_rows_layout.count():
            item = self.asset_mapping_rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _browse_fbx_for_edit(self, line_edit):
        selected_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select FBX File",
            "",
            "FBX Files (*.fbx)",
        )
        if selected_path:
            line_edit.setText(selected_path)

    def _rebuild_asset_mapping_ui(self, json_path):
        self._clear_asset_mapping_rows()
        self.asset_path_to_edit = {}

        try:
            asset_paths = get_unique_skeletal_mesh_assets_from_json(json_path)
        except Exception as error:
            info_label = QtWidgets.QLabel("Failed to read asset paths: {0}".format(error))
            info_label.setWordWrap(True)
            self.asset_mapping_rows_layout.addWidget(info_label)
            return

        if not asset_paths:
            info_label = QtWidgets.QLabel("No skeletal mesh asset paths found in JSON.")
            self.asset_mapping_rows_layout.addWidget(info_label)
            return

        for asset_path in asset_paths:
            row_widget = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)

            asset_label = QtWidgets.QLabel(asset_path)
            asset_label.setMinimumWidth(280)
            asset_label.setWordWrap(True)

            fbx_edit = QtWidgets.QLineEdit()
            fbx_edit.setPlaceholderText("Set FBX path for this skeletal mesh asset")

            browse_btn = QtWidgets.QPushButton("Browse")
            browse_btn.clicked.connect(lambda _=False, edit=fbx_edit: self._browse_fbx_for_edit(edit))

            row_layout.addWidget(asset_label)
            row_layout.addWidget(fbx_edit)
            row_layout.addWidget(browse_btn)
            self.asset_mapping_rows_layout.addWidget(row_widget)

            self.asset_path_to_edit[asset_path] = fbx_edit

        self.asset_mapping_rows_layout.addStretch(1)

    def _on_browse(self):
        selected_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Skeletal Mesh Transform JSON",
            "",
            "JSON Files (*.json)",
        )
        if selected_path:
            self.json_path_edit.setText(selected_path)
            self.total_actor_num_label.setText(str(get_total_actor_num_from_json(selected_path)))
            self._rebuild_asset_mapping_ui(selected_path)

    def _on_apply(self):
        json_path = self.json_path_edit.text().strip()
        pelvis_bone_name = self.pelvis_bone_edit.text().strip() or "root"
        namespace = self.namespace_edit.text().strip()
        apply_scale = self.apply_scale_checkbox.isChecked()

        if not json_path:
            QtWidgets.QMessageBox.warning(self, "Missing File", "Please select a JSON file.")
            return

        try:
            result = apply_all_skeletal_mesh_transforms_from_json(
                json_file_path=json_path,
                pelvis_bone_name=pelvis_bone_name,
                namespace=namespace,
                apply_scale=apply_scale,
            )
        except Exception as error:
            QtWidgets.QMessageBox.critical(self, "Apply Failed", str(error))
            self.result_label.setText("Failed: {0}".format(error))
            return

        self.result_label.setText(
            "Applied to {0} node(s). Missing {1} node(s). Ambiguous {2} node(s). Actors Applied: {3}/{4}. Actors Without Scope: {5}. Total Actor Num: {6}".format(
                len(result.get("updated_nodes", [])),
                len(result.get("missing_nodes", [])),
                len(result.get("ambiguous_nodes", [])),
                result.get("actors_applied", 0),
                result.get("actors_total", 0),
                len(result.get("actors_without_scope", [])),
                get_total_actor_num_from_json(json_path),
            )
        )
        print("[maya_apply_skeletal_mesh_transforms_from_json] UI Apply used apply_all path. version={0}".format(TOOL_VERSION))

    def _on_import_and_convert(self):
        json_path = self.json_path_edit.text().strip()
        pelvis_bone_name = self.pelvis_bone_edit.text().strip() or "root"
        
        if not json_path:
            QtWidgets.QMessageBox.warning(self, "Missing File", "Please select a JSON file.")
            return

        if not self.asset_path_to_edit:
            self._rebuild_asset_mapping_ui(json_path)

        missing_fbx = []
        asset_to_fbx_path = {}
        for asset_path, path_edit in self.asset_path_to_edit.items():
            fbx_path = path_edit.text().strip()
            if not fbx_path:
                missing_fbx.append(asset_path)
                continue
            asset_to_fbx_path[asset_path] = fbx_path

        if missing_fbx:
            QtWidgets.QMessageBox.warning(
                self,
                "Missing FBX Mapping",
                "Set FBX path for all skeletal mesh assets before import.\nMissing: {0}".format(
                    "\n".join(missing_fbx)
                ),
            )
            return

        try:
            result = import_and_convert_actors_to_static_meshes(
                json_file_path=json_path,
                asset_to_fbx_path=asset_to_fbx_path,
                pelvis_bone_name=pelvis_bone_name,
                root_group_name="UE_StaticMeshes",
                apply_actor_scale=self.apply_scale_checkbox.isChecked(),
            )
        except Exception as error:
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(self, "Import & Convert Failed", str(error))
            self.result_label.setText("Failed: {0}".format(error))
            return

        self.result_label.setText(
            "Created {0} static mesh(es). Skipped {1} actor(s). Version: {2}".format(
                len(result.get("created_meshes", [])),
                len(result.get("skipped_actors", [])),
                TOOL_VERSION,
            )
        )
        print("[maya_apply_skeletal_mesh_transforms_from_json] Import & Convert completed. version={0}".format(TOOL_VERSION))


_APPLY_SKELETAL_TRANSFORM_UI = None


def show_apply_skeletal_mesh_transforms_qt_ui():
    global _APPLY_SKELETAL_TRANSFORM_UI

    try:
        if _APPLY_SKELETAL_TRANSFORM_UI is not None:
            _APPLY_SKELETAL_TRANSFORM_UI.close()
            _APPLY_SKELETAL_TRANSFORM_UI.deleteLater()
    except Exception:
        pass

    _APPLY_SKELETAL_TRANSFORM_UI = ApplySkeletalMeshTransformsDialog()
    _APPLY_SKELETAL_TRANSFORM_UI.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, False)
    _APPLY_SKELETAL_TRANSFORM_UI.show()
    _APPLY_SKELETAL_TRANSFORM_UI.raise_()
    _APPLY_SKELETAL_TRANSFORM_UI.activateWindow()


if __name__ == "__main__":
    show_apply_skeletal_mesh_transforms_qt_ui()