import os
import maya.cmds as cmds

ROOT = r"D:\GameDev\Resource\FFXVIOut\animation\chara\c1001\animation\a0001\wep_swd_emp\battle_move"

# Use the same FBX/DAE options string from your manual import/export log
FBX_OPTIONS = (
    "ts=0;ec=1;cd=0.0015;icl=0.01;mcl=100;s=3;adp=1;smp=8;ant=0;leg=0;"
    "en=1;nt=15;st=0;gar=21.5;mel=11.314646;sso=0;stol=0.01;ssps1=0;ssps2=0;sym=1"
)

def ensure_plugins():
    if not cmds.pluginInfo("fbxmaya", q=True, loaded=True):
        cmds.loadPlugin("fbxmaya")

def find_dae_files(root):
    files = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith(".dae"):
                files.append(os.path.join(dirpath, fn))
    files.sort()
    return files

def new_scene():
    cmds.file(f=True, new=True)

def import_dae_like_manual(dae_path):
    # Match your exact successful manual command behavior
    cmds.file(
        dae_path,
        i=True,
        type="DAE_FBX",
        ignoreVersion=True,
        ra=True,
        mergeNamespacesOnClash=False,
        namespace="head",
        options=FBX_OPTIONS,
        pr=True,
        importFrameRate=True,
        importTimeRange="override",
    )

def export_fbx_like_manual(fbx_path):
    cmds.file(
        fbx_path,
        force=True,
        options=FBX_OPTIONS,
        type="FBX export",
        pr=True,
        ea=True,   # export all
    )

def batch_convert(root):
    ensure_plugins()
    dae_files = find_dae_files(root)

    if not dae_files:
        print("No DAE files found.")
        return

    print("Found {} DAE files".format(len(dae_files)))

    ok, fail, skipped = 0, 0, 0
    for idx, dae_path in enumerate(dae_files, 1):
        fbx_path = os.path.splitext(dae_path)[0] + ".fbx"
        print("\n[{}/{}] Processing: {}".format(idx, len(dae_files), dae_path))
        if os.path.isfile(fbx_path):
            print("SKIPPED (FBX already exists): {}".format(fbx_path))
            skipped += 1
            continue
        try:
            new_scene()
            import_dae_like_manual(dae_path)
            export_fbx_like_manual(fbx_path)
            print("Exported: {}".format(fbx_path))
            ok += 1
        except Exception as e:
            print("FAILED: {} -> {}".format(dae_path, e))
            fail += 1

    print("\nDone. Success: {}, Failed: {}, Skipped: {}".format(ok, fail, skipped))

batch_convert(ROOT)