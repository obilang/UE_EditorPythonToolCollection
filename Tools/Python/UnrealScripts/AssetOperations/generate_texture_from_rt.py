"""
generate_texture_from_rt.py

Generates a Texture2D asset from a TextureRenderTarget2D path.
Accepts the "Copy Reference" path format from the Unreal Editor, e.g.:
  /Script/Engine.TextureRenderTarget2D'/PrismParallaxMaterial/Maps/MAP_Demo.MAP_Demo:TextureRenderTarget2D_480'

Usage (from Unreal Python console):
  import AssetOperations.generate_texture_from_rt as gtr
  gtr.generate_texture_from_rt("/Script/Engine.TextureRenderTarget2D'/Game/Maps/MyMap.MyMap:MyRT'")

Or launch the UI directly:
  py AssetOperations/generate_texture_from_rt.py
"""

import sys
import unreal

from PySide6 import QtWidgets, QtCore
from QtUtil import qt_util


# ---------------------------------------------------------------------------
# Path utilities
# ---------------------------------------------------------------------------

def parse_rt_object_path(rt_path_str: str) -> str:
    """
    Extract the inner object path from a full Unreal reference string.

    Handles both formats:
      - /Script/Engine.TextureRenderTarget2D'/Game/Maps/MyMap.MyMap:MyRT'
      - /Game/Maps/MyMap.MyMap:MyRT
    """
    path = rt_path_str.strip()
    if "'" in path:
        start = path.index("'") + 1
        end = path.rindex("'")
        path = path[start:end]
    return path


def derive_default_name(object_path: str) -> str:
    """Derive a default texture name from the render target object path."""
    if ":" in object_path:
        return object_path.split(":")[-1]
    if "." in object_path:
        return object_path.split(".")[-1]
    return object_path.split("/")[-1]


def derive_default_output_dir(object_path: str) -> str:
    """Derive the default output directory (parent folder of the RT package)."""
    package_path = object_path.split(".")[0]
    parent = "/".join(package_path.split("/")[:-1])
    return parent if parent else "/Game"


# ---------------------------------------------------------------------------
# Core generation logic
# ---------------------------------------------------------------------------

COMPRESSION_OPTIONS = [
    ("Default (TC_DEFAULT)",         unreal.TextureCompressionSettings.TC_DEFAULT),
    ("Normal Map (TC_NORMALMAP)",    unreal.TextureCompressionSettings.TC_NORMALMAP),
    ("Grayscale (TC_GRAYSCALE)",     unreal.TextureCompressionSettings.TC_GRAYSCALE),
    ("HDR (TC_HDR)",                 unreal.TextureCompressionSettings.TC_HDR),
    ("High Quality (TC_BC7)",        unreal.TextureCompressionSettings.TC_BC7),
    ("No Compression (TC_EDITORICON)", unreal.TextureCompressionSettings.TC_EDITOR_ICON),
]

MIP_OPTIONS = [
    ("From Texture Group",   unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP),
    ("No Mipmaps",           unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS),
    ("Leave Existing Mips",  unreal.TextureMipGenSettings.TMGS_LEAVE_EXISTING_MIPS),
    ("Blur (1 Level)",       unreal.TextureMipGenSettings.TMGS_BLUR1),
    ("Sharpen (1 Level)",    unreal.TextureMipGenSettings.TMGS_SHARPEN1),
]


