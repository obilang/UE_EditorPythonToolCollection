import sys
import types

import unreal

from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import qt_util
import os
import path_util
import json
from QtUtil import common_widgets
from QtUtil import qt_style_preset

from Cinematic import cinematic_utils
from LevelUtilities import level_utils

from typing import List

# import importlib
# importlib.reload(cinematic_utils)
# importlib.reload(level_utils)
# importlib.reload(qt_style_preset)


WINDOW_TITLE = "CS Character Lighting Setup Tool v1.0"
WINDOW_MIN_WIDTH = 1000
WINDOW_MIN_HEIGHT = 800
DOC_URL = "https://"

editor_util_lib = unreal.EditorUtilityLibrary()
level_sequence_lib = unreal.LevelSequenceEditorBlueprintLibrary()
sys_lib = unreal.SystemLibrary()
editor_actor_subsystem = unreal.EditorActorSubsystem()
source_control = unreal.SourceControl


DEFAULT_ATTACH_COMPONENT_NAME = "LightAttachment"
SPAWN_LIGHT_TYPES = [
    ["Spot Light", unreal.SpotLight, "Spot"],
    ["Rect Light", unreal.RectLight, "Rect"],
    ["Point Light", unreal.PointLight, "Point"]
]
TOOL_LIGHT_NAME_PREFIX = "AUTO_ATTACH_LIGHT_"
TOOL_LIGHT_FOLDER = "AUTO_ATTACH_LIGHTS"

CIN_CHARACTER_BP_PATH = "/Game/Cinematics/Art/Characters/"
CIN_PROP_BP_PATH = "/Game/Cinematics/Art/Props/"


PRESET_STORE_PATH = "Content\\Tools\\Cinematic\\CharacterLightSetup\\Presets"


def get_preset_folder_path():
    path = os.path.join(path_util.ue_project_root(), PRESET_STORE_PATH)
    path = os.path.realpath(path)
    return path


def show_save_preset_file_dialog():
    options = QtWidgets.QFileDialog.Options()
    options |= QtWidgets.QFileDialog.DontUseNativeDialog
    file_dialog = QtWidgets.QFileDialog()
    file_dialog.setDefaultSuffix('json')
    file_name, ext = file_dialog.getSaveFileName(
        None,
        "Light Preset",
        get_preset_folder_path(),
        "*.json",
        options=options,
    )
    
    file_name = str(file_name).replace(".json", "")
    return file_name + ".json"


def find_unique_name(current_sequence, base_name):
    exist_lights = get_all_binded_lights_name(current_sequence)
    exist_names = []
    for exist_light in exist_lights:
        exist_names.append(exist_light)
    
    has_same_name = False
    for exist_name in exist_names:
        if base_name in exist_name:
            has_same_name = True

    if has_same_name:
        MAX_LOOP = 499
        for i in range(0, MAX_LOOP):
            auto_name = "{}_{:02d}".format(base_name, i)
            has_same_name = False
            for exist_name in exist_names:
                if auto_name in exist_name:
                    has_same_name = True
                    break
            if not has_same_name:
                target_name = auto_name
                break
    else:
        target_name = base_name
                
    return target_name


class BindedCharacter:
    def __init__(self, binding_proxy: unreal.SequencerBindingProxy, ref_actor: unreal.Actor, sub_sequence: unreal.MovieSceneSequence):
        self.binding_proxy = binding_proxy
        self._ref_actor = ref_actor
        self.sub_sequence = sub_sequence
        
    def init_component_sockets(self):
        if self.ref_actor is not None:
            self.comp_sockets = cinematic_utils.get_all_attachable_sockets_in_actor(self.ref_actor)
        
    def get_display_name(self):
        return str(self.binding_proxy.get_display_name())

    @property
    def ref_actor(self):
        # if self._ref_actor is None:
        # Not work
        #     self._ref_actor = cinematic_utils.get_binding_source_object(self.binding_proxy, self.sub_sequence, cinematic_utils.get_current_opened_sequence())
        return self._ref_actor

    # a setter function
    @ref_actor.setter
    def ref_actor(self, a):
        self._ref_actor = a


