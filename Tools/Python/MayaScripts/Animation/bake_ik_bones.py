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
SOURCE_FBX_PATH = r"E:\Workspace\FF16\Output\animation\chara\c1001\animation\a0001\wep_swd_emp\battle_move\run_f_lp.fbx"

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
ROOT_BONE = "n_root"

# Output directory for the exported FBX (defaults to same folder as source)
OUTPUT_DIR = r"E:\Workspace\FF16\Output\animation\chara\c1001\animation\a0001\wep_swd_emp\battle_move\IKBaked"  # leave empty to auto-use the source FBX folder

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _collect_source_fbx_paths(path, recursive=True, exclude_dirs=()):
    """
    Return a sorted list of FBX file paths from a file or folder path.

    exclude_dirs are skipped entirely. OUTPUT_DIR normally lives *inside*
    SOURCE_FBX_PATH, so without this a recursive scan feeds the previous run's
    exports back in as sources — they only carry the FK/IK bones, so the rig
    loses its body animation and any static value (e.g. ik_foot_root's -90
    rotateX) is overwritten with whatever the re-baked file happened to hold.
    """
    if os.path.isfile(path):
        if path.lower().endswith(".fbx"):
            return [path]
        raise IOError("[FK→IK] Source file is not an FBX: {}".format(path))

    if not os.path.isdir(path):
        raise IOError("[FK→IK] Source path not found: {}".format(path))

    blocked = [os.path.normcase(os.path.abspath(d)) for d in exclude_dirs if d]

    def _is_blocked(dir_path):
        norm = os.path.normcase(os.path.abspath(dir_path))
        return any(norm == b or norm.startswith(b + os.sep) for b in blocked)

    fbx_paths, skipped = [], []
    if recursive:
        for root, dir_names, files in os.walk(path):
            # Prune blocked subtrees in place so os.walk never descends into them
            for name in list(dir_names):
                if _is_blocked(os.path.join(root, name)):
                    dir_names.remove(name)
                    skipped.append(os.path.join(root, name))
            if _is_blocked(root):
                continue
            for file_name in files:
                if file_name.lower().endswith(".fbx"):
                    fbx_paths.append(os.path.join(root, file_name))
    else:
        for file_name in os.listdir(path):
            full_path = os.path.join(path, file_name)
            if os.path.isfile(full_path) and file_name.lower().endswith(".fbx"):
                fbx_paths.append(full_path)

    for folder in skipped:
        print("[FK→IK] Skipping output folder while scanning for sources: {}".format(folder))

    return sorted(fbx_paths)

def _load_fbx_plugin():
    """Ensure the FBX plug-in is loaded."""
    if not cmds.pluginInfo("fbxmaya", q=True, loaded=True):
        cmds.loadPlugin("fbxmaya")


def _set_fbx_import_mode(mode):
    """
    Set FBXImportMode, returning whatever it was set to before.

    This has to be "add" for the whole tool to work, and it is NOT safe to
    assume: FBXImportMode is a sticky preference, so whatever the FBX UI was
    last set to is what you get, across sessions.

    In "merge"/"exmerge" the importer updates name-matched nodes in place, which
    silently bypasses the namespace= flag on the cmds.file() call below. Nothing
    lands in _TEMP_NS, transfer_scene_animation() wipes the rig's channels to
    make room for a transfer that then finds no source, and the animation the
    import just landed is destroyed. Merge mode also grafts the source FBX's
    unmatched bones onto the rig, leaving duplicate short names behind that make
    cmds.xform("j_leg_03_r", ...) ambiguous on the next run.
    """
    _load_fbx_plugin()
    previous = mel.eval("FBXImportMode -q;")
    if previous != mode:
        mel.eval("FBXImportMode -v {};".format(mode))
        print("[FK→IK] FBXImportMode '{}' -> '{}'".format(previous, mode))
    return previous


