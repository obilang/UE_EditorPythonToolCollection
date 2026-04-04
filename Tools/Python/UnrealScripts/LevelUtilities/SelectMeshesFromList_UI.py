import sys

from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import qt_util
import unreal
from AssetChecker import checker_tools
import path_util
import math

editor_level_lib = unreal.EditorActorSubsystem()
editor_filter_lib = unreal.EditorFilterLibrary()
editor_asset_subsystem = unreal.EditorAssetSubsystem()


def get_meshes_from_current_level():
    mesh_list = []
    all_actors = editor_level_lib.get_all_level_actors()
    smas = editor_filter_lib.by_class(all_actors, unreal.StaticMeshActor)
    for sma in smas:
        smc = sma.static_mesh_component
        sm = smc.get_editor_property("static_mesh")
        if sm is None:
            continue
        sm_path = sm.get_package().get_path_name()
        if sm_path not in mesh_list:
            mesh_list.append(sm_path)
    return mesh_list


def get_meshes_from_text(text):
    mesh_set = set()
    lines = text.split('\n')
    for line in lines:
        if line == '':
            continue
        columns = line.split("'")
        if columns is not None and len(columns) > 1:
            mesh = columns[1]
            mesh_set.add(mesh)
        else:
            mesh_set.add(line)
    return mesh_set


def get_maps_from_text(text):
    map_set = set()
    lines = text.split('\n')
    for line in lines:
        if line == '':
            continue
        map_set.add(line)
    return map_set


def select_meshes_related_to(mesh_set):
    all_actors = editor_level_lib.get_all_level_actors()
    smas = editor_filter_lib.by_class(all_actors, unreal.StaticMeshActor)
    should_select_actors = []
    for sma in smas:
        smc = sma.static_mesh_component
        sm = smc.get_editor_property("static_mesh")
        if sm is None:
            continue
        sm_path = sm.get_package().get_path_name()
        if sm_path in mesh_set:
            # editor_level_lib.set_actor_selection_state(sma, True)
            should_select_actors.append(sma)
    # foliages = editor_filter_lib.by_class(all_actors, unreal.InstancedFoliageActor)
    # print(all_actors)
    editor_level_lib.set_selected_level_actors(should_select_actors)
    

PREVIEW_MESH_SPACE = 1000
TARGET_FOLDER = "Python_Spawned_Meshes"


def spawn_static_mesh_actor(mesh_item, location, index):
    mesh_obj: unreal.StaticMesh = unreal.load_asset(mesh_item)

    spawned_actor = editor_level_lib.spawn_actor_from_object(mesh_obj, location)
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
        approx_size = asset_data.get_tag_value("ApproxSize")
        approx_size = get_max_bound_size(approx_size)
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
            spawned_actor = spawn_static_mesh_actor(item['Path'], location, index)
            editor_level_lib.set_actor_selection_state(spawned_actor, True)
            index = index + 1
    

WINDOW_TITLE = "Select Meshes From List"
WINDOW_MIN_WIDTH = 400
WINDOW_MIN_HEIGHT = 600

    
class MainScriptWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(MainScriptWindow, self).__init__(parent)

        # window setup 
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(WINDOW_MIN_WIDTH)
        self.setMinimumHeight(WINDOW_MIN_HEIGHT)

        vbox = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel('Mesh List:')
        vbox.addWidget(label)
        self.text_box = QtWidgets.QPlainTextEdit('Input Mesh List Here')
        vbox.addWidget(self.text_box)
        btn = QtWidgets.QPushButton('Get Meshes From Current Gym')
        btn.clicked.connect(self.on_click_get_gym_mesh_btn)
        vbox.addWidget(btn)   
        btn = QtWidgets.QPushButton('Spawn Meshes To Current Gym')
        btn.clicked.connect(self.on_click_spawn_gym_mesh_btn)
        vbox.addWidget(btn)
        
        label = QtWidgets.QLabel('Level List:')
        vbox.addWidget(label)
        self.level_text_box = QtWidgets.QPlainTextEdit('')
        self.init_level_text_box_content()
        vbox.addWidget(self.level_text_box)
        btn = QtWidgets.QPushButton('Search Mesh Referenced Levels')
        btn.clicked.connect(self.on_click_search_mesh_level_btn)
        vbox.addWidget(btn)
        label = QtWidgets.QLabel('Please check the result in output log window')
        vbox.addWidget(label)

        btn = QtWidgets.QPushButton('Select Mesh In Current Level')
        btn.clicked.connect(self.on_click_select_mesh_btn)
        vbox.addWidget(btn)

        vbox.addStretch()

    def init_level_text_box_content(self):
        maps = checker_tools.get_used_maps()
        text_str = ""
        for map in maps:
            text_str = text_str + map + "\n"
        self.level_text_box.setPlainText(text_str)

    def on_click_get_gym_mesh_btn(self):
        unreal.log('Get Gym Meshes')
        meshes = get_meshes_from_current_level()
        text_str = ""
        for mesh in meshes:
            text_str = text_str + mesh + "\n"
        self.text_box.setPlainText(text_str)
        #print(meshes)
        
    def on_click_spawn_gym_mesh_btn(self):
        unreal.log('Spawn Gym Meshes')
        text = self.text_box.toPlainText()
        meshes = get_meshes_from_text(text)
        spawn_meshes_to_current_level(meshes)

    def on_click_search_mesh_level_btn(self):
        text = self.text_box.toPlainText()
        meshes = get_meshes_from_text(text)
        map_text = self.level_text_box.toPlainText()
        maps = get_maps_from_text(map_text)

        for mesh in meshes:
            if mesh is None or mesh == '':
                continue
            refs = unreal.EditorAssetLibrary.find_package_referencers_for_asset(mesh)
            if len(refs) > 0:
                levelRefs = set()
                for r in refs:
                    for map in maps:
                        if str(map) in r:
                            levelRefs.add(r)
                            # print("Map: {}".format(map))
                            # print("Ref: {}".format(r))
                            break

                if len(levelRefs) > 0:
                    print("---------------- Find Mesh: {} in Levels:".format(mesh))
                    for level_ref in levelRefs:
                        print("\t\t{}".format(level_ref))

    def on_click_select_mesh_btn(self):
        text = self.text_box.toPlainText()
        editor_level_lib.clear_actor_selection_set()
        meshes = get_meshes_from_text(text)
        select_meshes_related_to(meshes)
        #print(meshes)


if __name__ == "__main__":
    app = qt_util.create_qt_application()

    widget = MainScriptWindow()
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())