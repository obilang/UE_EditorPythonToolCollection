import unreal
import path_util
import os
import sys
from QtUtil import qt_util
from PySide6 import QtWidgets

# import importlib
# 
# importlib.reload(path_util)

TEMP_STORE_FBX_FOLDER = "ExportTexture"

editor_util_lib = unreal.EditorUtilityLibrary()
editor_dialog = unreal.EditorDialog()


def get_export_folder_path():
    export_folder = path_util.tool_output_temp_folder()
    export_folder = os.path.join(export_folder, TEMP_STORE_FBX_FOLDER)
    if not os.path.isdir(export_folder):
        os.makedirs(export_folder)
    return export_folder


def show_export_folder_dialog():
    options = QtWidgets.QFileDialog.Options()
    options |= QtWidgets.QFileDialog.DontUseNativeDialog
    file_dialog = QtWidgets.QFileDialog()
    folder_name = file_dialog.getExistingDirectory(
        None,
        "Select Export Directory",
        get_export_folder_path(),
        options
    )

    return folder_name


def export_selected_texture(asset_to_export: unreal.Object, export_file_path, texture_type):
    task = unreal.AssetExportTask()
    task.set_editor_property('filename', export_file_path)
    task.set_editor_property('automated', True)
    # this will cause export error... not sure why. we can let engine decide the output type
    if texture_type == "tga":
        task.set_editor_property('exporter', unreal.TextureExporterTGA())
    else:
        task.set_editor_property('exporter', unreal.TextureExporterPNG())

    task.set_editor_property('object', asset_to_export)

    with unreal.ScopedSlowTask(1, "Exporting Texture for {}...".format(asset_to_export.get_name())) as slow_task:
        # display the dialog
        slow_task.make_dialog(True)
        result = unreal.Exporter.run_asset_export_task(task)

    print('[Export Texture] Export {} Result: {}'.format(asset_to_export.get_name(), result))

    if not result:
        editor_dialog.show_message("Export Texture Error",
                                   "Fail to export texture: {}".format(asset_to_export.get_name()),
                                   unreal.AppMsgType.OK)


if __name__ == "__main__":
    texture_type = sys.argv[1]
    
    app = qt_util.create_qt_application()

    export_folder = show_export_folder_dialog()
    if export_folder is not None and export_folder != "":
        selected_assets = editor_util_lib.get_selected_asset_data()
        for selected_asset_data in selected_assets:
            export_file_name = "{}/{}.{}".format(export_folder, selected_asset_data.asset_name, texture_type)
            export_selected_texture(selected_asset_data.get_asset(), export_file_name, texture_type)
