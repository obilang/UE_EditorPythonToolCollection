import unreal
from Materials import material_utils
from enum import Enum
import json
from typing import List
import os
import time
import path_util
from PySide6 import QtWidgets
from PySide6 import QtGui
import sys
from QtUtil import qt_util
from AssetOperations import asset_utils
from QtUtil import qt_style_preset
import subprocess

# import importlib
# importlib.reload(material_utils)
# importlib.reload(path_util)


mat_editing_lib = unreal.MaterialEditingLibrary()
mat_param_assoc = unreal.MaterialParameterAssociation
sys_lib = unreal.SystemLibrary()
editor_util_lib = unreal.EditorUtilityLibrary()
editor_asset_sub = unreal.EditorAssetSubsystem()
asset_registry = unreal.AssetRegistryHelpers().get_asset_registry()


OUTPUT_JSON_FOLDER = "MaterialParameters"


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
        "QFileDialog.getOpenFileName()",
        get_export_folder_path(),
        "Material Params Files (*.json)",
        options=options,
    )
    return fileName


class EParameterType(Enum):
    SCALAR = 'scalar'
    VECTOR = 'vector'
    TEXTURE = 'texture'
    STATIC_SWITCH = 'static switch'


class MaterialParameter(dict):
    def __init__(self, my_dict=None):
        dict.__init__(self)
        self.parameter_name = ""
        self.parameter_type = EParameterType.SCALAR
        self.parameter_value = None
        # TODO
        # self.parameter_association = mat_param_assoc.GLOBAL_PARAMETER
        self.is_overriding_value = False

        if my_dict:
            for key in my_dict:
                setattr(self, key, my_dict[key])

            # for index, layer in enumerate(self.layers):
            #     layer_class = Layers(layer)
            #     self.layers[index] = layer_class
            # 
            # for index, blend_mask in enumerate(self.blend_masks):
            #     blend_masks_class = Layers(blend_mask)
            #     self.blend_masks[index] = blend_masks_class

    def __getitem__(self, key):
        return dict.__getitem__(self, key)

    @property
    def parameter_name(self):
        return self["parameter_name"]

    @parameter_name.setter
    def parameter_name(self, value):
        self["parameter_name"] = str(value)

    @property
    def parameter_type(self) -> EParameterType:
        return EParameterType(self["parameter_type"])

    @parameter_type.setter
    def parameter_type(self, value: EParameterType):
        if isinstance(value, EParameterType):
            self["parameter_type"] = value.value
        else:
            self["parameter_type"] = value

    @property
    def parameter_value(self):
        value_str = self["parameter_value"]
        if self.parameter_type == EParameterType.VECTOR:
            value_str = value_str.replace('rgba: (', '')
            value_str = value_str.replace(')', '')
            channels = value_str.split(',')
            return unreal.LinearColor(float(channels[0]), float(channels[1]), float(channels[2]), float(channels[3]))
        elif self.parameter_type == EParameterType.SCALAR:
            return float(value_str)
        elif self.parameter_type == EParameterType.TEXTURE:
            if editor_asset_sub.does_asset_exist(value_str):
                return editor_asset_sub.load_asset(value_str)
            else:
                return value_str
        elif self.parameter_type == EParameterType.STATIC_SWITCH:
            return True if value_str == "True" else False
        else:
            return value_str

    @parameter_value.setter
    def parameter_value(self, value):
        if isinstance(value, str):
            self["parameter_value"] = value
            return 
        
        if self.parameter_type == EParameterType.VECTOR:
            self["parameter_value"] = "rgba: ({},{},{},{})".format(value.r, value.g, value.b, value.a)
        elif self.parameter_type == EParameterType.TEXTURE:
            if isinstance(value, unreal.Object):
                self["parameter_value"] = value.get_package().get_path_name()
            else:
                self["parameter_value"] = str(value)
        else:
            self["parameter_value"] = str(value)
    
    # @property
    # def parameter_association(self):
    #     return self["parameter_association"]
    # 
    # @parameter_association.setter
    # def parameter_association(self, value):
    #     self["parameter_association"] = value

    @property
    def is_overriding_value(self):
        return self["is_overriding_value"]

    @is_overriding_value.setter
    def is_overriding_value(self, value):
        self["is_overriding_value"] = value


