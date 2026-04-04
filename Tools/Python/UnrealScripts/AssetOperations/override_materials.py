from PySide6 import QtWidgets
from QtUtil import common_widgets
from AssetOperations import asset_section_widget
import unreal
import json
import os
import path_util
from LevelUtilities import actor_section_widget
from Materials import material_utils
from AssetOperations import asset_utils
from PySide6.QtGui import QBrush, QColor
from PySide6.QtCore import Qt
from LevelUtilities import update_material_override_lod

import importlib

# 
importlib.reload(update_material_override_lod)

WHITE_LIST_JSON_PATH = "AssetOperations/override_material_whitelist.json"

DOC_URL = "https://"
editor_filter_lib = unreal.EditorFilterLibrary()
editor_asset_lib = unreal.EditorAssetLibrary()
EValidStat = asset_section_widget.EValidStat
editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor_asset_subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
mat_edit_lib = unreal.MaterialEditingLibrary()

TYPE_SCALAR_PARAM = "scalar"
TYPE_VECTOR_PARAM = "vector"
TYPE_TEXTURE_PARAM = "texture"
TYPE_STATIC_SWITCH_PARAM = "staticswitch"

TREE_BP_NAME = "Default__TreeActor"


class OverrideWhiteList:
    def __init__(self):
        setting_file_path = os.path.join(path_util.ue_tool_python_path(), WHITE_LIST_JSON_PATH)
        with open(setting_file_path, "r") as setting_file:
            settings = json.load(setting_file)

        self.white_list = settings

    def get_if_override_param_valid(self, base_mat_name, param_type, param_name):
        if base_mat_name in self.white_list:
            mat_setting = self.white_list[base_mat_name]
            if param_name in mat_setting[param_type]:
                return True
        else:
            return True
        return False
    
    def get_if_base_mat_in_list(self, base_mat_name):
        return base_mat_name in self.white_list


class OverrideMatStat:
    def __init__(self):
        self.origin_mat = None
        self.related_components = set()
        self.origin_mesh = None


