import sys
import unreal

from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import qt_util
from QtUtil import common_widgets
import path_util
import os
from MemoryReport import memory_report_analysis
import subprocess

from Materials import material_parameter_checker

import importlib

importlib.reload(material_parameter_checker)
# importlib.reload(path_util)
# importlib.reload(qt_util)
# importlib.reload(common_widgets)

WINDOW_TITLE = "Material Parameter Checker"
WINDOW_MIN_WIDTH = 800
WINDOW_MIN_HEIGHT = 600
DOC_URL = "https://"


OUTPUT_JSON_FOLDER = "MaterialParameters"


def get_export_folder_path():
    export_folder = path_util.tool_output_temp_folder()
    export_folder = os.path.join(export_folder, OUTPUT_JSON_FOLDER)
    export_folder = os.path.realpath(export_folder)
    if not os.path.isdir(export_folder):
        os.makedirs(export_folder)
    return export_folder


def log_result_to_file(param_name, results):
    result_str = ""
    for result_path, result_info in results.items():
        for mat_info in result_info:
            para_info = mat_info[0]
            para_value = mat_info[1]
            if isinstance(para_value, unreal.LinearColor):
                para_value = '"({:.2f},{:.2f},{:.2f},{:.2f})"'.format(para_value.r, para_value.g, para_value.b, para_value.a)
            if isinstance(para_value, unreal.Texture2D):
                para_value = para_value.get_package().get_name()
            result_str = "{}{},{},{}\n".format(result_str, result_path, para_info.index, para_value)
    
    param_name_out = ''.join(e for e in param_name if e.isalnum())
    export_file_path = os.path.join(get_export_folder_path(), "Modified_{}.csv".format(param_name_out))
    with open(export_file_path, 'w') as output_file:
        output_file.write(result_str)
    return export_file_path
        

class MainScriptWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(MainScriptWindow, self).__init__(parent)

        # window setup 
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(WINDOW_MIN_WIDTH)
        self.setMinimumHeight(WINDOW_MIN_HEIGHT)
        self.setAcceptDrops(True)

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.build_ui()
        # align all widget to top
        self.main_layout.addStretch()

    def build_ui(self):
        doc_widget = common_widgets.DocumentLinkBar(DOC_URL)
        self.main_layout.addWidget(doc_widget)

        label = QtWidgets.QLabel("Base Material Path: (exp. '/Game/Art/Materials/M_Replace_Material.M_Replace_Material'")
        self.main_layout.addWidget(label)
        self.mat_path_text_box = QtWidgets.QLineEdit('/Game/Art/Materials/Environmental_Material/Base_Master_Material/LayeredMaterial/M_LayeredMaterial_Base.M_LayeredMaterial_Base')
        self.mat_path_text_box.setDragEnabled(True)
        
        self.main_layout.addWidget(self.mat_path_text_box)

        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)

        label = QtWidgets.QLabel("Parameter Name: ")
        h_layout.addWidget(label)
        self.parm_name_text_box = QtWidgets.QLineEdit('Base Color Tint')
        h_layout.addWidget(self.parm_name_text_box)

        h_layout.addStretch()
        
        label = QtWidgets.QLabel("Parameter Type: ")
        h_layout.addWidget(label)
        self.para_type_cb = QtWidgets.QComboBox()
        self.para_type_cb.addItem(material_parameter_checker.EParameterType.SCALAR.value, 
                                  material_parameter_checker.EParameterType.SCALAR)
        self.para_type_cb.addItem(material_parameter_checker.EParameterType.STATIC_SWITCH.value,
                                  material_parameter_checker.EParameterType.STATIC_SWITCH)
        self.para_type_cb.addItem(material_parameter_checker.EParameterType.TEXTURE.value,
                                  material_parameter_checker.EParameterType.TEXTURE)
        self.para_type_cb.addItem(material_parameter_checker.EParameterType.VECTOR.value,
                                  material_parameter_checker.EParameterType.VECTOR)
        h_layout.addWidget(self.para_type_cb)
        
        
        label = QtWidgets.QLabel("Static Switch Value: ")
        h_layout.addWidget(label)
        self.static_switch_value_cb = QtWidgets.QCheckBox()
        self.static_switch_value_cb.setChecked(True)
        h_layout.addWidget(self.static_switch_value_cb)
        
        h_layout.addStretch()
        
        label = QtWidgets.QLabel("Parameter Place: ")
        h_layout.addWidget(label)
        self.para_place_cb = QtWidgets.QComboBox()
        self.para_place_cb.addItem("Global(Default)", unreal.MaterialParameterAssociation.GLOBAL_PARAMETER.value)
        self.para_place_cb.addItem("Layer", unreal.MaterialParameterAssociation.LAYER_PARAMETER.value)
        self.para_place_cb.addItem("Blend", unreal.MaterialParameterAssociation.BLEND_PARAMETER.value)
        h_layout.addWidget(self.para_place_cb)
        
        btn = QtWidgets.QPushButton('Search')
        btn.clicked.connect(self.on_click_search_btn)
        self.main_layout.addWidget(btn)
        
        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)
        self.export_path_le = QtWidgets.QLineEdit('Export File:')
        self.export_path_le.setEnabled(False)
        h_layout.addWidget(self.export_path_le)
        btn = QtWidgets.QPushButton('Open Export CSV Folder')
        btn.clicked.connect(self.on_click_open_folder_btn)
        h_layout.addWidget(btn)

        self.result_layout = QtWidgets.QVBoxLayout()
        self.container_widget = QtWidgets.QGroupBox('Result:')
        self.container_widget.setLayout(self.result_layout)
        
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidget(self.container_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedHeight(600)
        self.main_layout.addWidget(scroll_area)

    def on_click_search_btn(self):
        base_mat_path = self.mat_path_text_box.text()
        para_name = self.parm_name_text_box.text()
        para_type = self.para_type_cb.currentData()
        para_place = self.para_place_cb.currentData()
        static_switch_value = self.static_switch_value_cb.isChecked()
        
        mat_results = material_parameter_checker.check_parameter_value_in_child_instances(
            base_mat_path, para_name, para_type, static_switch_value, para_place
        )
        # print(mat_results)
        self.update_search_results(mat_results)
        
        file_path = log_result_to_file(para_name, mat_results)
        self.export_path_le.setText(file_path)
        
    def update_search_results(self, mat_results):
        qt_util.clear_qt_layout(self.result_layout)
        for mat_path, mat_info in mat_results.items():
            result_widget = SearchResultWidget(mat_path, mat_info)
            self.result_layout.addWidget(result_widget)
        self.result_layout.addStretch()
        
    def on_click_open_folder_btn(self):
        subprocess.Popen(r'explorer /select,{}'.format(self.export_path_le.text()))


class SearchResultWidget(QtWidgets.QWidget):
    def __init__(self, math_path, mat_infos):
        super(SearchResultWidget, self).__init__()
        self.mat_path = math_path
        self.mat_infos = mat_infos

        self.__build_ui()

    def __build_ui(self):
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        
        h_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(h_layout)
        self.text_box = QtWidgets.QLineEdit(self.mat_path)
        h_layout.addWidget(self.text_box)
        browse_button = QtWidgets.QPushButton('Find In Content Browser')
        h_layout.addWidget(browse_button)
        browse_button.clicked.connect(self.on_click_browse_btn)
        
        for mat_info in self.mat_infos:
            para_info = mat_info[0]
            para_value = mat_info[1]
            label = QtWidgets.QLabel(
                "\t\tIndex {}:  {}".format(para_info.index, para_value)
            )
            self.layout.addWidget(label)
        
        self.layout.addStretch()
            
    def on_click_browse_btn(self):
        unreal.EditorAssetLibrary.sync_browser_to_objects([self.mat_path])


if __name__ == "__main__":
    app = qt_util.create_qt_application()

    widget = MainScriptWindow()
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())