from PySide6 import QtWidgets
from PySide6 import QtCore
from QtUtil import qt_util
from QtUtil import common_widgets
from LevelUtilities import actor_section_widget
from LevelUtilities import level_utils
from PySide6.QtGui import QBrush, QColor
from PySide6.QtCore import Qt
from AssetOperations import asset_utils

import unreal

# import importlib
# importlib.reload(actor_section_widget)


DOC_URL = ""

editor_filter_lib = unreal.EditorFilterLibrary()
editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
system_lib = unreal.SystemLibrary()
editor_world = unreal.UnrealEditorSubsystem().get_editor_world()


def get_all_components_by_class(object_class):
    all_components = editor_actor_subsystem.get_all_level_actors_components()
    result = editor_filter_lib.by_class(all_components, object_class)
    return result


class CollisionInfoSectionData(actor_section_widget.StaticMeshSectionData):
    def __init__(self, name):
        super(CollisionInfoSectionData, self).__init__(name)
        self.init_display_properties(["Actor Name", "Component Name", "Collision Preset", "Origin Mesh Preset",
                                      "Trace Response", "Physic Materials", "Has Simple Collision", "Origin Mesh Complexity"])

    def find_valid_component(self):
        all_component = get_all_components_by_class(unreal.StaticMeshComponent)
        self.components.clear()
        for smc in all_component:
            self.components.append(smc)
        return self.components


class CollisionGroundSectionData(CollisionInfoSectionData):
    def __init__(self, name):
        super(CollisionGroundSectionData, self).__init__(name)
        self.init_display_properties(["Actor Name", "Component Name", "Collision Preset",
                                      "Trace Response", "Physic Materials"])

    def find_valid_component(self):
        all_component = get_all_components_by_class(unreal.StaticMeshComponent)
        self.components.clear()
        for smc in all_component:
            block_channels = level_utils.get_mesh_collision_trace_block_channels(smc)
            if "Ground" in block_channels:
                physic_mats = level_utils.get_mesh_physic_materials(smc)
                has_invalid_pm = False
                for physic_mat in physic_mats:
                    path_name = physic_mat.get_package().get_path_name()
                    if '/Game/Art/Materials/Physical_Material_New/' not in path_name:
                        has_invalid_pm = True
                        break
                if not has_invalid_pm:
                    self.components.append(smc)

        return self.components


class CollisionBulletSectionData(CollisionInfoSectionData):
    def __init__(self, name):
        super(CollisionBulletSectionData, self).__init__(name)
        self.init_display_properties(["Actor Name", "Component Name", "Collision Preset",
                                      "Trace Response", "Physic Materials"])

    def find_valid_component(self):
        all_component = get_all_components_by_class(unreal.StaticMeshComponent)
        self.components.clear()
        for smc in all_component:
            block_channels = level_utils.get_mesh_collision_trace_block_channels(smc)
            if "BulletHitEnv" in block_channels:
                physic_mats = level_utils.get_mesh_physic_materials(smc)
                has_invalid_pm = False
                for physic_mat in physic_mats:
                    path_name = physic_mat.get_package().get_path_name()
                    if '/Game/Art/Materials/Physical_Material_New/' not in path_name:
                        has_invalid_pm = True
                        break
                if not has_invalid_pm:
                    self.components.append(smc)
                    
        return self.components


class CollisionBulletGoThroughSectionData(CollisionInfoSectionData):
    def __init__(self, name):
        super(CollisionBulletGoThroughSectionData, self).__init__(name)
        self.init_display_properties(["Actor Name", "Component Name", "Collision Preset",
                                      "Trace Response", "Physic Materials"])

    def find_valid_component(self):
        all_component = get_all_components_by_class(unreal.StaticMeshComponent)
        self.components.clear()
        for smc in all_component:
            block_channels = level_utils.get_mesh_collision_trace_block_channels(smc)
            if "BulletGoThrough" in block_channels:
                physic_mats = level_utils.get_mesh_physic_materials(smc)
                has_invalid_pm = False
                for physic_mat in physic_mats:
                    path_name = physic_mat.get_package().get_path_name()
                    if '/Game/Art/Materials/Physical_Material_New/' not in path_name:
                        has_invalid_pm = True
                        break
                if not has_invalid_pm:
                    self.components.append(smc)

        return self.components


