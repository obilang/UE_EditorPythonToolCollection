from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import common_widgets
from AssetOperations import asset_section_widget
from LevelUtilities import spawn_assets_to_level
from typing import List
from AssetOperations import asset_utils
from Materials import material_utils
import unreal

# import importlib
# 
# importlib.reload(asset_section_widget)
# importlib.reload(spawn_assets_to_level)
# importlib.reload(asset_utils)

TEST_MESHES = [

]

editor_filter_lib = unreal.EditorFilterLibrary()
editor_asset_lib = unreal.EditorAssetLibrary()
EValidStat = asset_section_widget.EValidStat


class MeshStat:
    def __init__(self, name):
        self.name = name
        self.cached_materials = set()
        self.cached_textures = set()


class MeshSectionData(asset_section_widget.AssetSectionData):
    def __init__(self, name, asset_paths):
        super(MeshSectionData, self).__init__(name)
        self.asset_paths = asset_paths
        self.asset_detail = {}
        self.init_display_properties(["approx_size(m)", 
                                      "Vertices",
                                      "Triangles",
                                      "used_material_counts", 
                                      "used_layer_materials", 
                                      "used_texture_counts", 
                                      "used_texture_size(MB)", 
                                      "nanite_mask",
                                      "DistanceFieldSize",
                                      "EstNaniteCompressedSize"
                                      ])

    def find_valid_assets(self):
        self.assets = []
        for asset_path in self.asset_paths:
            if editor_asset_lib.does_asset_exist(asset_path):
                asset_data = editor_asset_lib.find_asset_data(asset_path)
                if asset_utils.get_asset_data_class(asset_data.package_name) == "StaticMesh":
                    self.assets.append(asset_data)
                    self.asset_detail[asset_data] = MeshStat(asset_data.package_name)
        return self.assets

    def get_property_value(self, asset: unreal.AssetData, property_name):
        result = None
        asset_detail = self.asset_detail[asset]
        try:
            pass
        except:
            # print("cannot find editor property")
            pass
        else:
            if property_name == "used_material_counts":
                mats = asset_utils.get_assets_depend_on(asset.package_name, 0, unreal.MaterialInstanceConstant,
                                                          [unreal.Material])
                for mat in mats:
                    if editor_asset_lib.does_asset_exist(mat):
                        asset_detail.cached_materials.add(editor_asset_lib.find_asset_data(mat))
                result = len(asset_detail.cached_materials)
            elif property_name == "used_layer_materials":
                layered_mi = set()
                for cached_material in asset_detail.cached_materials:
                    base_mat = material_utils.get_base_material(cached_material)
                    if base_mat is not None and base_mat.asset_name == "M_LayeredMaterial_Base":
                        layered_mi.add(cached_material)
                result = len(layered_mi)
            elif property_name == "used_texture_counts":
                textures = asset_utils.get_assets_depend_on(asset.package_name, 2, unreal.Texture2D,
                                                        [unreal.Material, unreal.MaterialFunctionMaterialLayerInstance])
                for texture in textures:
                    if editor_asset_lib.does_asset_exist(texture):
                        asset_detail.cached_textures.add(editor_asset_lib.find_asset_data(texture))
                result = len(asset_detail.cached_textures)
            elif property_name == "used_texture_size(MB)":
                approximate_size = 0
                for texture in asset_detail.cached_textures:
                    texture_obj = editor_asset_lib.load_asset(texture.package_name)
                    approximate_size = approximate_size + material_utils.get_approximate_memory_size(texture_obj)
                return "{:.2f}".format(approximate_size / 1024), EValidStat.VALID
            elif property_name == "approx_size(m)":
                approximate_size = asset.get_tag_value("ApproxSize")
                size_single = approximate_size.split('x')
                average_size = (int(size_single[0]) + int(size_single[1]) + int(size_single[2])) / 3
                return "{:.2f}".format(average_size / 100), EValidStat.VALID
            elif property_name == "nanite_mask":
                is_nanite = asset.get_tag_value("NaniteEnabled")
                result = "Not Nanite"
                valid_stat = EValidStat.VALID
                if is_nanite == "True":
                    result = "Nanite Opaque"
                    for cached_material in asset_detail.cached_materials:
                        mat_obj = editor_asset_lib.load_asset(cached_material.package_name)
                        blend_mode = mat_obj.get_blend_mode()
                        if blend_mode != unreal.BlendMode.BLEND_OPAQUE:
                            if blend_mode == unreal.BlendMode.BLEND_MASKED:
                                result = "Nanite Mask"
                                valid_stat = EValidStat.INVALID_STRICT
                            else:
                                result = "Nanite Transparent"
                                valid_stat = EValidStat.INVALID
                        
                        two_side = mat_obj.get_editor_property("base_property_overrides").get_editor_property("two_sided")
                        if two_side:
                            result = "{} {}".format(result, "Two Side")
                            if valid_stat != EValidStat.INVALID:
                                valid_stat = EValidStat.INVALID_STRICT
            elif property_name == "Vertices":
                valid_stat = EValidStat.VALID
                vertices = int(asset.get_tag_value("Vertices"))
                triangles = int(asset.get_tag_value("Triangles"))
                if vertices > triangles:
                    valid_stat = EValidStat.INVALID
                return "{}".format(vertices), valid_stat
            elif property_name == "Triangles":
                valid_stat = EValidStat.VALID
                triangles = int(asset.get_tag_value("Triangles"))
                if triangles > 4000000:
                    valid_stat = EValidStat.INVALID_STRICT
                return "{}".format(triangles), valid_stat
            elif property_name == "DistanceFieldSize":
                valid_stat = EValidStat.VALID
                df_size = asset.get_tag_value("DistanceFieldSize")
                if df_size is None:
                    df_size_int = 0
                else:
                    df_size_int = int(df_size)
                if df_size_int > 4000000:
                    valid_stat = EValidStat.INVALID_STRICT
                return "{:.2f}".format(df_size_int / (1024.0 * 1024.0)), valid_stat
            elif property_name == "EstNaniteCompressedSize":
                valid_stat = EValidStat.VALID
                df_size = asset.get_tag_value("EstNaniteCompressedSize")
                if df_size is None:
                    df_size_int = 0
                else:
                    df_size_int = int(df_size)
                if df_size_int > 30000000:
                    valid_stat = EValidStat.INVALID_STRICT
                return "{:.2f}".format(df_size_int / (1024.0 * 1024.0)), valid_stat
                
                return result, valid_stat
            
        return str(result), EValidStat.VALID


class MeshStatWidget(QtWidgets.QWidget):
    def __init__(self):
        super(MeshStatWidget, self).__init__()

        vbox = QtWidgets.QVBoxLayout(self)
        self.setLayout(vbox)

        # doc_widget = common_widgets.DocumentLinkBar(DOC_URL)
        # vbox.addWidget(doc_widget)

        self.spawn_assets_widget = spawn_assets_to_level.SpawnAssetWidget()
        self.spawn_assets_widget.add_event_listener("AssetListChanged", self.on_asset_list_changed)
        vbox.addWidget(self.spawn_assets_widget)

        self.common_assets_data = MeshSectionData("Meshes", TEST_MESHES)
        common_assets_widget = asset_section_widget.AssetSectionWidget(self.common_assets_data)
        vbox.addWidget(common_assets_widget)

    def on_asset_list_changed(self, asset_paths: List[str]):
        self.common_assets_data.asset_paths = asset_paths
