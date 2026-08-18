from PySide6 import QtWidgets
from PySide6 import QtCore
import unreal
from QtUtil import qt_util

asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()

editor_util_lib = unreal.EditorUtilityLibrary()
editor_asset_subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
asset_editor_subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
mat_edit_lib = unreal.MaterialEditingLibrary()

WINDOW_TITLE = "Batch Change Physics Material"
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 800

NO_CHANGE_LABEL = "-- No Change --"
COL_ASSET = 0
COL_MESH = 1
COL_CURRENT_PM = 2
COL_TARGET_PM = 3


# ---------------------------------------------------------------------------
# Logic helpers
# ---------------------------------------------------------------------------

def parse_asset_paths(text):
    """Parse Unreal asset package paths from multi-line text, preserving order.
    Handles raw paths, Unreal reference strings (Class'/Game/…')
    and object paths (/Game/…Asset.Asset).
    """
    seen = set()
    result = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        parts = line.split("'")
        if len(parts) > 1:
            line = parts[1]
        parts = line.split(".")
        if len(parts) > 1:
            line = parts[0]
        if line not in seen:
            seen.add(line)
            result.append(line)
    return result


def load_phys_materials_in_folder(folder_path):
    """Return sorted list of {'name': str, 'path': str} for all
    PhysicalMaterial assets found recursively in *folder_path*.
    """
    ar_filter = unreal.ARFilter(
        package_paths=[folder_path],
        recursive_paths=True,
        class_paths=[unreal.TopLevelAssetPath("/Script/PhysicsCore", "PhysicalMaterial")],
        recursive_classes=True,
    )
    assets_data = asset_registry.get_assets(ar_filter)
    result = []
    for asset_data in assets_data:
        result.append({
            'name': str(asset_data.asset_name),
            'path': str(asset_data.package_name),
        })
    result.sort(key=lambda x: x['name'])
    return result


def get_current_phys_mat_name(mat_inst_path):
    """Load a MaterialInstance and return its current phys_material name."""
    mat_inst = unreal.load_asset(mat_inst_path)
    if not mat_inst or not isinstance(mat_inst, unreal.MaterialInstance):
        return "N/A"
    phys_mat = mat_inst.get_editor_property("phys_material")
    return phys_mat.get_name() if phys_mat else "None"


def get_first_referencing_static_mesh(mat_inst_path):
    """Return {'name': str, 'path': str} for the first StaticMesh that
    directly references *mat_inst_path*, or None if none found.
    """
    referencers = editor_asset_subsystem.find_package_referencers_for_asset(mat_inst_path, False)
    if not referencers:
        return None
    ar_filter = unreal.ARFilter(
        package_names=list(referencers),
        class_paths=[unreal.TopLevelAssetPath("/Script/Engine", "StaticMesh")],
    )
    assets = asset_registry.get_assets(ar_filter)
    if assets:
        asset_data = assets[0]
        return {
            'name': str(asset_data.asset_name),
            'path': str(asset_data.package_name),
        }
    return None


def get_material_instances_from_selected_actors():
    """Return an ordered, deduplicated list of MaterialInstance package paths
    from all StaticMeshComponents on currently selected level actors.
    """
    actors = editor_actor_subsystem.get_selected_level_actors()
    seen = set()
    result = []
    for actor in actors:
        components = actor.get_components_by_class(unreal.StaticMeshComponent)
        for comp in components:
            for mat in comp.get_materials():
                if not mat or not isinstance(mat, unreal.MaterialInstance):
                    continue
                path = mat.get_package().get_path_name()
                if path not in seen:
                    seen.add(path)
                    result.append(path)
    return result


