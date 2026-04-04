from PySide6 import QtWidgets
from PySide6 import QtGui
from QtUtil import qt_util
import path_util
import os
from PySide6 import QtCore


class DocumentLinkBar(QtWidgets.QWidget):
    def __init__(self, url):
        super(DocumentLinkBar, self).__init__()
        self.layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.layout)
        
        self.layout.addStretch()
        
        pixmap = QtGui.QPixmap(os.path.join(path_util.qt_icon_path(), 'icon_info.png'))
        scaled = pixmap.scaled(20, 20)
        label = QtWidgets.QLabel()
        label.setPixmap(scaled)
        self.layout.addWidget(label)

        label = QtWidgets.QLabel()
        label.setOpenExternalLinks(True)
        label.setText(qt_util.get_hyper_link_txt(url, "Document"))

        self.layout.addWidget(label)
        
        
class ShowHideArrow(QtWidgets.QWidget):
    def __init__(self, linked_widget: QtWidgets.QWidget = None):
        super(ShowHideArrow, self).__init__()
        self.linked_widget = linked_widget
        
        self.check_box = QtWidgets.QCheckBox()
        self.check_box.clicked.connect(self.on_checked)
        self.check_box.setStyleSheet("""
        QCheckBox::indicator
        {
            background-color: transparent;
            border: 0px solid #D3D3D3;
            width: 12px;
            height: 12px;
            image:url("Icons:icon_arrow_right.png");
        }
        QCheckBox::indicator:checked
        {
            image:url("Icons:icon_arrow_down.png");
            background-color: transparent;
            border: 0px solid #D3D3D3;
        }
                """
        )
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.check_box)
        
    def link_to_widget(self, linked_widget: QtWidgets.QWidget, init_show=True):
        self.linked_widget = linked_widget
        self.check_box.setChecked(init_show)
        self.on_checked(init_show)
    
    def on_checked(self, is_checked) -> None:
        if self.linked_widget:
            if is_checked:
                self.linked_widget.show()
            else:
                self.linked_widget.hide()
