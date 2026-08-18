from PySide6 import QtGui
from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6 import QtCore
from QtUtil import common_widgets
from LevelUtilities import actor_section_widget
# from LevelUtilities import foliage_utils
from Materials import material_utils
from AssetOperations import asset_utils

import unreal

# import importlib
# importlib.reload(actor_section_widget)
# importlib.reload(foliage_utils)


TAG_SHADOW_MESH = "ShadowMesh"
TAG_SHADOW_PROXY = "ShadowProxy"
TAG_CAMERA_BLOCKER = "CameraBlocker"
DOC_URL = ""

editor_filter_lib = unreal.EditorFilterLibrary()
editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor_asset_subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
system_lib = unreal.SystemLibrary()

correct_property_ref = {
    "Shadow Meshes": {
        "Actor Name": "_ShadowMesh",
        "Component Name": "_ShadowMesh",
        "bHiddenInGame": True,
        "bCastHiddenShadow": True,
        "visible_in_ray_tracing": False,
        "CollisionPreset": "NoCollision",
        "component_tags": ["ShadowMesh", ],
        "Material": ["M_Base_Shadow", "M_Base_Shadow_Masked", ]
    },
    "Shadow Proxy": {
        "Actor Name": "_PSM",
        "Component Name": "PSM",
        "visible": False,
        "render_in_main_pass": True,
        "visible_in_ray_tracing": False,
        "bHiddenInGame": True,
        "bCastHiddenShadow": True,
        "CollisionPreset": "NoCollision",
        "bAffectDistanceFieldLighting": True,
        "component_tags": ["ShadowProxy", ],
        "Material": ["M_Base_Shadow", "M_Base_Shadow_Masked", ]
    },
    "Camera Blockers": {
        "Actor Name": "_CameraBlocker",
        "Component Name": "_CameraBlocker",
        "bHiddenInGame": True,
        "CollisionPreset": "CameraBlocker",
        "bAffectDistanceFieldLighting": False,
        "component_tags": ["CameraBlocker", ],
        "Material": ["M_Collision", ],
        "Has Simple Collision": True
    },
    "Invisible/Translucent Mesh": {
        "CollisionPreset": "NoCollision",
    },
    "Foliage": {
        "CollisionPreset": ["NoCollision", "Grass"],
        "instance_end_cull_distance": 0,
        "LOD count": 1,
        "Instance Count": 0,
        "Overlapping Instances": 0
    },
    "Tree BP Shadow Proxy": {
        "Actor Name": "_PSM",
        "Component Name": "PSM",
        "visible": False,
        "CollisionPreset": "NoCollision",
        "Material": ["M_Base_Shadow", "M_Base_Shadow_Masked", ],
        "bHiddenInGame": True,
        "bCastHiddenShadow": True
    },
    "Empty Mesh": {

    }
}


def get_all_components_by_class(object_class):
    all_components = editor_actor_subsystem.get_all_level_actors_components()
    result = editor_filter_lib.by_class(all_components, object_class)
    return result


def has_tag(component: unreal.ActorComponent, tag_name):
    current_tags = component.get_editor_property("component_tags")
    for tag in current_tags:
        if tag == tag_name:
            return True


def check_mesh_property_value(name, property_name, property_value, isBP):
    real_property_name = actor_section_widget.get_ui_name_to_real_name(property_name)
    if real_property_name not in correct_property_ref.get(name).keys():
        return True

    correct_property_value = correct_property_ref.get(name).get(real_property_name)
    result = True
    if real_property_name in ["component_tags", "Material"]:
        if not len(property_value):
            result = False
        else:
            for element in property_value:
                if element not in correct_property_value:
                    result = False
    elif real_property_name in ["Actor Name", "Component Name"]:
        if isBP and real_property_name == "Component Name" and not property_value.endswith(correct_property_value):
            result = False
        elif not isBP and real_property_name == "Actor Name" and not property_value.endswith(correct_property_value):
            result = False
    elif property_value != correct_property_value:
        result = False
        
    return result