class BindedLight:
    def __init__(self, binding_proxy: unreal.SequencerBindingProxy, ref_actor: unreal.Actor, attach_character: BindedCharacter, sub_sequence: unreal.MovieSceneSequence):
        self.binding_proxy = binding_proxy
        self._ref_actor = ref_actor
        self.attach_character = attach_character
        self.sub_sequence = sub_sequence
        self.attach_component = None
        self.attach_socket = None
        self.start_frame = -1
        self.end_frame = -1

    @property
    def ref_actor(self):
        if self._ref_actor is None:
            self._ref_actor = cinematic_utils.get_binding_source_object(self.binding_proxy, self.sub_sequence, cinematic_utils.get_current_opened_sequence())
        return self._ref_actor

    # a setter function
    @ref_actor.setter
    def ref_actor(self, a):
        self._ref_actor = a

    def get_display_name(self):
        return str(self.binding_proxy.get_display_name())
    
    def get_light_type(self):
        for LIGHT_TYPE in SPAWN_LIGHT_TYPES:
            if isinstance(self.ref_actor, LIGHT_TYPE[1]):
                return LIGHT_TYPE[2]
        return None
    
    def get_relative_transform(self):
        socket_transform = get_socket_world_transform(self.attach_character.ref_actor,
                                                      self.attach_component,
                                                      self.attach_socket)
        relative_trans = self.ref_actor.get_actor_transform().make_relative(socket_transform)
        return relative_trans
    
    def set_pivot_to_character_foot(self):
        socket_transform = get_socket_world_transform(self.attach_character.ref_actor,
                                                      DEFAULT_ATTACH_COMPONENT_NAME,
                                                      "pelvis")
        offset = socket_transform.make_relative(self.ref_actor.get_actor_transform())
        self.ref_actor.set_editor_property("pivot_offset", offset.translation)
        
    def reset_pivot_offset(self):
        self.ref_actor.set_editor_property("pivot_offset", [0, 0, 0])
        
    
def bind_light_to_character(binding_light: BindedLight, should_convert_to_relative=True):
    if should_convert_to_relative:
        socket_transform = get_socket_world_transform(binding_light.attach_character.ref_actor,
                                                      binding_light.attach_component,
                                                      binding_light.attach_socket)
        relative_trans = binding_light.ref_actor.get_actor_transform().make_relative(socket_transform)
        binding_light.ref_actor.set_actor_transform(relative_trans, False, False)
        
    binding_light.sub_sequence = cinematic_utils.get_current_focused_sequence()
    light_binding = cinematic_utils.add_actor_to_sequence(binding_light.ref_actor,
                                                          binding_light.sub_sequence)

    binding_light.binding_proxy = light_binding
    cinematic_utils.attach_binding_to(binding_light.binding_proxy,
                                      binding_light.attach_character.binding_proxy,
                                      binding_light.attach_component,
                                      binding_light.attach_socket,
                                      binding_light.start_frame,
                                      binding_light.end_frame,
                                      binding_light.sub_sequence
                                      )


def get_all_binded_BP(level_sequence: unreal.MovieSceneSequence) -> List[BindedCharacter]:
    binded_bps = []
    
    subsequences = cinematic_utils.get_subsequences(level_sequence)
    subsequences.append(level_sequence)

    with unreal.ScopedSlowTask(len(subsequences), "Finding Binding Characters...") as slow_task:
        # display the dialog
        slow_task.make_dialog(True)
        for subsequence in subsequences:
            if slow_task.should_cancel():
                break
            slow_task.enter_progress_frame(1, "Finding Binding Characters in {}".format(subsequence.get_name()))

            all_bindings = subsequence.get_bindings()
            for binding in all_bindings:
                object_class = binding.get_possessed_object_class()
                object_template = binding.get_object_template()

                if object_class is None:
                    if isinstance(object_template, unreal.Actor):
                        object_class = object_template.get_class()
                
                if object_class is not None and \
                    (CIN_CHARACTER_BP_PATH in object_class.get_path_name() or 
                     CIN_PROP_BP_PATH in object_class.get_path_name()):
                    origin_object = cinematic_utils.get_binding_source_object(binding, subsequence, level_sequence)
                    if origin_object is None:
                        continue
                    
                    binding_actor = BindedCharacter(binding, origin_object, subsequence)
                    binding_actor.init_component_sockets()
                    if CIN_CHARACTER_BP_PATH in object_class.get_path_name():
                        # make characters sort at top
                        binded_bps.insert(0, binding_actor)
                    else:
                        binded_bps.append(binding_actor)
                    
    return binded_bps