class OverrideMatSectionData(asset_section_widget.AssetSectionData):
    def __init__(self, name, asset_paths):
        super(OverrideMatSectionData, self).__init__(name)
        self.asset_paths = asset_paths
        self.white_list = OverrideWhiteList()
        self.init_display_properties([
            "Origin Mat",
            "Child To Origin",
            "Base Material",
            "Wrong Override Params",
            "Wrong Override Properties",
            "Path"
        ])

    def get_mat_stat_of(self, asset_data: unreal.AssetData):
        for key, value in self.mat_stats.items():
            if asset_data.package_name == key:
                return value
        return None

    def find_valid_assets(self):
        self.assets = []

        all_components = editor_actor_subsystem.get_all_level_actors_components()
        mesh_components = editor_filter_lib.by_class(all_components, unreal.StaticMeshComponent)

        self.mat_stats = {}
        for mesh_c in mesh_components:
            owner_actor = mesh_c.get_owner()
            if unreal.ValidationToolFunction.is_blueprint_type(owner_actor.get_class()):
                base_bp_name = owner_actor.get_default_object().get_name()
                if base_bp_name == "Default__TreeActor":
                    continue
            
            # if (len(mesh_c.get_editor_property("override_materials")) > 0):
            #     print("mesh：{} override {}".format(mesh_c.get_name(), mesh_c.get_editor_property("override_materials")))
            static_mesh = mesh_c.static_mesh
            mat_count = mesh_c.get_num_materials()
            for i in range(mat_count):
                origin_mat = static_mesh.get_material(i)
                actor_mat = mesh_c.get_material(i)
                asset_path = str(actor_mat.get_package().get_name())

                if isinstance(actor_mat, unreal.MaterialInstanceDynamic) or isinstance(actor_mat, unreal.Material):
                    continue

                if origin_mat is None or origin_mat.get_name() == "WorldGridMaterial":
                    continue

                if origin_mat != actor_mat:
                    if asset_path not in self.mat_stats:
                        mat_stat = OverrideMatStat()
                        mat_stat.origin_mat = origin_mat
                        mat_stat.origin_mesh = static_mesh
                        mat_stat.related_components.add(mesh_c)
                        self.mat_stats[asset_path] = mat_stat
                    else:
                        self.mat_stats[asset_path].related_components.add(mesh_c)

        for mat_path in self.mat_stats.keys():
            # if override_material == "None":
            #     continue
            # print(asset_path)
            asset_data = editor_asset_lib.find_asset_data(mat_path)
            # if asset_utils.get_asset_data_class(asset_data.package_name) == "Texture2D":
            self.assets.append(asset_data)
        return self.assets

    def get_property_value(self, asset: unreal.AssetData, property_name):
        result = None
        mat_obj = editor_asset_lib.load_asset(asset.package_name)
        asset_path = str(asset.package_name)

        try:
            pass
        except:
            # print("cannot find editor property")
            pass
        else:
            if property_name == "Path":
                return asset_path, EValidStat.VALID
            elif property_name == "Origin Mat":
                valid_stat = EValidStat.VALID
                origin_mat = self.mat_stats[asset_path].origin_mat
                return origin_mat.get_name(), valid_stat
            elif property_name == "Child To Origin":
                valid_stat = EValidStat.VALID
                origin_mat = self.mat_stats[asset_path].origin_mat
                if isinstance(mat_obj, unreal.World):
                    print(mat_obj)
                    test = self.get_mat_stat_of(asset)
                    print(test)
                    print(test.origin_mat)
                    print(test.related_components)
                child_to_origin = (mat_obj.parent == origin_mat)
                # print(mat_obj.get_editor_property("scalar_parameter_values"))
                if not child_to_origin:
                    base_material = mat_obj.get_base_material().get_name()
                    if base_material not in ["M_FoliageTree", "M_FoliageGrass", "M_FoliageBase"]:
                        EValidStat.INVALID_STRICT
                    else:
                        valid_stat = EValidStat.INVALID
                return child_to_origin, valid_stat
            elif property_name == "Base Material":
                valid_stat = EValidStat.VALID
                base_material = mat_obj.get_base_material()
                return base_material.get_name(), valid_stat
            elif property_name == "Wrong Override Params":
                valid_stat = EValidStat.VALID
                base_material = mat_obj.get_base_material().get_name()
                wrong_params = []

                if not self.white_list.get_if_base_mat_in_list(base_material):
                    return wrong_params, valid_stat
                
                for param in mat_obj.scalar_parameter_values:
                    is_valid = self.white_list.get_if_override_param_valid(base_material, TYPE_SCALAR_PARAM,
                                                                           param.parameter_info.name)
                    if not is_valid:
                        valid_stat = EValidStat.INVALID
                        wrong_params.append(str(param.parameter_info.name))
                for param in mat_obj.vector_parameter_values:
                    is_valid = self.white_list.get_if_override_param_valid(base_material, TYPE_VECTOR_PARAM,
                                                                           param.parameter_info.name)
                    if not is_valid:
                        valid_stat = EValidStat.INVALID
                        wrong_params.append(str(param.parameter_info.name))
                for param in mat_obj.texture_parameter_values:
                    is_valid = self.white_list.get_if_override_param_valid(base_material, TYPE_TEXTURE_PARAM,
                                                                           param.parameter_info.name)
                    if not is_valid:
                        valid_stat = EValidStat.INVALID
                        wrong_params.append(str(param.parameter_info.name))
                for param in mat_edit_lib.get_static_switch_parameter_names(mat_obj):
                    if self.white_list.get_if_override_param_valid(base_material, TYPE_STATIC_SWITCH_PARAM,
                                                                           param):
                        continue
                    
                    parent_mat = mat_obj.get_editor_property("parent")
                    if isinstance(parent_mat, unreal.MaterialInstance):
                        parent_ss_value = mat_edit_lib.get_material_instance_static_switch_parameter_value(parent_mat,
                                                                                                           param)
                        ss_value = mat_edit_lib.get_material_instance_static_switch_parameter_value(mat_obj, param)
                        if parent_ss_value != ss_value:
                            valid_stat = EValidStat.INVALID
                            wrong_params.append(str(param))
                return wrong_params, valid_stat
            elif property_name == "Wrong Override Properties":
                valid_stat = EValidStat.VALID
                result = "OK"
                property_overrides = mat_obj.get_editor_property("base_property_overrides")
                override_shading_model = property_overrides.get_editor_property("override_shading_model")
                override_two_sided = property_overrides.get_editor_property("override_two_sided")
                override_blend_mode = property_overrides.get_editor_property("override_blend_mode")

                if override_shading_model or override_two_sided or override_blend_mode:
                    valid_stat = EValidStat.INVALID
                    result = "Override"

                return result, valid_stat

            # elif property_name == "LODBias":
            #     valid_stat = EValidStat.VALID
            #     bias = texture_obj.get_editor_property("lod_bias")
            #     if bias > 0:
            #         valid_stat = EValidStat.INVALID
            #     return bias, valid_stat

        return str(result), EValidStat.VALID