def _temp_nodes(node_type="joint"):
    """
    Every node of *node_type* living anywhere under the temp namespace.

    Deliberately unfiltered-then-filtered rather than cmds.ls("_fkik_temp:*"):
    a pattern with ':' in it matches one namespace level only, and cmds.ls
    patterns don't search nested namespaces at all unless you ask. Both of those
    silently under-report, which is exactly the bug this replaced.
    """
    prefix = _TEMP_NS + ":"
    return [n for n in (cmds.ls(type=node_type, long=True) or []) if prefix in n]


def _count_keys(node, attrs=None):
    """Total keyframes across a node's transferable channels."""
    total = 0
    for attr in (attrs or TRANSFER_ATTRS):
        plug = "{}.{}".format(node, attr)
        if cmds.objExists(plug):
            total += cmds.keyframe(plug, q=True, keyframeCount=True) or 0
    return total


def _build_temp_bone_index():
    """
    Map short bone name -> imported node, across *every* namespace nested under
    _TEMP_NS.

    An FBX that was authored with its own namespace gets that namespace nested
    inside the one we import into, so its bones land at
    '_fkik_temp:run_f_lp:j_leg_03_r', not '_fkik_temp:j_leg_03_r'. Hardcoding the
    flat prefix loses every bone in the nested part of the file — for c1001 that
    was 209 of 435 joints, including both FK_BONES, with no error until the very
    end of the run.

    When a short name exists in more than one namespace, the copy with the most
    keyframes wins: that's the animated one, which is the only one worth
    transferring.
    """
    index = {}
    for node in _temp_nodes("joint"):
        short = node.split("|")[-1].split(":")[-1]
        incumbent = index.get(short)
        if incumbent is None or _count_keys(node) > _count_keys(incumbent):
            index[short] = node
    return index


def _suggest_temp_names(short_name, temp_index, limit=10):
    """Index entries resembling *short_name*, to diagnose a genuine name mismatch."""
    stem = short_name.split(":")[-1]
    hits = [k for k in temp_index if stem in k or k in stem]

    if not hits and "_" in stem:
        # Loosen off the side/index suffix: j_leg_03_r -> j_leg
        token = "_".join(stem.split("_")[:2])
        hits = [k for k in temp_index if token in k]

    return sorted(hits)[:limit]


def _report_temp_namespace(temp_index):
    """Census of what the import actually produced, for diagnosing mismatches."""
    nested = [n for n in (cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or [])
              if _TEMP_NS in n]
    flat = cmds.ls("{}:*".format(_TEMP_NS), type="joint") or []

    print("[FK→IK] temp namespace(s): {}".format(nested))
    print("[FK→IK] joints directly in '{}': {}   (indexed across all of them: {})".format(
        _TEMP_NS, len(flat), len(temp_index)))


def _assert_unambiguous(names):
    """
    Fail early on short names that match more than one DAG node.

    cmds.xform() and cmds.select() take short names throughout this tool; an
    ambiguous one raises from deep inside the bake with a message that doesn't
    say which bone is at fault.
    """
    for name in names:
        if not name:
            continue
        matches = cmds.ls(name, long=True) or []
        if len(matches) > 1:
            raise RuntimeError(
                "[FK→IK] '{}' is ambiguous — {} nodes share that short name:\n  {}\n"
                "A merge-mode import has probably grafted a duplicate hierarchy onto "
                "the rig. Reopen the clean rig scene and run again.".format(
                    name, len(matches), "\n  ".join(matches)))
        if not matches:
            cmds.warning("[FK→IK] not found in scene: {}".format(name))


