from PySide6 import QtGui
from PySide6 import QtWidgets
from PySide6 import QtCore
from QtUtil import qt_util
from QtUtil import qt_style_preset
from typing import List
import unreal
from enum import Enum
from P4Utils import p4_wrapper
import path_util
import pyperclip

import os
import subprocess
from AssetOperations import asset_utils
import datetime

# import importlib
# importlib.reload(p4_wrapper)

editor_filter_lib = unreal.EditorFilterLibrary()
editor_asset_lib = unreal.EditorAssetLibrary()


class EValidStat(Enum):
    VALID = 'valid'
    INVALID_STRICT = 'invalid_strict'
    INVALID = 'invalid'
    
    
P4_COLUMN_CREATE = "Created By"
P4_COLUMN_LAST_CHANGE = "Last Changed By"
P4_COLUMN_MOST_CHANGE = "Most Changed By"
P4_COLUMN_LAST_CHANGE_DATE = "Last Change Date"
P4_COLUMNS = [
    P4_COLUMN_CREATE,
    P4_COLUMN_LAST_CHANGE,
    P4_COLUMN_MOST_CHANGE,
    P4_COLUMN_LAST_CHANGE_DATE
]


def copy2clip(txt):
    pyperclip.copy(txt)

# def copy2clip(txt):
#     txt = txt.replace('\n', '^')
#     cmd = 'echo '+txt.strip()+'|clip'
#     print(cmd)
#     return subprocess.check_call(cmd, shell=True)


class AssetSectionData:
    def __init__(self, name):
        self.name = name
        self.assets: List[unreal.AssetData] = []

    def init_display_properties(self, property_names):
        self.display_properties = property_names

    def find_valid_assets(self) -> List[unreal.AssetData]:
        self.assets = []
        return self.assets

    def get_property_value(self, asset: unreal.AssetData, property_name):
        result = None
        return str(result), EValidStat.VALID

    @staticmethod
    def get_asset_object(asset: unreal.AssetData):
        return editor_asset_lib.load_asset(str(asset.package_name))
    

class CommonAssetSectionData(AssetSectionData):
    def __init__(self, name, asset_paths):
        super(CommonAssetSectionData, self).__init__(name)
        self.asset_paths = asset_paths
        self.init_display_properties([])
    
    def find_valid_assets(self):
        self.assets = []
        for asset_path in self.asset_paths:
            if editor_asset_lib.does_asset_exist(asset_path):
                self.assets.append(editor_asset_lib.find_asset_data(asset_path))
        return self.assets


class CustomTableWidget(QtWidgets.QTableWidgetItem):
    def __lt__(self, other):   
        lvalue = self.text()
        rvalue = other.text()

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


