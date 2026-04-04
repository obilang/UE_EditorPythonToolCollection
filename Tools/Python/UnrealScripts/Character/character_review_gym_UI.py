import sys
import unreal

from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import qt_util
from QtUtil import qt_style_preset
from PySide6 import QtCore
import path_util
import os
import random
import string
from Character import character_review_settings
from threading import Timer
import time

import importlib
importlib.reload(character_review_settings)

WINDOW_TITLE = "Character Review Gym Interface"
WINDOW_MIN_WIDTH = 600
WINDOW_MIN_HEIGHT = 800

LIGHTING_LEVEL_MAP = character_review_settings.LIGHTING_LEVEL_MAP
LIGHTING_LEVEL_SEQUENCE_MAP = character_review_settings.LIGHTING_LEVEL_SEQUENCE_MAP
CAMERA_PRESET_MAP = character_review_settings.CAMERA_PRESET_MAP
# CHARACTER_BP_MAP = character_review_settings.CHARACTER_BP_MAP


LOOKDEV_BP = "BP_AssetsPreview_C"
CHARACTER_ROOT_ACTOR = "ArtSource"
CHARACTER_ACTOR = "BP_MHI_Wol1_C"
OUTPUT_SCREENSHOT_FOLDER = "CharacterReview"
STANDARD_CHARACTER_HEIGHT = 185

editor_actor_sub = unreal.EditorActorSubsystem()
editor_level_util = unreal.EditorLevelUtils()
editor_world = unreal.UnrealEditorSubsystem().get_editor_world()
editor_asset_sub = unreal.EditorAssetSubsystem()
level_actor_sub = unreal.LevelEditorSubsystem()


def get_character_attach_root(root_actor: unreal.Actor):
    components = root_actor.get_components_by_tag(unreal.SceneComponent, "RotateRoot")
    if len(components) > 0:
        root_component = components[0]
        return root_component
    return None


def attach_character_bp():
    all_actors = editor_actor_sub.get_all_level_actors()

    for bp_actor in all_actors:
        if bp_actor.get_actor_label() == CHARACTER_ROOT_ACTOR:
            root_actor = bp_actor
        if bp_actor.get_class().get_name() == CHARACTER_ACTOR:
            character_bp = bp_actor

    attach_root_component = get_character_attach_root(root_actor)

    character_bp.attach_to_component(attach_root_component, "None",
                                        unreal.AttachmentRule.KEEP_RELATIVE,
                                        unreal.AttachmentRule.KEEP_RELATIVE,
                                        unreal.AttachmentRule.KEEP_RELATIVE)

    # if bp_name != "":
    #     bound_origin, bound_extent = character_actor.get_actor_bounds(True)
    #     z_height = bound_extent.z
    #     # print(z_height)
    #     scale_amount = STANDARD_CHARACTER_HEIGHT * 0.5 / z_height
    #     character_actor.set_actor_scale3d(unreal.Vector(scale_amount, scale_amount, scale_amount))

        
def load_character_bp(bp_name, bp_path):
    with unreal.ScopedSlowTask(1,
                               "Loading Character...") as slow_task:
        slow_task.make_dialog(True)

        all_actors = editor_actor_sub.get_all_level_actors()
    
        for bp_actor in all_actors:
            if bp_actor.get_actor_label() == CHARACTER_ROOT_ACTOR:
                root_actor = bp_actor
                break
        
        bp_object = editor_asset_sub.load_asset(bp_path)
        character_actor = editor_actor_sub.spawn_actor_from_object(bp_object, unreal.Vector(0.0, 0.0, 0.0))
        character_actor.tags.append("Review")
        
        for actor in root_actor.get_attached_actors():
            actor.destroy_actor()
        attach_root_component = get_character_attach_root(root_actor)
        
        if bp_name == "":
            character_actor.set_actor_rotation(unreal.Rotator(0.0, 0.0, 90.0), True)
            character_actor.set_actor_location(unreal.Vector(0.0, 0.0, 90.0), False, False)
        else:
            character_actor.set_actor_rotation(unreal.Rotator(0.0, 0.0, 0.0), True)
            character_actor.set_actor_location(unreal.Vector(0.0, 0.0, 0.0), False, False)
            
        character_actor.attach_to_component(attach_root_component, "None", 
                                            unreal.AttachmentRule.KEEP_RELATIVE,
                                            unreal.AttachmentRule.KEEP_RELATIVE,
                                            unreal.AttachmentRule.KEEP_RELATIVE)
        
        if bp_name != "":
            bound_origin, bound_extent = character_actor.get_actor_bounds(True)
            z_height = bound_extent.z
            # print(z_height)
            scale_amount = STANDARD_CHARACTER_HEIGHT * 0.5 / z_height
            character_actor.set_actor_scale3d(unreal.Vector(scale_amount, scale_amount, scale_amount))
    
        return character_actor


