"""
Check FBX T-Pose @ Frame 0 (Unreal Import Diagnostic)
======================================================
WHY THIS EXISTS
---------------
Maya shows the correct T-pose at frame 0 because it interpolates
backwards from the first real key.  Unreal does NOT — it maps its
own "frame 0" to whatever the FBX AnimStack LocalStart time is.

The three most common reasons frame 0 is broken in Unreal
(NOT visible as a problem from inside Maya):

  1. ANIMATION STARTS AT FRAME 1 IN MAYA
     Maya exports LocalStart = frame 1.  Unreal calls that its
     "frame 0", so your T-pose key at Maya frame 0 is excluded.
     FIX: set Maya's playback range min to 0 before exporting,
          OR add a T-pose key at frame 1 as well.

  2. NO KEYFRAME EXISTS AT TIME 0
     The exporter only writes a key if one was explicitly set.
     Unreal has nothing to read for that frame.
     FIX: key every bone in T-pose at frame 0.

  3. MISSING / INCORRECT BIND POSE IN FBX
     Unreal falls back to the FBX BindPose node for the reference
     pose.  If absent or wrong, retargeting artefacts appear.
     FIX: enable "Bind Pose" in the FBX Export dialog.

WHAT THIS SCRIPT CHECKS
-----------------------
  Part A — reads the raw FBX text (ASCII FBX only):
    - AnimStack LocalStart  → must be 0
    - Presence of a BindPose node

  Part B — imports the FBX into a clean Maya scene:
    - Earliest keyframe time on every joint curve
    - % of joints that have a key exactly at time = 0
    - Maya timeline start (mirrors FBX LocalStart)

  Each failure includes a concrete FIX instruction.

USAGE
-----
  1. Set FBX_PATH below.
  2. Run inside Maya Script Editor (Python tab).
"""

import os
import re
import maya.cmds as cmds


# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────────────────

FBX_PATH = r"D:\GameDev\Resource\output.fbx"

# A keyframe within this many frames of 0 counts as "at frame 0".
# 0.5 = within half a frame, which is safe for any reasonable frame rate.
FRAME_ZERO_TOLERANCE = 0.5   # frames

# Print a per-joint table of earliest key times.
VERBOSE = True

# Leave the imported scene open after the check.
KEEP_SCENE_OPEN = False


# ─────────────────────────────────────────────────────────────────────────────
#  PART A — raw FBX text inspection  (ASCII FBX only)
# ─────────────────────────────────────────────────────────────────────────────

# FBX stores time in "KTime" units.  1 second = 46 186 158 000 units.
_KTIME_PER_SEC = 46186158000.0


def _ktime_to_sec(k):
    return k / _KTIME_PER_SEC


def _inspect_fbx_text(path):
    """
    Parse the FBX file as plain text and extract AnimStack / BindPose info.
    Returns a dict.  Binary FBX files will have is_ascii=False and no data.
    """
    result = {
        "is_ascii":        False,
        "fbx_version":     None,
        "anim_start_ktime": None,
        "anim_stop_ktime":  None,
        "anim_start_sec":   None,
        "anim_stop_sec":    None,
        "bindpose_found":   False,
    }

    with open(path, "rb") as fh:
        header = fh.read(24)

    if b"Kaydara FBX Binary" in header:
        return result   # binary — skip text inspection

    result["is_ascii"] = True

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    m = re.search(r"FBXVersion:\s*(\d+)", text)
    if m:
        result["fbx_version"] = int(m.group(1))

    # AnimationStack block with LocalTime property
    # Two known formats:
    #   LocalTime: *2 { a: <start>, <stop> }
    #   LocalTime: <start>, <stop>
    m = re.search(
        r"AnimationStack\b.*?LocalTime\s*:\s*\*\s*\d+\s*\{\s*a:\s*(\d+)\s*,\s*(\d+)",
        text, re.DOTALL
    )
    if not m:
        m = re.search(
            r"AnimationStack\b.*?LocalTime\s*:\s*(\d+)\s*,\s*(\d+)",
            text, re.DOTALL
        )
    if m:
        result["anim_start_ktime"] = int(m.group(1))
        result["anim_stop_ktime"]  = int(m.group(2))
        result["anim_start_sec"]   = _ktime_to_sec(result["anim_start_ktime"])
        result["anim_stop_sec"]    = _ktime_to_sec(result["anim_stop_ktime"])

    if re.search(r'Pose\s*:[^{]*"BindPose"', text):
        result["bindpose_found"] = True

    return result


