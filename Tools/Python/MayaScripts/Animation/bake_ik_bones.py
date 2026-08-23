"""
FK → IK Bake & Export Tool for Maya
-------------------------------------
- Opens a user-defined FBX (or all FBX files in a folder), imports animation onto the rig already open in the scene
- Bakes world-space transforms from FK bones → matching IK bones (only where FK has keys)
- Exports the result as {original_name}_new.fbx (animation only, no mesh)
- Restores the scene to its original state after export

USAGE:
  1. Have your rig scene open in Maya.
  2. Fill in the CONFIG section below.
  3. Run the script.
"""

import os
import maya.cmds as cmds
import maya.mel as mel


# ─────────────────────────────────────────────
#  CONFIG  —  Edit these before running
# ��────────────────────────────────────────────

# Full path to a source FBX file OR a folder containing FBX files.
SOURCE_FBX_PATH = r"D:\GameDev\Resource\FFXVIOut\animation\chara\c1001\animation\a0001\wep_swd_emp\battle"

# If SOURCE_FBX_PATH is a folder, search subfolders too.
RECURSIVE_SEARCH = True

# Parallel lists: FK bone name  →  its matching IK bone name
#   The IK bone starts at the same world transform as the FK bone.
FK_BONES = [
    "j_leg_03_r",
    "j_leg_03_l"
]

IK_BONES = [
    "ik_foot_r",
    "ik_foot_l"
]

# Root bone of your rig — the entire hierarchy under this node will be exported.
# Set to "" to auto-detect (uses the top-most joint in the scene).
ROOT_BONE = "root"

# Output directory for the exported FBX (defaults to same folder as source)
OUTPUT_DIR = r"D:\Workspace\FF16UE\Raw\Animation\Clive\Battle"  # leave empty to auto-use the source FBX folder

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _collect_source_fbx_paths(path, recursive=True):
    """Return a sorted list of FBX file paths from a file or folder path."""
    if os.path.isfile(path):
        if path.lower().endswith(".fbx"):
            return [path]
        raise IOError("[FK→IK] Source file is not an FBX: {}".format(path))

    if not os.path.isdir(path):
        raise IOError("[FK→IK] Source path not found: {}".format(path))

    fbx_paths = []
    if recursive:
        for root, _, files in os.walk(path):
            for file_name in files:
                if file_name.lower().endswith(".fbx"):
                    fbx_paths.append(os.path.join(root, file_name))
    else:
        for file_name in os.listdir(path):
            full_path = os.path.join(path, file_name)
            if os.path.isfile(full_path) and file_name.lower().endswith(".fbx"):
                fbx_paths.append(full_path)

    return sorted(fbx_paths)

def _load_fbx_plugin():
    """Ensure the FBX plug-in is loaded."""
    if not cmds.pluginInfo("fbxmaya", q=True, loaded=True):
        cmds.loadPlugin("fbxmaya")


def _get_keyframe_times(node, attrs=("tx", "ty", "tz", "rx", "ry", "rz")):
    """Return a sorted list of unique keyframe times across the given attributes."""
    times = set()
    for attr in attrs:
        plug = "{}.{}".format(node, attr)
        if cmds.objExists(plug):
            keys = cmds.keyframe(plug, q=True, timeChange=True) or []
            times.update(keys)
    return sorted(times)


# Predefined list of bones whose keys may be cleared by remove_keys_for_bone_and_children.
# Add any bone names here that should be eligible for key removal.
REMOVE_KEYS_BONE_LIST = [
    "j_mantleRoot",
    "j_addSkirtRoot_l",
    "j_addSkirtRoot_r",
]


def remove_keys_for_bone_and_children(bone_list=None):
    """
    For every bone in *bone_list*, remove all keyframes from that bone
    and every one of its descendants unconditionally.

    Parameters
    ----------
    bone_list : list[str] | None
        Root bone short-names to clear (together with their full hierarchies).
        Defaults to REMOVE_KEYS_BONE_LIST when None.

    Returns
    -------
    list[str]
        Short names of all nodes that had their keys removed.
    """
    if bone_list is None:
        bone_list = REMOVE_KEYS_BONE_LIST

    cleared = []
    for bone in bone_list:
        if not cmds.objExists(bone):
            cmds.warning("[FK→IK] remove_keys: bone not found: {}".format(bone))
            continue

        # Gather the bone itself plus all descendants
        descendants = cmds.listRelatives(bone, allDescendents=True, fullPath=True) or []
        candidates = [bone] + descendants

        for node in candidates:
            if not cmds.objExists(node):
                continue
            cmds.cutKey(node, clear=True, option="keys")
            short_name = node.split("|")[-1].split(":")[-1]
            cleared.append(short_name)
            print("[FK→IK] Removed all keys from: {}".format(short_name))

    if not cleared:
        print("[FK→IK] remove_keys: no bones found for list: {}".format(bone_list))
    return cleared


