import sys
import unreal

from PySide6 import QtGui
from PySide6 import QtWidgets
from QtUtil import qt_util


WINDOW_TITLE = "Window Template"
WINDOW_MIN_WIDTH = 400
WINDOW_MIN_HEIGHT = 600


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
        label = QtWidgets.QLabel("Input:")
        self.main_layout.addWidget(label)
        self.text_box = QtWidgets.QLineEdit('')
        self.main_layout.addWidget(self.text_box)
        btn = QtWidgets.QPushButton('Button')
        btn.clicked.connect(self.on_click_btn)
        self.main_layout.addWidget(btn)
    
    
    def on_click_btn(self):
        text = self.text_box.text()
        unreal.log_warning(text) 
        
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


if __name__ == "__main__":
    app = qt_util.create_qt_application()

    widget = MainScriptWindow()
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())