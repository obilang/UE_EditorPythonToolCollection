import sys
import unreal

from PySide6 import QtCore
from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import qt_util
from LevelUtilities import level_utils


WINDOW_TITLE = "Modular Building"
WINDOW_MIN_WIDTH = 400
WINDOW_MIN_HEIGHT = 600


def get_all_static_meshes_in_level():
    """
    Returns a dict of {asset_path: [StaticMeshActor, ...]} for every
    StaticMeshActor in the currently open level.
    """
    return level_utils.get_meshes_from_current_level()


class MainScriptWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(MainScriptWindow, self).__init__(parent)

        # window setup
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(WINDOW_MIN_WIDTH)
        self.setMinimumHeight(WINDOW_MIN_HEIGHT)

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.build_ui()
        # align all widget to top
        self.main_layout.addStretch()

    def build_ui(self):
        # ── Level Static Mesh Section ──────────────────────────────────
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.main_layout.addWidget(separator)

        mesh_header_layout = QtWidgets.QHBoxLayout()
        mesh_label = QtWidgets.QLabel("Level Static Meshes:")
        mesh_header_layout.addWidget(mesh_label)
        mesh_header_layout.addStretch()

        self.btn_get_meshes = QtWidgets.QPushButton("Get Level Meshes")
        self.btn_get_meshes.clicked.connect(self.on_get_level_meshes)
        mesh_header_layout.addWidget(self.btn_get_meshes)
        self.main_layout.addLayout(mesh_header_layout)

        self.mesh_list_widget = QtWidgets.QListWidget()
        self.mesh_list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.mesh_list_widget.setMinimumHeight(200)
        self.mesh_list_widget.itemClicked.connect(self.on_mesh_item_clicked)
        self.main_layout.addWidget(self.mesh_list_widget)

        select_btn_layout = QtWidgets.QHBoxLayout()
        btn_select_all = QtWidgets.QPushButton("Select All")
        btn_select_all.clicked.connect(self.on_select_all_meshes)
        btn_deselect_all = QtWidgets.QPushButton("Deselect All")
        btn_deselect_all.clicked.connect(self.on_deselect_all_meshes)
        select_btn_layout.addWidget(btn_select_all)
        select_btn_layout.addWidget(btn_deselect_all)
        self.main_layout.addLayout(select_btn_layout)

        # internal storage: maps asset_path -> list of StaticMeshActors
        self._mesh_data = {}

    # ── Original button handler ────────────────────────────────────────
    def on_click_btn(self):
        text = self.text_box.text()
        unreal.log_warning(text)

    # ── Level mesh handlers ────────────────────────────────────────────
    def on_get_level_meshes(self):
        """Populate the list with every unique static mesh asset in the level."""
        self.mesh_list_widget.clear()
        self._mesh_data = get_all_static_meshes_in_level()

        for asset_path, actors in self._mesh_data.items():
            # Show the asset name with the actor count for clarity
            display_name = asset_path.split('/')[-1]  # e.g. "SM_Wall"
            label = "{} ({} actor{})  –  {}".format(
                display_name,
                len(actors),
                "s" if len(actors) != 1 else "",
                asset_path,
            )
            item = QtWidgets.QListWidgetItem(label)
            item.setFlags(
                item.flags()
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                | QtCore.Qt.ItemFlag.ItemIsEnabled
            )
            item.setCheckState(QtCore.Qt.CheckState.Unchecked)
            # Store the asset path as item data for easy retrieval
            item.setData(QtCore.Qt.ItemDataRole.UserRole, asset_path)
            self.mesh_list_widget.addItem(item)

        unreal.log("Found {} unique static mesh asset(s) in level.".format(len(self._mesh_data)))

    def on_mesh_item_clicked(self, item: QtWidgets.QListWidgetItem):
        """Select all level actors that use the clicked static mesh asset."""
        asset_path = item.data(QtCore.Qt.ItemDataRole.UserRole)
        actors = self._mesh_data.get(asset_path, [])
        if actors:
            editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
            editor_actor_subsystem.set_selected_level_actors(actors)

    def on_select_all_meshes(self):
        for i in range(self.mesh_list_widget.count()):
            self.mesh_list_widget.item(i).setCheckState(QtCore.Qt.CheckState.Checked)

    def on_deselect_all_meshes(self):
        for i in range(self.mesh_list_widget.count()):
            self.mesh_list_widget.item(i).setCheckState(QtCore.Qt.CheckState.Unchecked)

    def get_selected_meshes(self):
        """
        Returns a dict of {asset_path: [StaticMeshActor, ...]} for every
        mesh whose checkbox is checked in the list.
        """
        result = {}
        for i in range(self.mesh_list_widget.count()):
            item = self.mesh_list_widget.item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                asset_path = item.data(QtCore.Qt.ItemDataRole.UserRole)
                if asset_path in self._mesh_data:
                    result[asset_path] = self._mesh_data[asset_path]
        return result


if __name__ == "__main__":
    app = qt_util.create_qt_application()

    widget = MainScriptWindow()
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())