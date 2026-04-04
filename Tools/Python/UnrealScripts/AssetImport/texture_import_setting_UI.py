import sys
import unreal
import re

from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import qt_util
from AssetImport import texture_import_setting
from QtUtil import qt_style_preset

import importlib
importlib.reload(texture_import_setting)

WINDOW_TITLE = "Texture Import"
WINDOW_MIN_WIDTH = 400
WINDOW_MIN_HEIGHT = 600


asset_editor_sub = unreal.AssetEditorSubsystem()
editor_asset_lib = unreal.EditorAssetLibrary()


def is_power_of_two(number):
    return number != 0 and (number & (number - 1)) == 0


def get_texture_width_height(texture_path):
    texture_asset_data = editor_asset_lib.find_asset_data(texture_path)
    dimensions = texture_asset_data.get_tag_value("dimensions")
    size = dimensions.split("x")
    return int(size[0]), int(size[1])


class MainScriptWindow(QtWidgets.QDialog):
    def __init__(self, texture_path):
        super(MainScriptWindow, self).__init__(None)
        self.texture_path = texture_path
        self._init_data()
        
        # window setup 
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(WINDOW_MIN_WIDTH)
        self.setMinimumHeight(WINDOW_MIN_HEIGHT)

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self._build_ui()
        # align all widget to top
        self.main_layout.addStretch()
        
    def _init_data(self):
        self.texture_obj = editor_asset_lib.load_asset(texture_path)
        texture_name = str(self.texture_obj.get_name())
        
        self.all_texture_settings = texture_import_setting.get_texture_import_settings()
        self.smart_type = None
        for texture_setting in self.all_texture_settings:
            # print(texture_setting.pattern)
            result = re.search(texture_setting.pattern, texture_name.lower())
            if result:
                # print(result)
                # print(result.group(0))
                self.smart_type = texture_setting.id
                break

    def _build_ui(self):
        label = QtWidgets.QLabel("Texture: {}".format(self.texture_path))
        self.main_layout.addWidget(label)
        
        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)

        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)

        label = QtWidgets.QLabel("Select Texture Group: ")
        h_layout.addWidget(label)

        self.texture_group_combobox = QtWidgets.QComboBox()
        self.texture_group_combobox.addItem("Environment", "Environment")
        if "/Art/Environment/" in self.texture_path:
            self.texture_group_combobox.setCurrentIndex(0)
        self.texture_group_combobox.addItem("Character", "Character")
        if "/Art/Character/" in self.texture_path:
            self.texture_group_combobox.setCurrentIndex(1)
        self.texture_group_combobox.addItem("VFX", "VFX")
        if "/Art/VFX/" in self.texture_path:
            self.texture_group_combobox.setCurrentIndex(2)
        h_layout.addWidget(self.texture_group_combobox)
        
        label = QtWidgets.QLabel("Select Texture Type: ")
        h_layout.addWidget(label)
        
        self.texture_type_combobox = QtWidgets.QComboBox()
        index = 0
        target_index = index
        for texture_setting in self.all_texture_settings:
            if texture_setting.id == self.smart_type:
                target_index = index
            self.texture_type_combobox.addItem(texture_setting.name, texture_setting)
            index += 1
        self.texture_type_combobox.setCurrentIndex(target_index)
        self.texture_type_combobox.currentIndexChanged.connect(self.on_texture_type_cb_changed)
        h_layout.addWidget(self.texture_type_combobox)
        
        self.texture_type_detail_label = QtWidgets.QPlainTextEdit("")
        self.main_layout.addWidget(self.texture_type_detail_label)

        self.warning_label = QtWidgets.QPlainTextEdit("")
        self.warning_label.setStyleSheet(qt_style_preset.LABEL_WARNING)
        self.main_layout.addWidget(self.warning_label)
        
        self.on_texture_type_cb_changed(0)

        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)
        self.rename_cb = QtWidgets.QCheckBox("Rename Texture: ")
        self.rename_cb.setChecked(False)
        h_layout.addWidget(self.rename_cb)
        texture_name = str(self.texture_obj.get_name())
        suggest_name = texture_name.replace("_MTL_", "")
        suggest_name = suggest_name.replace("_SM_", "")
        if not suggest_name.startswith("T_"):
            suggest_name = "T_{}".format(suggest_name)
        self.rename_to_le = QtWidgets.QLineEdit(suggest_name)
        h_layout.addWidget(self.rename_to_le)
        
        self.enable_VT_cb = QtWidgets.QCheckBox("Enable VT")
        self.enable_VT_cb.setChecked(False)
        self.main_layout.addWidget(self.enable_VT_cb)
        
        # label = QtWidgets.QLabel()
        # label.setOpenExternalLinks(True)
        # label.setText(qt_util.get_hyper_link_txt(TEXTURE_SETTING_LINK, "Texture Setting Guild Doc"))
        # self.main_layout.addWidget(label)
        # label = QtWidgets.QLabel()
        # label.setOpenExternalLinks(True)
        # label.setText(qt_util.get_hyper_link_txt(TEXTURE_SETTING_CHARCHER_LINK, "Texture Setting Guild Doc (Character)"))
        # self.main_layout.addWidget(label)
        
        btn = QtWidgets.QPushButton('OK')
        btn.clicked.connect(self.on_click_btn)
        self.main_layout.addWidget(btn)

    def on_click_btn(self):
        texture_setting = self.texture_type_combobox.currentData()
        texture_group = self.texture_group_combobox.currentData()
        target_group = unreal.TextureGroup.TEXTUREGROUP_WORLD
        if texture_group == "Environment":
            if texture_setting.name == "Normal":
                target_group = unreal.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP
            elif texture_setting.id == "MRO":
                target_group = unreal.TextureGroup.TEXTUREGROUP_WORLD_SPECULAR
            else:
                target_group = unreal.TextureGroup.TEXTUREGROUP_WORLD
        elif texture_group == "Character":
            if texture_setting.name == "Normal":
                target_group = unreal.TextureGroup.TEXTUREGROUP_CHARACTER_NORMAL_MAP
            elif texture_setting.id == "MRO":
                target_group = unreal.TextureGroup.TEXTUREGROUP_CHARACTER_SPECULAR
            else:
                target_group = unreal.TextureGroup.TEXTUREGROUP_CHARACTER
        elif texture_group == "VFX":
            target_group = unreal.TextureGroup.TEXTUREGROUP_EFFECTS
            
        texture_import_setting.set_texture_as(self.texture_obj, texture_setting, target_group)
        self.texture_obj.set_editor_property("virtual_texture_streaming", self.enable_VT_cb.isChecked())

        if self.rename_cb.isChecked():
            texture_data = editor_asset_lib.find_asset_data(self.texture_obj.get_path_name())
            editor_asset_lib.rename_asset(self.texture_obj.get_path_name(),
                                          "{}/{}.{}".format(texture_data.package_path, self.rename_to_le.text(), self.rename_to_le.text()))
        
        editor_asset_lib.save_asset(self.texture_obj.get_path_name())

        self.close()
        
    def on_texture_type_cb_changed(self, index):
        texture_setting = self.texture_type_combobox.currentData()
        self.texture_type_detail_label.setPlainText(texture_setting.description)
        self.update_warning_text()
        
    def update_warning_text(self):
        suggest_max_size = 4096
        texture_setting = self.texture_type_combobox.currentData()
        texture_group = self.texture_group_combobox.currentData()
        if texture_setting.id == "Mask" or texture_setting.id == "MRO":
            suggest_max_size = 2048
        if texture_setting.id == "Normal":
            if texture_group == "Environment":
                suggest_max_size = 2048
        
        texture_width, texture_height = get_texture_width_height(self.texture_path)
        self.warning_label.setStyleSheet(qt_style_preset.LABEL_WARNING)
        WARNING_TXT = ""
        if texture_width > suggest_max_size or texture_height > suggest_max_size:
            WARNING_TXT = "{}-Texture Size is larger than {}. Are you sure????? {}x{}\n".format(WARNING_TXT, suggest_max_size, texture_width, texture_height)
        
        if texture_setting.id not in ["PosMap", "PivotPainter_PivotPos", "PivotPainter_XVector"]:
            if not is_power_of_two(texture_width) or not is_power_of_two(texture_height):
                WARNING_TXT = "{}-Texture Not Power Of Two {}x{}\n".format(WARNING_TXT, texture_width, texture_height)
            self.warning_label.setStyleSheet(qt_style_preset.LABEL_ERROR)
                
        self.warning_label.setPlainText(WARNING_TXT)


if __name__ == "__main__":
    app = qt_util.create_qt_application()
    
    texture_path = sys.argv[1]
    
    widget = MainScriptWindow(texture_path)
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())