def check_foliage_property_value(name, property_name, property_value, isBP):
    real_property_name = actor_section_widget.get_ui_name_to_real_name(property_name)
    if real_property_name not in correct_property_ref.get(name).keys():
        return True

    correct_property_value = correct_property_ref.get(name).get(real_property_name)
    result = True
    if real_property_name == "CollisionPreset":
        if property_value not in correct_property_value:
            result = False
    elif real_property_name in ["Actor Name", "Component Name"]:
        if isBP and real_property_name == "Component Name" and not property_value.endswith(correct_property_value):
            result = False
        elif not isBP and real_property_name == "Actor Name" and not property_value.endswith(correct_property_value):
            result = False
    elif real_property_name in ["instance_end_cull_distance", "LOD count", "Instance Count"]:
        if property_value <= correct_property_value:
            result = False
    elif real_property_name in ["Overlapping Instances"]:
        if property_value > correct_property_value:
            result = False
    return result


class ShadowMeshSectionData(actor_section_widget.StaticMeshSectionData):
    def __init__(self, name):
        super(ShadowMeshSectionData, self).__init__(name)
        self.init_display_properties(["Actor Name", "Component Name", "Actor Hidden In Game", "Hidden Shadow",
                                      "Collision Preset",
                                      "Affect Distance Field Lighting", "Component Tags", "Material"])

    def find_valid_component(self):
        all_component = get_all_components_by_class(unreal.StaticMeshComponent)
        self.components.clear()
        for smc in all_component:
            is_bp = unreal.ValidationToolFunction.is_blueprint_type(smc.get_owner().get_class())
            if is_bp:
                continue
            
            if has_tag(smc, TAG_SHADOW_PROXY) or has_tag(smc, TAG_CAMERA_BLOCKER):
                continue
            
            if has_tag(smc, TAG_SHADOW_MESH):
                self.components.append(smc)
                continue
            
            cast_hidden_shadow = smc.get_editor_property("cast_hidden_shadow")
            if cast_hidden_shadow:
                self.components.append(smc)
                continue
            
            visible = smc.get_editor_property("visible")
            cast_shadow = smc.get_editor_property("cast_shadow")
            render_in_main_pass = smc.get_editor_property("render_in_main_pass")
            
            if (not visible or not render_in_main_pass) and cast_shadow:
                self.components.append(smc)
        return self.components


class ShadowProxySectionData(actor_section_widget.StaticMeshSectionData):
    def __init__(self, name):
        super(ShadowProxySectionData, self).__init__(name)
        self.init_display_properties(
            ["Actor Name", "Component Name", "Visible", "Render in Main Pass", "Actor Hidden In Game", "Hidden Shadow", "Collision Preset",
             "Affect Distance Field Lighting", "Component Tags", "Material"])

    def find_valid_component(self):
        all_components = get_all_components_by_class(unreal.StaticMeshComponent)
        self.components.clear()
        for smc in all_components:
            owner_actor = smc.get_owner()
            if unreal.ValidationToolFunction.is_blueprint_type(owner_actor.get_class()):
                base_bp_name = owner_actor.get_default_object().get_name()
                if base_bp_name == "Default__TreeActor":
                    continue
            
            if has_tag(smc, TAG_SHADOW_MESH) or has_tag(smc, TAG_CAMERA_BLOCKER):
                continue
            
            if has_tag(smc, TAG_SHADOW_PROXY):
                self.components.append(smc)
                continue
            
            visible = smc.get_editor_property("visible")
            cast_shadow = smc.get_editor_property("cast_shadow")
            render_in_main_pass = smc.get_editor_property("render_in_main_pass")
            if (not render_in_main_pass) and cast_shadow:
                self.components.append(smc)
                continue
            
            if "Shadow" in smc.get_name() or "PSM" in smc.get_name():
                self.components.append(smc)
                continue
                
            for element in smc.get_materials():
                if isinstance(element, unreal.MaterialInstance):
                    mat_name = system_lib.get_object_name(element.get_base_material())
                else:
                    mat_name = system_lib.get_object_name(element)

                if "Shadow" in str(mat_name) or "PSM" in smc.get_name():
                    self.components.append(smc)
                    continue
                
        return self.components