def generate_texture_from_rt(
    rt_path_str: str,
    output_name: str = "",
    output_dir: str = "",
    compression: unreal.TextureCompressionSettings = unreal.TextureCompressionSettings.TC_DEFAULT,
    mip_settings: unreal.TextureMipGenSettings = unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP,
) -> unreal.Texture2D:
    """
    Generate a Texture2D asset from a TextureRenderTarget2D.

    Args:
        rt_path_str:  Full reference path of the render target (from "Copy Reference").
        output_name:  Desired asset name. Defaults to the RT name.
        output_dir:   Target content browser folder (e.g. '/Game/Textures').
                      Defaults to the parent directory of the RT's package.
        compression:  Texture compression setting for the output texture.
        mip_settings: Mip-map generation setting for the output texture.

    Returns:
        The created unreal.Texture2D, or None on failure.
    """
    object_path = parse_rt_object_path(rt_path_str)
    if not object_path:
        unreal.log_error("[GenerateTextureFromRT] Empty render target path.")
        return None

    # Resolve defaults
    if not output_name:
        output_name = derive_default_name(object_path)
    if not output_dir:
        output_dir = derive_default_output_dir(object_path)

    # Load the render target
    unreal.log("[GenerateTextureFromRT] Loading render target: {}".format(object_path))
    render_target = unreal.load_object(None, object_path, unreal.TextureRenderTarget2D)
    if not render_target:
        unreal.log_error(
            "[GenerateTextureFromRT] Could not load TextureRenderTarget2D at: '{}'.\n"
            "Make sure the level containing the render target is loaded.".format(object_path)
        )
        return None

    # Create the Texture2D
    unreal.log("[GenerateTextureFromRT] Creating texture '{}' in '{}'...".format(output_name, output_dir))
    texture = unreal.RenderingLibrary.render_target_create_static_texture2d_editor_only(
        render_target, output_name, compression, mip_settings
    )

    if not texture:
        unreal.log_error("[GenerateTextureFromRT] render_target_create_static_texture2d_editor_only returned None.")
        return None

    created_pkg = texture.get_package().get_path_name()
    unreal.log("[GenerateTextureFromRT] Texture created at: {}".format(created_pkg))

    editor_asset_subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

    # Move to desired output directory if it differs from where it was created
    desired_pkg = "{}/{}".format(output_dir.rstrip("/"), output_name)
    if created_pkg != desired_pkg:
        success = editor_asset_subsystem.rename_asset(created_pkg, desired_pkg)
        if success:
            unreal.log("[GenerateTextureFromRT] Texture moved to: {}".format(desired_pkg))
            created_pkg = desired_pkg
        else:
            unreal.log_warning(
                "[GenerateTextureFromRT] Could not move texture to '{}'. "
                "Keeping at: {}".format(desired_pkg, created_pkg)
            )

    # Save
    editor_asset_subsystem.save_asset(created_pkg, only_if_is_dirty=False)
    unreal.log("[GenerateTextureFromRT] Done. Texture saved: {}".format(created_pkg))

    return texture


# ---------------------------------------------------------------------------
# Qt UI
# ---------------------------------------------------------------------------

WINDOW_TITLE = "Generate Texture from Render Target"
WINDOW_MIN_WIDTH = 520