class OverrideMaterialSectionWidget(asset_section_widget.AssetSectionWidget):
    def on_table_selection_changed(self):
        super(OverrideMaterialSectionWidget, self).on_table_selection_changed()
        editor_actor_subsystem.clear_actor_selection_set()
        actor_to_select = []
        for selected_item in self.table.selectedItems():
            if selected_item.is_name_column:
                mat_stat = self.section_data.get_mat_stat_of(selected_item.asset)
                for comp in mat_stat.related_components:
                    if comp.get_owner() not in actor_to_select:
                        actor_to_select.append(comp.get_owner())
                        print("{}: {}".format(comp.get_owner().get_name(), comp.get_name()))
        editor_actor_subsystem.set_selected_level_actors(actor_to_select)
        
    def on_table_double_clicked(self):
        for selected_item in self.table.selectedItems():
            if selected_item.is_name_column:
                mat_stat = self.section_data.get_mat_stat_of(selected_item.asset)
                unreal.AssetEditorSubsystem().open_editor_for_assets(
                    [unreal.load_asset(selected_item.asset.package_name),
                     mat_stat.origin_mat,
                     mat_stat.origin_mesh
                     ]
                )
                break


FOLIAGE_BASE_MATERIALS = ["M_FoliageTree", "M_FoliageGrass", "M_FoliageBase"]
MESH_META_DATA_TYPE_NAME = "Mesh Import Type"