def _report_text(d, fps):
    print("\n── Part A: Raw FBX file inspect ──")

    if not d["is_ascii"]:
        print("  [SKIP] Binary FBX — AnimStack start time cannot be read as text.")
        print("         Re-export as ASCII FBX once to enable this check,")
        print("         or use the Autodesk FBX Python SDK directly.")
        return

    if d["fbx_version"]:
        print(f"  FBX version  : {d['fbx_version']}")

    if d["anim_start_sec"] is not None:
        start_fr = d["anim_start_sec"] * fps
        stop_fr  = d["anim_stop_sec"]  * fps
        print(f"  AnimStack start : {d['anim_start_ktime']} KTime "
              f"= {d['anim_start_sec']:.6f} s = frame {start_fr:.3f} @ {fps} fps")
        print(f"  AnimStack stop  : {d['anim_stop_ktime']} KTime "
              f"= {d['anim_stop_sec']:.6f} s = frame {stop_fr:.3f} @ {fps} fps")

        if abs(start_fr) < 0.01:
            print("  [PASS]  AnimStack LocalStart = 0  "
                  "→ Unreal's frame 0 aligns with Maya's frame 0.")
        else:
            print(f"  [FAIL]  AnimStack LocalStart = frame {start_fr:.3f},  NOT 0.")
            print( "          Unreal will label this as its 'frame 0'.")
            print( "          Your Maya-frame-0 T-pose key is outside the take and lost.")
            print( "  FIX:    In Maya set the playback range min to 0,")
            print( "          bake a T-pose key on ALL joints at frame 0,")
            print( "          then re-export the FBX.")
    else:
        print("  [WARN]  AnimStack / LocalTime not found in text.")
        print("          File may be binary, or saved without an AnimationStack node.")

    if d["bindpose_found"]:
        print("  [PASS]  BindPose node is present in the FBX.")
    else:
        print("  [FAIL]  No BindPose node found.")
        print("          Unreal uses the BindPose as the skeleton's reference pose.")
        print("          Without it, bone orientations and retargeting can be wrong.")
        print("  FIX:    In Maya's FBX Export dialog, enable 'Bind Pose'.")


# ─────────────────────────────────────────────────────────────────────────────
#  PART B — Maya scene inspection after import
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_fbx_plugin():
    if not cmds.pluginInfo("fbxmaya", q=True, loaded=True):
        cmds.loadPlugin("fbxmaya")


def _curve_key_times(curve):
    """Return all key times (in scene time units) for one animCurve node."""
    n = cmds.keyframe(curve, q=True, keyframeCount=True)
    if not n:
        return []
    times = cmds.keyframe(curve, q=True, timeChange=True)
    return list(times) if times else []


def _inspect_maya_scene():
    """
    Inspect animation curves in the current Maya scene.
    Returns times in Maya's current time unit (usually frames).
    """
    result = {
        "joint_count":         0,
        "joints_with_keys":    0,
        "joints_keyed_at_0":   0,
        "earliest_key":        None,
        "timeline_start":      None,
        "timeline_end":        None,
        "per_joint":           {},
    }

    all_joints = cmds.ls(type="joint") or []
    result["joint_count"]    = len(all_joints)
    result["timeline_start"] = cmds.playbackOptions(q=True, minTime=True)
    result["timeline_end"]   = cmds.playbackOptions(q=True, maxTime=True)

    all_earliest = []

    for jnt in all_joints:
        curves = cmds.listConnections(jnt, type="animCurve") or []
        if not curves:
            continue

        result["joints_with_keys"] += 1
        all_times = []
        for crv in curves:
            all_times.extend(_curve_key_times(crv))

        if not all_times:
            continue

        earliest = min(all_times)
        has_at_0 = any(abs(t) <= FRAME_ZERO_TOLERANCE for t in all_times)
        short    = jnt.split("|")[-1].split(":")[-1]

        result["per_joint"][short] = {"earliest": earliest, "has_key_at_0": has_at_0}
        if has_at_0:
            result["joints_keyed_at_0"] += 1
        all_earliest.append(earliest)

    if all_earliest:
        result["earliest_key"] = min(all_earliest)

    return result


