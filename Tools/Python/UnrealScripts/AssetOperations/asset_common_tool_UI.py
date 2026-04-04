import sys
import unreal

from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import qt_util
from AssetOperations import asset_p4_stat
from AssetOperations import mesh_stat
from AssetOperations import texture_stat
from AssetOperations import asset_to_delete
from AssetOperations import asset_tags

import importlib

importlib.reload(asset_tags)
# importlib.reload(texture_stat)
# importlib.reload(asset_to_delete)


WINDOW_TITLE = "Asset Tools"
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
        self.build_ui()
        # align all widget to top
        # self.main_layout.addStretch()

    def build_ui(self):
        # Initialize tab screen
        tabs = QtWidgets.QTabWidget()
        # tabs.resize(300, 200)
        self.main_layout.addWidget(tabs)
        # Add tabs
        asset_p4_stat_tab = asset_p4_stat.AssetP4StatWidget()
        asset_p4_stat_tab.adjustSize()
        tabs.addTab(asset_p4_stat_tab, "Asset P4")

        mesh_stat_tab = mesh_stat.MeshStatWidget()
        mesh_stat_tab.adjustSize()
        tabs.addTab(mesh_stat_tab, "Mesh Stat")

        tab = asset_to_delete.AssetNoRefWidget()
        tab.adjustSize()
        tabs.addTab(tab, "No Ref")

        tab = asset_to_delete.AssetRefCountWidget()
        tab.adjustSize()
        tabs.addTab(tab, "Use In Game")

        texture_stat_tab = texture_stat.TextureStatWidget()
        texture_stat_tab.adjustSize()
        tabs.addTab(texture_stat_tab, "Texture Stat")
        
        asset_tags_tab = asset_tags.AssetTagsWidget()
        asset_tags_tab.adjustSize()
        tabs.addTab(asset_tags_tab, "Asset Tags")


if __name__ == "__main__":
    app = qt_util.create_qt_application()

    widget = MainScriptWindow()
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())