class GenerateTextureFromRTWindow(QtWidgets.QDialog):
    def __init__(self, initial_rt_path: str = ""):
        super().__init__(None)
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(WINDOW_MIN_WIDTH)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self._build_ui(initial_rt_path)
        if initial_rt_path:
            self._on_rt_path_changed(initial_rt_path)

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self, initial_rt_path: str):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # --- Render Target Path ---
        main_layout.addWidget(self._make_label("Render Target Path (Copy Reference):"))
        rt_path_layout = QtWidgets.QHBoxLayout()
        self.rt_path_edit = QtWidgets.QLineEdit(initial_rt_path)
        self.rt_path_edit.setPlaceholderText(
            "/Script/Engine.TextureRenderTarget2D'/Game/Maps/MyMap.MyMap:MyRT'"
        )
        self.rt_path_edit.textChanged.connect(self._on_rt_path_changed)
        rt_path_layout.addWidget(self.rt_path_edit)
        main_layout.addLayout(rt_path_layout)

        # --- Resolved object path (read-only feedback) ---
        self.resolved_label = QtWidgets.QLabel("")
        self.resolved_label.setWordWrap(True)
        self.resolved_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        main_layout.addWidget(self.resolved_label)

        main_layout.addWidget(self._make_separator())

        # --- Output Directory ---
        main_layout.addWidget(self._make_label("Output Directory:"))
        out_dir_layout = QtWidgets.QHBoxLayout()
        self.out_dir_edit = QtWidgets.QLineEdit()
        self.out_dir_edit.setPlaceholderText("/Game/Textures")
        out_dir_layout.addWidget(self.out_dir_edit)
        main_layout.addLayout(out_dir_layout)

        # --- Output Name ---
        main_layout.addWidget(self._make_label("Output Texture Name:"))
        self.out_name_edit = QtWidgets.QLineEdit()
        self.out_name_edit.setPlaceholderText("MyTexture")
        main_layout.addWidget(self.out_name_edit)

        main_layout.addWidget(self._make_separator())

        # --- Compression ---
        main_layout.addWidget(self._make_label("Compression Settings:"))
        self.compression_combo = QtWidgets.QComboBox()
        for label, _ in COMPRESSION_OPTIONS:
            self.compression_combo.addItem(label)
        main_layout.addWidget(self.compression_combo)

        # --- Mip Settings ---
        main_layout.addWidget(self._make_label("Mip Generation Settings:"))
        self.mip_combo = QtWidgets.QComboBox()
        for label, _ in MIP_OPTIONS:
            self.mip_combo.addItem(label)
        main_layout.addWidget(self.mip_combo)

        main_layout.addWidget(self._make_separator())

        # --- Buttons ---
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        self.generate_btn = QtWidgets.QPushButton("Generate Texture")
        self.generate_btn.setFixedHeight(32)
        self.generate_btn.clicked.connect(self._on_generate)
        btn_layout.addWidget(self.generate_btn)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setFixedHeight(32)
        cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

        main_layout.addStretch()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_label(text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setStyleSheet("font-weight: bold;")
        return label

    @staticmethod
    def _make_separator() -> QtWidgets.QFrame:
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        return line

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_rt_path_changed(self, text: str):
        """Auto-populate output fields when a valid RT path is entered."""
        object_path = parse_rt_object_path(text)
        if object_path:
            self.resolved_label.setText("Object path: {}".format(object_path))
            if not self.out_name_edit.text():
                self.out_name_edit.setText(derive_default_name(object_path))
            if not self.out_dir_edit.text():
                self.out_dir_edit.setText(derive_default_output_dir(object_path))
        else:
            self.resolved_label.setText("")

    def _on_generate(self):
        rt_path = self.rt_path_edit.text().strip()
        if not rt_path:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Please enter a Render Target path.")
            return

        output_name = self.out_name_edit.text().strip()
        output_dir = self.out_dir_edit.text().strip()
        compression = COMPRESSION_OPTIONS[self.compression_combo.currentIndex()][1]
        mip_settings = MIP_OPTIONS[self.mip_combo.currentIndex()][1]

        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("Generating...")
        QtWidgets.QApplication.processEvents()

        try:
            texture = generate_texture_from_rt(
                rt_path,
                output_name=output_name,
                output_dir=output_dir,
                compression=compression,
                mip_settings=mip_settings,
            )
            if texture:
                result_path = texture.get_package().get_path_name()
                QtWidgets.QMessageBox.information(
                    self,
                    "Success",
                    "Texture2D created successfully!\n\n{}".format(result_path),
                )
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Failed",
                    "Failed to generate texture. Check the Unreal Output Log for details.",
                )
        except Exception as e:
            unreal.log_error("[GenerateTextureFromRT] Exception: {}".format(str(e)))
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
        finally:
            self.generate_btn.setEnabled(True)
            self.generate_btn.setText("Generate Texture")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Optionally accept an RT path as a command-line argument
    initial_path = sys.argv[1] if len(sys.argv) > 1 else ""

    app = qt_util.create_qt_application()

    window = GenerateTextureFromRTWindow(initial_path)
    window.show()
    unreal.parent_external_window_to_slate(window.winId())