def _report_maya(d):
    print("\n── Part B: Maya scene inspect (post-import) ──")

    tstart    = d["timeline_start"]
    earliest  = d["earliest_key"]
    keyed0    = d["joints_keyed_at_0"]
    keyed_any = d["joints_with_keys"]

    print(f"  Joints in scene        : {d['joint_count']}")
    print(f"  Joints with any keys   : {keyed_any}")
    print(f"  Maya timeline range    : {tstart} – {d['timeline_end']}")
    if earliest is not None:
        print(f"  Earliest key overall   : frame {earliest}")

    # ── timeline start ───────────────────────────────────────────────────────
    if tstart is not None:
        if abs(tstart) <= FRAME_ZERO_TOLERANCE:
            print("  [PASS]  Maya timeline starts at frame 0.")
        else:
            print(f"  [FAIL]  Maya timeline starts at frame {tstart}.")
            print( "          The FBX AnimStack LocalStart will match this value.")
            print( "          Unreal will call frame {tstart} its 'frame 0'.".format(tstart=tstart))
            print( "  FIX:    Window > Animation Settings — set Start Time to 0,")
            print( "          add T-pose keys on all joints at frame 0, re-export.")

    # ── earliest key ─────────────────────────────────────────────────────────
    if earliest is not None:
        if abs(earliest) <= FRAME_ZERO_TOLERANCE:
            print("  [PASS]  Earliest keyframe is at frame 0.")
        else:
            print(f"  [FAIL]  Earliest keyframe is at frame {earliest}, not 0.")
            print( "          The FBX contains no bone data before this frame.")
            print( "          Unreal will not have a T-pose stored for frame 0.")
            print( "  FIX:    Select all joints, set frame to 0, key all channels (S),")
            print( "          confirm the pose is T-pose, then re-export.")

    # ── per-joint key-at-0 coverage ──────────────────────────────────────────
    if keyed_any > 0:
        pct = 100.0 * keyed0 / keyed_any
        if keyed0 == keyed_any:
            print(f"  [PASS]  All {keyed_any} animated joints have a key at frame 0.")
        elif keyed0 > 0:
            print(f"  [WARN]  Only {keyed0}/{keyed_any} animated joints ({pct:.0f}%)"
                  f" have a key at frame 0.")
            print( "          Missing joints will use Unreal's bind pose for frame 0,")
            print( "          which may not be T-pose.")
        else:
            print(f"  [FAIL]  0 / {keyed_any} animated joints have a key at frame 0.")

    # ── verbose table ────────────────────────────────────────────────────────
    if VERBOSE and d["per_joint"]:
        print()
        print(f"  {'Joint':<50} {'Earliest key':>13}  Key @ f0")
        print(f"  {'-'*50}  {'-'*13}  --------")
        for name, info in sorted(d["per_joint"].items()):
            flag = "YES" if info["has_key_at_0"] else "NO  <-- MISSING"
            print(f"  {name:<50} {info['earliest']:>13.2f}  {flag}")


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def check_fbx_tpose(fbx_path):
    if not os.path.isfile(fbx_path):
        print(f"[check_tpose] ERROR: File not found: {fbx_path}")
        return

    print("\n" + "=" * 70)
    print(f"[check_tpose] Diagnosing: {fbx_path}")
    print("=" * 70)

    # ── Part A ────────────────────────────────────────────────────────────────
    text_data = _inspect_fbx_text(fbx_path)
    # Determine scene FPS after import for frame-number display.
    # For now use 30 as the display hint; Part B will use the actual imported rate.
    _report_text(text_data, fps=30.0)

    # ── Part B ────────────────────────────────────────────────────────────────
    print("\n── Importing FBX into a clean scene… ──")
    _ensure_fbx_plugin()
    cmds.file(f=True, new=True)
    cmds.file(
        fbx_path,
        i=True,
        type="FBX",
        ignoreVersion=True,
        ra=True,
        mergeNamespacesOnClash=False,
        options="",
        pr=True,
        importFrameRate=True,
        importTimeRange="override",
    )
    print("  Import done.")

    maya_data = _inspect_maya_scene()
    _report_maya(maya_data)

    # ── verdict ───────────────────────────────────────────────────────────────
    print("\n── Verdict ──")

    a_ok = (
        not text_data["is_ascii"]
        or text_data["anim_start_sec"] is None
        or abs(text_data["anim_start_sec"] * 30) < 0.5
    )
    b_timeline_ok = (
        maya_data["timeline_start"] is None
        or abs(maya_data["timeline_start"]) <= FRAME_ZERO_TOLERANCE
    )
    b_earliest_ok = (
        maya_data["earliest_key"] is None
        or abs(maya_data["earliest_key"]) <= FRAME_ZERO_TOLERANCE
    )
    b_coverage_ok = (
        maya_data["joints_with_keys"] == 0
        or maya_data["joints_keyed_at_0"] == maya_data["joints_with_keys"]
    )

    all_ok = a_ok and b_timeline_ok and b_earliest_ok and b_coverage_ok

    if all_ok:
        print("  PASS — FBX has proper frame-0 data. Unreal should show T-pose at frame 0.")
    else:
        print("  FAIL — Issues found (see [FAIL] lines above).")
        print("         Until fixed, Unreal will NOT show T-pose at frame 0.")

    print("=" * 70 + "\n")

    if not KEEP_SCENE_OPEN:
        cmds.file(f=True, new=True)


# ─────────────────────────────────────────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────────────────────────────────────────

check_fbx_tpose(FBX_PATH)