class MaterialPropertyPack(dict):
    def __init__(self):
        super().__init__()
        self.material_package_path = ""
        self.parent_material_package_path = ""
        self.material_asset_p4_revision = ""
        self.material_asset_file_last_modified_time = ""
        self.mat_parameters = []

    @property
    def mat_parameters(self) -> [MaterialParameter]:
        return self["mat_parameters"]

    @mat_parameters.setter
    def mat_parameters(self, value: [MaterialParameter]):
        self["mat_parameters"] = value

    @property
    def material_package_path(self):
        return self["material_package_path"]

    @material_package_path.setter
    def material_package_path(self, value):
        self["material_package_path"] = value

    @property
    def parent_material_package_path(self):
        return self["parent_material_package_path"]

    @parent_material_package_path.setter
    def parent_material_package_path(self, value):
        self["parent_material_package_path"] = value
        
    @property
    def material_asset_p4_revision(self):
        return self["material_asset_p4_revision"]

    @material_asset_p4_revision.setter
    def material_asset_p4_revision(self, value):
        self["material_asset_p4_revision"] = value

    @property
    def material_asset_file_last_modified_time(self):
        return self["material_asset_file_last_modified_time"]
    
    @material_asset_file_last_modified_time.setter
    def material_asset_file_last_modified_time(self, value):
        self["material_asset_file_last_modified_time"] = value

    def __getitem__(self, key):
        return dict.__getitem__(self, key)

    def serialize_to_json(self):
        json_str = json.dumps(self, indent=2)
        return json_str

    def convert_dict(self):
        for index, mat_parameter in enumerate(self.mat_parameters):
            mat_parameter_class = MaterialParameter(mat_parameter)
            self.mat_parameters[index] = mat_parameter_class

    def deserialize_from_json(self, json_str):
        data = json.loads(json_str)
        for key, value in data.items():
            self[key] = value
        self.convert_dict()

    def deserialize_from_json_file(self, json_file_path):
        with open(json_file_path, 'r') as json_file:
            data = json.loads(json_file.read())
            for key, value in data.items():
                self[key] = value
        self.convert_dict()


def get_all_params_of_type_in_material(material_instance: unreal.MaterialInstanceConstant, param_type: EParameterType):
    all_params = []
    if param_type == EParameterType.SCALAR:
        all_param_names = mat_editing_lib.get_scalar_parameter_names(material_instance)
    elif param_type == EParameterType.VECTOR:
        all_param_names = mat_editing_lib.get_vector_parameter_names(material_instance)
    elif param_type == EParameterType.TEXTURE:
        all_param_names = mat_editing_lib.get_texture_parameter_names(material_instance)
    elif param_type == EParameterType.STATIC_SWITCH:
        all_param_names = mat_editing_lib.get_static_switch_parameter_names(material_instance)

    for param_name in all_param_names:
        if param_type == EParameterType.SCALAR:
            value = mat_editing_lib.get_material_instance_scalar_parameter_value(material_instance, param_name)
            # default_value = mat_editing_lib.get_material_default_scalar_parameter_value(
            #     material_instance.get_base_material(),
            #     param_name)
        elif param_type == EParameterType.VECTOR:
            value = mat_editing_lib.get_material_instance_vector_parameter_value(material_instance, param_name)
        elif param_type == EParameterType.TEXTURE:
            value = mat_editing_lib.get_material_instance_texture_parameter_value(material_instance, param_name)
        elif param_type == EParameterType.STATIC_SWITCH:
            value = mat_editing_lib.get_material_instance_static_switch_parameter_value(material_instance, param_name)
    
        material_param = MaterialParameter()
        material_param.parameter_name = param_name
        material_param.parameter_type = param_type
        material_param.parameter_value = value

        if param_type == EParameterType.STATIC_SWITCH:
            material_param.is_overriding_value = not has_same_value_as_parent(material_instance, EParameterType.STATIC_SWITCH, param_name, value)
        else:
            overriding_param_values = get_override_param_values(material_instance, param_type)
                
            for overriding_param_value in overriding_param_values:
                if overriding_param_value.parameter_info.name == param_name:
                    material_param.is_overriding_value = True
                    break
    
        all_params.append(material_param)

    return all_params   


def get_all_material_params_in_material(material_instance: unreal.MaterialInstanceConstant):
    all_params = []
    scaler_params = get_all_params_of_type_in_material(material_instance, EParameterType.SCALAR)
    for param in scaler_params:
        all_params.append(param)
    vector_params = get_all_params_of_type_in_material(material_instance, EParameterType.VECTOR)
    for param in vector_params:
        all_params.append(param)
    texture_params = get_all_params_of_type_in_material(material_instance, EParameterType.TEXTURE)
    for param in texture_params:
        all_params.append(param)
    static_switch_params = get_all_params_of_type_in_material(material_instance, EParameterType.STATIC_SWITCH)
    for param in static_switch_params:
        all_params.append(param)

    return all_params


