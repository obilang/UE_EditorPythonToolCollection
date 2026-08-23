"""Quickly renew the active Perforce ticket from the Unreal Tools menu.

The password is stored only in the current Windows user's Credential Manager.
No password is written to this project, the menu settings, or the Unreal
configuration files.
"""

import ctypes
from ctypes import wintypes

import unreal
from PySide6 import QtWidgets

from P4Utils import p4_wrapper
from QtUtil import qt_util


_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2
_ERROR_NOT_FOUND = 1168
_dialog = None


class _FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


class _CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", _FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


_PCREDENTIALW = ctypes.POINTER(_CREDENTIALW)


def _credential_target(server, user):
    return "FF16UE.Perforce.{}.{}".format(server, user)


def _credential_functions():
    credential_manager = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    credential_manager.CredReadW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_PCREDENTIALW),
    ]
    credential_manager.CredReadW.restype = wintypes.BOOL
    credential_manager.CredWriteW.argtypes = [ctypes.POINTER(_CREDENTIALW), wintypes.DWORD]
    credential_manager.CredWriteW.restype = wintypes.BOOL
    credential_manager.CredFree.argtypes = [ctypes.c_void_p]
    credential_manager.CredFree.restype = None
    return credential_manager


def load_password(target):
    """Return a password from Windows Credential Manager, or ``None``."""
    credential_manager = _credential_functions()
    credential = _PCREDENTIALW()
    if not credential_manager.CredReadW(target, _CRED_TYPE_GENERIC, 0, ctypes.byref(credential)):
        error = ctypes.get_last_error()
        if error == _ERROR_NOT_FOUND:
            return None
        raise ctypes.WinError(error)

    try:
        size = credential.contents.CredentialBlobSize
        password_bytes = ctypes.string_at(credential.contents.CredentialBlob, size)
        return password_bytes.decode("utf-16-le")
    finally:
        credential_manager.CredFree(credential)


def save_password(target, user, password):
    """Save a password in the current Windows user's Credential Manager."""
    password_bytes = password.encode("utf-16-le")
    password_buffer = ctypes.create_string_buffer(password_bytes)
    credential = _CREDENTIALW()
    credential.Type = _CRED_TYPE_GENERIC
    credential.TargetName = target
    credential.CredentialBlobSize = len(password_bytes)
    credential.CredentialBlob = ctypes.cast(password_buffer, ctypes.POINTER(ctypes.c_byte))
    credential.Persist = _CRED_PERSIST_LOCAL_MACHINE
    credential.UserName = user

    credential_manager = _credential_functions()
    if not credential_manager.CredWriteW(ctypes.byref(credential), 0):
        raise ctypes.WinError(ctypes.get_last_error())


def _error_message(error):
    errors = getattr(error, "errors", None)
    if errors:
        return "\n".join(str(item) for item in errors)
    return str(error)


class P4ReconnectDialog(QtWidgets.QDialog):
    def __init__(self, server, user, workspace, parent=None):
        super(P4ReconnectDialog, self).__init__(parent)
        self.server = server
        self.user = user
        self.workspace = workspace
        self.target = _credential_target(server, user)

        self.setWindowTitle("Reconnect Perforce")
        self.setMinimumWidth(440)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("No saved Perforce password was found."))
        layout.addWidget(QtWidgets.QLabel("Enter it once to save it securely for later reconnects."))

        connection = QtWidgets.QFormLayout()
        connection.addRow("Server:", QtWidgets.QLabel(server))
        connection.addRow("User:", QtWidgets.QLabel(user))
        connection.addRow("Workspace:", QtWidgets.QLabel(workspace))
        layout.addLayout(connection)

        self.password_edit = QtWidgets.QLineEdit()
        self.password_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Perforce password")
        layout.addWidget(self.password_edit)

        self.remember_password = QtWidgets.QCheckBox("Save in Windows Credential Manager")
        self.remember_password.setChecked(True)
        layout.addWidget(self.remember_password)

        buttons = QtWidgets.QDialogButtonBox()
        reconnect_button = buttons.addButton("Reconnect", QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        reconnect_button.clicked.connect(self.reconnect)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def reconnect(self):
        password = self.password_edit.text()
        if not password:
            QtWidgets.QMessageBox.warning(self, "Reconnect Perforce", "Enter your Perforce password.")
            return

        try:
            p4_wrapper.p4_login_ue_editor(password)
            if self.remember_password.isChecked():
                save_password(self.target, self.user, password)
        except Exception as error:
            unreal.log_error("Perforce reconnect failed: {}".format(_error_message(error)))
            QtWidgets.QMessageBox.critical(self, "Reconnect Perforce", _error_message(error))
            return

        QtWidgets.QMessageBox.information(self, "Reconnect Perforce", "Perforce is connected.")
        self.accept()


def reconnect():
    global _dialog
    server, user, workspace = p4_wrapper.ue_perforce_config()
    if not all((server, user, workspace)):
        message = "Configure Perforce in Unreal Editor Source Control before reconnecting."
        unreal.log_error(message)
        QtWidgets.QMessageBox.warning(None, "Reconnect Perforce", message)
        return

    target = _credential_target(server, user)
    try:
        password = load_password(target)
    except Exception as error:
        unreal.log_error("Could not access Windows Credential Manager: {}".format(error))
        password = None

    if password:
        try:
            p4_wrapper.p4_login_ue_editor(password)
        except Exception as error:
            unreal.log_warning("Saved Perforce password could not reconnect: {}".format(_error_message(error)))
        else:
            QtWidgets.QMessageBox.information(None, "Reconnect Perforce", "Perforce is connected.")
            return

    _dialog = P4ReconnectDialog(server, user, workspace)
    _dialog.show()
    _dialog.password_edit.setFocus()
    unreal.parent_external_window_to_slate(_dialog.winId())


if __name__ == "__main__":
    qt_util.create_qt_application()
    reconnect()
