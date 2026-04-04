from PySide6 import QtWidgets
from PySide6 import QtCore
import os
import path_util
import sys

UE_STYLE_SHEET = "unreal_qt_style.stylesheet"

# set global or it will be GC by unreal
g_qt_app = globals().get('__qt_app', None)


def create_qt_application(argv=None):
    global g_qt_app
    g_qt_app = QtWidgets.QApplication.instance()
    # in some case the instance could be None..
    if not g_qt_app:
        g_qt_app = QtWidgets.QApplication(sys.argv)
        
    # use unreal stylesheet
    QtCore.QDir.addSearchPath('Icons', os.path.join(path_util.ue_tool_python_path(), 'QtUtil/Icons'))
    style_file = os.path.join(path_util.ue_tool_python_path(), 'QtUtil', UE_STYLE_SHEET) 
    if g_qt_app.style().objectName() != UE_STYLE_SHEET:
        if UE_STYLE_SHEET is not None:
            if not os.path.isfile(style_file):
                raise Exception("Can not find style sheet: '%s'" % style_file)
            with open(style_file, "r") as sheet_file:
                g_qt_app.setStyleSheet(sheet_file.read())
                g_qt_app.style().setObjectName(UE_STYLE_SHEET)
    return g_qt_app


def clear_qt_layout(layout: QtWidgets.QLayout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
            child.widget().setParent(None)
            

def get_hyper_link_txt(url, name):
    link_template = "<a href={0} style='color:darkCyan'>{1}</a>"
    return link_template.format(url, name)


def pop_up_simple_messagebox(message, title=''):
    msg_box = QtWidgets.QMessageBox()
    msg_box.setText(message)
    msg_box.setWindowTitle(title)
    msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
    msg_box.exec_()
