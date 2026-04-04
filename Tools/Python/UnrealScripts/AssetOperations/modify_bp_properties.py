import unreal

from PySide6 import QtWidgets
from QtUtil import qt_util
from AssetOperations import asset_utils
from typing import List
from QtUtil import common_widgets

# import importlib
# 
# importlib.reload()

WINDOW_TITLE = "Modify Blueprint Properties"
WINDOW_MIN_WIDTH = 400
WINDOW_MIN_HEIGHT = 600
DOC_URL = "https://"

asset_editor_sub = unreal.AssetEditorSubsystem()
editor_asset_lib = unreal.EditorAssetLibrary()
editor_util_lib = unreal.EditorUtilityLibrary()

MODIFY_COMPONENT_TYPES = {
    "Static Mesh": unreal.StaticMeshComponent,
    "Skeletal Mesh": unreal.SkeletalMeshComponent,
    "Component": unreal.ActorComponent
}


class MainScriptWindow(QtWidgets.QDialog):
    def __init__(self, bp_list: List[unreal.AssetData]):
        super(MainScriptWindow, self).__init__(None)
        self.bp_list = bp_list
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
        self.bp_components_map = {}
        with unreal.ScopedSlowTask(len(self.bp_list),
                                   "Loading Selected Blueprints") as slow_task:
            # display the dialog
            slow_task.make_dialog(True)
            for bp_asset_data in self.bp_list:
                if slow_task.should_cancel():
                    break
                slow_task.enter_progress_frame(1, "Loading Selected Blueprint {}".format(bp_asset_data.asset_name))
                bp_components = asset_utils.get_blueprint_asset_components(bp_asset_data)
                # print(bp_components)
                self.bp_components_map[bp_asset_data] = bp_components

    def _build_ui(self):
        doc_widget = common_widgets.DocumentLinkBar(DOC_URL)
        self.main_layout.addWidget(doc_widget)
        
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
        self.modify_components_tree.setHeaderLabels(['BP', 'Components'])
        self.main_layout.addWidget(self.modify_components_tree)

        self.main_layout.addSpacing(20)

        h_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Light Channel: ")
        h_layout.addWidget(label)

        self.light_channel_0_cb = QtWidgets.QCheckBox("Channel 0")
        self.light_channel_0_cb.setChecked(True)
        h_layout.addWidget( self.light_channel_0_cb)
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
        label = QtWidgets.QLabel("Collision Respond: ")
        h_layout.addWidget(label)

        self.collision_respond_cb = QtWidgets.QComboBox()
        for channel in unreal.CollisionChannel:
            self.collision_respond_cb.addItem(channel.name, channel.value)
        # self.collision_respond_cb.currentIndexChanged.connect(self.on_collision_respond_cb_changed)
        h_layout.addWidget(self.collision_respond_cb)
        
        self.collision_respond_type_cb = QtWidgets.QComboBox()
        for respond_type in unreal.CollisionResponseType:
            self.collision_respond_type_cb.addItem(respond_type.name, respond_type.value)
        # self.collision_respond_cb.currentIndexChanged.connect(self.on_collision_respond_cb_changed)
        h_layout.addWidget(self.collision_respond_type_cb)

        generic_value_btn = QtWidgets.QPushButton('Change')
        generic_value_btn.clicked.connect(self.on_click_modify_collision_respond_btn)
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
        self.update_to_modify_bp_components()

    def on_component_type_cb_changed(self, index):
        self.target_component_type = self.component_type_combobox.currentData()
        self.update_generic_editor_property_combobox()
        self.on_click_preview_btn()
        
    def on_component_name_filter_changed(self, text):
        self.on_click_preview_btn()

    def update_to_modify_bp_components(self):
        self.modify_components_tree.clear()
        index = 0
        for bp, bp_components in self.bp_components_map.items():
            bp_item = QtWidgets.QTreeWidgetItem(self.modify_components_tree)
            bp_item.setText(0, str(bp.asset_name))
            # set the children
            for component in bp_components:
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
    
    def on_click_modify_collision_respond_btn(self):
        result_str = ''
        try:
            for bp, bp_components in self.bp_components_map.items():
                for component in bp_components:
                    if self.get_filtered_component(component):
                        component.set_collision_response_to_channel(self.collision_respond_cb.currentData(), self.collision_respond_type_cb.currentData())
                        result_str = "{}[{}][{}] Collision Response {} is set to {}\n".format(
                            result_str, bp.asset_name, component.get_name(), self.collision_respond_cb.currentData(), self.collision_respond_type_cb.currentData())
                editor_asset_lib.save_asset(bp.package_name, True)
        except:
            self.result_label.setPlainText("Failed to set property.\n{}".format(result_str))
        else:
            self.result_label.setPlainText("Success.\n{}".format(result_str))

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
            for bp, bp_components in self.bp_components_map.items():
                for component in bp_components:
                    if self.get_filtered_component(component):
                        component.set_editor_property(property_name, property_value)
                        result_str = "{}[{}][{}] Property {} is set to {}\n".format(result_str, bp.asset_name, component.get_name(), property_name, property_value)
                editor_asset_lib.save_asset(bp.package_name, True)
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

    selected_assets = editor_util_lib.get_selected_asset_data()
    widget = MainScriptWindow(selected_assets)
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())
