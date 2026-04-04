import unreal
import path_util
import os
from P4Utils import p4_wrapper


def get_sp_start_up_bat():
    path = os.path.join(path_util.project_root(), "Art/ArtPipeline/SubstancePainter/run_adobe_substance_painter.bat")
    return path


if __name__ == "__main__":
    # Get the current editor selection
    selected_asset_data = unreal.EditorUtilityLibrary().get_selected_asset_data()[0]
    editor_selection = unreal.EditorAssetSubsystem().load_asset(selected_asset_data.package_name)

    # Get the first selected asset (if any)
    if editor_selection:
        # Get the metadata of the selected asset
        json_path = unreal.EditorAssetLibrary().get_metadata_tag(editor_selection, "SP Source Path")
        json_path = os.path.join(path_util.project_root(), json_path)
        sp_path = json_path.replace("_unreal.json", ".spp")
        if os.path.exists(sp_path):
            print(sp_path)

        else:
            # with unreal.ScopedSlowTask(1, "Sync Source Files From P4") as slow_task:
            try:
                p4 = p4_wrapper.p4_init_ue_editor()
                p4_wrapper.sync_to_latest(sp_path)
                p4_wrapper.sync_to_latest(json_path)
            except Exception as e:
                unreal.log_error(e)

        if os.path.exists(sp_path):
            sp_startup_path = get_sp_start_up_bat()

            import subprocess

            # Call the batch file with the parameter
            subprocess.Popen([sp_startup_path, sp_path])