class CollisionCameraSectionData(CollisionInfoSectionData):
    def __init__(self, name):
        super(CollisionCameraSectionData, self).__init__(name)
        self.init_display_properties(["Actor Name", "Component Name", "Collision Preset",
                                      "Trace Response", "Has Simple Collision", "Invisible", "Translucent"])

    def find_valid_component(self):
        all_component = get_all_components_by_class(unreal.StaticMeshComponent)
        self.components.clear()
        for smc in all_component:
            block_channels = level_utils.get_mesh_collision_trace_block_channels(smc)
            if "CameraCollision" in block_channels:
                if smc.static_mesh and asset_utils.mesh_has_simple_collision(smc.static_mesh):
                    self.components.append(smc)

        return self.components
    

class CollisionObstacleSectionData(CollisionInfoSectionData):
    def __init__(self, name):
        super(CollisionObstacleSectionData, self).__init__(name)
        self.init_display_properties(["Actor Name", "Component Name", "Collision Preset",
                                      "Trace Response", "Has Simple Collision", "Invisible", "Translucent"])

    def find_valid_component(self):
        all_component = get_all_components_by_class(unreal.StaticMeshComponent)
        self.components.clear()
        for smc in all_component:
            if smc.component_has_tag("Obstacle") or smc.get_owner().actor_has_tag("Obstacle"):
                if smc.static_mesh and asset_utils.mesh_has_simple_collision(smc.static_mesh):
                    self.components.append(smc)

        return self.components
    
    
class CollisionCameraFadeSectionData(CollisionInfoSectionData):
    def __init__(self, name):
        super(CollisionCameraFadeSectionData, self).__init__(name)
        self.init_display_properties(["Actor Name", "Component Name", "Collision Preset", "Trace Response"])

    def find_valid_component(self):
        all_component = get_all_components_by_class(unreal.StaticMeshComponent)
        self.components.clear()
        for smc in all_component:
            block_channels = level_utils.get_mesh_collision_trace_block_channels(smc)
            if "Tree" in block_channels:
                if smc.static_mesh and asset_utils.mesh_has_simple_collision(smc.static_mesh):
                    self.components.append(smc)

        return self.components


class CollisionInfoWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(CollisionInfoWidget, self).__init__(parent)

        vbox = QtWidgets.QVBoxLayout(self)
        self.setLayout(vbox)

        doc_widget = common_widgets.DocumentLinkBar(DOC_URL)
        vbox.addWidget(doc_widget)
        
        h_layout = QtWidgets.QHBoxLayout()
        vbox.addLayout(h_layout)
        
        btn = QtWidgets.QPushButton("Show Simple Collision")
        btn.clicked.connect(self.on_click_show_simple_col_btn)
        h_layout.addWidget(btn)

        btn = QtWidgets.QPushButton("Hide Simple Collision")
        btn.clicked.connect(self.on_click_hide_simple_col_btn)
        h_layout.addWidget(btn)
        
        h_layout.addStretch()

        vbox_section = QtWidgets.QVBoxLayout()
        vbox_section.setAlignment(QtCore.Qt.AlignTop)
        widget = QtWidgets.QWidget()
        widget.setLayout(vbox_section)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        vbox.addWidget(scroll)

        section_data = CollisionInfoSectionData("All Collision")
        section_widget = CollisionSectionWidget(section_data)
        vbox_section.addWidget(section_widget)

        section_data = CollisionBulletSectionData("Meshes Can Be Hit By Bullet")
        section_widget = CollisionSectionWidget(section_data, True)
        vbox_section.addWidget(section_widget)

        section_data = CollisionBulletGoThroughSectionData("Meshes Bullet Can Go Through")
        section_widget = CollisionSectionWidget(section_data, True)
        vbox_section.addWidget(section_widget)

        section_data = CollisionCameraSectionData("Meshes Can Block Camera")
        section_widget = CollisionSectionWidget(section_data, True)
        vbox_section.addWidget(section_widget)

        section_data = CollisionObstacleSectionData("Obstacle")
        section_widget = CollisionSectionWidget(section_data, True)
        vbox_section.addWidget(section_widget)

        section_data = CollisionCameraFadeSectionData("Camera Fade")
        section_widget = CollisionSectionWidget(section_data, True)
        vbox_section.addWidget(section_widget)

        section_data = CollisionGroundSectionData("Ground")
        section_widget = CollisionSectionWidget(section_data, True)
        vbox_section.addWidget(section_widget)

        vbox_section.addStretch()
        
    def on_click_show_simple_col_btn(self):
        system_lib.execute_console_command(editor_world, str("ShowFlag.collision 1"))
    
    def on_click_hide_simple_col_btn(self):
        system_lib.execute_console_command(editor_world, str("ShowFlag.collision 0"))