def apply_phys_material_assignments(assignments):
    """assignments: list of (mat_inst_path, phys_mat_path | None).
    Entries with None phys_mat_path are skipped (No Change).
    Returns (success_list, fail_list).
    """
    phys_mat_cache = {}
    success_list = []
    fail_list = []
    assets_to_save = []

    with unreal.ScopedSlowTask(len(assignments), "Applying Physics Materials...") as slow_task:
        slow_task.make_dialog(True)
        for mat_path, pm_path in assignments:
            if slow_task.should_cancel():
                break
            slow_task.enter_progress_frame(1, mat_path)

            if pm_path is None:
                continue

            if pm_path not in phys_mat_cache:
                phys_mat_cache[pm_path] = unreal.load_asset(pm_path)
            phys_mat = phys_mat_cache[pm_path]

            if not phys_mat:
                fail_list.append("{} (PM failed to load: {})".format(mat_path, pm_path))
                continue

            mat_inst = unreal.load_asset(mat_path)
            if not mat_inst:
                fail_list.append("{} (failed to load)".format(mat_path))
                continue
            if not isinstance(mat_inst, unreal.MaterialInstance):
                fail_list.append("{} (not a MaterialInstance)".format(mat_path))
                continue

            mat_inst.set_editor_property("phys_material", phys_mat)
            mat_edit_lib.update_material_instance(mat_inst)
            assets_to_save.append(mat_inst)
            success_list.append(mat_path)

    if assets_to_save:
        editor_asset_subsystem.save_loaded_assets(assets_to_save, False)

    return success_list, fail_list


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class BatchChangePhysMatWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._phys_material_list = []
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        vbox = QtWidgets.QVBoxLayout(self)

        # ---- 1. Physics Material Source Folder (top) ----
        pm_group = QtWidgets.QGroupBox("Physics Material Source Folder")
        pm_group_layout = QtWidgets.QVBoxLayout(pm_group)
        vbox.addWidget(pm_group)

        hbox_folder = QtWidgets.QHBoxLayout()
        pm_group_layout.addLayout(hbox_folder)

        self.folder_input = QtWidgets.QLineEdit()
        self.folder_input.setPlaceholderText("/Game/Art/Materials/PhysicsMaterials")
        self.folder_input.setText("/CrystalMaterials/PhysicalMaterials/Enviroment/")
        hbox_folder.addWidget(self.folder_input)

        btn_load_pm = QtWidgets.QPushButton("Load")
        btn_load_pm.setFixedWidth(80)
        btn_load_pm.clicked.connect(self._on_load_phys_materials)
        hbox_folder.addWidget(btn_load_pm)

        self.pm_status_label = QtWidgets.QLabel("No physics materials loaded.")
        pm_group_layout.addWidget(self.pm_status_label)

        # ---- 2. Material Instance Asset List ----
        mi_group = QtWidgets.QGroupBox("Material Instance Asset List")
        mi_group_layout = QtWidgets.QVBoxLayout(mi_group)
        vbox.addWidget(mi_group)

        self.text_box = QtWidgets.QPlainTextEdit()
        self.text_box.setPlaceholderText(
            "Paste material instance package paths here, one per line.\n"
            "Example: /Game/Art/Materials/MI_Rock"
        )
        self.text_box.setMinimumHeight(120)
        mi_group_layout.addWidget(self.text_box)

        hbox_asset_btns = QtWidgets.QHBoxLayout()
        mi_group_layout.addLayout(hbox_asset_btns)

        btn_content_browser = QtWidgets.QPushButton("Get Assets From Content Browser Selection")
        btn_content_browser.clicked.connect(self._on_get_from_content_browser)
        hbox_asset_btns.addWidget(btn_content_browser)

        btn_from_level = QtWidgets.QPushButton("Get From Selected Level Actor")
        btn_from_level.clicked.connect(self._on_get_from_selected_level_actor)
        hbox_asset_btns.addWidget(btn_from_level)

        btn_load_assets = QtWidgets.QPushButton("Load Assets")
        btn_load_assets.clicked.connect(self._on_load_assets)
        hbox_asset_btns.addWidget(btn_load_assets)

        # ---- 3. Asset Table ----
        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Asset", "Used By Mesh", "Current PM", "Target PM"])
        self.table.horizontalHeader().setSectionResizeMode(
            COL_ASSET, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            COL_MESH, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            COL_CURRENT_PM, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(
            COL_TARGET_PM, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(200)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        vbox.addWidget(self.table)

        # ---- 4. Apply button ----
        btn_apply = QtWidgets.QPushButton("Apply to All")
        btn_apply.clicked.connect(self._on_apply_all)
        vbox.addWidget(btn_apply)

        # ---- 5. Log ----
        vbox.addWidget(QtWidgets.QLabel("Log:"))
        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(100)
        vbox.addWidget(self.log_box)

        self._on_load_phys_materials()

    # ------------------------------------------------------------------
    def _on_get_from_content_browser(self):
        selected_assets = editor_util_lib.get_selected_asset_data()
        lines = [str(a.package_name) for a in selected_assets]
        self.text_box.setPlainText("\n".join(lines))

    def _on_get_from_selected_level_actor(self):
        paths = get_material_instances_from_selected_actors()
        if not paths:
            self._log("No MaterialInstance assets found on the selected level actor(s).")
            return
        self.text_box.setPlainText("\n".join(paths))
        self._log("Found {} material instance(s) from selected actor(s).".format(len(paths)))

    def _on_load_phys_materials(self):
        folder = self.folder_input.text().strip()
        if not folder:
            self._log("Please enter a folder path.")
            return

        self._phys_material_list = load_phys_materials_in_folder(folder)

        if not self._phys_material_list:
            self._log("No PhysicalMaterial assets found in: {}".format(folder))
            self.pm_status_label.setText("No physics materials found.")
            return

        self.pm_status_label.setText("Loaded {} physics material(s).".format(
            len(self._phys_material_list)))
        self._log("Loaded {} physics material(s) from: {}".format(
            len(self._phys_material_list), folder))

        # Refresh combos in any existing table rows
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, COL_TARGET_PM)
            if combo:
                self._populate_pm_combo(combo)

    def _on_load_assets(self):
        asset_paths = parse_asset_paths(self.text_box.toPlainText())
        if not asset_paths:
            self._log("No asset paths found in the list.")
            return

        self.table.setRowCount(0)

        with unreal.ScopedSlowTask(len(asset_paths), "Loading material instances...") as slow_task:
            slow_task.make_dialog(True)
            for path in asset_paths:
                if slow_task.should_cancel():
                    break
                slow_task.enter_progress_frame(1, path)
                current_pm = get_current_phys_mat_name(path)
                mesh_info = get_first_referencing_static_mesh(path)
                self._add_table_row(path, current_pm, mesh_info)

        self._log("Loaded {} asset(s) into table.".format(self.table.rowCount()))

    def _add_table_row(self, asset_path, current_pm_name, mesh_info):
        row = self.table.rowCount()
        self.table.insertRow(row)

        asset_name = asset_path.rsplit('/', 1)[-1]
        item_asset = QtWidgets.QTableWidgetItem(asset_name)
        item_asset.setToolTip(asset_path)
        item_asset.setData(QtCore.Qt.ItemDataRole.UserRole, asset_path)
        self.table.setItem(row, COL_ASSET, item_asset)

        if mesh_info:
            item_mesh = QtWidgets.QTableWidgetItem(mesh_info['name'])
            item_mesh.setToolTip(mesh_info['path'])
            item_mesh.setData(QtCore.Qt.ItemDataRole.UserRole, mesh_info['path'])
        else:
            item_mesh = QtWidgets.QTableWidgetItem("--")
        self.table.setItem(row, COL_MESH, item_mesh)

        self.table.setItem(row, COL_CURRENT_PM, QtWidgets.QTableWidgetItem(current_pm_name))

        combo = QtWidgets.QComboBox()
        self._populate_pm_combo(combo)
        self.table.setCellWidget(row, COL_TARGET_PM, combo)

    def _populate_pm_combo(self, combo):
        current_data = combo.currentData()
        combo.clear()
        combo.addItem(NO_CHANGE_LABEL, None)
        for item in self._phys_material_list:
            combo.addItem(item['name'], item['path'])
        if current_data:
            idx = combo.findData(current_data)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _on_apply_all(self):
        row_count = self.table.rowCount()
        if row_count == 0:
            self._log("No assets in table. Load assets first.")
            return

        assignments = []
        for row in range(row_count):
            asset_item = self.table.item(row, COL_ASSET)
            asset_path = asset_item.data(QtCore.Qt.ItemDataRole.UserRole)
            combo = self.table.cellWidget(row, COL_TARGET_PM)
            pm_path = combo.currentData() if combo else None
            assignments.append((asset_path, pm_path))

        change_count = sum(1 for _, pm in assignments if pm is not None)
        self._log("Applying to {}/{} asset(s)...".format(change_count, row_count))

        success_list, fail_list = apply_phys_material_assignments(assignments)

        self._log("Done. Success: {}, Failed: {}, Skipped: {}.".format(
            len(success_list), len(fail_list), row_count - change_count))
        for path in success_list:
            self._log("  OK  : {}".format(path))
        for path in fail_list:
            self._log("  FAIL: {}".format(path))

        # Refresh Current PM column and reset combos for applied rows
        for row in range(row_count):
            asset_item = self.table.item(row, COL_ASSET)
            asset_path = asset_item.data(QtCore.Qt.ItemDataRole.UserRole)
            if asset_path in success_list:
                combo = self.table.cellWidget(row, COL_TARGET_PM)
                if combo:
                    self.table.item(row, COL_CURRENT_PM).setText(combo.currentText())
                    combo.setCurrentIndex(0)

    def _on_table_selection_changed(self):
        selected_rows = set(item.row() for item in self.table.selectedItems())
        asset_paths = []
        for row in selected_rows:
            asset_item = self.table.item(row, COL_ASSET)
            if asset_item:
                asset_paths.append(asset_item.data(QtCore.Qt.ItemDataRole.UserRole))
        if asset_paths:
            unreal.EditorAssetLibrary.sync_browser_to_objects(asset_paths)

    def _on_row_double_clicked(self, row, col):
        if col == COL_ASSET:
            item = self.table.item(row, COL_ASSET)
        elif col == COL_MESH:
            item = self.table.item(row, COL_MESH)
        else:
            return
        if not item:
            return
        asset_path = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not asset_path:
            return
        asset_obj = unreal.load_asset(asset_path)
        if asset_obj:
            asset_editor_subsystem.open_editor_for_assets([asset_obj])
        else:
            self._log("Could not load asset to open: {}".format(asset_path))

    def _log(self, msg):
        self.log_box.appendPlainText(msg)


# ---------------------------------------------------------------------------
# Standalone window (mirrors asset_common_tool_UI pattern)
# ---------------------------------------------------------------------------

class MainScriptWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(WINDOW_MIN_WIDTH)
        self.setMinimumHeight(WINDOW_MIN_HEIGHT)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(BatchChangePhysMatWidget())


if __name__ == "__main__":
    app = qt_util.create_qt_application()

    widget = MainScriptWindow()
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())