def _purge_temp_namespace():
    """
    Delete the temp namespace and everything inside it.

    The import lands a complete, separate copy of the source skeleton in
    _TEMP_NS (it does NOT merge onto the rig — the rig has had bones deleted, so
    the skeletons no longer match). Once transfer_scene_animation() has copied
    the keys onto the rig, that copy is pure garbage and must go: the old
    mergeNamespaceWithRoot=True only stripped the namespace, leaving a full
    world-level skeleton behind per processed file (n_root1, n_root2, … n_root9)
    and duplicate short names for every joint, which is what made short-name
    lookups like cmds.xform("ik_foot_r", …) and cmds.select("n_root") ambiguous.
    """
    if not cmds.namespace(exists=_TEMP_NS):
        return

    try:
        cmds.namespace(removeNamespace=_TEMP_NS, deleteNamespaceContent=True)
        return
    except Exception:
        pass

    # Fallback: delete top-most nodes first so their children go with them.
    # Scans by substring rather than the 'ns:*' pattern so nodes in namespaces
    # nested under _TEMP_NS (an FBX carrying its own namespace) get caught too.
    nodes = [n for n in (cmds.ls(long=True) or []) if _TEMP_NS + ":" in n]
    tops = [n for n in nodes if not (cmds.listRelatives(n, parent=True, fullPath=True) or [])]
    for node in (tops or nodes):
        if cmds.objExists(node):
            try:
                cmds.delete(node)
            except Exception:
                pass

    leftovers = [n for n in (cmds.ls(long=True) or [])
                 if _TEMP_NS + ":" in n and cmds.objExists(n)]
    if leftovers:
        try:
            cmds.delete(leftovers)
        except Exception:
            pass

    try:
        cmds.namespace(removeNamespace=_TEMP_NS, force=True)
    except Exception:
        cmds.warning("[FK→IK] Could not fully remove namespace '{}'.".format(_TEMP_NS))


def cleanup_orphan_skeletons(root_bone):
    """
    Delete world-level skeletons left behind by earlier runs of this tool
    (n_root1, n_root2, …). They are duplicates of the source skeleton and make
    every short-name lookup in this script ambiguous.
    """
    keep = cmds.ls(root_bone, long=True) or []
    orphans = []
    for joint in cmds.ls(type="joint", long=True) or []:
        if joint.count("|") != 1:          # world-level only
            continue
        if joint in keep:
            continue
        orphans.append(joint)

    if orphans:
        print("[FK→IK] Deleting {} orphan skeleton(s) from previous runs: {}".format(
            len(orphans), [o.lstrip("|") for o in orphans]))
        try:
            cmds.delete(orphans)
        except Exception as ex:
            cmds.warning("[FK→IK] Could not delete orphan skeletons: {}".format(ex))
    return orphans


def _ik_chain_ancestors(ik_bones, root_bone):
    """Every ancestor of the IK bones up to (and excluding) root_bone."""
    ancestors = []
    for ik_bone in ik_bones:
        if not cmds.objExists(ik_bone):
            continue
        node = ik_bone
        while True:
            parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
            if not parents:
                break
            node = parents[0]
            short = node.split("|")[-1].split(":")[-1]
            if short == root_bone:
                break
            if short not in ancestors:
                ancestors.append(short)
    return ancestors


_STATIC_ATTRS = ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz",
                 "jointOrientX", "jointOrientY", "jointOrientZ")


def snapshot_static_transforms(nodes):
    """Record the local transform of nodes that are expected to stay static."""
    snap = {}
    for node in nodes:
        if not cmds.objExists(node):
            continue
        values = {}
        for attr in _STATIC_ATTRS:
            plug = "{}.{}".format(node, attr)
            if cmds.objExists(plug):
                try:
                    values[attr] = cmds.getAttr(plug)
                except Exception:
                    pass
        if values:
            snap[node] = values
    return snap


def restore_static_transforms(snap):
    """
    Re-apply the snapshotted local transforms, skipping anything that has since
    been genuinely animated. Prints whenever it has to correct a value, so a
    drifting rig shows up in the log instead of silently in the export.
    """
    for node, values in snap.items():
        if not cmds.objExists(node):
            cmds.warning("[FK→IK] static-guard: node vanished: {}".format(node))
            continue
        for attr, want in values.items():
            plug = "{}.{}".format(node, attr)
            if not cmds.objExists(plug):
                continue
            if cmds.keyframe(plug, q=True, keyframeCount=True):
                continue  # real animation — leave it alone
            try:
                have = cmds.getAttr(plug)
            except Exception:
                continue
            if abs(have - want) < 1e-6:
                continue
            try:
                cmds.setAttr(plug, want)
                print("[FK→IK] static-guard: {} {} -> {} (was {})".format(
                    node, attr, want, have))
            except Exception:
                cmds.warning("[FK→IK] static-guard: could not set {}".format(plug))


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

    # Strip the temp namespace (must merge, never delete — see _release_temp_namespace)
    _release_temp_namespace()

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