def _snapshot_scene_state():
    """
    Record enough state to fully restore the scene afterwards:
      - current time / range
      - keyframes on IK bones (so we can delete newly added ones)
    """
    state = {
        "current_time": cmds.currentTime(q=True),
        "min_time":     cmds.playbackOptions(q=True, min=True),
        "max_time":     cmds.playbackOptions(q=True, max=True),
        "anim_start":   cmds.playbackOptions(q=True, ast=True),
        "anim_end":     cmds.playbackOptions(q=True, aet=True),
    }
    return state


def _restore_scene_state(state, imported_nodes, fk_bones, ik_bones):
    """Remove everything that was added during the bake, restore time range."""
    # Remove keyframes copied onto FK bones
    for bone in fk_bones:
        if cmds.objExists(bone):
            cmds.cutKey(bone, clear=True, option="keys")

    # Remove keyframes added to IK bones
    for bone in ik_bones:
        if cmds.objExists(bone):
            cmds.cutKey(bone, clear=True, option="keys")

    # Delete the temp namespace and all its nodes
    if cmds.namespace(exists=_TEMP_NS):
        try:
            cmds.namespace(removeNamespace=_TEMP_NS, mergeNamespaceWithRoot=True)
        except Exception:
            pass

    # Delete any remaining imported nodes
    to_delete = [n for n in imported_nodes if cmds.objExists(n)]
    if to_delete:
        try:
            cmds.delete(to_delete)
        except Exception:
            pass

    # Restore time range
    cmds.playbackOptions(
        min=state["min_time"],
        max=state["max_time"],
        ast=state["anim_start"],
        aet=state["anim_end"],
    )
    cmds.currentTime(state["current_time"])
    print("[FK→IK] Scene restored to original state.")


# Temp namespace used to isolate the imported FBX skeleton
_TEMP_NS = "_fkik_temp"


# ─────────────────────────────────────────────
#  CORE STEPS
# ─────────────────────────────────────────────

def import_animation(fbx_path, fk_bones):
    """
    Import the FBX via cmds.file (same path as the Maya UI) into a temp
    namespace, bake the temp FK bones to plain keyframes, then transfer
    those keyframes onto the matching scene FK bones.
    Returns the list of new nodes created (for later cleanup).
    """
    _load_fbx_plugin()

    # Clean up any leftover temp namespace from a previous failed run
    if cmds.namespace(exists=_TEMP_NS):
        cmds.namespace(removeNamespace=_TEMP_NS, mergeNamespaceWithRoot=True)

    before = set(cmds.ls(long=True))

    # Use cmds.file — identical to the Maya UI Import dialog for FBX
    cmds.file(
        fbx_path,
        i=True,
        type="FBX",
        ignoreVersion=True,
        ra=True,
        mergeNamespacesOnClash=False,
        namespace=_TEMP_NS,
        options="fbx",
        pr=True,
        importFrameRate=True,
        importTimeRange="override",
    )

    after     = set(cmds.ls(long=True))
    new_nodes = list(after - before)
    print("[FK→IK] Imported {} nodes into namespace '{}'".format(len(new_nodes), _TEMP_NS))

    # Determine the animated range from the playback range (set by importTimeRange=override)
    anim_start = int(cmds.playbackOptions(q=True, min=True))
    anim_end   = int(cmds.playbackOptions(q=True, max=True))
    print("[FK→IK] Animation range: {} – {}".format(anim_start, anim_end))

    # Bake the temp FK bones to explicit keyframes (handles anim layers, constraints, etc.)
    temp_src_bones = []
    for fk_bone in fk_bones:
        src = "{}:{}".format(_TEMP_NS, fk_bone)
        if cmds.objExists(src):
            temp_src_bones.append(src)
        else:
            cmds.warning("[FK→IK] Temp bone not found (name mismatch?): {}".format(src))

    if temp_src_bones:
        cmds.bakeResults(
            temp_src_bones,
            simulation=True,
            time=(anim_start, anim_end),
            sampleBy=1,
            oversamplingRate=1,
            disableImplicitControl=True,
            preserveOutsideKeys=False,
            sparseAnimCurveBake=False,
            removeBakedAttributeFromLayer=False,
            bakeOnOverrideLayer=False,
            minimizeRotation=True,
            at=["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"],
        )
        print("[FK→IK] Baked {} temp bones".format(len(temp_src_bones)))

    # Transfer keyframes from temp bones → scene FK bones
    for fk_bone in fk_bones:
        src = "{}:{}".format(_TEMP_NS, fk_bone)
        if not cmds.objExists(src):
            continue
        if not cmds.objExists(fk_bone):
            cmds.warning("[FK→IK] Scene FK bone not found: {}".format(fk_bone))
            continue
        total_keys = 0
        for attr in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"):
            src_plug = "{}.{}".format(src, attr)
            dst_plug = "{}.{}".format(fk_bone, attr)
            if not cmds.objExists(src_plug):
                continue
            times  = cmds.keyframe(src_plug, q=True, timeChange=True)  or []
            values = cmds.keyframe(src_plug, q=True, valueChange=True) or []
            if not times:
                continue
            try:
                cmds.setAttr(dst_plug, lock=False)
            except Exception:
                pass
            for t, v in zip(times, values):
                cmds.setKeyframe(dst_plug, time=t, value=v)
            total_keys += len(times)
        print("[FK→IK] Transferred {} keys: {} → {}".format(total_keys, src, fk_bone))

    return new_nodes


