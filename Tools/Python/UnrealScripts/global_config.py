import path_util
import os

GLOBAL_CONFIG_FILE_PATH = os.path.join(path_util.tool_output_temp_folder(), "GlobalConfig/PythonToolConfig.ini")
DEFAULT_GLOBAL_CONFIG_FILE_PATH = os.path.join(path_util.ue_tool_python_path(), "Config/DefaultPythonToolConfig.ini")


def str_to_bool(str):
    return True if str == "True" else False


class GlobalConfig:
    def __init__(self):
        self.enable_import_hook = True
        
    def load_from_file(self):
        with open(DEFAULT_GLOBAL_CONFIG_FILE_PATH, 'r') as config_file:
            for line in config_file.readlines():
                if not line.isspace():
                    config = line.split("=")
                    config_name = config[0]
                    config_value = config[1]
                    if config_name == "enable_import_hook":
                        self.enable_import_hook = str_to_bool(config_value)
                        
        if os.path.exists(GLOBAL_CONFIG_FILE_PATH):
            with open(GLOBAL_CONFIG_FILE_PATH, 'r') as config_file:
                for line in config_file.readlines():
                    if not line.isspace():
                        config = line.split("=")
                        config_name = config[0]
                        config_value = config[1]
                        if config_name == "enable_import_hook":
                            self.enable_import_hook = str_to_bool(config_value)
                            print("self.enable_import_hook: {}".format(config_value))
                            
    def save_to_file(self):
        file_dir = os.path.dirname(GLOBAL_CONFIG_FILE_PATH)
        is_exist = os.path.exists(file_dir)
        if not is_exist:
            os.makedirs(file_dir)
            print("The new directory is created!")
        
        default_enable_import_hook = self.enable_import_hook
        with open(DEFAULT_GLOBAL_CONFIG_FILE_PATH, 'r') as config_file:
            for line in config_file.readlines():
                if not line.isspace():
                    config = line.split("=")
                    config_name = config[0]
                    config_value = config[1]
                    if config_name == "enable_import_hook":
                        default_enable_import_hook = str_to_bool(config_value)
        
        print("default import hook: {}".format(default_enable_import_hook))
        with open(GLOBAL_CONFIG_FILE_PATH, 'w') as config_file:
            if self.enable_import_hook != default_enable_import_hook:
                config_file.write("enable_import_hook={}\n".format(self.enable_import_hook))


GLOBAL_CONFIG = GlobalConfig()
GLOBAL_CONFIG.load_from_file()

