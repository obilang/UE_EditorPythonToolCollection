import sys
import unreal

from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import qt_util
from LevelUtilities import level_actor_filter
from LevelUtilities import level_actor_overview
# from LevelUtilities import mark_asset_to_be_delete
from LevelUtilities import level_collision_checker
# from AssetOperations import override_materials
from LevelUtilities import find_decal_texture
from LevelUtilities import find_static_mesh_actor

# import importlib
# importlib.reload(override_materials)
# importlib.reload(level_actor_filter)
# importlib.reload(mark_asset_to_be_delete)
# importlib.reload(level_collision_checker)


WINDOW_TITLE = "Level Tools"
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 900


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
        level_actor_filter_tab = level_actor_filter.LevelActorFilterWidget()
        level_actor_filter_tab.adjustSize()
        tabs.addTab(level_actor_filter_tab, "Actor Validation")
               
        level_actor_overview_tab = level_actor_overview.LevelActorOverviewWidget()
        level_actor_overview_tab.adjustSize()
        tabs.addTab(level_actor_overview_tab, "Actor Overview")

        collision_info_tab = level_collision_checker.CollisionInfoWidget()
        collision_info_tab.adjustSize()
        tabs.addTab(collision_info_tab, "Collision Info")

        # mark_asset_tab = mark_asset_to_be_delete.MarkDeprecatedWidget()
        # mark_asset_tab.adjustSize()
        # tabs.addTab(mark_asset_tab, "Mark Deprecated Assets")
        
        # override_mat_asset_tab = override_materials.OverrideMatWidget()
        # override_mat_asset_tab.adjustSize()
        # tabs.addTab(override_mat_asset_tab, "Override Materials")
        
        find_decal_asset_tab = find_decal_texture.FindDecalWidget()
        find_decal_asset_tab.adjustSize()
        tabs.addTab(find_decal_asset_tab, "Find Decal Texture")
        
        find_mesh_asset_tab = find_static_mesh_actor.FindMeshActorWidget()
        find_mesh_asset_tab.adjustSize()
        tabs.addTab(find_mesh_asset_tab, "Find Meshes")

        
if __name__ == "__main__":
    app = qt_util.create_qt_application()

    widget = MainScriptWindow()
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())