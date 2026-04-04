from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import common_widgets
from AssetOperations import asset_section_widget
from LevelUtilities import spawn_assets_to_level
from typing import List

# import importlib
# importlib.reload(asset_section_widget)
# importlib.reload(spawn_assets_to_level)

TEST_MESHES = [

]

DOC_URL = "https://"


class AssetP4StatWidget(QtWidgets.QWidget):
    def __init__(self):
        super(AssetP4StatWidget, self).__init__()

        vbox = QtWidgets.QVBoxLayout(self)
        self.setLayout(vbox)
        
        doc_widget = common_widgets.DocumentLinkBar(DOC_URL)
        vbox.addWidget(doc_widget)
        
        self.spawn_assets_widget = spawn_assets_to_level.SpawnAssetWidget()
        self.spawn_assets_widget.add_event_listener("AssetListChanged", self.on_asset_list_changed)
        vbox.addWidget(self.spawn_assets_widget)
        
        self.common_assets_data = asset_section_widget.CommonAssetSectionData("Assets", TEST_MESHES)
        common_assets_widget = asset_section_widget.AssetSectionWidget(self.common_assets_data)
        vbox.addWidget(common_assets_widget)
    
    def on_asset_list_changed(self, asset_paths: List[str]):
        self.common_assets_data.asset_paths = asset_paths