class WrongOverrideLODMeshSectionData(actor_section_widget.ActorSectionData):
    def __init__(self, name):
        super(WrongOverrideLODMeshSectionData, self).__init__(name)
        self.init_display_properties(
            ["Actor Name", "Component Name", "Mesh Group", "Is Nanite", "LOD Count", "Materials"])

    def find_valid_component(self):
        all_components = editor_actor_subsystem.get_all_level_actors_components()
        all_components = editor_filter_lib.by_class(all_components, unreal.StaticMeshComponent)
        self.components.clear()
        for smc in all_components:
            owner_actor = smc.get_owner()
            if unreal.ValidationToolFunction.is_blueprint_type(owner_actor.get_class()):
                base_bp_name = owner_actor.get_default_object().get_name()
                if base_bp_name == "Default__TreeActor":
                    continue
                    
            static_mesh = smc.static_mesh
            group = editor_asset_subsystem.get_metadata_tag(static_mesh, MESH_META_DATA_TYPE_NAME)
            if group is None or group == "":
                continue
            
            override_materials = smc.get_editor_property("override_materials")
            if len(override_materials) == 0:
                continue

            mat_count = smc.get_num_materials()
            has_overrides = False
            is_foliage = False
            for i in range(mat_count):
                origin_mat = static_mesh.get_material(i)

                if not isinstance(origin_mat, unreal.MaterialInstanceConstant):
                    continue

                origin_mat_asset = asset_utils.get_asset_data_from_obj(origin_mat)
                base_mat = material_utils.get_base_material(origin_mat_asset)

                if base_mat is None:
                    break
                
                if origin_mat != smc.get_material(i):
                    has_overrides = True

                if base_mat.asset_name in FOLIAGE_BASE_MATERIALS:
                    is_foliage = True
            
            if is_foliage and has_overrides:
                self.components.append(smc)

        return self.components

    @staticmethod
    def get_property_value(component, property_name):
        valid_stat = EValidStat.VALID
        if property_name == "Source Mesh":
            result = component.static_mesh.get_name()
        elif property_name == "LOD Count":
            static_mesh = component.static_mesh
            result = static_mesh.get_num_lods()
        elif property_name == "Is Nanite":
            static_mesh = component.static_mesh
            nanite_setting = static_mesh.get_editor_property("nanite_settings")
            is_nanite_enabled = nanite_setting.get_editor_property("enabled")
            result = is_nanite_enabled
        elif property_name == "Mesh Group":
            static_mesh = component.static_mesh
            group = editor_asset_subsystem.get_metadata_tag(static_mesh, MESH_META_DATA_TYPE_NAME)
            result = group
        elif property_name == "Base Material":
            static_mesh = component.static_mesh
            mat_count = component.get_num_materials()
            base_mats = set()
            for i in range(mat_count):
                origin_mat = static_mesh.get_material(i)
                if not isinstance(origin_mat, unreal.MaterialInstanceConstant):
                    continue
                origin_mat_asset = asset_utils.get_asset_data_from_obj(origin_mat)
                base_mat = material_utils.get_base_material(origin_mat_asset)
                base_mats.add(str(base_mat.asset_name))
            result = base_mats
        elif property_name == "Actor Name":
            result = unreal.SystemLibrary.get_display_name(component.get_owner())
        elif property_name == "Component Name":
            result = unreal.SystemLibrary.get_object_name(component)
        elif property_name == "Materials":
            mat_count = component.get_num_materials()
            materials = []
            for i in range(mat_count):
                materials.append(component.get_material(i).get_name())
            result = materials

            static_mesh = component.static_mesh
            mat_count = component.get_num_materials()
            for i in range(mat_count):
                origin_mat = static_mesh.get_material(i)
                actor_mat = component.get_material(i)

                if "_LOD" in origin_mat.get_name():
                    continue

                if isinstance(actor_mat, unreal.MaterialInstanceDynamic):
                    continue

                if origin_mat != actor_mat:
                    origin_mat_file = path_util.get_system_path_from_ue_package_path(actor_mat.get_package().get_path_name())
                    origin_mat_change_time = os.path.getmtime(origin_mat_file)

                    mat_chain = update_material_override_lod.find_lod_material_chain(static_mesh, origin_mat)
                    
                    for lod, mat_index in mat_chain.items():
                        if lod == 0:
                            continue
                            
                        if component.get_material(mat_index) == static_mesh.get_material(mat_index):
                            valid_stat = EValidStat.INVALID
                            break
                        
                        override_lod_mat = component.get_material(mat_index)
                        override_lod_mat_file = path_util.get_system_path_from_ue_package_path(
                            override_lod_mat.get_package().get_path_name())
                        override_lod_mat_change_time = os.path.getmtime(override_lod_mat_file)
                        
                        # if the time is close enough, we can treat them judge the lod material is generated with lod0 material
                        print("gap time: {}".format(origin_mat_change_time - override_lod_mat_change_time))

                        if origin_mat_change_time - override_lod_mat_change_time > 180:
                            valid_stat = EValidStat.INVALID
        else:
            # real_property_name = actor_section_widget.get_ui_name_to_real_name(property_name)
            # result = component.get_editor_property(real_property_name)
            result = "TODO"
        return result, valid_stat