def show_lighting_sublevel(sublevel_name):
    for level in editor_level_util.get_levels(editor_world):
        for light_levels in LIGHTING_LEVEL_MAP.values():
            levels = light_levels.split(",")
            for target_level in levels:
                if target_level in level.get_full_name():
                    editor_level_util.set_level_visibility(level, False, False)
        show_levels = LIGHTING_LEVEL_MAP[sublevel_name].split(",")
        for show_level in show_levels:
            if show_level in level.get_full_name():
                editor_level_util.set_level_visibility(level, True, False)


def get_export_folder_path():
    export_folder = path_util.tool_output_temp_folder()
    export_folder = os.path.join(export_folder, OUTPUT_SCREENSHOT_FOLDER)
    export_folder = os.path.realpath(export_folder)
    if not os.path.isdir(export_folder):
        os.makedirs(export_folder)
    return export_folder


def generate_random_string(length):
    # Generate a random string of alphanumeric characters
    letters_and_digits = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(letters_and_digits) for i in range(length))
    return random_string


class MainScriptWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(MainScriptWindow, self).__init__(parent)
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
        all_actors = editor_actor_sub.get_all_level_actors()

        self.current_character_name = ""
        self.current_camou_name = "Default"
        self.current_face_name = "Default"
        for bp_actor in all_actors:
            if bp_actor.get_class().get_name() == LOOKDEV_BP:
                self.lookdev_bp = bp_actor
            
            if bp_actor.get_actor_label() == CHARACTER_ROOT_ACTOR:
                self.character_root_bp = bp_actor
            
            
            if "FaceClose" in bp_actor.get_actor_label():
                self.close_face_camera = bp_actor
                
        self.lookdev_bp.set_editor_property("Hide Lights", False)
        show_lighting_sublevel("Neutral")
        self.lookdev_bp.set_editor_property("TurnLighting", 0)

        attach_character_bp()

    def _build_ui(self):
        # Initialize tab screen
        tabs = QtWidgets.QTabWidget()
        # tabs.resize(300, 200)
        self.main_layout.addWidget(tabs)
        # Add tabs
        general_tab = QtWidgets.QWidget()
        general_tab.adjustSize()
        tabs.addTab(general_tab, "General")
        
        general_layout = QtWidgets.QVBoxLayout()
        general_tab.setLayout(general_layout)
        
        # lightings
        label = QtWidgets.QLabel("Lightings")
        label.setStyleSheet(qt_style_preset.LABEL_TITLE_SECTION_LARGE)
        general_layout.addWidget(label)
        
        h_layout = QtWidgets.QHBoxLayout()
        general_layout.addLayout(h_layout)
        
        label = QtWidgets.QLabel("Select Lighting Presets:")
        h_layout.addWidget(label)
        
        self.tod_cb = QtWidgets.QComboBox()
        for name, level in LIGHTING_LEVEL_MAP.items():
            self.tod_cb.addItem(name, level)
        self.tod_cb.currentIndexChanged.connect(self.on_tod_cb_changed)
        h_layout.addWidget(self.tod_cb)
        
        self.netural_widget = QtWidgets.QWidget()
        v_layout = QtWidgets.QVBoxLayout()
        self.netural_widget.setLayout(v_layout)
        general_layout.addWidget(self.netural_widget)

        h_layout = QtWidgets.QHBoxLayout()
        v_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Light Scenario:")
        h_layout.addWidget(label)
        self.light_scenario_cb = QtWidgets.QComboBox()
        self.light_scenario_cb.addItem("LowContrast")
        self.light_scenario_cb.addItem("MidContrast")
        self.light_scenario_cb.addItem("HighContrast")
        self.current_light_scenarios = self.lookdev_bp.get_editor_property("LightingScenarios")
        print(str(self.current_light_scenarios))
        current_index = int(str(self.current_light_scenarios)[str(self.current_light_scenarios).find(':') + 1: str(self.current_light_scenarios).find('>')])
        self.light_scenario_cb.setCurrentIndex(current_index)
        self.light_scenario_cb.currentIndexChanged.connect(self.on_light_scenario_cb_changed)
        h_layout.addWidget(self.light_scenario_cb)

        h_layout = QtWidgets.QHBoxLayout()
        v_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Rotate Light H:")
        h_layout.addWidget(label)

        self.light_h_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.light_h_slider.setMinimum(-180)
        self.light_h_slider.setMaximum(180)
        self.light_h_slider.setValue(0)
        self.light_h_slider.valueChanged.connect(self.on_light_h_slider_value_changed)
        h_layout.addWidget(self.light_h_slider)

        self.light_h_label = QtWidgets.QLabel("0")
        h_layout.addWidget(self.light_h_label)

        btn = QtWidgets.QPushButton("Reset")
        btn.clicked.connect(lambda: self.on_light_h_slider_value_changed(0))
        h_layout.addWidget(btn)
        
        h_layout = QtWidgets.QHBoxLayout()
        v_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Rotate Light V:")
        h_layout.addWidget(label)

        self.light_v_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.light_v_slider.setMinimum(-30)
        self.light_v_slider.setMaximum(60)
        self.light_v_slider.setValue(0)
        self.light_v_slider.valueChanged.connect(self.on_light_v_slider_value_changed)
        h_layout.addWidget(self.light_v_slider)

        self.light_v_label = QtWidgets.QLabel("0")
        h_layout.addWidget(self.light_v_label)
        
        btn = QtWidgets.QPushButton("Reset")
        btn.clicked.connect(lambda: self.on_light_v_slider_value_changed(0))
        h_layout.addWidget(btn)

        self.on_light_v_slider_value_changed(0)
        self.on_light_h_slider_value_changed(0)

        self.tod_widget = QtWidgets.QWidget()
        v_layout = QtWidgets.QVBoxLayout()
        self.tod_widget.setLayout(v_layout)
        general_layout.addWidget(self.tod_widget)

        self.tod_adjust_light_btn = QtWidgets.QPushButton("Adjusted Light")
        self.tod_adjust_light_btn.setCheckable(True)
        self.tod_adjust_light_btn.setChecked(True)
        self.tod_adjust_light_btn.toggled.connect(self.on_adjust_light_clicked)
        v_layout.addWidget(self.tod_adjust_light_btn)
        
        self.on_tod_cb_changed(0)

        # camera
        label = QtWidgets.QLabel("Cameras")
        label.setStyleSheet(qt_style_preset.LABEL_TITLE_SECTION_LARGE)
        general_layout.addWidget(label)
        
        h_layout = QtWidgets.QHBoxLayout()
        general_layout.addLayout(h_layout)

        label = QtWidgets.QLabel("Select Camera Presets:")
        h_layout.addWidget(label)

        self.camera_cb = QtWidgets.QComboBox()
        for name, level in CAMERA_PRESET_MAP.items():
            self.camera_cb.addItem(name, level)
        self.camera_cb.currentIndexChanged.connect(self.on_camera_cb_changed)
        h_layout.addWidget(self.camera_cb)

        self.close_camera_widget = QtWidgets.QWidget()
        v_layout = QtWidgets.QVBoxLayout()
        self.close_camera_widget.setLayout(v_layout)
        general_layout.addWidget(self.close_camera_widget)

        h_layout = QtWidgets.QHBoxLayout()
        v_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Move Camera H:")
        h_layout.addWidget(label)

        self.camera_h_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.camera_h_slider.setMinimum(-5)
        self.camera_h_slider.setMaximum(5)
        self.camera_h_slider.setValue(0)
        self.camera_h_slider.valueChanged.connect(self.on_camera_h_slider_value_changed)
        h_layout.addWidget(self.camera_h_slider)

        self.camera_h_label = QtWidgets.QLabel("0")
        h_layout.addWidget(self.camera_h_label)

        btn = QtWidgets.QPushButton("Reset")
        btn.clicked.connect(lambda: self.on_camera_h_slider_value_changed(0))
        h_layout.addWidget(btn)

        h_layout = QtWidgets.QHBoxLayout()
        v_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Move Camera V:")
        h_layout.addWidget(label)

        self.camera_v_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.camera_v_slider.setMinimum(-8)
        self.camera_v_slider.setMaximum(12)
        self.camera_v_slider.setValue(0)
        self.camera_v_slider.valueChanged.connect(self.on_camera_v_slider_value_changed)
        h_layout.addWidget(self.camera_v_slider)

        self.camera_v_label = QtWidgets.QLabel("0")
        h_layout.addWidget(self.camera_v_label)

        btn = QtWidgets.QPushButton("Reset")
        btn.clicked.connect(lambda: self.on_camera_v_slider_value_changed(0))
        h_layout.addWidget(btn)

        h_layout = QtWidgets.QHBoxLayout()
        general_layout.addLayout(h_layout)

        self.view_camera_btn = QtWidgets.QPushButton("Set Viewport To Camera")
        self.view_camera_btn.setCheckable(True)
        self.view_camera_btn.setChecked(True)
        self.view_camera_btn.clicked.connect(self.on_view_camera_btn_click)
        h_layout.addWidget(self.view_camera_btn)

        btn = QtWidgets.QPushButton("Save ScreenShot")
        btn.clicked.connect(self.on_screen_shot_btn_click)
        h_layout.addWidget(btn)

        self.output_widget = QtWidgets.QWidget()
        v_layout = QtWidgets.QVBoxLayout()
        self.output_widget.setLayout(v_layout)
        general_layout.addWidget(self.output_widget)
        
        h_layout = QtWidgets.QHBoxLayout()
        v_layout.addLayout(h_layout)
        self.output_path_label = QtWidgets.QLabel("")
        h_layout.addWidget(self.output_path_label)
        btn = QtWidgets.QPushButton("Open Folder")
        btn.clicked.connect(self.on_open_screen_shot_folder_btn_click)
        h_layout.addWidget(btn)
        self.output_widget.setVisible(False)

        self.on_camera_v_slider_value_changed(0)
        self.on_camera_h_slider_value_changed(0)
        self.on_camera_cb_changed(0)

        # rotate character
        general_layout.addSpacing(30)
        label = QtWidgets.QLabel("Rotate Character:")
        general_layout.addWidget(label)

        h_layout = QtWidgets.QHBoxLayout()
        general_layout.addLayout(h_layout)
        
        # btn = QtWidgets.QPushButton("-30")
        # btn.clicked.connect(lambda: self.on_rotate_btn_click(-30))
        # h_layout.addWidget(btn)
        # btn = QtWidgets.QPushButton("30")
        # btn.clicked.connect(lambda: self.on_rotate_btn_click(30))
        # h_layout.addWidget(btn)
        
        self.character_rot_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.character_rot_slider.setMinimum(-180)
        self.character_rot_slider.setMaximum(180)
        self.character_rot_slider.setValue(0)
        self.character_rot_slider.valueChanged.connect(self.on_character_slider_value_changed)
        h_layout.addWidget(self.character_rot_slider)

        self.character_rot_label = QtWidgets.QLabel("0")
        h_layout.addWidget(self.character_rot_label)

        btn = QtWidgets.QPushButton("Reset")
        btn.clicked.connect(lambda: self.on_character_slider_value_changed(0))
        h_layout.addWidget(btn)

        self.on_character_slider_value_changed(0)

        h_layout = QtWidgets.QHBoxLayout()
        general_layout.addLayout(h_layout)
        label = QtWidgets.QLabel("Show Calibrator: ")
        h_layout.addWidget(label)
        cb = QtWidgets.QCheckBox("")
        cb.setChecked(False)
        self.lookdev_bp.set_editor_property("Calibrator", False)
        cb.stateChanged.connect(
            lambda state: self.lookdev_bp.set_editor_property("Calibrator", state))
        h_layout.addWidget(cb)

        general_layout.addStretch()

        character_tab = QtWidgets.QWidget()
        character_tab.adjustSize()
        tabs.addTab(character_tab, "Character Setup")

        character_layout = QtWidgets.QVBoxLayout()
        character_tab.setLayout(character_layout)
        
        h_layout = QtWidgets.QHBoxLayout()
        character_layout.addLayout(h_layout)
        
        label = QtWidgets.QLabel("Select Character:")
        h_layout.addWidget(label)

        self.character_cb = QtWidgets.QComboBox()
        self.character_cb.addItem("TODO")
        
        self.character_cb.currentIndexChanged.connect(self.on_character_cb_changed)
        h_layout.addWidget(self.character_cb)

        character_layout.addStretch()

    def on_tod_cb_changed(self, index):
        selected_item = self.tod_cb.itemText(index)
        selected_item_data = self.tod_cb.itemData(index)
        self.current_tod_name = selected_item
        print("Selected item: {} data {}".format(selected_item, selected_item_data))
        
        if selected_item == "Neutral":
            self.lookdev_bp.set_editor_property("Hide Lights", False)
            self.netural_widget.show()
            self.tod_widget.hide()
            self.on_adjust_light_clicked(False)
        else:
            self.netural_widget.hide()
            self.tod_widget.show()
            self.tod_adjust_light_btn.setChecked(True)
            self.on_adjust_light_clicked(True)
            self.lookdev_bp.set_editor_property("Hide Lights", True)
        
        show_lighting_sublevel(selected_item)
        
    def on_camera_cb_changed(self, index):
        selected_item = self.camera_cb.itemText(index)
        selected_item_data = self.camera_cb.itemData(index)
        self.current_camera_name = selected_item
        print("Selected item: {} data {}".format(selected_item, selected_item_data))
        self.on_view_camera_btn_click()
        
    def on_character_cb_changed(self, index):
        selected_item = self.character_cb.itemText(index)
        selected_item_data = self.character_cb.itemData(index)
        self.current_character_name = selected_item
        load_character_bp(selected_item, selected_item_data)

        
    def on_view_camera_btn_click(self):
        if self.view_camera_btn.isChecked():
            all_actors = editor_actor_sub.get_all_level_actors()
            for bp_actor in all_actors:
                if CAMERA_PRESET_MAP[self.current_camera_name] in bp_actor.get_actor_label():
                    unreal.PythonFunctionLibrary.set_viewport_to_camera(bp_actor)
                    level_actor_sub.editor_set_game_view(True)
                    
                    if self.current_camera_name == "Face(CloseUp)":
                        self.close_camera_widget.show()
                    else:
                        self.close_camera_widget.hide()
                    break
        else:
            level_actor_sub.eject_pilot_level_actor()
            level_actor_sub.editor_set_game_view(False)

    def on_light_scenario_cb_changed(self, index):
        if index == 0:
            self.lookdev_bp.set_editor_property("LightingScenarios", self.current_light_scenarios.LOW_CONTRAST)
        elif index == 1:
            self.lookdev_bp.set_editor_property("LightingScenarios", self.current_light_scenarios.MID_CONTRAST)
        elif index == 2:
            self.lookdev_bp.set_editor_property("LightingScenarios", self.current_light_scenarios.HIGH_CONTRAST)
        
    def on_rotate_btn_click(self, rotate_angle):
        root_component = get_character_attach_root(self.character_root_bp)
        root_component.add_local_rotation(unreal.Rotator(0, 0, rotate_angle * -1.0), False, False)
        
    def on_character_slider_value_changed(self, value):
        self.character_rot_slider.setValue(value)
        self.character_rot_label.setText("{}".format(value))
        components = self.character_root_bp.get_components_by_tag(unreal.SceneComponent, "RotateRoot")
        if len(components) > 0:
            root_component = components[0]
            # root_component.add_local_rotation(unreal.Rotator(0, 0, rotate_angle * -1.0), False, False)
            root_component.set_editor_property("relative_rotation", unreal.Rotator(0, 0, value * -1.0))
    
    def on_rotate_light_btn_click(self, rotate_angle):
        current_value = self.lookdev_bp.get_editor_property("TurnLighting")
        self.lookdev_bp.set_editor_property("TurnLighting", current_value + rotate_angle)
        
    def on_rotate_light_v_btn_click(self, rotate_angle):
        current_value = self.lookdev_bp.get_editor_property("TurnLighting Vertical")
        self.lookdev_bp.set_editor_property("TurnLighting Vertical", current_value + rotate_angle)
        
    def on_light_h_slider_value_changed(self, value):
        self.light_h_slider.setValue(value)
        self.light_h_label.setText("{}".format(value))
        self.lookdev_bp.set_editor_property("TurnLighting", value)

    def on_light_v_slider_value_changed(self, value):
        self.light_v_slider.setValue(value)
        self.light_v_label.setText("{}".format(value))
        self.lookdev_bp.set_editor_property("TurnLighting Vertical", value)

    def on_camera_h_slider_value_changed(self, value):
        self.camera_h_slider.setValue(value)
        self.camera_h_label.setText("{}".format(value))
        self.close_face_camera.set_actor_relative_location(unreal.Vector(0, value, self.camera_v_slider.value()), False, False)

    def on_camera_v_slider_value_changed(self, value):
        self.camera_v_slider.setValue(value)
        self.camera_v_label.setText("{}".format(value))
        self.close_face_camera.set_actor_relative_location(unreal.Vector(0, self.camera_h_slider.value(), value), False, False)
        
    def on_screen_shot_btn_click(self):
        export_folder = get_export_folder_path()
        export_file_name = "{}/{}_{}_{}_{}.png".format(export_folder, 
                                                       "name", 
                                                       self.current_tod_name, 
                                                       self.current_camera_name, 
                                                       generate_random_string(6))
        unreal.AutomationLibrary().take_high_res_screenshot(3840, 2160, export_file_name)
        self.output_path_label.setText(export_file_name)
        self.output_widget.setVisible(True)
        self.on_view_camera_btn_click()
    
    def on_open_screen_shot_folder_btn_click(self):
        export_folder = get_export_folder_path()
        print(export_folder)
        import subprocess
        subprocess.Popen(r'explorer /select,{}'.format(os.path.realpath(self.output_path_label.text())))

    def on_adjust_light_clicked(self, checked):
        if checked:
            # sequence_path
            # sequence_path = LIGHTING_LEVEL_SEQUENCE_MAP[self.current_tod_name]
            sequence_obj = unreal.EditorAssetLibrary().load_asset("/Game/Art/Level/AssetMarket/Character/Assets/LightingSequence")
            unreal.LevelSequenceEditorBlueprintLibrary().open_level_sequence(sequence_obj)
        else:
            unreal.LevelSequenceEditorBlueprintLibrary().close_level_sequence()
            
    def closeEvent(self, event):
        level_actor_sub.eject_pilot_level_actor()
        level_actor_sub.editor_set_game_view(False)
        unreal.LevelSequenceEditorBlueprintLibrary().close_level_sequence()


if __name__ == "__main__":
    app = qt_util.create_qt_application()

    widget = MainScriptWindow()
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())