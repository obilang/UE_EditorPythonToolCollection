import sys

import PySide6.QtCore
from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import qt_util
from QtUtil import qt_style_preset
import unreal

from LevelUtilities import level_utils


editor_filter_lib = unreal.EditorFilterLibrary()
editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor_subsystem = unreal.get_editor_subsystem(unreal.LayersSubsystem)


def get_all_static_mesh_actors():
    all_actors = editor_actor_subsystem.get_all_level_actors()
    smas = editor_filter_lib.by_class(all_actors, unreal.StaticMeshActor)
    return smas


class ActorSectionData:
    def __init__(self, name):
        self.name = name
        self.actors = []

    def init_display_properties(self, property_names):
        self.display_properties = property_names

    def find_valid_actors(self) -> {str: list}:
        return {}

    def select_actors(self):
        editor_actor_subsystem.clear_actor_selection_set()
        editor_actor_subsystem.set_selected_level_actors(self.actors)

    @staticmethod
    def get_property_value(actor, property_name):
        result = None
        try:
            result = actor.get_editor_property(property_name)
        except:
            # print("cannot find editor property")
            pass
        else:
            pass
        return str(result)


class StaticMeshSectionData(ActorSectionData):
    def __init__(self, name):
        super(StaticMeshSectionData, self).__init__(name)

    @staticmethod
    def get_property_value(actor, property_name):
        result = None
        static_mesh_component = actor.static_mesh_component
        try:
            result = static_mesh_component.get_editor_property(property_name)
        except:
            # print("cannot find editor property")
            pass
        else:
            pass

        return str(result)


class SameMeshSectionData(StaticMeshSectionData):
    def __init__(self, name):
        super(SameMeshSectionData, self).__init__(name)
        self.init_display_properties(
            [])

    def find_valid_actors(self) -> {str: list}:
        # all_actors = get_all_static_mesh_actors()
        all_actors = level_utils.get_meshes_from_current_level()
        # self.actors.clear() 
        return all_actors


class SameBpSectionData(ActorSectionData):
    def __init__(self, name):
        super(SameBpSectionData, self).__init__(name)
        self.init_display_properties(
            [])

    def find_valid_actors(self) -> {str: list}:
        # all_actors = get_all_static_mesh_actors()
        all_actors = level_utils.get_bps_from_current_level()
        # self.actors.clear()
        return all_actors


class LevelActorOverviewWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(LevelActorOverviewWidget, self).__init__(parent)

        vbox = QtWidgets.QVBoxLayout(self)
        self.setLayout(vbox)

        label = QtWidgets.QLabel(
            "Useful Actor Overview")
        label.setStyleSheet(qt_style_preset.LABEL_NORMAL_HIGHLIGHT)
        vbox.addWidget(label)

        section_data = SameMeshSectionData("Same Meshes")
        section_widget = ActorSectionWidget(section_data)
        vbox.addWidget(section_widget)

        section_data = SameBpSectionData("Same Blueprints")
        section_widget = ActorSectionWidget(section_data)
        vbox.addWidget(section_widget)

        vbox.addStretch()


class CustomTreeWidget(QtWidgets.QTreeWidgetItem):
    def __lt__(self, other):
        lvalue = self.text(2)
        rvalue = other.text(2)

        for num_type in (int, float):
            try:
                l_data = num_type(lvalue)
                r_data = num_type(rvalue)
                break
            except (ValueError, OverflowError):
                pass
        else:
            return lvalue < rvalue
            # super(CustomTableWidget, self).__lt__(other)

        return l_data < r_data


