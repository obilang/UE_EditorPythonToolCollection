"""
Unreal Python Tools – Environment Setup Script
==================================================
Run via setup.bat which invokes this with the Unreal Engine embedded Python.

Actions performed:
  1. Validate setup_config.ini
  2. Download / install Python packages into .\\Libs
  3. Write / update the VS Code .code-workspace file
  4. Patch Config\\DefaultEngine.ini (Python plugin section)
  5. Patch UnrealScripts\\path_util.py constants
"""

from __future__ import annotations

import configparser
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths derived from this script's location
# ---------------------------------------------------------------------------
SCRIPT_ROOT = Path(__file__).resolve().parent   # …/Tools/Python
LIBS_DIR    = SCRIPT_ROOT / "Libs"
CONFIG_FILE = SCRIPT_ROOT / "setup_config.ini"
REQS_FILE   = SCRIPT_ROOT / "lib_requirements.txt"

SEPARATOR = "=" * 60


def log(msg: str = "") -> None:
    print(msg)


def log_section(title: str) -> None:
    log()
    log(SEPARATOR)
    log(f"  {title}")
    log(SEPARATOR)


def abort(msg: str) -> None:
    log(f"\n[ERROR] {msg}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 1. Read & validate config
# ---------------------------------------------------------------------------

def load_config() -> tuple[Path, Path, str, list[str]]:
    """Return (engine_dir, uproject_path, workspace_filename, plugin_py_paths)."""
    log_section("Reading setup_config.ini")

    if not CONFIG_FILE.exists():
        abort(f"Config file not found: {CONFIG_FILE}")

    cfg = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
    cfg.read(CONFIG_FILE, encoding="utf-8")

    def get(key: str) -> str:
        return cfg.get("Setup", key, fallback="").strip()

    raw_engine = get("UnrealEnginePath")
    raw_uproject = get("UProjectPath")

    if not raw_engine:
        abort("UnrealEnginePath is empty in setup_config.ini. Please fill it in.")
    if not raw_uproject:
        abort("UProjectPath is empty in setup_config.ini. Please fill it in.")

    engine_dir = Path(raw_engine)
    uproject_path = Path(raw_uproject)

    if not engine_dir.is_dir():
        abort(f"UnrealEnginePath does not exist: {engine_dir}")
    if not uproject_path.is_file():
        abort(f"UProjectPath does not exist: {uproject_path}")

    ue_python = engine_dir / "Binaries" / "ThirdParty" / "Python3" / "Win64" / "python.exe"
    if not ue_python.is_file():
        abort(f"UE Python not found at expected path:\n  {ue_python}\nCheck that UnrealEnginePath is correct.")

    workspace_filename = get("WorkspaceFileName").strip()
    if not workspace_filename:
        workspace_filename = uproject_path.stem + ".code-workspace"
    elif not workspace_filename.endswith(".code-workspace"):
        workspace_filename += ".code-workspace"

    raw_plugins = get("PluginPythonPaths")
    plugin_paths = [p.strip() for p in raw_plugins.split(";") if p.strip()]

    log(f"  Engine  : {engine_dir}")
    log(f"  Project : {uproject_path}")
    log(f"  Workspace file: {workspace_filename}")
    if plugin_paths:
        log(f"  Plugin Python paths:")
        for p in plugin_paths:
            log(f"    {p}")

    return engine_dir, uproject_path, workspace_filename, plugin_paths


# ---------------------------------------------------------------------------
# 2. Install Python packages into ./Libs
# ---------------------------------------------------------------------------

def install_packages(engine_dir: Path) -> None:
    log_section("Installing Python packages into .\\Libs")

    if not REQS_FILE.exists():
        log(f"  lib_requirements.txt not found – skipping package install.")
        return

    packages = []
    for line in REQS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            packages.append(line)

    if not packages:
        log("  No packages listed – skipping.")
        return

    ue_python = engine_dir / "Binaries" / "ThirdParty" / "Python3" / "Win64" / "python.exe"
    LIBS_DIR.mkdir(exist_ok=True)

    log(f"  Packages to install: {packages}")
    log(f"  Target directory   : {LIBS_DIR}")
    log()

    cmd = [
        str(ue_python), "-m", "pip", "install",
        "--target", str(LIBS_DIR),
        "--upgrade",
        "--no-user",
    ] + packages

    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        abort("pip install failed. Check the output above.")

    log("\n  Packages installed successfully.")


# ---------------------------------------------------------------------------
# 3. Update VS Code workspace file
# ---------------------------------------------------------------------------

def update_workspace(uproject_path: Path, workspace_filename: str,
                     plugin_paths: list[str]) -> None:
    log_section("Updating VS Code workspace file")

    uproject_root = uproject_path.parent
    workspace_file = SCRIPT_ROOT / workspace_filename

    # Collect all immediate sub-folders of SCRIPT_ROOT as relative folder entries
    folder_entries: list[dict] = []
    subfolder_names: list[str] = []

    for item in sorted(SCRIPT_ROOT.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            folder_entries.append({"path": item.name})
            subfolder_names.append(item.name)

    # Relative path from SCRIPT_ROOT to Intermediate/PythonStub
    python_stub_abs = uproject_root / "Intermediate" / "PythonStub"
    python_stub_rel = os.path.relpath(python_stub_abs, SCRIPT_ROOT).replace("\\", "/")
    folder_entries.append({"path": python_stub_rel})

    # Plugin Python folders – relative from SCRIPT_ROOT
    for plugin_rel in plugin_paths:
        plugin_abs = uproject_root / plugin_rel.replace("/", os.sep)
        plugin_rel_from_root = os.path.relpath(plugin_abs, SCRIPT_ROOT).replace("\\", "/")
        folder_entries.append({"path": plugin_rel_from_root})

    # Build python.analysis.extraPaths using ${workspaceFolder:Name} tokens.
    # The VS Code display name of a folder entry is the last path component.
    extra_paths = []
    for entry in folder_entries:
        display_name = Path(entry["path"]).name
        extra_paths.append(f"${{workspaceFolder:{display_name}}}")

    workspace_data = {
        "folders": folder_entries,
        "settings": {
            "python.analysis.extraPaths": extra_paths,
        },
    }

    workspace_file.write_text(
        json.dumps(workspace_data, indent="\t"),
        encoding="utf-8",
    )

    log(f"  Written: {workspace_file}")
    log(f"  Folders included:")
    for e in folder_entries:
        log(f"    {e['path']}")


# ---------------------------------------------------------------------------
# 4. Patch DefaultEngine.ini
# ---------------------------------------------------------------------------

def update_default_engine_ini(uproject_path: Path) -> None:
    log_section("Patching Config\\DefaultEngine.ini")

    uproject_root = uproject_path.parent
    ini_path = uproject_root / "Config" / "DefaultEngine.ini"

    if not ini_path.exists():
        abort(f"DefaultEngine.ini not found: {ini_path}")

    # Build the new values
    # UE PythonScriptPlugin accepts absolute paths for StartupScripts and AdditionalPaths.
    startup_script  = (SCRIPT_ROOT / "UnrealScripts" / "init_unreal.py").as_posix()
    path_scripts    = (SCRIPT_ROOT / "UnrealScripts").as_posix()
    path_libs       = LIBS_DIR.as_posix()

    SECTION = "[/Script/PythonScriptPlugin.PythonScriptPluginSettings]"

    text = ini_path.read_text(encoding="utf-8")

    # ---- Locate or create the section ----
    if SECTION not in text:
        # Append the whole section at the end
        text = text.rstrip() + "\n\n" + SECTION + "\n"

    # Split into lines for surgical editing
    lines = text.splitlines(keepends=True)

    in_section  = False
    section_end = len(lines)  # index of the line after the section ends

    # We will rebuild the section block in place
    section_start_idx = None
    new_lines: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped == SECTION:
            in_section = True
            section_start_idx = len(new_lines)
            new_lines.append(line)
            i += 1
            continue

        if in_section:
            # Check if we hit a new section
            if stripped.startswith("[") and stripped != SECTION:
                in_section = False
                section_end = len(new_lines)
                new_lines.append(line)
                i += 1
                continue

            # Skip lines we are going to rewrite
            if (stripped.startswith("+StartupScripts=")
                    or stripped.startswith("+AdditionalPaths=")
                    or stripped.startswith("bDeveloperMode=")):
                i += 1
                continue

            new_lines.append(line)
            i += 1
            continue

        new_lines.append(line)
        i += 1

    if section_start_idx is None:
        abort(f"Could not locate section '{SECTION}' after attempting to create it.")

    # Determine insertion point: right after the SECTION header line
    insert_idx = section_start_idx + 1

    injected = [
        f'+StartupScripts="{startup_script}"\n',
        f'+AdditionalPaths=(Path="{path_scripts}")\n',
        f'+AdditionalPaths=(Path="{path_libs}")\n',
        'bDeveloperMode=True\n',
    ]

    final_lines = new_lines[:insert_idx] + injected + new_lines[insert_idx:]
    ini_path.write_text("".join(final_lines), encoding="utf-8")

    log(f"  Patched: {ini_path}")
    log(f"  +StartupScripts    = {startup_script}")
    log(f"  +AdditionalPaths   = {path_scripts}")
    log(f"  +AdditionalPaths   = {path_libs}")
    log(f"  bDeveloperMode     = True")


# ---------------------------------------------------------------------------
# 5. Patch path_util.py
# ---------------------------------------------------------------------------

def update_path_util(uproject_path: Path) -> None:
    log_section("Patching UnrealScripts\\path_util.py")

    path_util = SCRIPT_ROOT / "UnrealScripts" / "path_util.py"
    if not path_util.exists():
        log(f"  path_util.py not found at {path_util} – skipping.")
        return

    uproject_root = uproject_path.parent

    # UE_PROJECT_ROOT: absolute path with forward slashes and trailing slash
    project_root_str = uproject_root.as_posix().rstrip("/") + "/"

    # UE_TOOL_PYTHON: relative path from project root to the UnrealScripts folder
    unrealscripts_abs = SCRIPT_ROOT / "UnrealScripts"
    tool_python_rel = os.path.relpath(unrealscripts_abs, uproject_root).replace("\\", "/").rstrip("/") + "/"

    text = path_util.read_text(encoding="utf-8")

    # Replace UE_PROJECT_ROOT = "..." (any quoted value on the same line)
    text = re.sub(
        r'^(UE_PROJECT_ROOT\s*=\s*)["\'].*?["\']',
        lambda m: f'{m.group(1)}"{project_root_str}"',
        text,
        flags=re.MULTILINE,
    )

    # Replace UE_TOOL_PYTHON = "..." (any quoted value on the same line)
    text = re.sub(
        r'^(UE_TOOL_PYTHON\s*=\s*)["\'].*?["\']',
        lambda m: f'{m.group(1)}"{tool_python_rel}"',
        text,
        flags=re.MULTILINE,
    )

    path_util.write_text(text, encoding="utf-8")

    log(f"  Patched: {path_util}")
    log(f"  UE_PROJECT_ROOT = \"{project_root_str}\"")
    log(f"  UE_TOOL_PYTHON  = \"{tool_python_rel}\"")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    log()
    log("Unreal Python Tools – Environment Setup")
    log(f"Script root: {SCRIPT_ROOT}")

    engine_dir, uproject_path, workspace_filename, plugin_paths = load_config()
    install_packages(engine_dir)
    update_workspace(uproject_path, workspace_filename, plugin_paths)
    update_default_engine_ini(uproject_path)
    update_path_util(uproject_path)

    log()
    log(SEPARATOR)
    log("  Setup complete!")
    log(SEPARATOR)
    log()


if __name__ == "__main__":
    main()