def collect_fk_keys(fk_bones):
    """
    Build a dict  {fk_bone: sorted_key_times_list}
    Only bones that actually have at least one keyframe are included.
    """
    fk_key_map = {}
    for bone in fk_bones:
        if not cmds.objExists(bone):
            cmds.warning("[FK→IK] FK bone not found, skipping: {}".format(bone))
            continue
        times = _get_keyframe_times(bone)
        if times:
            fk_key_map[bone] = times
    return fk_key_map


def bake_fk_to_ik(fk_bones, ik_bones, fk_key_map):
    """
    For every FK bone that has keys, sample its world-space transform
    at each keyed frame and write matching keys onto the paired IK bone.
    Bones with no FK keys are left untouched.
    """
    attrs_t = ("tx", "ty", "tz")
    attrs_r = ("rx", "ry", "rz")
    attrs_s = ("sx", "sy", "sz")

    for fk_bone, ik_bone in zip(fk_bones, ik_bones):
        if fk_bone not in fk_key_map:
            print("[FK→IK] No keys on '{}' — skipping.".format(fk_bone))
            continue

        if not cmds.objExists(ik_bone):
            cmds.warning("[FK→IK] IK bone not found, skipping: {}".format(ik_bone))
            continue

        key_times = fk_key_map[fk_bone]
        print("[FK→IK] Baking '{}' → '{}' ({} keys)".format(
            fk_bone, ik_bone, len(key_times)))

        # Unlock all transform channels on IK bone just in case
        for attr in list(attrs_t) + list(attrs_r) + list(attrs_s):
            plug = "{}.{}".format(ik_bone, attr)
            if cmds.objExists(plug):
                try:
                    cmds.setAttr(plug, lock=False)
                except Exception:
                    pass

        for t in key_times:
            cmds.currentTime(t, update=True)

            # --- world-space translation ---
            ws_pos = cmds.xform(fk_bone, q=True, worldSpace=True, translation=True)
            cmds.xform(ik_bone, worldSpace=True, translation=ws_pos)
            cmds.setKeyframe(ik_bone, attribute=["tx", "ty", "tz"], time=t)

            # --- world-space rotation ---
            ws_rot = cmds.xform(fk_bone, q=True, worldSpace=True, rotation=True)
            cmds.xform(ik_bone, worldSpace=True, rotation=ws_rot)
            cmds.setKeyframe(ik_bone, attribute=["rx", "ry", "rz"], time=t)

            # --- world-space scale ---
            ws_scl = cmds.xform(fk_bone, q=True, worldSpace=True, scale=True)
            cmds.xform(ik_bone, worldSpace=True, scale=ws_scl)
            cmds.setKeyframe(ik_bone, attribute=["sx", "sy", "sz"], time=t)

    print("[FK→IK] Bake complete.")