def find_param_info_by_param_name(mat_params: List[MaterialParameter], param_name) -> MaterialParameter:
    for mat_param in mat_params:
        if mat_param.parameter_name == param_name:
            return mat_param
    return None


def set_param_value_of_type_in_material(material_instance: unreal.MaterialInstanceConstant, param_type: EParameterType, param_name, param_value):
    if param_type == EParameterType.SCALAR:
        mat_editing_lib.set_material_instance_scalar_parameter_value(material_instance, param_name, param_value)
    elif param_type == EParameterType.VECTOR:
        mat_editing_lib.set_material_instance_vector_parameter_value(material_instance, param_name, param_value)
    elif param_type == EParameterType.TEXTURE:
        if isinstance(param_value, unreal.Texture):
            mat_editing_lib.set_material_instance_texture_parameter_value(material_instance, param_name, param_value)
    elif param_type == EParameterType.STATIC_SWITCH:
        mat_editing_lib.set_material_instance_static_switch_parameter_value(material_instance, param_name, param_value)


def has_same_value_as_parent(material_instance: unreal.MaterialInstanceConstant, param_type: EParameterType, param_name, param_value):
    if param_type == EParameterType.SCALAR:
        if isinstance(material_instance.parent, unreal.Material):
            parent_value = mat_editing_lib.get_material_default_scalar_parameter_value(material_instance.parent,
                                                                                              param_name)
        else:
            parent_value = mat_editing_lib.get_material_instance_scalar_parameter_value(material_instance.parent,
                                                                                               param_name)
    elif param_type == EParameterType.VECTOR:
        if isinstance(material_instance.parent, unreal.Material):
            parent_value = mat_editing_lib.get_material_default_vector_parameter_value(material_instance.parent,
                                                                                              param_name)
        else:
            parent_value = mat_editing_lib.get_material_instance_vector_parameter_value(material_instance.parent,
                                                                                               param_name)
        return parent_value.equals(param_value)    
    elif param_type == EParameterType.TEXTURE:
        if not isinstance(param_value, unreal.Texture):
            return False
        
        if isinstance(material_instance.parent, unreal.Material):
            parent_value = mat_editing_lib.get_material_default_texture_parameter_value(material_instance.parent,
                                                                                              param_name)
        else:
            parent_value = mat_editing_lib.get_material_instance_texture_parameter_value(material_instance.parent,
                                                                                               param_name)
        return parent_value.get_path_name() == param_value.get_path_name()
        
    elif param_type == EParameterType.STATIC_SWITCH:
        if isinstance(material_instance.parent, unreal.Material):
            parent_value = mat_editing_lib.get_material_default_static_switch_parameter_value(material_instance.parent,
                                                                                              param_name)
        else:
            parent_value = mat_editing_lib.get_material_instance_static_switch_parameter_value(material_instance.parent,
                                                                                               param_name)
    return parent_value == param_value


def get_override_param_values(material_instance: unreal.MaterialInstanceConstant, param_type: EParameterType):
    if param_type == EParameterType.SCALAR:
        overriding_param_values = material_instance.scalar_parameter_values
    elif param_type == EParameterType.VECTOR:
        overriding_param_values = material_instance.vector_parameter_values
    elif param_type == EParameterType.TEXTURE:
        overriding_param_values = material_instance.texture_parameter_values
    elif param_type == EParameterType.STATIC_SWITCH:
        return []
    return overriding_param_values


def remove_override_param_value(material_instance: unreal.MaterialInstanceConstant, param_type: EParameterType, overriding_param_value):
    if param_type == EParameterType.SCALAR:
        material_instance.scalar_parameter_values.remove(overriding_param_value)
    elif param_type == EParameterType.VECTOR:
        material_instance.vector_parameter_values.remove(overriding_param_value)
    elif param_type == EParameterType.TEXTURE:
        material_instance.texture_parameter_values.remove(overriding_param_value)
        
    
