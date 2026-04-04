from PySide6 import QtWidgets
from PySide6 import QtCore
from QtUtil import common_widgets
from LevelUtilities import actor_section_widget
from QtUtil import qt_style_preset

import unreal

# import importlib
# importlib.reload(actor_section_widget)
# importlib.reload(foliage_utils)


editor_filter_lib = unreal.EditorFilterLibrary()
editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
system_lib = unreal.SystemLibrary()
editor_asset_lib = unreal.EditorAssetLibrary()


def get_all_components_by_class(object_class):
    all_components = editor_actor_subsystem.get_all_level_actors_components()
    result = editor_filter_lib.by_class(all_components, object_class)
    return result


def get_meshes_from_text(text):
    mesh_set = set()
    lines = text.split('\n')
    for line in lines:
        if line == '':
            continue
        mesh_path = line
        columns = line.split("'")
        if columns is not None and len(columns) > 1:
            mesh_path = columns[1]

        columns = mesh_path.split(".")
        if columns is not None and len(columns) > 1:
            mesh_path = columns[0]

        mesh_set.add(mesh_path)
    return mesh_set


class TargetStaticMeshActorSectionData(actor_section_widget.ActorSectionData):
    def __init__(self, name):
        super(TargetStaticMeshActorSectionData, self).__init__(name)
        self.target_static_meshes = []
        self.init_display_properties(["Actor Name", "Component Name", "Static Mesh"])

    def set_mesh_filter(self, target_static_meshes):
        self.target_static_meshes = target_static_meshes

    def find_valid_component(self):
        mesh_components = get_all_components_by_class(unreal.StaticMeshComponent)
        self.components.clear()

        for mesh_component in mesh_components:
            if len(self.target_static_meshes) > 0:
                sm = mesh_component.static_mesh
                if sm in self.target_static_meshes:
                    self.components.append(mesh_component)
            else:
                self.components.append(mesh_component)

        return self.components

    @staticmethod
    def get_property_value(component, property_name):
        if property_name == "Actor Name":
            return component.get_owner().get_actor_label()
        elif property_name == "Component Name":
            return component.get_name()
        elif property_name == "Static Mesh":
            return component.static_mesh.get_name()
            # return component.get_name()
        return "None"


class FindMeshActorWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(FindMeshActorWidget, self).__init__(parent)

        vbox = QtWidgets.QVBoxLayout(self)
        self.setLayout(vbox)

        # doc_widget = common_widgets.DocumentLinkBar(DOC_URL)
        # vbox.addWidget(doc_widget)

        vbox_section = QtWidgets.QVBoxLayout()
        vbox_section.setAlignment(QtCore.Qt.AlignTop)
        widget = QtWidgets.QWidget()
        widget.setLayout(vbox_section)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        vbox.addWidget(scroll)

        label = QtWidgets.QLabel("Input Static Mesh List Here: (All Mesh Actor will be listed if empty)")
        label.setStyleSheet(qt_style_preset.LABEL_NORMAL_HIGHLIGHT)
        vbox_section.addWidget(label)

        self.target_decal_tex_te = QtWidgets.QPlainTextEdit()
        self.target_decal_tex_te.textChanged.connect(self.on_asset_text_changed)
        self.target_decal_tex_te.setMaximumHeight(200)
        vbox_section.addWidget(self.target_decal_tex_te)

        section_data = TargetStaticMeshActorSectionData("Meshes")
        self.section_widget = TargetStaticMeshActorSectionWidget(section_data)
        vbox_section.addWidget(self.section_widget)

        vbox_section.addStretch()

    def on_asset_text_changed(self):
        self.section_widget.on_set_target_meshes(get_meshes_from_text(self.target_decal_tex_te.toPlainText()))


class TargetStaticMeshActorSectionWidget(actor_section_widget.ActorSectionWidget):
    def __init__(self, section_data: actor_section_widget.ActorSectionData, hide_section=False):
        super(TargetStaticMeshActorSectionWidget, self).__init__(section_data, hide_section)
        self.mesh_path_list = []
        self.refresh_btn.setText("Find")

    def on_set_target_meshes(self, mesh_path_list):
        self.mesh_path_list = mesh_path_list

    def on_refresh_btn_clicked(self):
        target_mesh_obj_list = []
        for mesh_path in self.mesh_path_list:
            mesh_obj = editor_asset_lib.load_asset(mesh_path)
            target_mesh_obj_list.append(mesh_obj)

        self.section_data.set_mesh_filter(target_mesh_obj_list)
        super(TargetStaticMeshActorSectionWidget, self).on_refresh_btn_clicked()