TRANSFER_ATTRS = ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz")


def transfer_scene_animation(root_bone, temp_index=None, attrs=TRANSFER_ATTRS):
    """
    Copy keys from the imported temp skeleton onto the rig, for *every* bone the
    two have in common — not just FK_BONES.

    The import lands a separate copy of the source skeleton in _TEMP_NS; without
    this step only the bones this script re-keys by hand (FK_BONES + IK_BONES)
    carry any animation into the export. Bones the rig no longer has are simply
    skipped, which is what keeps the exported animation small.

    Returns (bones_transferred, bones_without_a_source).
    """
    if temp_index is None:
        temp_index = _build_temp_bone_index()

    # Everything below this line is destructive, and the wipe happens before the
    # first source lookup. If the temp skeleton isn't there, bail while the rig's
    # animation is still intact -- the alternative is clearing 1700-odd channels
    # and *then* discovering there is nothing to put back.
    if not temp_index:
        raise RuntimeError(
            "[FK→IK] No source bones found under namespace '{}' — the FBX did not "
            "import as a separate skeleton, so there is nothing to transfer from. "
            "Refusing to clear the rig's keys. Check that "
            "mel.eval(\"FBXImportMode -q;\") returns 'add'.".format(_TEMP_NS))

    rig_joints = cmds.listRelatives(root_bone, allDescendents=True,
                                    fullPath=True, type="joint") or []
    rig_joints = (cmds.ls(root_bone, long=True) or []) + rig_joints

    # Wipe every transferable channel on the rig first. Doing it per-plug inside
    # the copy loop only clears channels the *new* file animates, so a channel
    # animated by file A but not by file B would keep A's keys in B's export.
    stale = ["{}.{}".format(j, a) for j in rig_joints for a in attrs]
    stale = [p for p in stale if cmds.objExists(p)
             and cmds.keyframe(p, q=True, keyframeCount=True)]
    if stale:
        for plug in stale:
            try:
                cmds.setAttr(plug, lock=False)
            except Exception:
                pass
        cmds.cutKey(stale, clear=True, option="keys")
        print("[FK→IK] Cleared stale keys on {} rig channels before transfer.".format(
            len(stale)))

    transferred, missing = [], []
    for joint in rig_joints:
        short = joint.split("|")[-1].split(":")[-1]
        src = temp_index.get(short)
        if not src:
            missing.append(short)
            continue

        copied_any = False
        for attr in attrs:
            src_plug = "{}.{}".format(src, attr)
            dst_plug = "{}.{}".format(joint, attr)
            if not cmds.objExists(src_plug) or not cmds.objExists(dst_plug):
                continue
            if not cmds.keyframe(src_plug, q=True, keyframeCount=True):
                continue

            try:
                cmds.setAttr(dst_plug, lock=False)
            except Exception:
                pass

            # Replace outright — a partial overwrite would leave keys from the
            # previous file alive wherever this file's range is shorter.
            cmds.cutKey(dst_plug, clear=True, option="keys")
            try:
                if cmds.copyKey(src, attribute=attr):
                    cmds.pasteKey(joint, attribute=attr, option="replaceCompletely")
                    copied_any = True
            except Exception:
                # Fall back to an explicit key-by-key copy
                times = cmds.keyframe(src_plug, q=True, timeChange=True) or []
                values = cmds.keyframe(src_plug, q=True, valueChange=True) or []
                for t, v in zip(times, values):
                    cmds.setKeyframe(dst_plug, time=t, value=v)
                copied_any = bool(times)

        if copied_any:
            transferred.append(short)

    print("[FK→IK] Transferred animation onto {} rig bones ({} rig bones had no "
          "source bone in the FBX)".format(len(transferred), len(missing)))
    if missing:
        print("[FK→IK]   no source for: {}".format(sorted(missing)))
        _report_temp_namespace(temp_index)
        for short in sorted(missing)[:5]:
            print("[FK→IK]   '{}' -> similar in import: {}".format(
                short, _suggest_temp_names(short, temp_index) or "(nothing resembling it)"))
    return transferred, missing