def set_material_params_in_material(material_instance: unreal.MaterialInstanceConstant, new_mat_params: List[MaterialParameter], has_different_parent=False):
    old_params = get_all_material_params_in_material(material_instance)
    
    log_str = ""
    failed_textures = []
    for new_mat_param in new_mat_params:
        exist_mat_param = find_param_info_by_param_name(old_params, new_mat_param.parameter_name)
        if exist_mat_param is None:
            continue
        
        new_value_same_as_parent = has_same_value_as_parent(material_instance, new_mat_param.parameter_type, new_mat_param.parameter_name, new_mat_param.parameter_value)
        new_value_same_as_old_value = exist_mat_param["parameter_value"] == new_mat_param["parameter_value"]

        if not has_different_parent:
            if not new_mat_param.is_overriding_value and not exist_mat_param.is_overriding_value:
                continue
                
            if new_mat_param.is_overriding_value and exist_mat_param.is_overriding_value and new_value_same_as_old_value:
                continue
        
        if new_value_same_as_old_value and new_value_same_as_parent:
            continue
        
        if new_mat_param.parameter_type == EParameterType.TEXTURE:
            if not editor_asset_sub.does_asset_exist(new_mat_param.parameter_value):
                failed_textures.append([new_mat_param.parameter_name, new_mat_param.parameter_value, exist_mat_param.parameter_value.get_package().get_path_name()])
                continue
                
        set_param_value_of_type_in_material(material_instance, new_mat_param.parameter_type, new_mat_param.parameter_name, new_mat_param.parameter_value)
        log_str = "{} -[{}]{}: {} -> {}\n".format(log_str,
            new_mat_param.parameter_type.name, new_mat_param.parameter_name, exist_mat_param["parameter_value"], new_mat_param["parameter_value"])
        
        if (not has_different_parent and not new_mat_param.is_overriding_value) or (has_different_parent and new_value_same_as_parent):
            if new_mat_param.parameter_type != EParameterType.STATIC_SWITCH:
                overriding_param_values = get_override_param_values(material_instance, new_mat_param.parameter_type)
                for overriding_param_value in overriding_param_values:
                    if overriding_param_value.parameter_info.name == new_mat_param.parameter_name:
                        remove_override_param_value(material_instance, new_mat_param.parameter_type, overriding_param_value)
                        
    return log_str, failed_textures
    

def export_material_property_to_file(material_instance: unreal.MaterialInstanceConstant):
    # editor_asset_sub.save_loaded_asset(material_instance)
    
    material_params = get_all_material_params_in_material(material_instance)
    
    mat_property_pack = MaterialPropertyPack()
    mat_property_pack.mat_parameters = material_params
    
    mat_property_pack.material_package_path = str(material_instance.get_path_name())
    mat_property_pack.parent_material_package_path = str(material_instance.parent.get_path_name())
    
    real_path = sys_lib.get_system_path(material_instance)

    ti_m = os.path.getmtime(real_path)
    m_ti = time.ctime(ti_m)
    mat_property_pack.material_asset_file_last_modified_time = m_ti
    # TODO
    mat_property_pack.material_asset_p4_revision = ""

    json_str = mat_property_pack.serialize_to_json()

    folder_path = get_export_folder_path()
    export_file_path = os.path.join(folder_path, "{}_Parameters.json".format(material_instance.get_name()))
    with open(export_file_path, 'w') as output_file:
        output_file.write(json_str)
        
    return export_file_path


class SelectTextureWidget(QtWidgets.QWidget):
    def __init__(self, name, value, old_value, pre_search_value):
        super(SelectTextureWidget, self).__init__()
        vbox = QtWidgets.QVBoxLayout(self)
        self.setLayout(vbox)
        self.name = name

        layout = QtWidgets.QHBoxLayout()
        vbox.addLayout(layout)
        label = QtWidgets.QLabel("Select Texture For Parameter:  ")
        layout.addWidget(label)
        label = QtWidgets.QLabel(name)
        label.setStyleSheet(qt_style_preset.LABEL_NORMAL_HIGHLIGHT)
        layout.addWidget(label)
        layout.addStretch()
        label = QtWidgets.QLabel("Texture Path in material: {}".format(old_value))
        vbox.addWidget(label)
        label = QtWidgets.QLabel("Texture Path in file: {}".format(value))
        vbox.addWidget(label)
        layout = QtWidgets.QHBoxLayout()
        vbox.addLayout(layout)
        self.text_box = QtWidgets.QLineEdit(str(pre_search_value))
        layout.addWidget(self.text_box)
        btn = QtWidgets.QPushButton('')
        icon = QtGui.QIcon(os.path.join(path_util.qt_icon_path(), 'icon_arrow_left.png'))
        btn.setIcon(icon)
        btn.setStyleSheet("QPushButton { background-color: transparent }")
        btn.clicked.connect(self.on_click_content_browser_select_btn)
        btn.setMaximumWidth(32)
        layout.addWidget(btn)
    
    def on_click_content_browser_select_btn(self):
        selected_assets = editor_util_lib.get_selected_asset_data()
        if len(selected_assets) > 0:
            self.text_box.setText(str(selected_assets[0].package_name))
    
    def get_texture_path(self):
        return self.name, self.text_box.text()


