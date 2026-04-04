import sys
import unreal
import os

from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import qt_util
import path_util
from pathlib import Path

WINDOW_TITLE = "Delete Empty Folders"
WINDOW_MIN_WIDTH = 400
WINDOW_MIN_HEIGHT = 600

DEFAULT_ROOT_FOLDER = "Content/"


def search_empty_folders(root_folder):
    project_root = path_util.ue_project_root()
    folder_path = os.path.join(project_root, root_folder)
    
    if not os.path.exists(folder_path):
        return "", 0

    sub_folders = []
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        if os.path.isdir(item_path):
            sub_folders.append(item_path)
    #print(sub_folders)
    result_str = ""
    empty_folder_count = 0
    # break down the empty folder search to small chunks, so we can have a rough progress bar
    with unreal.ScopedSlowTask(len(sub_folders), "Search Empty Folders") as slow_task:
        # display the dialog
        slow_task.make_dialog(True)
        for item in sub_folders:
            if slow_task.should_cancel():
                break
            slow_task.enter_progress_frame(1, "Search Empty Folders in {}".format(item))

            # check the sub folder itself is empty
            try:
                if len(os.listdir(item)) == 0:
                    result_str = "{}{}\n".format(result_str, str(item).replace(project_root, ''))
                    empty_folder_count = empty_folder_count + 1
                    continue

                for p in Path(item).glob('**/*'):
                    if p.is_dir() and len(list(p.iterdir())) == 0:
                        result_str = "{}{}\n".format(result_str, str(p).replace(project_root, ''))
                        empty_folder_count = empty_folder_count + 1
                        
            except:
                # somehow this could happen that it will throw a folder permission error
                print("Some thing wrong with folder access permission")
    
    return result_str, empty_folder_count


def delete_empty_folders(folder_list):
    project_root = path_util.ue_project_root()
    for folder in folder_list:
        # not work?
        # folder_to_delete = os.path.join(project_root, folder)
        folder_to_delete = project_root + folder
        os.removedirs(folder_to_delete)


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
        label = QtWidgets.QLabel("Root Folder: (example: Content/Art/VFX)")
        self.main_layout.addWidget(label)
        self.text_box = QtWidgets.QLineEdit(DEFAULT_ROOT_FOLDER)
        self.main_layout.addWidget(self.text_box)
        btn = QtWidgets.QPushButton('Search Empty Folders')
        btn.clicked.connect(self.on_click_search_btn)
        self.main_layout.addWidget(btn)
        
        label = QtWidgets.QLabel("Search Result:")
        self.main_layout.addWidget(label)
        self.result_label = QtWidgets.QLabel("")
        self.main_layout.addWidget(self.result_label)
        self.result_text_box = QtWidgets.QPlainTextEdit('')
        self.result_text_box.setReadOnly(True)
        self.main_layout.addWidget(self.result_text_box)

        btn = QtWidgets.QPushButton('Delete Empty Folders!!!')
        btn.clicked.connect(self.on_click_delete_btn)
        self.main_layout.addWidget(btn)

    def on_click_search_btn(self):
        root_folder_relative = self.text_box.text()

        unreal.log(
            """
/p
/p      /\  /\  
/p     ｜｜ ｜｜       ∩   ∩ 
/p     ｜ \_/ |      / /_/ / 
/p     /  _ _ \     / —  — \  
/p    ｜  @  @｜    ｜@  @  ｜ 
/p    ｜    ω  |    \   ω   /  
/p    /\ _____/—(O)～        \ 
/p  /          |— / | \      ∧\ 
/p ｜         |   ( _∧       ｜\) 
/p ｜         |      ｜      ｜ 
        """)
        result_str, empty_folder_count= search_empty_folders(root_folder_relative)
        #print(result_str)
        if empty_folder_count == 0:
            self.result_label.setText("No empty folder found")
        else:
            self.result_label.setText("Found {} empty folders".format(empty_folder_count))
        self.result_text_box.setPlainText(result_str)
    
    def on_click_delete_btn(self):
        result_str = self.result_text_box.toPlainText()
        lines = result_str.split()
        if len(lines) > 0:
            delete_empty_folders(lines)
            QtWidgets.QMessageBox.information(self, "Info", "Delete Successfully!")
            self.result_text_box.setPlainText("")


if __name__ == "__main__":
    app = qt_util.create_qt_application()

    widget = MainScriptWindow()
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())