class TreeShadowProxySectionData(actor_section_widget.StaticMeshSectionData):
    def __init__(self, name):
        super(TreeShadowProxySectionData, self).__init__(name)
        self.init_display_properties(
            ["Actor Name", "Component Name", "Visible", "Actor Hidden In Game", "Hidden Shadow", "Collision Preset", "Material"])

    def find_valid_component(self):
        all_components = get_all_components_by_class(unreal.StaticMeshComponent)
        self.components.clear()
        for smc in all_components:
            owner_actor = smc.get_owner()
            if unreal.ValidationToolFunction.is_blueprint_type(owner_actor.get_class()):
                base_bp_name = owner_actor.get_default_object().get_name()
                if base_bp_name != "Default__TreeActor":
                    continue
            else:
                continue

            visible = smc.get_editor_property("visible")
            cast_shadow = smc.get_editor_property("cast_shadow")
            render_in_main_pass = smc.get_editor_property("render_in_main_pass")
            if (not (visible and render_in_main_pass)) and cast_shadow:
                self.components.append(smc)
        return self.components


class CollisionMeshSectionData(actor_section_widget.StaticMeshSectionData):
    def __init__(self, name):
        super(CollisionMeshSectionData, self).__init__(name)
        self.init_display_properties(
            ["Actor Name", "Component Name", "Actor Hidden In Game", "Collision Preset",
             # "Affect Distance Field Lighting",
             "Component Tags", "Material", "Has Simple Collision"])

    def find_valid_component(self):
        all_components = get_all_components_by_class(unreal.StaticMeshComponent)
        self.components.clear()
        for smc in all_components:
            if has_tag(smc, TAG_SHADOW_MESH) or has_tag(smc, TAG_SHADOW_PROXY):
                continue
                
            if has_tag(smc, TAG_CAMERA_BLOCKER):
                self.components.append(smc)
                continue
                
            is_camera_blocker = smc.get_collision_profile_name()
            if is_camera_blocker == "CameraBlocker":
                self.components.append(smc)
        return self.components


class EmptyMeshSectionData(actor_section_widget.StaticMeshSectionData):
    def __init__(self, name):
        super(EmptyMeshSectionData, self).__init__(name)
        self.init_display_properties(
            ["Actor Name", "Component Name"])

    def find_valid_component(self):
        all_components = get_all_components_by_class(unreal.StaticMeshComponent)
        self.components.clear()
        for smc in all_components:
            if smc.static_mesh is None:
                self.components.append(smc)
        return self.components


class InvisibleOrTranslucentMeshSectionData(actor_section_widget.StaticMeshSectionData):
    def __init__(self, name):
        super(InvisibleOrTranslucentMeshSectionData, self).__init__(name)
        self.init_display_properties(["Actor Name", "Component Name", "Visible", "Collision Preset", "Component Tags", "Material"])

    def find_valid_component(self):
        all_components = get_all_components_by_class(unreal.StaticMeshComponent)
        self.components.clear()
        for smc in all_components:
            if has_tag(smc, TAG_CAMERA_BLOCKER) or has_tag(smc, TAG_SHADOW_PROXY) or has_tag(smc, TAG_SHADOW_MESH):
                continue
            
            materials = smc.get_materials()
            for element in materials:
                blend_mode = element.get_blend_mode()
                if isinstance(element, unreal.MaterialInstance):
                    mat_name = system_lib.get_object_name(element.get_base_material())
                else:
                    mat_name = system_lib.get_object_name(element)

                if "Glass" in str(mat_name):
                    continue

                if blend_mode is not unreal.BlendMode.BLEND_OPAQUE and blend_mode is not unreal.BlendMode.BLEND_MASKED:
                    self.components.append(smc)
                    break
            
            is_bp = unreal.ValidationToolFunction.is_blueprint_type(smc.get_owner().get_class())
            if is_bp:
                continue
            
            visible = smc.get_editor_property("visible")
            render_in_main_pass = smc.get_editor_property("render_in_main_pass")
            actor_hidden_in_game = smc.get_editor_property("bHiddenInGame")
            if not visible or not render_in_main_pass or actor_hidden_in_game:
                self.components.append(smc)
                    
        return self.components


