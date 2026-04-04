import unreal
from Materials import material_utils
from enum import Enum
import json
from typing import List
import os
import time
import path_util
from PySide6 import QtWidgets
import sys
from QtUtil import qt_util
import subprocess


mat_editing_lib = unreal.MaterialEditingLibrary()
mat_param_assoc = unreal.MaterialParameterAssociation
sys_lib = unreal.SystemLibrary()
editor_util_lib = unreal.EditorUtilityLibrary()
editor_asset_sub = unreal.EditorAssetSubsystem()


OUTPUT_JSON_FOLDER = "MaterialSlots"


def get_export_folder_path():
    export_folder = path_util.tool_output_temp_folder()
    export_folder = os.path.join(export_folder, OUTPUT_JSON_FOLDER)
    export_folder = os.path.realpath(export_folder)
    if not os.path.isdir(export_folder):
        os.makedirs(export_folder)
    return export_folder


def show_file_dialog():
    app = qt_util.create_qt_application()
    options = QtWidgets.QFileDialog.Options()
    options |= QtWidgets.QFileDialog.DontUseNativeDialog
    fileName, _ = QtWidgets.QFileDialog.getOpenFileName(
        None,
        "Material Slots",
        get_export_folder_path(),
        "Material Slots Files (*.json)",
        options=options,
    )
    return fileName


def export_material_slots_to_file(mesh: unreal.StreamableRenderAsset):
    output_json = []
    if isinstance(mesh, unreal.StaticMesh):
        for material in mesh.static_materials:
            material_json = {
                "slot_name": str(material.material_slot_name),
                "material_path": material.material_interface.get_package().get_path_name(),
            }
            output_json.append(material_json)
    if isinstance(mesh, unreal.SkeletalMesh):
        for material in mesh.materials:
            material_json = {
                "slot_name": str(material.material_slot_name),
                "material_path": material.material_interface.get_package().get_path_name(),
            }
            output_json.append(material_json)
    json_str = json.dumps(output_json, indent=2)

    folder_path = get_export_folder_path()
    export_file_path = os.path.join(folder_path, "{}_Material_Slots.json".format(mesh.get_name()))
    with open(export_file_path, 'w') as output_file:
        output_file.write(json_str)
        
    return export_file_path


def import_material_slots_from_file(mesh: unreal.StreamableRenderAsset):
    import_file_name = show_file_dialog()
    if import_file_name == '':
        return ''
    
    log_str = ''
    with open(import_file_name, 'r') as json_file:
        data = json.loads(json_file.read())
        for material_data in data:
            slot_name = material_data["slot_name"]
            mat_path = material_data["material_path"]
            material_instance = editor_asset_sub.load_asset(mat_path)
            if isinstance(mesh, unreal.StaticMesh):
                mat_index = mesh.get_material_index(slot_name)
                if mat_index != -1:
                    current_mat_instance = mesh.get_material(mat_index)
                    if current_mat_instance != material_instance:
                        mesh.set_material(mat_index, material_instance)
                        log_str = "{}++++++  Set Slot [{}] to : {}\n".format(log_str, slot_name, mat_path)
                    else:
                        log_str = "{} Slot [{}] Material Not Change\n".format(log_str, slot_name)
                else:
                    log_str = "{}xxxxxxx  Slot [{}] Not Exist Anymore\n".format(log_str, slot_name)
                    
            if isinstance(mesh, unreal.SkeletalMesh):
                found_mat = False
                materials = mesh.get_editor_property("materials")
                index = 0
                for sk_mat in materials:
                    if sk_mat.material_slot_name == slot_name:
                        found_mat = True
                        if sk_mat.material_interface != material_instance:
                            sk_mat.material_interface = material_instance
                            materials[index] = sk_mat
                            log_str = "{}++++++  Set Slot [{}] to : {}\n".format(log_str, slot_name, mat_path)
                        else:
                            log_str = "{} Slot [{}] Material Not Change\n".format(log_str, slot_name)
                        break
                    index += 1
                if not found_mat:
                    log_str = "{}xxxxxxx  Slot [{}] Not Exist Anymore\n".format(log_str, slot_name)
                mesh.set_editor_property("materials", materials)
            
    qt_util.pop_up_simple_messagebox("Import Result: \n{}".format(log_str), "Import Success")
    # unreal.AssetEditorSubsystem().close_all_editors_for_asset(mesh)
    # unreal.AssetEditorSubsystem().open_editor_for_assets([mesh])
    return log_str


if __name__ == "__main__":
    app = qt_util.create_qt_application()

    selected_assets_data = editor_util_lib.get_selected_asset_data()
    operation_type = sys.argv[1]
    
    try:
        for selected_asset_data in selected_assets_data:
            if not selected_asset_data.is_asset_loaded():
                editor_asset_sub.load_asset(selected_asset_data.package_path)
            if operation_type == "Export":
                export_file = export_material_slots_to_file(selected_asset_data.get_asset())
            elif operation_type == "Import":
                import_log = import_material_slots_from_file(selected_asset_data.get_asset())
                break
    except Exception as err:
        qt_util.pop_up_simple_messagebox("Failed! Please check console output for detail")
        print(err)
    else:
        if operation_type == "Export":
            msg_box = QtWidgets.QMessageBox()
            msg_box.setText("Export Success!")
            msg_box.setWindowTitle("Success")
            msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
            button_n = msg_box.button(QtWidgets.QMessageBox.Cancel)
            button_n.setText('Open Export Folder')
            button_n.setMinimumWidth(200)
            msg_box.exec_()

            if msg_box.clickedButton() == button_n:
                subprocess.Popen(r'explorer /select,{}'.format(export_file))