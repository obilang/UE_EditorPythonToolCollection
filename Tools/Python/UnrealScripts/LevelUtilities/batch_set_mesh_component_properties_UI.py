import unreal

from PySide6 import QtWidgets
from QtUtil import qt_util
from AssetOperations import asset_utils
from typing import List
from QtUtil import common_widgets

# import importlib
# 
# importlib.reload()

WINDOW_TITLE = "Modify Mesh Component Properties"
WINDOW_MIN_WIDTH = 400
WINDOW_MIN_HEIGHT = 600

editor_asset_lib = unreal.EditorAssetLibrary()
editor_util_lib = unreal.EditorUtilityLibrary()
editor_actor_lib = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()

MODIFY_COMPONENT_TYPES = {
    "Static Mesh": unreal.StaticMeshComponent,
    "Skeletal Mesh": unreal.SkeletalMeshComponent
}


class MainScriptWindow(QtWidgets.QDialog):
    def __init__(self, actor_list: List[unreal.Actor]):
        super(MainScriptWindow, self).__init__(None)
        self.actor_list = actor_list
        self._init_data()

        # window setup 
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(WINDOW_MIN_WIDTH)
        self.setMinimumHeight(WINDOW_MIN_HEIGHT)

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self._build_ui()
        # align all widget to top
        self.main_layout.addStretch()

    def _init_data(self):
        self.components_map = {}
        for actor in self.actor_list:
            components = actor.get_components_by_class(unreal.StaticMeshComponent)
            components_path = []
            for component in components:
                component_path = component.get_path_name()
                components_path.append(component_path)
            self.components_map[actor] = components_path

    def _build_ui(self):
        # doc_widget = common_widgets.DocumentLinkBar(DOC_URL)
        # self.main_layout.addWidget(doc_widget)

        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)

        label = QtWidgets.QLabel("Modify Component Type: ")
        h_layout.addWidget(label)

        self.component_type_combobox = QtWidgets.QComboBox()
        for component_type_name, component_type_class in MODIFY_COMPONENT_TYPES.items():
            self.component_type_combobox.addItem(component_type_name, component_type_class)
        self.component_type_combobox.currentIndexChanged.connect(self.on_component_type_cb_changed)
        self.target_component_type = self.component_type_combobox.currentData()
        h_layout.addWidget(self.component_type_combobox)

        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Name Filter: ")
        h_layout.addWidget(label)
        self.component_name_filter_le = QtWidgets.QLineEdit('')
        self.component_name_filter_le.textChanged.connect(self.on_component_name_filter_changed)
        h_layout.addWidget(self.component_name_filter_le)

        # btn = QtWidgets.QPushButton('Update')
        # btn.clicked.connect(self.on_click_preview_btn)
        # self.main_layout.addWidget(btn)

        self.modify_components_tree = QtWidgets.QTreeWidget(self)
        self.modify_components_tree.setColumnCount(2)
        self.modify_components_tree.setHeaderLabels(['Actor', 'Components'])
        self.main_layout.addWidget(self.modify_components_tree)

        self.main_layout.addSpacing(20)

        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Light Channel: ")
        h_layout.addWidget(label)

        self.light_channel_0_cb = QtWidgets.QCheckBox("Channel 0")
        self.light_channel_0_cb.setChecked(True)
        h_layout.addWidget(self.light_channel_0_cb)
        self.light_channel_1_cb = QtWidgets.QCheckBox("Channel 1")
        self.light_channel_1_cb.setChecked(False)
        h_layout.addWidget(self.light_channel_1_cb)
        self.light_channel_2_cb = QtWidgets.QCheckBox("Channel 2")
        self.light_channel_2_cb.setChecked(False)
        h_layout.addWidget(self.light_channel_2_cb)

        generic_value_btn = QtWidgets.QPushButton('Change')
        generic_value_btn.clicked.connect(self.on_click_modify_light_channel_btn)
        h_layout.addWidget(generic_value_btn)
        
        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Cast Shadow: ")
        h_layout.addWidget(label)
        
        self.cast_shadow_cb = QtWidgets.QCheckBox()
        h_layout.addWidget(self.cast_shadow_cb)

        generic_value_btn = QtWidgets.QPushButton('Change')
        generic_value_btn.clicked.connect(self.on_click_modify_cast_shadow_btn)
        h_layout.addWidget(generic_value_btn)

        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Cast Dynamic Shadow: ")
        h_layout.addWidget(label)

        self.cast_dynamic_shadow_cb = QtWidgets.QCheckBox()
        h_layout.addWidget(self.cast_dynamic_shadow_cb)

        generic_value_btn = QtWidgets.QPushButton('Change')
        generic_value_btn.clicked.connect(self.on_click_modify_cast_dynamic_shadow_btn)
        h_layout.addWidget(generic_value_btn)

        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Generic Property Change: ")
        h_layout.addWidget(label)

        self.editor_property_combobox = QtWidgets.QComboBox()
        h_layout.addWidget(self.editor_property_combobox)
        self.update_generic_editor_property_combobox()

        h_layout.addStretch()
        self.generic_property_value_le = QtWidgets.QLineEdit('')
        h_layout.addWidget(self.generic_property_value_le)

        generic_value_btn = QtWidgets.QPushButton('Change')
        generic_value_btn.clicked.connect(self.on_click_modify_generic_value_btn)
        h_layout.addWidget(generic_value_btn)

        self.main_layout.addSpacing(20)

        self.result_label = QtWidgets.QPlainTextEdit('')
        self.main_layout.addWidget(self.result_label)

        self.on_click_preview_btn()

    def on_click_preview_btn(self):
        self.update_to_modify_components()

    def on_component_type_cb_changed(self, index):
        self.target_component_type = self.component_type_combobox.currentData()
        
        self.components_map.clear()
        for actor in self.actor_list:
            components = actor.get_components_by_class(MODIFY_COMPONENT_TYPES[self.target_component_type])
            components_path = []
            for component in components:
                component_path = component.get_path_name()
                components_path.append(component_path)
            self.components_map[actor] = components_path
            
        self.update_generic_editor_property_combobox()
        self.on_click_preview_btn()

    def on_component_name_filter_changed(self, text):
        self.on_click_preview_btn()

    def update_to_modify_components(self):
        self.modify_components_tree.clear()
        index = 0
        for actor, actor_components in self.components_map.items():
            bp_item = QtWidgets.QTreeWidgetItem(self.modify_components_tree)
            bp_item.setText(0, str(actor.get_actor_label()))
            # set the children
            for component in actor_components:
                component = asset_registry.get_asset_by_object_path(component).get_asset()
                if self.get_filtered_component(component):
                    component_item = QtWidgets.QTreeWidgetItem(self.modify_components_tree)
                    component_item.setText(1, component.get_name())
                    bp_item.addChild(component_item)
            self.modify_components_tree.resizeColumnToContents(index)
            index = index + 1

    def on_click_modify_light_channel_btn(self):
        light_channels = unreal.LightingChannels(self.light_channel_0_cb.isChecked(),
                                                 self.light_channel_1_cb.isChecked(),
                                                 self.light_channel_2_cb.isChecked())
        self.update_property_value_on_components("lighting_channels", light_channels)
        
    def on_click_modify_cast_shadow_btn(self):
        cast_shadow = self.cast_shadow_cb.isChecked()
        self.update_property_value_on_components("cast_shadow", cast_shadow)
        
    def on_click_modify_cast_dynamic_shadow_btn(self):
        cast_shadow = self.cast_dynamic_shadow_cb.isChecked()
        self.update_property_value_on_components("cast_dynamic_shadow", cast_shadow)

    def update_generic_editor_property_combobox(self):
        editor_properties = unreal.PythonFunctionLibrary.get_all_editor_propertie_names(self.target_component_type)
        for editor_property in editor_properties:
            self.editor_property_combobox.addItem(editor_property, editor_property)

    def on_click_modify_generic_value_btn(self):
        value = self.generic_property_value_le.text()
        target_value = None
        if "true" in value.lower():
            target_value = True
        if "false" in value.lower():
            target_value = False
        try:
            float(value)
        except ValueError:
            pass
        else:
            target_value = float(value)
        target_property_name = self.editor_property_combobox.currentData()
        self.update_property_value_on_components(target_property_name, target_value)

    def update_property_value_on_components(self, property_name, property_value):
        result_str = ''
        try:
            for actor, actor_components in self.components_map.items():
                for component in actor_components:
                    component = asset_registry.get_asset_by_object_path(component).get_asset()
                    if self.get_filtered_component(component):
                        component.set_editor_property(property_name, property_value)
                        result_str = "{}[{}][{}] Property {} is set to {}\n".format(result_str, actor.get_actor_label(),
                                                                                    component.get_name(), property_name,
                                                                                    property_value)
                # editor_asset_lib.save_asset(bp.package_name, True)
        except:
            self.result_label.setPlainText("Failed to set property.\n{}".format(result_str))
        else:
            self.result_label.setPlainText("Success.\n{}".format(result_str))

    def get_filtered_component(self, component):
        if not isinstance(component, self.target_component_type):
            return False
        if self.component_name_filter_le.text().lower() not in component.get_name().lower():
            return False
        return True


if __name__ == "__main__":
    app = qt_util.create_qt_application()

    selected_assets = editor_actor_lib.get_selected_level_actors()
    widget = MainScriptWindow(selected_assets)
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())
