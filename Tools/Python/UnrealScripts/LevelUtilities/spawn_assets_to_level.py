from PySide6 import QtWidgets
from PySide6 import QtCore
import unreal
import math
from LevelUtilities import level_utils
from AssetOperations import asset_utils

editor_level_lib = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor_filter_lib = unreal.EditorFilterLibrary()
editor_asset_subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_util_lib = unreal.EditorUtilityLibrary()

PREVIEW_MESH_SPACE = 1000
TARGET_FOLDER = "Python_Spawned_Meshes"


def spawn_asset_to_level(mesh_item, location, index):
    obj = unreal.load_asset(mesh_item)

    spawned_actor = editor_level_lib.spawn_actor_from_object(obj, location)
    spawned_actor.set_actor_location(location, False, False)
    spawned_actor.set_folder_path(TARGET_FOLDER)
    # name
    spawned_actor.set_actor_label("{:04}_{}".format(index, spawned_actor.get_actor_label()))
    return spawned_actor


def get_max_bound_size(approx_size: str):
    size_single = approx_size.split('x')
    max_size = int(size_single[0])
    if int(size_single[1]) > max_size:
        max_size = int(size_single[1])
    if int(size_single[2]) > max_size:
        max_size = int(size_single[2])
    return max_size


def spawn_meshes_to_current_level(mesh_names):
    mesh_count = len(mesh_names)
    editor_level_lib.clear_actor_selection_set()

    sorted_items = []
    for item in mesh_names:
        asset_data = editor_asset_subsystem.find_asset_data(item)
        asset_class_name = asset_utils.get_asset_data_class(asset_data.package_name)
        if asset_class_name == "StaticMesh":
            approx_size = asset_data.get_tag_value("ApproxSize")
            approx_size = get_max_bound_size(approx_size)
        else:
            approx_size = PREVIEW_MESH_SPACE
        # print(approx_size)
        sorted_items.append({'Path': item, 'Size': approx_size})

    sorted_items.sort(key=lambda x: x.get('Size'))

    # Spawn mesh in gym
    row_count = math.floor(int(math.sqrt(mesh_count))) + 1
    with unreal.ScopedSlowTask(mesh_count, "Spawning Meshes In Level..") as slow_task:
        # display the dialog
        slow_task.make_dialog(True)

        index = 0
        first_item_size = 0
        for item in sorted_items:
            if slow_task.should_cancel():
                break
            # unreal.log("Start spawning {}".format(item['Path']))
            slow_task.enter_progress_frame(1, item['Path'])

            row = int(index / row_count)
            column = int(math.fmod(index, row_count))

            if column == 0:
                first_item_size = item['Size']

            location = unreal.Vector(row * first_item_size, column * item['Size'], 0)
            spawned_actor = spawn_asset_to_level(item['Path'], location, index)
            editor_level_lib.set_actor_selection_state(spawned_actor, True)
            index = index + 1


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

            
class SpawnAssetWidget(QtWidgets.QWidget):
    def __init__(self):
        super(SpawnAssetWidget, self).__init__()
        self._events = {}

        vbox = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel('Asset List:')
        vbox.addWidget(label)
        self.text_box = QtWidgets.QPlainTextEdit('Input Asset List Here')
        self.text_box.textChanged.connect(self.on_asset_text_changed)
        vbox.addWidget(self.text_box)
        
        hbox = QtWidgets.QHBoxLayout()
        vbox.addLayout(hbox)
        
        btn = QtWidgets.QPushButton('Get Assets From Content Browser Selection')
        btn.clicked.connect(self.on_click_get_content_browser_mesh_btn)
        hbox.addWidget(btn)
        btn = QtWidgets.QPushButton('Get Selected Meshes From Current Level')
        btn.clicked.connect(self.on_click_get_gym_mesh_btn)
        hbox.addWidget(btn)
        
        btn = QtWidgets.QPushButton('Spawn Assets To Current Level')
        btn.clicked.connect(self.on_click_spawn_gym_mesh_btn)
        vbox.addWidget(btn)

    def add_event_listener(self, name, func):
        if name not in self._events:
            self._events[name] = [func]
        else:
            self._events[name].append(func)

    def dispatch_event(self, name, arg1):
        functions = self._events.get(name, [])
        for func in functions:
            QtCore.QTimer.singleShot(0, self, QtCore.SLOT(func(arg1)))
            
    def on_asset_text_changed(self):
        self.dispatch_event("AssetListChanged", self.get_mesh_paths_from_text())        

    def on_click_get_gym_mesh_btn(self):
        meshes = level_utils.get_meshes_components_from_current_level(True)
        text_str = ""
        for mesh in meshes:
            text_str = text_str + mesh + "\n"
        self.text_box.setPlainText(text_str)
        # print(meshes)
        
    def on_click_get_content_browser_mesh_btn(self):
        selected_assets = editor_util_lib.get_selected_asset_data()
        text_str = ""
        for select_asset in selected_assets:
            text_str = text_str + str(select_asset.package_name) + "\n"
        self.text_box.setPlainText(text_str)

    def on_click_spawn_gym_mesh_btn(self):
        meshes = self.get_mesh_paths_from_text()
        spawn_meshes_to_current_level(meshes)
        
    def get_mesh_paths_from_text(self):
        text = self.text_box.toPlainText()
        meshes = get_meshes_from_text(text)
        return meshes