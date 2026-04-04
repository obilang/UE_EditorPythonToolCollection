import sys

from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import qt_util
from scipy.spatial import KDTree
import unreal
editor_level_lib = unreal.EditorActorSubsystem()
editor_filter_lib = unreal.EditorFilterLibrary()

# import importlib
# importlib.reload(qt_util)


def get_distance_of_two_actor(one, two):
    translation_one = one.get_actor_transform().translation
    translation_two = two.get_actor_transform().translation
    return translation_one.distance_squared(translation_two)


def if_near_equal(one, two):
    return one.get_actor_transform().is_near_equal(two.get_actor_transform())


def get_overlapping_assets_approximately(asset_instances):
    overlapping_instances = []

    pos_list = []
    for instance in asset_instances:
        pos = instance.get_actor_transform().translation
        pos_list.append((pos.x, pos.y, pos.z))

    kd_tree = KDTree(pos_list)
    pairs = kd_tree.query_pairs(r=0.0001)
        
    for (i, j) in pairs:
        # need to check rotation and scale near equal
        if if_near_equal(asset_instances[i], asset_instances[j]):
            overlapping_instances.append([asset_instances[i], asset_instances[j]])

    return overlapping_instances


def get_overlapping_duplicated_assets(target_actor_type):
    overlapping_meshes = {}
    if target_actor_type == "Mesh":
        meshes = get_meshes_from_current_level()
    else:
        meshes = get_bps_from_current_level()
    
    with unreal.ScopedSlowTask(len(meshes), "Checking Overlapping Meshes...") as slow_task:
        # display the dialog
        slow_task.make_dialog(True)
        for mesh_name, mesh_instances in meshes.items():
            if slow_task.should_cancel():
                break
            slow_task.enter_progress_frame(1, "Checking Overlapping Mesh: {}".format(mesh_name))
            if len(mesh_instances) > 1:
                # print("Mesh: {} Count:{}".format(mesh_name, len(mesh_instances)))
                overlapping_instances = get_overlapping_assets_approximately(mesh_instances)
                if len(overlapping_instances) > 0:
                    # print("-----------------------------{}-------------------------".format(mesh_name))
                    # print(overlapping_instances)
                    overlapping_meshes[mesh_name] = overlapping_instances
    
    return overlapping_meshes


def get_meshes_from_current_level():
    mesh_dict = {}
    all_actors = editor_level_lib.get_all_level_actors()
    smas = editor_filter_lib.by_class(all_actors, unreal.StaticMeshActor)
    for sma in smas:
        smc = sma.static_mesh_component
        sm = smc.get_editor_property("static_mesh")
        if sm is None:
            continue
        sm_path = str(sm).split("'")[1]
        if sm_path not in mesh_dict:
            mesh_dict[sm_path] = []
        if sma not in mesh_dict[sm_path]:
            mesh_dict[sm_path].append(sma)
    return mesh_dict


def get_bps_from_current_level():
    bp_dict = {}
    all_actors = editor_level_lib.get_all_level_actors()
    # bp_actors = editor_filter_lib.by_class(all_actors, unreal.Actor)
    
    for bp_actor in all_actors:
        if bp_actor.get_class().get_class().get_name() == "BlueprintGeneratedClass":
            bp_actor_class = unreal.SystemLibrary.get_class_display_name(bp_actor.get_class())
            if bp_actor_class not in bp_dict:
                bp_dict[bp_actor_class] = []
            if bp_actor not in bp_dict[bp_actor_class]:
                bp_dict[bp_actor_class].append(bp_actor)
    return bp_dict



WINDOW_TITLE = "Find Duplicated Actors"
WINDOW_MIN_WIDTH = 600
WINDOW_MIN_HEIGHT = 800


class MainScriptWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(MainScriptWindow, self).__init__(parent)

        # window setup 
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(WINDOW_MIN_WIDTH)
        self.setMinimumHeight(WINDOW_MIN_HEIGHT)


        vbox = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel("Warning: Please enable the visibility of every sublevel or the result won't be correct")
        vbox.addWidget(label)
        
        hbox = QtWidgets.QHBoxLayout()
        vbox.addLayout(hbox)

        radiobutton = QtWidgets.QRadioButton("Mesh")
        radiobutton.setChecked(True)
        radiobutton.actor_type = "Mesh"
        self.target_actor_type = "Mesh"
        radiobutton.toggled.connect(self.on_click_radio_btn)
        hbox.addWidget(radiobutton)

        radiobutton = QtWidgets.QRadioButton("BP")
        radiobutton.actor_type = "BP"
        radiobutton.toggled.connect(self.on_click_radio_btn)
        hbox.addWidget(radiobutton)

        btn = QtWidgets.QPushButton('Search')
        btn.clicked.connect(self.btn_clicked)
        vbox.addWidget(btn)
        self.text_box = QtWidgets.QPlainTextEdit('empty')
        self.text_box.setMinimumHeight(600)
        vbox.addWidget(self.text_box)
        vbox.addStretch()

    def on_click_radio_btn(self):
        radioButton = self.sender()
        if radioButton.isChecked():
            self.target_actor_type = radioButton.actor_type
            print("Select search type {}".format(self.target_actor_type))

    def btn_clicked(self):
        self.text_box.setPlainText('')
        #get_bps_from_current_level()
        editor_level_lib.clear_actor_selection_set()
        meshes = get_overlapping_duplicated_assets(self.target_actor_type)
        str_content = ''
        if meshes is None or len(meshes) == 0:
            self.text_box.setPlainText('no overlapping assets found')
        else:
            editor_level_lib.select_nothing()
            select_instances = []
            for mesh_name, mesh_instances in meshes.items():
                mesh_str = "-{}\n".format(mesh_name.split('/')[-1])
                mesh_instance_str = ''
                for instance_pair in mesh_instances:
                    mesh_instance_str = mesh_instance_str + "\t-{} | {}\n".format(instance_pair[0].get_actor_label(),
                                                                                    instance_pair[1].get_actor_label())
                    select_instances.append(instance_pair[0])

                str_content = str_content + mesh_str + mesh_instance_str
            self.text_box.setPlainText(str_content)
            
            editor_level_lib.set_selected_level_actors(select_instances)


if __name__ == "__main__":
    app = qt_util.create_qt_application()

    widget = MainScriptWindow()
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())