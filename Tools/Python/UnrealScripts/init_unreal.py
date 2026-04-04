import tool_menu_setup
from AssetImport import asset_import_watcher

if __name__ == '__main__':
    tool_menu_setup.init_tool_menus()
    asset_import_watcher.start_import_watcher()

