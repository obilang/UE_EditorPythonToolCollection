from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import common_widgets
from AssetOperations import asset_section_widget
from LevelUtilities import spawn_assets_to_level
from typing import List
from AssetOperations import asset_utils
import unreal


import importlib
# 
# importlib.reload(asset_section_widget)
# importlib.reload(spawn_assets_to_level)
importlib.reload(asset_utils)

TEST_MESHES = [
    "/Game/Art/Environment/SM_A",
    "/Game/Art/Environment/SM_B"
]


editor_filter_lib = unreal.EditorFilterLibrary()
editor_asset_lib = unreal.EditorAssetLibrary()
EValidStat = asset_section_widget.EValidStat


# class TextureStat:
#     def __init__(self, name):
#         self.name = name
#         self.cached_materials = set()
#         self.cached_textures = set()


class TextureSectionData(asset_section_widget.AssetSectionData):
    def __init__(self, name, asset_paths):
        super(TextureSectionData, self).__init__(name)
        self.asset_paths = asset_paths
        self.asset_detail = {}
        self.init_display_properties(["Width",
                                      "Height",
                                      "Compression",
                                      "TextureGroup",
                                      "NeverStream",
                                      "LODBias",
                                      "HasAlphaChannel",
                                      "VT",
                                      "Path"
                                      ])

    def find_valid_assets(self):
        self.assets = []
        for asset_path in self.asset_paths:
            if editor_asset_lib.does_asset_exist(asset_path):
                asset_data = editor_asset_lib.find_asset_data(asset_path)
                if asset_utils.get_asset_data_class(asset_data.package_name) == "Texture2D":
                    self.assets.append(asset_data)
                    # self.asset_detail[asset_data] = MeshStat(asset_data.package_name)
        return self.assets

    def get_property_value(self, asset: unreal.AssetData, property_name):
        result = None
        # asset_detail = self.asset_detail[asset]
        texture_obj = editor_asset_lib.load_asset(asset.package_name)
        try:
            pass
        except:
            # print("cannot find editor property")
            pass
        else:
            if property_name == "Width":
                valid_stat = EValidStat.VALID
                width = asset_utils.get_texture_in_game_width(texture_obj)
                if width > 4096:
                    valid_stat = EValidStat.INVALID
                return width, valid_stat
            elif property_name == "Height":
                valid_stat = EValidStat.VALID
                height = asset_utils.get_texture_in_game_height(texture_obj)
                if height > 4096:
                    valid_stat = EValidStat.INVALID
                return height, valid_stat
            elif property_name == "Compression":
                valid_stat = EValidStat.VALID
                compression = texture_obj.get_editor_property("compression_settings")
                if compression != unreal.TextureCompressionSettings.TC_HDR_COMPRESSED and \
                    compression != unreal.TextureCompressionSettings.TC_DEFAULT and \
                    compression != unreal.TextureCompressionSettings.TC_NORMALMAP and \
                    compression != unreal.TextureCompressionSettings.TC_MASKS and \
                    compression != unreal.TextureCompressionSettings.TC_BC7:
                    valid_stat = EValidStat.INVALID
                return compression, valid_stat
            elif property_name == "NeverStream":
                valid_stat = EValidStat.VALID
                never_stream = asset.get_tag_value("NeverStream")
                if never_stream == "True":
                    valid_stat = EValidStat.INVALID
                return never_stream, valid_stat
            elif property_name == "HasAlphaChannel":
                valid_stat = EValidStat.VALID
                has_alpha_channel = asset.get_tag_value("HasAlphaChannel")
                if has_alpha_channel == "True":
                    valid_stat = EValidStat.INVALID_STRICT
                return has_alpha_channel, EValidStat.VALID
            elif property_name == "VT":
                vt = asset.get_tag_value("VirtualTextureStreaming")
                return vt, EValidStat.VALID
            elif property_name == "Path":
                asset_path = asset.package_name
                return asset_path, EValidStat.VALID
            elif property_name == "TextureGroup":
                valid_stat = EValidStat.VALID
                group = texture_obj.get_editor_property("lod_group")
                if group == unreal.TextureGroup.TEXTUREGROUP_UI:
                    valid_stat = EValidStat.INVALID
                return group, valid_stat
            elif property_name == "LODBias":
                valid_stat = EValidStat.VALID
                bias = texture_obj.get_editor_property("lod_bias")
                if bias > 0:
                    valid_stat = EValidStat.INVALID
                return bias, valid_stat

        return str(result), EValidStat.VALID


class TextureStatWidget(QtWidgets.QWidget):
    def __init__(self):
        super(TextureStatWidget, self).__init__()

        vbox = QtWidgets.QVBoxLayout(self)
        self.setLayout(vbox)

        # doc_widget = common_widgets.DocumentLinkBar(DOC_URL)
        # vbox.addWidget(doc_widget)

        self.spawn_assets_widget = spawn_assets_to_level.SpawnAssetWidget()
        self.spawn_assets_widget.add_event_listener("AssetListChanged", self.on_asset_list_changed)
        vbox.addWidget(self.spawn_assets_widget)

        self.common_assets_data = TextureSectionData("Meshes", TEST_MESHES)
        common_assets_widget = asset_section_widget.AssetSectionWidget(self.common_assets_data)
        vbox.addWidget(common_assets_widget)

    def on_asset_list_changed(self, asset_paths: List[str]):
        self.common_assets_data.asset_paths = asset_paths