def export_ik_animation(ik_bones, source_fbx_path, output_dir, root_bone=""):
    """
    Select the full rig hierarchy (from root_bone) and export as animation-only FBX.
    Output filename: {source_stem}.fbx
    """
    _load_fbx_plugin()

    source_stem = os.path.splitext(os.path.basename(source_fbx_path))[0]
    out_folder  = output_dir if output_dir else os.path.dirname(source_fbx_path)
    if out_folder and not os.path.exists(out_folder):
        os.makedirs(out_folder)
    out_path    = os.path.join(out_folder, "{}.fbx".format(source_stem))
    out_path    = out_path.replace("\\", "/")

    # Resolve the root bone to export from
    export_root = root_bone
    if not export_root or not cmds.objExists(export_root):
        # Auto-detect: find top-level joints (no joint parent) outside the temp namespace
        all_joints = cmds.ls(type="joint", long=True) or []
        top_joints = [
            j for j in all_joints
            if not cmds.listRelatives(j, parent=True, type="joint")
            and not j.startswith("|" + _TEMP_NS + ":")
            and not j.startswith(_TEMP_NS + ":")
        ]
        if not top_joints:
            raise RuntimeError("[FK→IK] Could not find a root joint to export.")
        export_root = top_joints[0].split("|")[-1]  # short name
        print("[FK→IK] Auto-detected root bone: {}".format(export_root))

    # Select root + full hierarchy
    cmds.select(export_root, replace=True, hierarchy=True)
    print("[FK→IK] Exporting hierarchy under '{}'".format(export_root))

    # Export as ASCII FBX
    mel.eval("FBXExportInAscii -v true;")

    # Export using cmds.file — identical to the Maya UI Export Selection for FBX
    cmds.file(
        out_path,
        force=True,
        options="v=0;",
        type="FBX export",
        pr=True,
        es=True,   # export selection
    )

    cmds.select(clear=True)
    print("[FK→IK] Exported animation to: {}".format(out_path))
    return out_path


# ─────────────────────────────────────────────
#  MAIN ENTRY POINT
# ─────────────────────────────────────────────

def run():
    if len(FK_BONES) != len(IK_BONES):
        raise ValueError("[FK→IK] FK_BONES and IK_BONES lists must be the same length.")

    source_fbx_paths = _collect_source_fbx_paths(SOURCE_FBX_PATH, RECURSIVE_SEARCH)
    if not source_fbx_paths:
        raise RuntimeError("[FK→IK] No FBX files found at: {}".format(SOURCE_FBX_PATH))

    print("[FK→IK] Found {} FBX file(s).".format(len(source_fbx_paths)))
    outputs = []

    for idx, source_fbx in enumerate(source_fbx_paths, start=1):
        print("\n[FK→IK] ({}/{}) Processing: {}".format(idx, len(source_fbx_paths), source_fbx))

        scene_state = _snapshot_scene_state()
        imported_nodes = []

        try:
            # 1. Import animation from source FBX
            imported_nodes = import_animation(source_fbx, FK_BONES)

            # 2. Collect FK key times
            fk_key_map = collect_fk_keys(FK_BONES)
            if not fk_key_map:
                raise RuntimeError("[FK→IK] No FK bones had any keyframes after import.")

            # 3. Bake FK → IK (world-space, key-for-key)
            bake_fk_to_ik(FK_BONES, IK_BONES, fk_key_map)
            remove_keys_for_bone_and_children()

            # 4. Export full rig as {name}_new.fbx
            out = export_ik_animation(IK_BONES, source_fbx, OUTPUT_DIR, ROOT_BONE)
            outputs.append(out)
            print("[FK→IK] ✓ Done: {}".format(out))

        except Exception as ex:
            cmds.warning("[FK→IK] Failed for '{}': {}".format(source_fbx, ex))

        # finally:
        #     # Always restore the scene before the next file
        #     _restore_scene_state(scene_state, imported_nodes, FK_BONES, IK_BONES)
        
        # if idx == 10:
        #     print("[FK→IK] Stopping early for testing purposes.")
        #     break

    if not outputs:
        raise RuntimeError("[FK→IK] Batch finished with no successful exports.")

    print("\n[FK→IK] Batch complete. Exported {} file(s).".format(len(outputs)))


# Run immediately when executed
run()