def get_all_binded_Lights(level_sequence, attach_character: BindedCharacter = None):
    binded_lights = []
    subsequences = cinematic_utils.get_subsequences(level_sequence)
    subsequences.append(level_sequence)
    with unreal.ScopedSlowTask(len(subsequences), "Finding Lights Attached to Character {}".format(attach_character.get_display_name())) as slow_task:
        # display the dialog
        slow_task.make_dialog(True)
        for subsequence in subsequences:
            if slow_task.should_cancel():
                break
            slow_task.enter_progress_frame(1, "Finding Lights Attached to Character {} in {}".format(attach_character.get_display_name(), subsequence.get_name()))
            all_bindings = subsequence.get_bindings()
            for binding in all_bindings:
                name = binding.get_display_name()
                if TOOL_LIGHT_NAME_PREFIX in str(name):
                    attach_binding = cinematic_utils.get_attached_binding(binding, level_sequence)
                    if attach_character is None or attach_binding is None:
                        # binding_actor = BindedLight(binding, source_actor, None, subsequence)
                        # binded_lights.append(binding_actor)
                        continue
                    elif cinematic_utils.is_same_binding(attach_binding[0].get_binding_id(), attach_character.binding_proxy.get_binding_id()):
                        source_actor = cinematic_utils.get_binding_source_object(binding, subsequence)
                        binding_actor = BindedLight(binding, source_actor, attach_character, subsequence)
                        binding_actor.attach_component = attach_binding[1]
                        binding_actor.attach_socket = attach_binding[2]
                        binding_actor.start_frame = attach_binding[3]
                        binding_actor.end_frame = attach_binding[4]
                        binded_lights.append(binding_actor)
    return binded_lights


def get_all_binded_lights_name(level_sequence):
    binded_lights = []
    subsequences = cinematic_utils.get_subsequences(level_sequence)
    subsequences.append(level_sequence)
    for subsequence in subsequences:
        all_bindings = subsequence.get_bindings()
        for binding in all_bindings:
            name = binding.get_display_name()
            if TOOL_LIGHT_NAME_PREFIX in str(name):
                binded_lights.append(str(name))
    return binded_lights


def get_actor_bounding_box_location(actor: unreal.Actor):
    origin, extent = actor.get_actor_bounds(True, True)
    return origin


def get_socket_world_transform(actor: unreal.Actor, component_name, socket_name) -> unreal.Transform:
    sk_components = actor.get_components_by_class(unreal.SkeletalMeshComponent)
    for sk_component in sk_components:
        if sk_component.get_name() == component_name:
            return sk_component.get_socket_transform(socket_name)
    

class MainScriptWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(MainScriptWindow, self).__init__(parent)
        
        self.last_actor_list = []

        # window setup 
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(WINDOW_MIN_WIDTH)
        self.setMinimumHeight(WINDOW_MIN_HEIGHT)

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self._init_data()
        self._build_ui()
        # align all widget to top
        self.main_layout.addStretch()
        
        self.per_tick_callback = unreal.register_slate_pre_tick_callback(self.per_tick)

        
    def _init_data(self):
        self.current_sequence = cinematic_utils.get_current_opened_sequence()
        self.binded_characters = get_all_binded_BP(self.current_sequence)
        self.target_binded_character: BindedCharacter = self.binded_characters[0]

    def _build_ui(self):
        # Document
        doc_widget = common_widgets.DocumentLinkBar(DOC_URL)
        self.main_layout.addWidget(doc_widget)

        layout_target_character = QtWidgets.QVBoxLayout()
        self.main_layout.addLayout(layout_target_character)
        
        label = QtWidgets.QLabel("Target Character BP:")
        layout_target_character.addWidget(label)

        self.target_chara_combobox = QtWidgets.QComboBox()
        self.target_chara_combobox.activated.connect(self.on_target_character_cb_changed)
        self.target_chara_combobox.addItem("None")
        layout_target_character.addWidget(self.target_chara_combobox)
        if len(self.binded_characters) > 0:
            self.target_chara_combobox.clear()
            for character_bp in self.binded_characters:
                combo_text = character_bp.get_display_name()
                self.target_chara_combobox.addItem(combo_text, character_bp)

        layout_attach_setup = QtWidgets.QVBoxLayout()
        layout_attach_setup.setContentsMargins(0, 20, 0, 0)
        self.main_layout.addLayout(layout_attach_setup)

        label = QtWidgets.QLabel("Attach Setup:")
        label.setStyleSheet(qt_style_preset.LABEL_TITLE_SECTION_LARGE)
        layout_attach_setup.addWidget(label)
        
        layout_h = QtWidgets.QHBoxLayout()
        layout_attach_setup.addLayout(layout_h)
        label = QtWidgets.QLabel("Attach Socket:")
        layout_h.addWidget(label)
        self.target_component_combobox = QtWidgets.QComboBox()
        self.target_component_combobox.activated.connect(self.on_target_component_cb_changed)
        self.target_component_combobox.addItem("None")
        layout_h.addWidget(self.target_component_combobox)
        self.target_socket_combobox = QtWidgets.QComboBox()
        self.target_socket_combobox.addItem("None")
        layout_h.addWidget(self.target_socket_combobox)

        # not good
        self.binding_lights_container = None
        self.update_target_binded_character()
        

        # ---------- select light type to spawn ----------
        layout_h = QtWidgets.QHBoxLayout()
        layout_attach_setup.addLayout(layout_h)
        label = QtWidgets.QLabel("Light To Spawn:")
        layout_h.addWidget(label)
        first_index = True
        for light_type in SPAWN_LIGHT_TYPES:
            radiobutton = QtWidgets.QRadioButton(light_type[0])
            radiobutton.actor_type = light_type
            if first_index:
                first_index = False
                radiobutton.setChecked(True)
                self.target_spawn_light_actor_type = light_type
            radiobutton.toggled.connect(self.on_click_light_type_radio_btn)
            layout_h.addWidget(radiobutton)
                
        layout_h = QtWidgets.QHBoxLayout()
        layout_attach_setup.addLayout(layout_h)
        label = QtWidgets.QLabel("Attach Frame Range:")
        layout_h.addWidget(label)
        self.attach_light_start_frame_tf = QtWidgets.QLineEdit("0")
        only_int = QtGui.QIntValidator()
        # only_int.setRange(0, 4)
        self.attach_light_start_frame_tf.setValidator(only_int)
        layout_h.addWidget(self.attach_light_start_frame_tf)
        label = QtWidgets.QLabel(" - ")
        layout_h.addWidget(label)
        self.attach_light_end_frame_tf = QtWidgets.QLineEdit("0")
        self.attach_light_end_frame_tf.setValidator(only_int)
        layout_h.addWidget(self.attach_light_end_frame_tf)
        self.update_attach_frame_range()
        
        layout_h = QtWidgets.QHBoxLayout()
        layout_attach_setup.addLayout(layout_h)
        label = QtWidgets.QLabel("Light Name:")
        layout_h.addWidget(label)
        self.attach_light_name_tf = QtWidgets.QLineEdit("")
        layout_h.addWidget(self.attach_light_name_tf)
        self.update_auto_light_name()
        btn = QtWidgets.QPushButton('Attach Light')
        btn.clicked.connect(self.on_click_attach_light_btn)
        layout_h.addWidget(btn)
        
        self.spawn_light_error_label = QtWidgets.QLabel("")
        self.spawn_light_error_label.setStyleSheet(qt_style_preset.LABEL_ERROR)
        layout_attach_setup.addWidget(self.spawn_light_error_label)

        # --------- All Binding Lights -----------
        layout_binding_lights = QtWidgets.QVBoxLayout()
        layout_binding_lights.setContentsMargins(0, 20, 0, 0)
        self.main_layout.addLayout(layout_binding_lights)

        label = QtWidgets.QLabel("Binding Lights:")
        label.setStyleSheet(qt_style_preset.LABEL_TITLE_SECTION_LARGE)
        layout_binding_lights.addWidget(label)

        layout_h = QtWidgets.QHBoxLayout()
        layout_binding_lights.addLayout(layout_h)

        self.light_preset_combobox = QtWidgets.QComboBox()
        layout_h.addWidget(self.light_preset_combobox)
        btn = QtWidgets.QPushButton('Load Preset')
        btn.clicked.connect(self.on_click_load_preset_btn)
        layout_h.addWidget(btn)

        btn = QtWidgets.QPushButton('Save Preset')
        btn.clicked.connect(self.on_click_save_preset_btn)
        layout_h.addWidget(btn)
        self.update_light_presets()

        # layout_h = QtWidgets.QHBoxLayout()
        # layout_binding_lights.addLayout(layout_h)
        
        layout_h.addStretch()
        btn = QtWidgets.QPushButton('Center Pivot')
        btn.clicked.connect(self.on_click_center_pivot_btn)
        layout_h.addWidget(btn)
        btn = QtWidgets.QPushButton('Reset Pivot')
        btn.clicked.connect(self.on_click_reset_pivot_btn)
        layout_h.addWidget(btn)
        # btn = QtWidgets.QPushButton('Update All')
        # btn.clicked.connect(self.on_click_update_all_lights_btn)
        # layout_h.addWidget(btn)

        self.binding_lights_container = QtWidgets.QVBoxLayout()
        layout_binding_lights.addLayout(self.binding_lights_container)
        self.update_binding_lights_container()
    
    def per_tick(self, delta):
        try:
            if self.target_binded_character.ref_actor is None:
                print("Close Tool Cause Sequence Saved")
                self.close()
            elif len(self.target_binded_character.ref_actor.get_components_by_class(unreal.SkeletalMeshComponent)) == 0:
                print("Close Tool Cause Sequence Saved")
                self.close()
        except:
            print("Close Tool Cause Sequence Saved")
            self.close()
            

    def on_click_center_pivot_btn(self):
        for light in self.binding_lights:
            light.set_pivot_to_character_foot()
        editor_actor_subsystem.clear_actor_selection_set()
        for light in self.binding_lights:
            editor_actor_subsystem.set_actor_selection_state(light.ref_actor, True)
            
    def on_click_reset_pivot_btn(self):
        for light in self.binding_lights:
            light.reset_pivot_offset()
        editor_actor_subsystem.clear_actor_selection_set()
            
    def on_click_update_all_lights_btn(self):
        # for light in self.b
        pass
    
    def on_click_save_preset_btn(self):
        file_path = show_save_preset_file_dialog()
        self.save_light_preset(file_path)

    def save_light_preset(self, preset_file_path):
        output_json = []
        for binding_light in self.binding_lights:
            light_transform = binding_light.get_relative_transform()
            light_json = {
                "name": binding_light.get_display_name(), 
                "light_type": binding_light.get_light_type(),
                "relative_location": "{},{},{}".format(light_transform.translation.x, 
                                                       light_transform.translation.y, 
                                                       light_transform.translation.z),
                "relative_rotation": "{},{},{}".format(light_transform.rotation.rotator().get_editor_property("roll"),
                                                       light_transform.rotation.rotator().get_editor_property("pitch"),
                                                       light_transform.rotation.rotator().get_editor_property("yaw")),
                "attach_component": str(binding_light.attach_component),
                "attach_socket": str(binding_light.attach_socket)
            }
            output_json.append(light_json)
        json_str = json.dumps(output_json)
        
        source_control.check_out_or_add_file(preset_file_path)
        
        with open(preset_file_path, 'w') as output_file:
            output_file.write(json_str)

        self.update_light_presets()
        
    def on_click_load_preset_btn(self):
        current_preset_path = self.light_preset_combobox.currentData()
        with open(current_preset_path, 'r') as json_file:
            data = json.loads(json_file.read())
            for light_data in data:
                self.load_light_to_sequence(light_data)
                
    def load_light_to_sequence(self, light_data):
        light_name = light_data["name"]
        target_name = find_unique_name(self.current_sequence, light_name)

        light_type = unreal.SpotLight
        for LIGHT_TYPE in SPAWN_LIGHT_TYPES:
            if LIGHT_TYPE[2] == light_data["light_type"]:
                light_type = LIGHT_TYPE[1]
        
        location_xyz = light_data["relative_location"].split(",")
        relative_location = unreal.Vector(float(location_xyz[0]), float(location_xyz[1]), float(location_xyz[2]))

        rotation_xyz = light_data["relative_rotation"].split(",")
        relative_rotation = unreal.Rotator(float(rotation_xyz[0]), float(rotation_xyz[1]), float(rotation_xyz[2]))
        
        light_actor = level_utils.spawn_actor_from_class(light_type, relative_location, target_name, TOOL_LIGHT_FOLDER)
        light_actor.set_actor_rotation(relative_rotation, False)
        
        binding_light = BindedLight(None, light_actor, self.target_binded_character, None)
        binding_light.attach_component = light_data["attach_component"]
        binding_light.attach_socket = light_data["attach_socket"]
        binding_light.start_frame = int(self.attach_light_start_frame_tf.text())
        binding_light.end_frame = int(self.attach_light_end_frame_tf.text())
        bind_light_to_character(binding_light, False)

        self.update_binding_lights_container(binding_light_to_add=binding_light)
        self.update_auto_light_name()
        
    def update_light_presets(self):
        self.light_preset_combobox.clear()
        folder_path = get_preset_folder_path()
        dir_file_pair = {}
        for (dir_path, dir_names, filenames) in os.walk(folder_path):
            dir_file_pair[dir_path] = filenames
            dir_short_name = dir_path.replace(folder_path, '')
            for file in filenames:
                self.light_preset_combobox.addItem("{}\\{}".format(dir_short_name, file.replace(".json", "")), 
                                                   "{}\\{}".format(dir_path, file))
        
    def on_click_attach_light_btn(self):
        self.spawn_light_error_label.setText("")
        light_type = self.target_spawn_light_actor_type[1]
        light_name = "{}{}".format(TOOL_LIGHT_NAME_PREFIX, self.attach_light_name_tf.text())
        
        if self.check_light_name_valid(light_name) is False:
            self.spawn_light_error_label.setText("Light name conflict. Please choose another name.")
            return 
        
        light_actor = level_utils.spawn_actor_from_class(light_type, [0, 0, 0], light_name, TOOL_LIGHT_FOLDER)
        binding_light = BindedLight(None, light_actor, self.target_binded_character, None)
        binding_light.attach_component = self.target_binded_component
        binding_light.attach_socket = self.target_socket_combobox.currentData()
        binding_light.start_frame = int(self.attach_light_start_frame_tf.text())
        binding_light.end_frame = int(self.attach_light_end_frame_tf.text())

        bind_light_to_character(binding_light, False)

        self.update_binding_lights_container(binding_light_to_add=binding_light)
        self.update_auto_light_name()
        
    def on_target_character_cb_changed(self):
        self.update_target_binded_character()
        
    def on_target_component_cb_changed(self):
        self.update_target_binded_component()
        
    def on_click_light_type_radio_btn(self):
        radio_button = self.sender()
        if radio_button.isChecked():
            self.target_spawn_light_actor_type = radio_button.actor_type
            self.update_auto_light_name()

    def closeEvent(self, event):
        unreal.log("end event")
        unreal.unregister_slate_pre_tick_callback(self.per_tick_callback)
        
    def update_target_binded_character(self):
        self.target_binded_character = self.target_chara_combobox.currentData()
        
        self.target_component_combobox.clear()
        index = 0
        default_index = 0
        for comp in self.target_binded_character.comp_sockets.keys():
            if comp == DEFAULT_ATTACH_COMPONENT_NAME:
                default_index = index
            self.target_component_combobox.addItem(comp, comp)
            index = index + 1
        self.target_component_combobox.setCurrentIndex(default_index)
        self.update_target_binded_component()
        self.update_binding_lights_container()

    def update_target_binded_component(self):
        self.target_binded_component = self.target_component_combobox.currentData()
        
        self.target_socket_combobox.clear()
        sockets = []
        if self.target_binded_component is not None:
            sockets = self.target_binded_character.comp_sockets[self.target_binded_component]
        for socket in reversed(sockets):
            self.target_socket_combobox.addItem(str(socket), socket)
        
    def update_binding_lights_container(self, binding_light_to_add=None, binding_light_to_delete=None):
        if self.binding_lights_container is None:
            return 
        
        if binding_light_to_add is not None:
            self.binding_lights.append(binding_light_to_add)
        elif binding_light_to_delete is not None:
            self.binding_lights.remove(binding_light_to_delete)
        else:
            self.binding_lights = get_all_binded_Lights(self.current_sequence, self.target_binded_character)
        qt_util.clear_qt_layout(self.binding_lights_container)
        for binding_light in self.binding_lights:
            binding_light_widget = BindingLightWidget(self, binding_light, self.current_sequence, self.target_binded_character)
            self.binding_lights_container.addWidget(binding_light_widget)
            
    def update_auto_light_name(self):
        exist_lights = get_all_binded_lights_name(self.current_sequence)
        exist_names = []
        for exist_light in exist_lights:
            exist_names.append(exist_light)
        
        MAX_LOOP = 99
        target_name = "Please Enter Light Name"
        for i in range(0, MAX_LOOP):
            auto_name = "{}_{:02d}".format(self.target_spawn_light_actor_type[2], i)
            has_same_name = False
            for exist_name in exist_names:
                if auto_name in exist_name:
                    has_same_name = True
                    break
            if not has_same_name:
                target_name = auto_name
                break
        
        self.attach_light_name_tf.setText(target_name)
    
    def check_light_name_valid(self, light_name):
        exist_lights = get_all_binded_lights_name(self.current_sequence)
        for exist_light in exist_lights:
            if light_name == exist_light:
                return False
        return True
    
    def update_attach_frame_range(self):
        self.attach_light_start_frame_tf.setText(str(self.current_sequence.get_playback_start()))
        self.attach_light_end_frame_tf.setText(str(self.current_sequence.get_playback_end()))

    def refresh_current_character(self):
        origin_object = cinematic_utils.get_binding_source_object(self.target_binded_character.binding_proxy,
                                                                  self.target_binded_character.sub_sequence, 
                                                                  self.current_sequence)
        # self.target_binded_character.ref_actor
    