def import_animation(fbx_path, fk_bones, root_bone=""):
    """
    Import the FBX via cmds.file (same path as the Maya UI) into a temp
    namespace, bake the temp FK bones to plain keyframes, transfer the animation
    onto every matching rig bone, then delete the temp skeleton.
    Returns the list of new nodes created (for later cleanup).
    """
    _set_fbx_import_mode("add")

    # Clean up any leftover temp namespace from a previous file / failed run
    _purge_temp_namespace()

    before = set(cmds.ls(long=True))

    # Use cmds.file — identical to the Maya UI Import dialog for FBX.
    # mergeNamespacesOnClash=True so a _TEMP_NS that survived _purge_temp_namespace()
    # gets reused; with False, Maya would quietly import into '_fkik_temp1' instead
    # and every lookup below would miss.
    cmds.file(
        fbx_path,
        i=True,
        type="FBX",
        ignoreVersion=True,
        ra=True,
        mergeNamespacesOnClash=True,
        namespace=_TEMP_NS,
        options="fbx",
        pr=True,
        importFrameRate=True,
        importTimeRange="override",
    )

    after     = set(cmds.ls(long=True))
    new_nodes = list(after - before)

    # Substring match, not a 'ns:*' pattern: an FBX carrying its own internal
    # namespace gets it nested (_fkik_temp:run_f_lp:j_leg_03_r), and cmds.ls
    # patterns don't descend into nested namespaces.
    ns_nodes = [n for n in (cmds.ls(long=True) or []) if _TEMP_NS + ":" in n]
    if not ns_nodes:
        raise RuntimeError(
            "[FK→IK] Import created {} node(s) but none of them landed in '{}'. The FBX "
            "merged onto the rig by name instead of importing as a separate skeleton, "
            "which also means the rig in this scene has been modified — reopen it before "
            "retrying.".format(len(new_nodes), _TEMP_NS))

    print("[FK→IK] Imported {} nodes, {} into namespace '{}'".format(
        len(new_nodes), len(ns_nodes), _TEMP_NS))

    # Determine the animated range from the playback range (set by importTimeRange=override)
    anim_start = int(cmds.playbackOptions(q=True, min=True))
    anim_end   = int(cmds.playbackOptions(q=True, max=True))
    print("[FK→IK] Animation range: {} – {}".format(anim_start, anim_end))

    # Resolve source bones by short name across every nested namespace, not by a
    # flat '_fkik_temp:' prefix -- see _build_temp_bone_index.
    temp_index = _build_temp_bone_index()

    # Bake the temp FK bones to explicit keyframes (handles anim layers, constraints, etc.)
    temp_src_bones = []
    for fk_bone in fk_bones:
        src = temp_index.get(fk_bone)
        if src:
            temp_src_bones.append(src)
        else:
            cmds.warning("[FK→IK] Temp bone not found: {}\n    similar names in the "
                         "import: {}".format(
                             fk_bone, _suggest_temp_names(fk_bone, temp_index) or "(none)"))

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

    # Transfer the animation onto every rig bone that has a counterpart in the
    # imported skeleton (this covers FK_BONES too).
    if root_bone and cmds.objExists(root_bone):
        transfer_scene_animation(root_bone, temp_index)
    else:
        cmds.warning("[FK→IK] No root bone — falling back to FK_BONES only, the "
                     "export will have no body animation.")
        for fk_bone in fk_bones:
            src = temp_index.get(fk_bone)
            if not src or not cmds.objExists(fk_bone):
                continue
            for attr in TRANSFER_ATTRS:
                src_plug = "{}.{}".format(src, attr)
                dst_plug = "{}.{}".format(fk_bone, attr)
                if not cmds.objExists(src_plug):
                    continue
                times  = cmds.keyframe(src_plug, q=True, timeChange=True)  or []
                values = cmds.keyframe(src_plug, q=True, valueChange=True) or []
                if not times:
                    continue
                cmds.cutKey(dst_plug, clear=True, option="keys")
                for t, v in zip(times, values):
                    cmds.setKeyframe(dst_plug, time=t, value=v)

    # The imported skeleton is now redundant. Delete it immediately so it cannot
    # accumulate (n_root1, n_root2, …) or make short-name lookups ambiguous.
    _purge_temp_namespace()

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

    source_fbx_paths = _collect_source_fbx_paths(
        SOURCE_FBX_PATH, RECURSIVE_SEARCH, exclude_dirs=[OUTPUT_DIR])
    if not source_fbx_paths:
        raise RuntimeError("[FK→IK] No FBX files found at: {}".format(SOURCE_FBX_PATH))

    print("[FK→IK] Found {} FBX file(s).".format(len(source_fbx_paths)))

    # Earlier versions of this tool left a whole skeleton in the scene per
    # processed file (n_root1, n_root2, …). Clear them out before doing anything
    # else, so short-name lookups are unambiguous.
    cleanup_orphan_skeletons(ROOT_BONE)

    # Every lookup in this tool goes through short names, so a duplicate anywhere
    # in the rig is a hard stop rather than something to work around.
    _assert_unambiguous([ROOT_BONE] + list(FK_BONES) + list(IK_BONES))

    # Snapshot the static local transforms of the IK bones' parents *before* the
    # first import, while the rig is still pristine. These carry values like the
    # -90 rotateX on ik_foot_root that nothing should ever key or change; the
    # guard re-applies them just before each export and logs any correction.
    static_guard = snapshot_static_transforms(_ik_chain_ancestors(IK_BONES, ROOT_BONE))
    print("[FK→IK] Static guard watching: {}".format(sorted(static_guard) or "(nothing)"))

    # FBXImportMode is a persisted preference, so leaving it flipped would change
    # what the user's next manual FBX import does. Borrow it, hand it back.
    previous_import_mode = _set_fbx_import_mode("add")

    outputs = []

    try:
        _run_batch(source_fbx_paths, static_guard, outputs)
    finally:
        _set_fbx_import_mode(previous_import_mode)

    if not outputs:
        raise RuntimeError("[FK→IK] Batch finished with no successful exports.")

    print("\n[FK→IK] Batch complete. Exported {} file(s).".format(len(outputs)))