class AssetSectionWidget(QtWidgets.QWidget):
    def __init__(self, section_data: AssetSectionData):
        super(AssetSectionWidget, self).__init__()
        self._events = {}
        self.section_data = section_data

        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        h_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(h_layout)

        label = QtWidgets.QLabel(self.section_data.name)
        h_layout.addWidget(label)
        
        h_layout.addSpacing(10)
        
        label = QtWidgets.QLabel("Invalid Percentage: ")
        h_layout.addWidget(label)
        self.invalid_percentage_label = QtWidgets.QLabel("")
        h_layout.addWidget(self.invalid_percentage_label)

        h_layout.addStretch()
        
        self.p4_history_cb = QtWidgets.QCheckBox("P4 History")
        self.p4_history_cb.clicked.connect(self.on_p4_history_cb_checked)
        self.p4_connected = False
        h_layout.addWidget(self.p4_history_cb)

        self.p4_stat_label = QtWidgets.QLabel("")
        h_layout.addWidget(self.p4_stat_label)

        refresh_btn = QtWidgets.QPushButton('Refresh')
        refresh_btn.clicked.connect(self.on_refresh_btn_clicked)
        h_layout.addWidget(refresh_btn)

        select_btn = QtWidgets.QPushButton('Copy Selected')
        select_btn.clicked.connect(self.on_select_btn_clicked)
        h_layout.addWidget(select_btn)

        self.table = QtWidgets.QTableWidget(self)
        self.table.setSortingEnabled(True)
        
        # Disable editing
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        # Hide index column
        self.table.verticalHeader().setVisible(False)
        self.table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        self.table.cellDoubleClicked.connect(self.on_table_double_clicked)
        property_column_counts = len(self.section_data.display_properties) + 1
        self.p4_column_index = property_column_counts
        self.table.setColumnCount(property_column_counts + len(P4_COLUMNS))

        # self.table.setColumnWidth(0, 150)

        head_labels = self.section_data.display_properties.copy()
        head_labels.insert(0, "Asset Name")
        index = 0
        for p4_column in P4_COLUMNS:
            head_labels.insert(self.p4_column_index + index, p4_column)
            index += 1
        self.show_p4_columns(False)
        self.table.setHorizontalHeaderLabels(head_labels)
        self.table.resizeColumnsToContents()
        self.layout.addWidget(self.table)

    def add_event_listener(self, name, func):
        if name not in self._events:
            self._events[name] = [func]
        else:
            self._events[name].append(func)

    def dispatch_event(self, name, arg1):
        functions = self._events.get(name, [])
        for func in functions:
            QtCore.QTimer.singleShot(0, self, QtCore.SLOT(func(arg1)))
            
    def show_p4_columns(self, show):
        for i in range(len(P4_COLUMNS)):
            if show:
                self.table.showColumn(self.p4_column_index + i)
            else:
                self.table.hideColumn(self.p4_column_index + i)
            
    def on_p4_history_cb_checked(self, checked):
        if checked:
            self.p4_connected = p4_wrapper.p4_init_ue_editor()
            if self.p4_connected:
                self.p4_stat_label.setText("Connected")
                self.p4_stat_label.setStyleSheet(qt_style_preset.LABEL_PASS)
            else:
                self.p4_history_cb.setChecked(False)
                self.p4_stat_label.setText("Fail To Connect")
                self.p4_stat_label.setStyleSheet(qt_style_preset.LABEL_ERROR)
        self.show_p4_columns(self.p4_history_cb.isChecked())
    
    def on_refresh_btn_clicked(self):
        self.table.setSortingEnabled(False)
        # for i in range(self.table.rowCount()):
        #     self.table.removeRow(i)
        while self.table.rowCount() > 0:
            self.table.removeRow(0)
        self.table.setRowCount(0)
        
        assets = self.section_data.find_valid_assets()
        self.table.setRowCount(len(assets))
        row = 0
        fnt = QtGui.QFont()
        fnt.setPointSize(7)

        show_p4_history = self.p4_history_cb.isChecked()
        
        invalid_count = 0
        with unreal.ScopedSlowTask(len(assets),
                                   "Getting asset properties") as slow_task:
            # display the dialog
            slow_task.make_dialog(True)
            for asset in assets:
                if slow_task.should_cancel():
                    break
                slow_task.enter_progress_frame(1, "Getting asset {} properties".format(asset.asset_name))
                
                table_widget_item = QtWidgets.QTableWidgetItem(str(asset.asset_name))
                table_widget_item.setFont(fnt)
                table_widget_item.is_name_column = True
                table_widget_item.asset = asset
                self.table.setItem(row, 0, table_widget_item)
    
                column = 1
                has_invalid_value = False
                for property_name in self.section_data.display_properties:
                    property_value, valid_stat = self.section_data.get_property_value(asset, property_name)
                    table_widget_item = CustomTableWidget(str(property_value))
                    table_widget_item.setData(QtCore.Qt.UserRole, property_value)
                        
                    if valid_stat == EValidStat.INVALID:
                        table_widget_item.setBackgroundColor(QtGui.QColor(255, 15, 0))
                        table_widget_item.setForeground(QtGui.QBrush(QtGui.QColor(0, 0, 0)))
                        has_invalid_value = True
                    elif valid_stat == EValidStat.INVALID_STRICT:
                        table_widget_item.setBackgroundColor(QtGui.QColor(255, 199, 3))
                        table_widget_item.setForeground(QtGui.QBrush(QtGui.QColor(0, 0, 0)))
                    table_widget_item.setFont(fnt)
                    table_widget_item.is_name_column = False
                    self.table.setItem(row, column, table_widget_item)
                    column += 1
                if has_invalid_value:
                    invalid_count += 1
                    
                if show_p4_history:
                    last_changed_by, created_by, modified_most_by, last_change_date = get_asset_p4_history(asset.package_name)
                    table_widget_item = QtWidgets.QTableWidgetItem(created_by)
                    self.table.setItem(row, self.p4_column_index, table_widget_item)
                    table_widget_item = QtWidgets.QTableWidgetItem(last_changed_by)
                    self.table.setItem(row, self.p4_column_index + 1, table_widget_item)
                    table_widget_item = QtWidgets.QTableWidgetItem(modified_most_by)
                    self.table.setItem(row, self.p4_column_index + 2, table_widget_item)
                    table_widget_item = QtWidgets.QTableWidgetItem(str(last_change_date))
                    self.table.setItem(row, self.p4_column_index + 3, table_widget_item)
                
                row += 1
        
        min_height = len(assets) * 100
        if min_height > 500:
            min_height = 500
        self.table.setMinimumHeight(min_height)
        self.invalid_percentage_label.setText("{:.2f}%".format(invalid_count * 100.0 / len(assets)))
        self.table.resizeColumnsToContents()
        self.table.adjustSize()
        
        self.table.setSortingEnabled(True)

    def on_select_btn_clicked(self):
        text_str = ""
        for selected_item in self.table.selectedItems():
            if selected_item.is_name_column:
                text_str = "{}{}\n".format(text_str, selected_item.asset.package_name)
        copy2clip(text_str)

    def on_table_selection_changed(self):
        asset_paths = []
        for selected_item in self.table.selectedItems():
            if selected_item.is_name_column:
                asset_paths.append(selected_item.asset.package_name)
        editor_asset_lib.sync_browser_to_objects(asset_paths)
        
        if len(self.table.selectedItems()) > 0:
            self.dispatch_event("on_select_item_changed", self.table.selectedItems()[0].asset)
        
    def on_table_double_clicked(self):
        for selected_item in self.table.selectedItems():
            if selected_item.is_name_column:
                unreal.AssetEditorSubsystem().open_editor_for_assets(
                    [unreal.load_asset(selected_item.asset.package_name)]
                )
                break
                
                
def get_asset_p4_history(asset_path):
    file_system_path = path_util.get_system_path_from_ue_package_path(asset_path)
    return p4_wrapper.get_file_history_user_details(file_system_path)
