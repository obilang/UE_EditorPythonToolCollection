import os
import stat

UE_PROJECT_ROOT = "D:/Workspace/Unreal/PythonTools/"
UE_TOOL_PYTHON = "Tools/Python/UnrealScripts/"

PROJECT_ROOT = "../../../../"
TEMP_TOOL_GENERATE_FILE_ROOT = "Saved/PythonToolOutput/"

PACKAGE_PATH_ROOT = "/Game/"
SYSTEM_PATH_ROOT = "/Content/"


def ue_project_root():
    return os.path.realpath(UE_PROJECT_ROOT)

def ue_tool_python_path():
    return os.path.join(ue_project_root(), UE_TOOL_PYTHON)


def qt_icon_path():
    return os.path.join(ue_tool_python_path(), 'QtUtil/Icons/')


def current_working_directory():
    return os.getcwd()


def project_root():
    return os.path.realpath(os.path.join(os.getcwd(), PROJECT_ROOT))


def tool_output_temp_folder():
    return os.path.join(ue_project_root(), TEMP_TOOL_GENERATE_FILE_ROOT)


def get_system_path_from_ue_package_path(package_path: str, is_map_asset=False):
    package_path = str(package_path).replace(PACKAGE_PATH_ROOT, SYSTEM_PATH_ROOT)
    system_path = "{}{}.{}".format(ue_project_root(), package_path, "uasset" if not is_map_asset else "umap")
    return os.path.realpath(system_path)


def make_writable(filepath):
    """ Make file is writable on disk. """
    if os.path.isfile(filepath):
        os.chmod(str(filepath), stat.S_IWRITE)


def is_writable(filepath):
    """ Check if file is writable on disk. """
    return os.access(filepath, os.W_OK)