class ManualSetTextureWindow(QtWidgets.QDialog):
    def __init__(self, failed_textures, material_instance):
        super(ManualSetTextureWindow, self).__init__()
        self.setWindowTitle("Failed Texture Settings")
        self.material_instance = material_instance

        presearch_textures = []
        try:
            material_path = material_instance.get_package().get_path_name()
            material_parent_folder = material_path[0: str(material_path).rindex("/")]
            material_parent_folder = material_parent_folder[0: str(material_parent_folder).rindex("/")]
    
            if editor_asset_sub.does_directory_exist(material_parent_folder):
                presearch_textures = asset_utils.get_assets_data_in_folder_by_class(material_parent_folder, unreal.Texture2D)
        except:
            pass
        
        vbox = QtWidgets.QVBoxLayout(self)
        self.setLayout(vbox)
        
        label = QtWidgets.QLabel("Cannot find below textures in content browser. Please set manually.")
        vbox.addWidget(label)
        
        self.texture_set_widgets = []
        for failed_texture in failed_textures:
            new_texture_name = failed_texture[1]
            new_texture_name = new_texture_name[new_texture_name.rindex("/") + 1:]
            presearch_texture_value = ""
            for presearch_texture in presearch_textures:
                if new_texture_name == presearch_texture.asset_name:
                    presearch_texture_value = presearch_texture.package_name
                    break
            
            print(presearch_texture_value)
            texture_widget = SelectTextureWidget(failed_texture[0], failed_texture[1], failed_texture[2], presearch_texture_value)
            vbox.addWidget(texture_widget)
            self.texture_set_widgets.append(texture_widget)

        h_layout = QtWidgets.QHBoxLayout()
        vbox.addLayout(h_layout)
        
        h_layout.addStretch()
        btn = QtWidgets.QPushButton("OK")
        btn.clicked.connect(self.on_click_ok_btn)
        h_layout.addWidget(btn)
        btn = QtWidgets.QPushButton("Cancel")
        btn.clicked.connect(self.on_click_cancel_btn)
        h_layout.addWidget(btn)

    def on_click_ok_btn(self):
        for texture_widget in self.texture_set_widgets:
            print(texture_widget.get_texture_path())
            name, value = texture_widget.get_texture_path()
            if editor_asset_sub.does_asset_exist(value):
                set_param_value_of_type_in_material(self.material_instance,
                                                    EParameterType.TEXTURE,
                                                    name,
                                                    editor_asset_sub.load_asset(value))
            
        unreal.PythonFunctionLibrary.force_refresh_material_instance(self.material_instance)
        self.close()
    
    def on_click_cancel_btn(self):
        self.close()


g_set_texture_window = None 


def import_material_property_from_file(material_instance: unreal.MaterialInstanceConstant):
    import_file_name = show_file_dialog()
    if import_file_name == '':
        return ''
    mat_property_pack = MaterialPropertyPack()
    mat_property_pack.deserialize_from_json_file(import_file_name)
    
    has_different_parent = False
    if mat_property_pack.parent_material_package_path != material_instance.parent.get_path_name():
        has_different_parent = True
        msg_box = QtWidgets.QMessageBox()
        msg_box.setText("""
The parent material of this instance is different from the parent instance in the text file. Continue?
Parent in text file    : {}
Parent of this instance: {}
        """.format(mat_property_pack.parent_material_package_path, material_instance.parent.get_path_name()))
        msg_box.setWindowTitle("Warning!")
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        button_n = msg_box.button(QtWidgets.QMessageBox.Cancel)
        msg_box.exec_()

        if msg_box.clickedButton() == button_n:
            return 
    
    log_str, failed_textures = set_material_params_in_material(material_instance, mat_property_pack.mat_parameters, has_different_parent)
    
    qt_util.pop_up_simple_messagebox("Import Result: \n{}".format(log_str), "Import Result")
    
    if len(failed_textures) > 0:
        global g_set_texture_window
        g_set_texture_window = ManualSetTextureWindow(failed_textures, material_instance)
        g_set_texture_window.show()
        unreal.parent_external_window_to_slate(g_set_texture_window.winId())
    
    unreal.PythonFunctionLibrary.force_refresh_material_instance(material_instance)
    # unreal.AssetToolsHelpers.get_asset_tools().open_editor_for_assets([material_instance])
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
                export_file = export_material_property_to_file(selected_asset_data.get_asset())
            elif operation_type == "Import":
                import_log = import_material_property_from_file(selected_asset_data.get_asset())
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
