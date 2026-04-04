import sys
import unreal

from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import qt_util
from LevelUtilities import spawn_assets_to_level
from typing import List 
from AssetOperations import set_mesh_mat_param_values

# import importlib
# 
# importlib.reload(set_mesh_mat_param_values)
# importlib.reload(asset_to_delete)
editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


WINDOW_TITLE = "Set Camera Fade"
WINDOW_MIN_WIDTH = 800
WINDOW_MIN_HEIGHT = 950


class MainScriptWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(MainScriptWindow, self).__init__(parent)

        # window setup 
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(WINDOW_MIN_WIDTH)
        self.setMinimumHeight(WINDOW_MIN_HEIGHT)

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self._build_ui()
        # align all widget to top
        # self.main_layout.addStretch()
        self.asset_paths = []

    def _build_ui(self):
        self.spawn_assets_widget = spawn_assets_to_level.SpawnAssetWidget()
        self.spawn_assets_widget.add_event_listener("AssetListChanged", self.on_asset_list_changed)
        self.main_layout.addWidget(self.spawn_assets_widget)
        
        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Camera Fade Near: ")
        h_layout.addWidget(label)
        self.camera_fade_near_value_le = QtWidgets.QLineEdit("20")
        h_layout.addWidget(self.camera_fade_near_value_le)
        
        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Camera Fade Far: ")
        h_layout.addWidget(label)
        self.camera_fade_far_value_le = QtWidgets.QLineEdit("100")
        h_layout.addWidget(self.camera_fade_far_value_le)

        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Camera Fade Near First Person View: ")
        h_layout.addWidget(label)
        self.camera_fade_near_fp_value_le = QtWidgets.QLineEdit("60")
        h_layout.addWidget(self.camera_fade_near_fp_value_le)

        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Camera Fade Far First Person View: ")
        h_layout.addWidget(label)
        self.camera_fade_far_fp_value_le = QtWidgets.QLineEdit("150")
        h_layout.addWidget(self.camera_fade_far_fp_value_le)
        
        btn = QtWidgets.QPushButton('Set Values')
        btn.clicked.connect(self.on_click_btn)
        self.main_layout.addWidget(btn)
        
    def on_asset_list_changed(self, asset_paths: List[str]):
        self.asset_paths = asset_paths
        
    def on_click_btn(self):
        near_value = float(self.camera_fade_near_value_le.text())
        far_value = float(self.camera_fade_far_value_le.text())
        near_value_fp = float(self.camera_fade_near_fp_value_le.text())
        far_value_fp = float(self.camera_fade_far_fp_value_le.text())
        
        param_pair = {
            "Camera Fade Near Distance": near_value,
            "Camera Fade Far Distance": far_value,
            "Camera Fade Near Distance First Person View": near_value_fp,
            "Camera Fade Far Distance First Person View": far_value_fp
        }
        
        for asset_path in self.asset_paths:
            mesh = editor_asset_sub.load_asset(asset_path)
            if isinstance(mesh, unreal.StaticMesh):
                set_mesh_mat_param_values.set_mat_scalar_param_for_mesh(mesh, param_pair)


if __name__ == "__main__":
    app = qt_util.create_qt_application()

    widget = MainScriptWindow()
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())