class CollisionSectionWidget(actor_section_widget.ActorSectionWidget):
    def __init__(self, section_data: actor_section_widget.ActorSectionData, hide_section=False):
        super(CollisionSectionWidget, self).__init__(section_data, hide_section)

        btn = QtWidgets.QPushButton('HideAll')
        btn.clicked.connect(self.on_hide_all_btn_clicked)
        self.title_h_layout.addWidget(btn)

        btn = QtWidgets.QPushButton('UnHideAll')
        btn.clicked.connect(self.on_unhide_all_btn_clicked)
        self.title_h_layout.addWidget(btn)

        btn = QtWidgets.QPushButton('Isolate')
        btn.clicked.connect(self.on_isolate_btn_clicked)
        self.title_h_layout.addWidget(btn)

        btn = QtWidgets.QPushButton('UnIsolate')
        btn.clicked.connect(self.on_unisolate_btn_clicked)
        self.title_h_layout.addWidget(btn)
    
    def on_hide_all_btn_clicked(self):
        for component in self.cached_components:
            component.get_owner().set_is_temporarily_hidden_in_editor(True)
            
    def on_unhide_all_btn_clicked(self):
        for component in self.cached_components:
            component.get_owner().set_is_temporarily_hidden_in_editor(False)
            
    def on_isolate_btn_clicked(self):
        self.on_unisolate_btn_clicked()
        cached_actors = []
        for component in self.cached_components:
            owner = component.get_owner()
            if owner not in cached_actors:
                cached_actors.append(owner)
        all_actors = editor_actor_subsystem.get_all_level_actors()
        for actor in all_actors:
            if actor not in cached_actors:
                actor.set_is_temporarily_hidden_in_editor(True)
                
    def on_unisolate_btn_clicked(self):
        all_actors = editor_actor_subsystem.get_all_level_actors()
        for actor in all_actors:
            actor.set_is_temporarily_hidden_in_editor(False)

    def on_refresh_btn_clicked(self):
        super(CollisionSectionWidget, self).on_refresh_btn_clicked()
        row = 0
        for component in self.cached_components:
            actor = component.get_owner()
            is_bp = unreal.ValidationToolFunction.is_blueprint_type(actor.get_class())
            
            if is_bp:
                owner_actor = component.get_owner()
                # owner_actor = unreal.Actor()
                has_invalid_component = False
                for sm_component in owner_actor.get_components_by_class(unreal.StaticMeshComponent):
                    if sm_component not in self.cached_components:
                        has_invalid_component = True
                        break
                if has_invalid_component:
                    table_widget_item = self.table.takeItem(row, 0)
                    table_widget_item.setBackground(QBrush(Qt.darkYellow))
                    self.table.setItem(row, 0, table_widget_item)
            row += 1

    