class FoliageSectionData(actor_section_widget.ActorSectionData):
    def __init__(self, name):
        self.name = name
        self.components = []
        self.display_properties = ["Actor Name", "Component Name", "Mesh Name", "Instance Count", "Overlapping Instances", "Collision Preset",
                                   "Instance Start Culling Distance", "Instance End Cull Distance", "LOD count", "Cast Shadow", "Receive Decal"]

    def find_valid_component(self):
        self.components = get_all_components_by_class(unreal.FoliageInstancedStaticMeshComponent)
        return self.components

    @staticmethod
    def get_property_value(foliage_component, property_name):
        if property_name == "Collision Preset":
            result = foliage_component.get_collision_profile_name()
        elif property_name == "LOD count":
            static_mesh = foliage_component.get_editor_property("static_mesh")
            if static_mesh is not None:
                result = static_mesh.get_num_lods()
            else:
                result = 0
        elif property_name == "Instance Count":
            result = foliage_component.get_instance_count()
        elif property_name == "Component Name":
            result = unreal.SystemLibrary.get_object_name(foliage_component)
        elif property_name == "Actor Name":
            result = unreal.SystemLibrary.get_display_name(foliage_component.get_owner())
        elif property_name == "Mesh Name":
            result = foliage_component.static_mesh.get_name()
        elif property_name == "Receive Decal":
            result = foliage_component.receives_decals
        elif property_name == "Overlapping Instances":
            # result = foliage_utils.find_overlapping_foliages(foliage_component)
            result = "-1"
        else:
            real_property_name = actor_section_widget.get_ui_name_to_real_name(property_name)
            result = foliage_component.get_editor_property(real_property_name)
        return result


FOLIAGE_BASE_MATERIALS = ["M_FoliageTree", "M_FoliageGrass", "M_FoliageBase"]
MESH_META_DATA_TYPE_NAME = "Mesh Import Type"


class VegetationMeshSectionData(actor_section_widget.StaticMeshSectionData):
    def __init__(self, name):
        super(VegetationMeshSectionData, self).__init__(name)
        self.init_display_properties(
            ["Actor Name", "Component Name", "Source Mesh", "Mesh Group",
             "Base Material", "Is Nanite", "WPO Distance", "LOD Count", "Has Overrides", "Materials"])

    def find_valid_component(self):
        all_components = get_all_components_by_class(unreal.StaticMeshComponent)
        self.components.clear()
        for smc in all_components:
            owner_actor = smc.get_owner()
            if unreal.ValidationToolFunction.is_blueprint_type(owner_actor.get_class()):
                base_bp_name = owner_actor.get_default_object().get_name()
                if base_bp_name == "Default__TreeActor":
                    continue
            
            static_mesh = smc.static_mesh
            mat_count = smc.get_num_materials()
            for i in range(mat_count):
                origin_mat = static_mesh.get_material(i)
                
                if not isinstance(origin_mat, unreal.MaterialInstanceConstant):
                    continue
                
                origin_mat_asset = asset_utils.get_asset_data_from_obj(origin_mat)
                base_mat = material_utils.get_base_material(origin_mat_asset)
                
                if base_mat is None:
                    break
                
                if base_mat.asset_name in FOLIAGE_BASE_MATERIALS:
                    self.components.append(smc)
                    break
        return self.components
    
    @staticmethod
    def get_property_value(component, property_name):
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
        elif property_name == "Has Overrides":
            override_materials = component.get_editor_property("override_materials")
            result = len(override_materials)
        elif property_name == "WPO Distance":
            wpo_distance = component.get_editor_property("world_position_offset_disable_distance")
            result = wpo_distance
        else:
            # real_property_name = actor_section_widget.get_ui_name_to_real_name(property_name)
            # result = component.get_editor_property(real_property_name)
            result = "TODO"
        return result


class LevelActorFilterWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(LevelActorFilterWidget, self).__init__(parent)

        vbox = QtWidgets.QVBoxLayout(self)
        self.setLayout(vbox)
        
        doc_widget = common_widgets.DocumentLinkBar(DOC_URL)
        vbox.addWidget(doc_widget)
        
        vbox_section = QtWidgets.QVBoxLayout()
        vbox_section.setAlignment(QtCore.Qt.AlignTop)
        widget = QtWidgets.QWidget()
        widget.setLayout(vbox_section)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        vbox.addWidget(scroll)

        section_data = ShadowMeshSectionData("Shadow Meshes")
        section_widget = StaticSectionWidget(section_data)
        vbox_section.addWidget(section_widget)
        
        section_data = ShadowProxySectionData("Shadow Proxy")
        section_widget = StaticSectionWidget(section_data, True)
        vbox_section.addWidget(section_widget)

        # section_data = TreeShadowProxySectionData("Tree BP Shadow Proxy")
        # section_widget = StaticSectionWidget(section_data, True)
        # vbox_section.addWidget(section_widget)
        
        section_data = CollisionMeshSectionData("Camera Blockers")
        section_widget = StaticSectionWidget(section_data, True)
        vbox_section.addWidget(section_widget)
        
        section_data = InvisibleOrTranslucentMeshSectionData("Invisible/Translucent Mesh")
        section_widget = StaticSectionWidget(section_data, True)
        vbox_section.addWidget(section_widget)
        
        section_data = EmptyMeshSectionData("Empty Mesh")
        section_widget = StaticSectionWidget(section_data, True)
        vbox_section.addWidget(section_widget)
        
        section_data = FoliageSectionData("Foliage")
        section_widget = FoliageSectionWidget(section_data, True)
        vbox_section.addWidget(section_widget)
        
        section_data = VegetationMeshSectionData("Bush/Grass")
        section_widget = StaticSectionWidget(section_data, True)
        vbox_section.addWidget(section_widget)
        
        vbox_section.addStretch()


class StaticSectionWidget(actor_section_widget.ActorSectionWidget):
    def __init__(self, section_data: actor_section_widget.ActorSectionData, hide_section=False):
        super(StaticSectionWidget, self).__init__(section_data, hide_section)
        self.refresh_btn.setText("Validate")

    def on_refresh_btn_clicked(self):
        super(StaticSectionWidget, self).on_refresh_btn_clicked()
        row = 0
        is_pass = True
        for component in self.cached_components:
            column = 0
            actor = component.get_owner()
            is_bp = unreal.ValidationToolFunction.is_blueprint_type(actor.get_class())
            for property_name in self.section_data.display_properties:
                property_value = self.section_data.get_property_value(component, property_name)
                table_widget_item = self.table.takeItem(row, column)
                if not check_mesh_property_value(self.section_data.name, property_name, property_value, is_bp):
                    table_widget_item.setBackground(QBrush(Qt.red))
                    is_pass = False
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


class FoliageSectionWidget(actor_section_widget.ActorSectionWidget):
    def __init__(self, section_data: FoliageSectionData, hide_section=False):
        super(FoliageSectionWidget, self).__init__(section_data, hide_section)
        self.refresh_btn.setText("Validate")

    def on_refresh_btn_clicked(self):
        super(FoliageSectionWidget, self).on_refresh_btn_clicked()
        row = 0
        is_pass = True
        for component in self.cached_components:
            column = 0
            actor = component.get_owner()
            is_bp = unreal.ValidationToolFunction.is_blueprint_type(actor.get_class())
            for property_name in self.section_data.display_properties:
                property_value = self.section_data.get_property_value(component, property_name)
                table_widget_item = self.table.takeItem(row, column)
                if not check_foliage_property_value(self.section_data.name, property_name, property_value, is_bp):
                    table_widget_item.setBackground(QBrush(Qt.red))
                    is_pass = False
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