def _run_batch(source_fbx_paths, static_guard, outputs):
    for idx, source_fbx in enumerate(source_fbx_paths, start=1):
        print("\n[FK→IK] ({}/{}) Processing: {}".format(idx, len(source_fbx_paths), source_fbx))

        scene_state = _snapshot_scene_state()
        imported_nodes = []

        try:
            # 1. Import animation from source FBX and transfer it onto the rig
            imported_nodes = import_animation(source_fbx, FK_BONES, ROOT_BONE)

            # 2. Collect FK key times
            fk_key_map = collect_fk_keys(FK_BONES)
            if not fk_key_map:
                raise RuntimeError("[FK→IK] No FK bones had any keyframes after import.")

            # 3. Bake FK → IK (world-space, key-for-key)
            bake_fk_to_ik(FK_BONES, IK_BONES, fk_key_map)
            remove_keys_for_bone_and_children()

            # 4. Put back any static transform the import/bake disturbed
            restore_static_transforms(static_guard)

            # 5. Export full rig as {name}_new.fbx
            out = export_ik_animation(IK_BONES, source_fbx, OUTPUT_DIR, ROOT_BONE)
            outputs.append(out)
            print("[FK→IK] ✓ Done: {}".format(out))

        except Exception as ex:
            cmds.warning("[FK→IK] Failed for '{}': {}".format(source_fbx, ex))

        # NOTE: left disabled. The import merges animation onto the whole rig (not
        # just FK_BONES), so this restore is incomplete — and its
        # cmds.delete(imported_nodes) would remove the merged anim curves and the
        # joints the import added to the rig.
        # finally:
        #     _restore_scene_state(scene_state, imported_nodes, FK_BONES, IK_BONES)

        # if idx == 10:
        #     print("[FK→IK] Stopping early for testing purposes.")
        #     break


# Run immediately when executed
run()