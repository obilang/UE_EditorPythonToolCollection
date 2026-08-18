import datetime
import json
import os
import sys

import unreal


editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _vector_to_dict(vector: unreal.Vector) -> dict:
    return {
        "x": float(vector.x),
        "y": float(vector.y),
        "z": float(vector.z),
    }


def _rotator_to_dict(rotator: unreal.Rotator) -> dict:
    return {
        "roll": float(rotator.roll),
        "pitch": float(rotator.pitch),
        "yaw": float(rotator.yaw),
    }


def _transform_to_dict(transform: unreal.Transform) -> dict:
    return {
        "location": _vector_to_dict(transform.translation),
        "rotation": _rotator_to_dict(transform.rotation.rotator()),
        "scale": _vector_to_dict(transform.scale3d),
    }


def _resolve_output_path(cli_output_path: str | None) -> str:
    if cli_output_path:
        if os.path.isabs(cli_output_path):
            output_path = cli_output_path
        else:
            output_path = os.path.join(unreal.Paths.project_saved_dir(), cli_output_path)

        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        return os.path.normpath(output_path)

    export_dir = os.path.join(unreal.Paths.project_saved_dir(), "PythonExports")
    os.makedirs(export_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = "selected_skeletal_mesh_bone_transforms_{0}.json".format(timestamp)
    return os.path.normpath(os.path.join(export_dir, file_name))


def _is_in_play_mode() -> bool:
    try:
        return len(unreal.EditorLevelLibrary.get_pie_worlds(False)) > 0
    except Exception:
        return False


def _get_selected_actors() -> list[unreal.Actor]:
    # EditorActorSubsystem selection APIs exclude PIE actors; use EditorUtilityLibrary while in play mode.
    if _is_in_play_mode():
        try:
            return list(unreal.EditorUtilityLibrary.get_selection_set())
        except Exception:
            return []

    try:
        return list(editor_actor_subsystem.get_selected_level_actors())
    except Exception:
        try:
            return list(unreal.EditorUtilityLibrary.get_selection_set())
        except Exception:
            return []


def _get_skeletal_mesh_components(actor: unreal.Actor) -> list[unreal.SkeletalMeshComponent]:
    if isinstance(actor, unreal.SkeletalMeshActor):
        return [actor.skeletal_mesh_component]

    try:
        return list(actor.get_components_by_class(unreal.SkeletalMeshComponent))
    except Exception:
        return []


def _get_skeletal_mesh_asset_path(sk_comp: unreal.SkeletalMeshComponent) -> str:
    try:
        skinned_asset = sk_comp.get_skinned_asset()
        if skinned_asset:
            return skinned_asset.get_path_name()
    except Exception:
        pass

    for property_name in ("skinned_asset", "skeletal_mesh"):
        try:
            asset = sk_comp.get_editor_property(property_name)
            if asset:
                return asset.get_path_name()
        except Exception:
            continue

    return ""


def _collect_component_bone_data(sk_comp: unreal.SkeletalMeshComponent) -> dict:
    bone_data = []

    bone_count = sk_comp.get_num_bones()
    for bone_index in range(bone_count):
        bone_name = sk_comp.get_bone_name(bone_index)
        bone_transform = sk_comp.get_bone_transform(
            bone_name,
            unreal.RelativeTransformSpace.RTS_WORLD,
        )
        bone_data.append(
            {
                "bone_name": str(bone_name),
                "transform": _transform_to_dict(bone_transform),
            }
        )

    return {
        "component_name": sk_comp.get_name(),
        "component_path": sk_comp.get_path_name(),
        "skeletal_mesh_asset_path": _get_skeletal_mesh_asset_path(sk_comp),
        "bone_count": bone_count,
        "bones": bone_data,
    }


def _collect_actor_bone_data(actor: unreal.Actor) -> dict:
    sk_components = _get_skeletal_mesh_components(actor)

    return {
        "actor_name": actor.get_actor_label(),
        "actor_path": actor.get_path_name(),
        "actor_transform": _transform_to_dict(actor.get_actor_transform()),
        "skeletal_mesh_component_count": len(sk_components),
        "skeletal_mesh_components": [
            _collect_component_bone_data(sk_comp) for sk_comp in sk_components
        ],
    }


def export_selected_skeletal_mesh_bone_transforms_to_json(output_path: str | None = None) -> str | None:
    selected_actors = _get_selected_actors()
    skeletal_mesh_actors = [actor for actor in selected_actors if len(_get_skeletal_mesh_components(actor)) > 0]

    if len(skeletal_mesh_actors) == 0:
        play_mode_note = " (play mode)" if _is_in_play_mode() else ""
        unreal.log_warning(
            "[export_selected_skeletal_mesh_bone_transforms_to_json] No actor with SkeletalMeshComponent selected{0}.".format(
                play_mode_note
            )
        )
        return None

    resolved_output_path = _resolve_output_path(output_path)

    export_payload = {
        "generated_at": datetime.datetime.now().isoformat(),
        "actor_count": len(skeletal_mesh_actors),
        "actors": [_collect_actor_bone_data(actor) for actor in skeletal_mesh_actors],
    }

    with open(resolved_output_path, "w", encoding="utf-8") as json_file:
        json.dump(export_payload, json_file, indent=2)

    unreal.log(
        "[export_selected_skeletal_mesh_bone_transforms_to_json] Exported {0} actor(s) to {1}".format(
            len(skeletal_mesh_actors),
            resolved_output_path,
        )
    )

    return resolved_output_path


if __name__ == "__main__":
    output_file_path = sys.argv[1] if len(sys.argv) > 1 else None
    export_selected_skeletal_mesh_bone_transforms_to_json(output_file_path)
