import sys
import unreal

from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import qt_util
import global_config


import importlib
importlib.reload(global_config)

WINDOW_TITLE = "Python Tool Config"
WINDOW_MIN_WIDTH = 600
WINDOW_MIN_HEIGHT = 800

system_lib = unreal.SystemLibrary()
editor_world = unreal.UnrealEditorSubsystem().get_editor_world()


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
        self.main_layout.addStretch()

    def _build_ui(self):
        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)

        label = QtWidgets.QLabel("Enable Import Hook")
        h_layout.addWidget(label)
        h_layout.addStretch()

        self.import_hook_cb = QtWidgets.QCheckBox()
        self.import_hook_cb.setChecked(global_config.GLOBAL_CONFIG.enable_import_hook)
        h_layout.addWidget(self.import_hook_cb)
        
        btn = QtWidgets.QPushButton("Save Config")
        btn.clicked.connect(self.update_config_file)
        self.main_layout.addWidget(btn)
    
    def update_config_file(self):
        global_config.GLOBAL_CONFIG.enable_import_hook = self.import_hook_cb.isChecked()
        global_config.GLOBAL_CONFIG.save_to_file()
        qt_util.pop_up_simple_messagebox("Update Succeeded. Please restart the editor.", "Message")
        self.close()


if __name__ == "__main__":
    app = qt_util.create_qt_application()

    widget = MainScriptWindow()
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())