class WrongOverrideLODSectionWidget(actor_section_widget.ActorSectionWidget):
    def __init__(self, section_data: actor_section_widget.ActorSectionData, hide_section=False):
        super(WrongOverrideLODSectionWidget, self).__init__(section_data, hide_section)
        self.refresh_btn.setText("Validate")
        
        h_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(h_layout)
        
        btn = QtWidgets.QPushButton("Update Selected Material LODs")
        btn.clicked.connect(self.on_click_update_lod_btn)
        h_layout.addWidget(btn)

        btn = QtWidgets.QPushButton("Update All Invalid Material LODs")
        btn.clicked.connect(self.on_click_update_invalid_lod_btn)
        h_layout.addWidget(btn)

    def on_click_update_lod_btn(self):
        components = set()
        levels = set()
        for selected_item in self.table.selectedItems():
            row_index = selected_item.row()
            # Get the first item in the row
            first_item = self.table.item(row_index, 0)
            
            if first_item.is_name_column:
                components.add(first_item.component)
                levels.add(first_item.component.get_owner().get_level().get_package().get_path_name())
                
        changed_mats, should_save = update_material_override_lod.update_material_override_for_components_in_current_level(components)
        for changed_mat in changed_mats:
            print(" Force recompile material: {}".format(changed_mat.get_name()))
            unreal.PythonFunctionLibrary.force_refresh_material_instance(changed_mat)
            editor_asset_subsystem.save_loaded_asset(changed_mat)
        for level in levels:
            print(level)
            editor_asset_subsystem.save_asset(level, False)

    def on_click_update_invalid_lod_btn(self):
        components = set()
        levels = set()
        for row in range(self.table.rowCount()):
            for column in range(self.table.columnCount()):
                selected_item = self.table.item(row, column)
                if selected_item.is_invalid:
                    row_index = selected_item.row()
                    # Get the first item in the row
                    first_item = self.table.item(row_index, 0)
        
                    if first_item.is_name_column:
                        components.add(first_item.component)
                        levels.add(first_item.component.get_owner().get_level().get_package().get_path_name())

        changed_mats, should_save = update_material_override_lod.update_material_override_for_components_in_current_level(components)
        for changed_mat in changed_mats:
            print(" Force recompile material: {}".format(changed_mat.get_name()))
            # unreal.PythonFunctionLibrary.force_refresh_material_instance(changed_mat)
            unreal.MaterialEditingLibrary.update_material_instance(changed_mat)
            editor_asset_subsystem.save_loaded_asset(changed_mat)
        
        for level in levels:
            print(level)
            editor_asset_subsystem.save_asset(level, False)

    def on_refresh_btn_clicked(self):
        super(WrongOverrideLODSectionWidget, self).on_refresh_btn_clicked()
        row = 0
        is_pass = True
        for component in self.cached_components:
            column = 0
            actor = component.get_owner()
            for property_name in self.section_data.display_properties:
                property_value, valid_stat = self.section_data.get_property_value(component, property_name)
                table_widget_item = self.table.takeItem(row, column)
                table_widget_item.setText(str(property_value))
                if valid_stat == EValidStat.INVALID:
                    table_widget_item.setBackground(QBrush(Qt.red))
                    table_widget_item.is_invalid = True
                    is_pass = False
                else:
                    table_widget_item.is_invalid = False
                self.table.setItem(row, column, table_widget_item)
                column += 1
            row += 1

        if not is_pass:
            self.title_label.setText("Fail!!!")
            self.title_label.setStyleSheet('''color: red''')
        else:
            self.title_label.setText("Pass!!!")
            self.title_label.setStyleSheet('''color: green''')
        self.table.resizeColumnsToContents()


class OverrideMatWidget(QtWidgets.QWidget):
    def __init__(self):
        super(OverrideMatWidget, self).__init__()

        vbox = QtWidgets.QVBoxLayout(self)
        self.setLayout(vbox)

        doc_widget = common_widgets.DocumentLinkBar(DOC_URL)
        vbox.addWidget(doc_widget)
        # 
        # self.spawn_assets_widget = spawn_assets_to_level.SpawnAssetWidget()
        # self.spawn_assets_widget.add_event_listener("AssetListChanged", self.on_asset_list_changed)
        # vbox.addWidget(self.spawn_assets_widget)

        self.common_assets_data = OverrideMatSectionData("Override Materials", [])
        common_assets_widget = OverrideMaterialSectionWidget(self.common_assets_data)
        vbox.addWidget(common_assets_widget)
        
        section_data = WrongOverrideLODMeshSectionData("WrongLOD")
        section_widget = WrongOverrideLODSectionWidget(section_data, True)
        vbox.addWidget(section_widget)
        
    # def on_asset_list_changed(self, asset_paths: List[str]):
    #     self.common_assets_data.asset_paths = asset_paths


if __name__ == "__main__":
    test_white_list = OverrideWhiteList()
    print(test_white_list.get_if_override_param_valid("M_FoliageGrass", TYPE_SCALAR_PARAM, "Roughness Contras"))