class ActorSectionWidget(QtWidgets.QWidget):
    def __init__(self, section_data: ActorSectionData):
        super(ActorSectionWidget, self).__init__()

        self.section_data = section_data

        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        h_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(h_layout)

        label = QtWidgets.QLabel(self.section_data.name)
        h_layout.addWidget(label)

        h_layout.addStretch()

        refresh_btn = QtWidgets.QPushButton('Collapse All')
        refresh_btn.clicked.connect(self.on_collapse_btn_clicked)
        h_layout.addWidget(refresh_btn)

        refresh_btn = QtWidgets.QPushButton('Expand All')
        refresh_btn.clicked.connect(self.on_expand_btn_clicked)
        h_layout.addWidget(refresh_btn)

        refresh_btn = QtWidgets.QPushButton('Refresh')
        refresh_btn.clicked.connect(self.on_refresh_btn_clicked)
        h_layout.addWidget(refresh_btn)

        self.table = QtWidgets.QTreeWidget(self)
        self.table.setSortingEnabled(True)
        # Disable editing
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.table.setMaximumHeight(400)
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        self.table.itemChanged.connect(self.on_table_changed)
        self.table.setColumnCount(2)
        self.table.setAllColumnsShowFocus(True)

        head_labels = self.section_data.display_properties.copy()
        head_labels.insert(0, "Visibility")
        head_labels.insert(1, "Path - Actor Name")
        head_labels.insert(2, "Number")
        head_labels.insert(3, "Default Class")
        head_labels.insert(4, "Source Asset Path")

        self.table.setHeaderLabels(head_labels)
        # self.table.resizeColumnToContents(3)
        self.layout.addWidget(self.table)

    def on_expand_btn_clicked(self):
        self.table.expandAll()

    def on_collapse_btn_clicked(self):
        self.table.collapseAll()

    def on_refresh_btn_clicked(self):
        actors = self.section_data.find_valid_actors()

        row = 0
        fnt = QtGui.QFont()
        fnt.setPointSize(10)

        self.table.clear()

        for key_path, value_actor_list in actors.items():
            table_widget_item = CustomTreeWidget(self.table)
            table_widget_item.setCheckState(0, QtGui.Qt.CheckState.PartiallyChecked)
            table_widget_item.setFont(1, fnt)
            table_widget_item.setFont(2, fnt)
            if key_path.find(".") > 0:
                table_widget_item.setText(1, key_path.split(".")[1])
            else:
                table_widget_item.setText(1, key_path)
            
            table_widget_item.setText(2, str(len(value_actor_list)))
            table_widget_item.setTextAlignment(2, QtGui.Qt.AlignRight)
            
            one_actor = value_actor_list[0]
            default_bp_name = str(one_actor.get_default_object().get_name())
            default_bp_name = default_bp_name[default_bp_name.rfind(".") + 1:]
            bp_name = str(one_actor.get_class())
            bp_name = bp_name[bp_name.find("'")+1:]
            bp_name = bp_name[0:bp_name.find("'")]
            table_widget_item.setText(3, default_bp_name)
            table_widget_item.setText(4, bp_name)
            
            table_widget_item.is_child = False
            table_widget_item.sub_item_list = []
            table_widget_item.actor_list = value_actor_list
            # if len(value_actor_list) > 1:
            #     table_widget_item.setExpanded(True)
            for actor in value_actor_list:
                table_widget_item_child = CustomTreeWidget(table_widget_item)
                table_widget_item_child.setFont(1, fnt)
                level_name = str(actor.get_package().get_name())
                level_name = level_name[level_name.rfind("/") + 1:]
                table_widget_item_child.setText(1, "    " + "{} | {}".format(level_name, actor.get_actor_label()))
                table_widget_item_child.is_child = True
                table_widget_item_child.actor = actor
                table_widget_item_child.parent = table_widget_item
                table_widget_item.sub_item_list.append(table_widget_item_child)
                if actor.is_hidden_ed() is True:
                    table_widget_item_child.setCheckState(0, QtGui.Qt.CheckState.Unchecked)
                else:
                    table_widget_item_child.setCheckState(0, QtGui.Qt.CheckState.Checked)
            self.table.resizeColumnToContents(1)
            self.table.sortItems(2, PySide6.QtCore.Qt.SortOrder.DescendingOrder)

    def on_table_selection_changed(self):
        editor_actor_subsystem.clear_actor_selection_set()
        for selected_item in self.table.selectedItems():
            if selected_item.is_child:
                editor_actor_subsystem.set_actor_selection_state(selected_item.actor, True)
                # selected_item.actor.set_is_temporarily_hidden_in_editor(True)
            else:
                for item in selected_item.actor_list:
                    editor_actor_subsystem.set_actor_selection_state(item, True)

    def on_table_changed(self, changed_item, changed_column):
        if changed_column is not 0:
            return
        if changed_item.checkState(changed_column) is QtGui.Qt.CheckState.PartiallyChecked:
            return

        if changed_item.is_child is False:
            if changed_item.checkState(changed_column) is QtGui.Qt.CheckState.Unchecked:
                for item in changed_item.actor_list:
                    item.set_is_temporarily_hidden_in_editor(True)
                for sub_item in changed_item.sub_item_list:
                    sub_item.setCheckState(0, QtGui.Qt.CheckState.Unchecked)
            elif changed_item.checkState(changed_column) is QtGui.Qt.CheckState.Checked:
                for item in changed_item.actor_list:
                    item.set_is_temporarily_hidden_in_editor(False)
                for sub_item in changed_item.sub_item_list:
                    sub_item.setCheckState(0, QtGui.Qt.CheckState.Checked)
        else:
            if changed_item.checkState(changed_column) is QtGui.Qt.CheckState.Unchecked:
                changed_item.actor.set_is_temporarily_hidden_in_editor(True)
            elif changed_item.checkState(changed_column) is QtGui.Qt.CheckState.Checked:
                changed_item.actor.set_is_temporarily_hidden_in_editor(False)
            # update parent check state
            visible_num = 0
            for sub_item in changed_item.parent.sub_item_list:
                if sub_item.checkState(changed_column) is QtGui.Qt.CheckState.Checked:
                    visible_num += 1
            if visible_num == len(changed_item.parent.sub_item_list):
                changed_item.parent.setCheckState(0, QtGui.Qt.CheckState.Checked)
            elif visible_num == 0:
                changed_item.parent.setCheckState(0, QtGui.Qt.CheckState.Unchecked)
            else:
                changed_item.parent.setCheckState(0, QtGui.Qt.CheckState.PartiallyChecked)