class BindingLightWidget(QtWidgets.QWidget):
    def __init__(self, main_window: MainScriptWindow, 
                 binding_light: BindedLight, 
                 level_sequence: unreal.MovieSceneSequence,
                 target_character: BindedCharacter):
        super(BindingLightWidget, self).__init__()
        self.main_window = main_window
        self.binding_light = binding_light
        self.level_sequence = level_sequence
        self.target_character = target_character
        
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        h_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(h_layout)
        
        label = QtWidgets.QLabel("Light: {}".format(binding_light.get_display_name()))
        label.setStyleSheet(qt_style_preset.LABEL_NORMAL_HIGHLIGHT)
        h_layout.addWidget(label)
        label = QtWidgets.QLabel(" Current Binding Socket: {}.{} Frame Range[{}-{}]".format(
            str(binding_light.attach_component),
            str(binding_light.attach_socket),
            binding_light.start_frame,
            binding_light.end_frame
        ))
        h_layout.addWidget(label)
        
        h_layout.addStretch()

        select_btn = QtWidgets.QPushButton("Select")
        select_btn.clicked.connect(self.on_click_select_btn)
        h_layout.addWidget(select_btn)
        
        h_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(h_layout)

        self.target_component_combobox = QtWidgets.QComboBox()
        self.target_component_combobox.activated.connect(self.on_target_component_cb_changed)
        h_layout.addWidget(self.target_component_combobox)
        self.target_socket_combobox = QtWidgets.QComboBox()
        self.target_socket_combobox.addItem("None")
        h_layout.addWidget(self.target_socket_combobox)
        index = 0
        default_index = 0
        for comp in self.target_character.comp_sockets.keys():
            if comp == self.binding_light.attach_component:
                default_index = index
            self.target_component_combobox.addItem(comp, comp)
            index = index + 1
        self.target_component_combobox.setCurrentIndex(default_index)
        self.update_target_binded_component()

        label = QtWidgets.QLabel("Range:")
        h_layout.addWidget(label)
        self.attach_light_start_frame_tf = QtWidgets.QLineEdit(str(self.binding_light.start_frame))
        only_int = QtGui.QIntValidator()
        self.attach_light_start_frame_tf.setValidator(only_int)
        h_layout.addWidget(self.attach_light_start_frame_tf)
        label = QtWidgets.QLabel(" - ")
        h_layout.addWidget(label)
        self.attach_light_end_frame_tf = QtWidgets.QLineEdit(str(self.binding_light.end_frame))
        self.attach_light_end_frame_tf.setValidator(only_int)
        h_layout.addWidget(self.attach_light_end_frame_tf)
        
        h_layout.addStretch()

        delete_btn = QtWidgets.QPushButton("Delete")
        delete_btn.clicked.connect(self.on_click_delete_btn)
        h_layout.addWidget(delete_btn)

        update_btn = QtWidgets.QPushButton("Update")
        update_btn.clicked.connect(self.on_click_update_btn)
        h_layout.addWidget(update_btn)
        
    def on_click_select_btn(self):
        editor_actor_subsystem.clear_actor_selection_set()
        editor_actor_subsystem.set_selected_level_actors([self.binding_light.ref_actor])
        
    def on_click_delete_btn(self):
        self.binding_light.binding_proxy.remove()
        editor_actor_subsystem.destroy_actor(self.binding_light.ref_actor)
        
        self.main_window.update_binding_lights_container(binding_light_to_delete=self.binding_light)
        self.main_window.update_auto_light_name()
        
    def on_click_update_btn(self):
        self.binding_light.binding_proxy.remove()
        
        light_name = self.binding_light.ref_actor.get_actor_label()
        self.binding_light.ref_actor.set_actor_label("Temp_Pending_Delete")
        
        light_actor = editor_actor_subsystem.duplicate_actor(self.binding_light.ref_actor)
        editor_actor_subsystem.destroy_actor(self.binding_light.ref_actor)
        light_actor.set_actor_label(light_name)

        self.binding_light.ref_actor = light_actor
        self.binding_light.attach_character = self.target_character
        self.binding_light.attach_component = self.target_binded_component
        self.binding_light.attach_socket = self.target_socket_combobox.currentData()
        self.binding_light.start_frame = int(self.attach_light_start_frame_tf.text())
        self.binding_light.end_frame = int(self.attach_light_end_frame_tf.text())
        bind_light_to_character(self.binding_light, True)
        
        self.on_click_select_btn()

    def on_target_component_cb_changed(self):
        self.update_target_binded_component()

    def update_target_binded_component(self):
        self.target_binded_component = self.target_component_combobox.currentData()

        self.target_socket_combobox.clear()
        sockets = []
        if self.target_binded_component is not None:
            sockets = self.target_character.comp_sockets[self.target_binded_component]

        index = 0
        default_index = 0
        for socket in sockets:
            if socket == self.binding_light.attach_socket:
                default_index = index
            self.target_socket_combobox.addItem(str(socket), socket)
            index = index + 1
        self.target_socket_combobox.setCurrentIndex(default_index)


if __name__ == "__main__":
    app = qt_util.create_qt_application()
    main_window = MainScriptWindow()
    main_window.show()
    unreal.parent_external_window_to_slate(main_window.winId())
