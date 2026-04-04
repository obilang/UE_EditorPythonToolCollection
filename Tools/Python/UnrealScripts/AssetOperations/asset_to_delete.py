from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import common_widgets
from AssetOperations import asset_section_widget
from LevelUtilities import spawn_assets_to_level
from typing import List
import unreal
from AssetOperations import asset_utils

# import importlib
# 
# importlib.reload(asset_utils)
# importlib.reload(spawn_assets_to_level)

TEST_MESHES = [
  
]

EValidStat = asset_section_widget.EValidStat




editor_asset_subsystem = unreal.EditorAssetSubsystem()


class AssetNoRef(asset_section_widget.CommonAssetSectionData):
    def find_valid_assets(self):
        self.assets = []
        for asset_path in self.asset_paths:
            if editor_asset_subsystem.does_asset_exist(asset_path):
                refs = editor_asset_subsystem.find_package_referencers_for_asset(asset_path)
                if len(refs) == 0:
                    self.assets.append(editor_asset_subsystem.find_asset_data(asset_path))
        return self.assets
    


class AssetNoRefWidget(QtWidgets.QWidget):
    def __init__(self):
        super(AssetNoRefWidget, self).__init__()

        vbox = QtWidgets.QVBoxLayout(self)
        self.setLayout(vbox)

        # doc_widget = common_widgets.DocumentLinkBar(DOC_URL)
        # vbox.addWidget(doc_widget)

        self.spawn_assets_widget = spawn_assets_to_level.SpawnAssetWidget()
        self.spawn_assets_widget.add_event_listener("AssetListChanged", self.on_asset_list_changed)
        vbox.addWidget(self.spawn_assets_widget)

        self.common_assets_data = AssetNoRef("Assets", TEST_MESHES)
        common_assets_widget = asset_section_widget.AssetSectionWidget(self.common_assets_data)
        vbox.addWidget(common_assets_widget)

    def on_asset_list_changed(self, asset_paths: List[str]):
        self.common_assets_data.asset_paths = asset_paths

