import unreal
import path_util
import json
import os

MAIN_MENU_NAME = "LevelEditor.MainMenu"
ACTOR_CONTEXT_MENU_NAME = "LevelEditor.LevelEditorSceneOutliner.ContextMenu"
CONTENT_BROWSER_CONTEXT_MENU_NAME = "ContentBrowser.AssetContextMenu"
PYTHON_TOOL_MENU_NAME = "PythonTools"
SECTION_UTILS = "Utils"
SECTION_SCRIPTS = "PythonScripts"
SECTION_ACTOR_CONTEXT = "CustomActorContext"
SECTION_CONTENT_BROWSER_CONTEXT = "CustomContentBrowserContext"

MENU_SETTING_FILE = "tool_menu_settings.json"


class ScriptItem:
    def __init__(self):
        self.id = ""
        self.name = ""
        self.script_path = ""
        self.menu_path = ""
        self.tool_type = ""
        self.custom_string_command = ""
    
    def init_from_json(self, data_dict):
        self.id = data_dict["id"]
        self.name = data_dict["name"]
        self.script_path = data_dict["script_path"]
        self.menu_path = data_dict["menu_path"]
        self.tool_type = data_dict["tool_type"]
        self.custom_string_command = data_dict["custom_string_command"]


def group_scripts(script_items):
    group = {}
    for item in script_items:
        if item.menu_path not in group:
            item_list = []
            group[item.menu_path] = item_list
        group[item.menu_path].append(item)
    
    return group


def list_menu(num=1000):
    """
    util function to get all registered menus in editor
    :param num: 
    :return: 
    """
    menu_list = set()
    for i in range(num):
        obj = unreal.find_object(None,"/Engine/Transient.ToolMenus_0:RegisteredMenu_%s" % i)
        if not obj:
            continue
        menu_name = str(obj.menu_name)
        if menu_name != "None":
            menu_list.add(menu_name)
            print(menu_name)
    return list(menu_list)


def create_menu_entry(entry_id, entry_label_name, tool_type, script_path, custom_str_command=''):
    entry = unreal.ToolMenuEntry(
        name=entry_id,
        type=unreal.MultiBlockType.MENU_ENTRY,
        insert_position=unreal.ToolMenuInsert("", unreal.ToolMenuInsertType.FIRST)
    )
    # print(entry)
    entry.set_label(entry_label_name)
    if custom_str_command != "":
        str_command = custom_str_command
    elif tool_type == "Python":
        str_command = "{}/{}".format(path_util.ue_project_root(), script_path)
    else:
        str_command = """
import unreal
euw_asset = unreal.EditorAssetLibrary.load_asset('{}')
print(euw_asset)
if euw_asset is not None:
    unreal.EditorUtilitySubsystem().spawn_and_register_tab(euw_asset)
                            """.format(script_path)
    entry.set_string_command(unreal.ToolMenuStringCommandType.PYTHON,
                             custom_type="Python",
                             string=str_command)
    return entry


def add_sub_menu(parent_context_menu, section_context_name, json_items):
    script_items = []
    for item in json_items:
        script_item = ScriptItem()
        script_item.init_from_json(item)
        script_items.append(script_item)
    groups = group_scripts(script_items)

    for group_key, group_items in groups.items():
        group_menu = parent_context_menu.add_sub_menu(parent_context_menu.get_name(), section_context_name, group_key,
                                                     group_key)
        for group_item in group_items:
            # print(group_item)
            entry = create_menu_entry(group_item.id,
                                      group_item.name,
                                      group_item.tool_type,
                                      group_item.script_path,
                                      group_item.custom_string_command)
            group_menu.add_menu_entry(section_context_name, entry)


def refresh_tool_menus():
    menus = unreal.ToolMenus.get()

    # read json
    setting_file_path = os.path.join(path_util.ue_tool_python_path(), MENU_SETTING_FILE)
    with open(setting_file_path, "r") as setting_file:
        setting = json.load(setting_file)

    if setting is not None:
        python_menu_name = "{}.{}".format(MAIN_MENU_NAME, PYTHON_TOOL_MENU_NAME)
        python_menu = menus.find_menu(python_menu_name)
        if python_menu is not None:
            # TODO: this will not clean up the existing entries, need further research
            menus.remove_section(python_menu_name, SECTION_SCRIPTS)
            # menus.unregister_owner_by_name(python_menu_name + "." + SECTION_SCRIPTS)
            python_menu.add_section(SECTION_SCRIPTS, "Tools")
            
            items = setting['menu_items']
            add_sub_menu(python_menu, SECTION_SCRIPTS, items)
            
            # script_items = []
            # for item in items:
            #     script_item = ScriptItem()
            #     script_item.init_from_json(item)
            #     script_items.append(script_item)
            # groups = group_scripts(script_items)
            # 
            # for group_key, group_items in groups.items():
            #     group_menu = python_menu.add_sub_menu(python_menu.get_name(), SECTION_SCRIPTS, group_key, group_key)
            #     for group_item in group_items:
            #         # print(group_item)
            #         entry = create_menu_entry(group_item.id, 
            #                                   group_item.name, 
            #                                   group_item.tool_type, 
            #                                   group_item.script_path, 
            #                                   group_item.custom_string_command)
            #         group_menu.add_menu_entry(SECTION_SCRIPTS, entry)
                    
        menus.refresh_menu_widget(python_menu_name)

        actor_context_menu = menus.find_menu(ACTOR_CONTEXT_MENU_NAME)
        
        if actor_context_menu is not None:
            # TODO: this will not clean up the existing entries, need further research
            menus.remove_section(ACTOR_CONTEXT_MENU_NAME, SECTION_ACTOR_CONTEXT)
            actor_context_menu.add_section(SECTION_ACTOR_CONTEXT, "Custom Actions")

            items = setting['actor_context_items']
            add_sub_menu(actor_context_menu, SECTION_ACTOR_CONTEXT, items)

            # script_items = []
            # for item in items:
            #     script_item = ScriptItem()
            #     script_item.init_from_json(item)
            #     script_items.append(script_item)
            # groups = group_scripts(script_items)
            # 
            # for group_key, group_items in groups.items():
            #     group_menu = actor_context_menu.add_sub_menu(ACTOR_CONTEXT_MENU_NAME, SECTION_ACTOR_CONTEXT, group_key, group_key)
            #     for group_item in group_items:
            #         # print(group_item)
            #         entry = create_menu_entry(group_item.id,
            #                                   group_item.name,
            #                                   group_item.tool_type,
            #                                   group_item.script_path,
            #                                   group_item.custom_string_command)
            #         group_menu.add_menu_entry(SECTION_ACTOR_CONTEXT, entry)

        menus.refresh_menu_widget(ACTOR_CONTEXT_MENU_NAME)

        content_browser_context_menu = menus.find_menu(CONTENT_BROWSER_CONTEXT_MENU_NAME)
        
        if content_browser_context_menu is not None:
            # TODO: this will not clean up the existing entries, need further research
            menus.remove_section(CONTENT_BROWSER_CONTEXT_MENU_NAME, SECTION_CONTENT_BROWSER_CONTEXT)
            content_browser_context_menu.add_section(SECTION_CONTENT_BROWSER_CONTEXT, "Custom Actions")

            items = setting['content_browser_context_items']
            add_sub_menu(content_browser_context_menu, SECTION_CONTENT_BROWSER_CONTEXT, items)

        menus.refresh_menu_widget(CONTENT_BROWSER_CONTEXT_MENU_NAME)

        #menus.refresh_all_widgets()



def init_tool_menus():
    """
    Create a new menu in the UE editor for python tools
    :return: 
    """
    menus = unreal.ToolMenus.get()
    
    # init custom main menu
    main_menu = menus.find_menu(MAIN_MENU_NAME)
    if not main_menu:
        unreal.log_error("Failed to find the 'Main' menu. Something is wrong in the force!")

    python_menu = main_menu.add_sub_menu(main_menu.get_name(), "CustomTool", PYTHON_TOOL_MENU_NAME, "+ Custom Tools")

    # utils
    python_menu.add_section(SECTION_UTILS, "Utils")
    refresh_entry = unreal.ToolMenuEntry(
        name="RefreshTools",
        type=unreal.MultiBlockType.MENU_ENTRY,
        insert_position=unreal.ToolMenuInsert("", unreal.ToolMenuInsertType.FIRST)
    )
    refresh_entry.set_label("Refresh Tools")
    # This is weird, but I didn't find a way to get a call back from menu
    refresh_entry.set_string_command(unreal.ToolMenuStringCommandType.PYTHON, custom_type="Python", string=(
        "import importlib;import tool_menu_setup;importlib.reload(tool_menu_setup);tool_menu_setup.refresh_tool_menus()"))
    python_menu.add_menu_entry(SECTION_UTILS, refresh_entry)

    doc_entry = unreal.ToolMenuEntry(
        name="OpenDocUrl",
        type=unreal.MultiBlockType.MENU_ENTRY,
        insert_position=unreal.ToolMenuInsert("", unreal.ToolMenuInsertType.FIRST)
    )
    doc_entry.set_label("Documents")
    doc_entry.set_string_command(unreal.ToolMenuStringCommandType.PYTHON, custom_type="Python", string=(
        "import webbrowser;webbrowser.open('https://weblink')"))
    python_menu.add_menu_entry(SECTION_UTILS, doc_entry)
    
    # init custom actor context menu
    actor_context_menu = menus.extend_menu(ACTOR_CONTEXT_MENU_NAME)
    actor_context_menu.add_section(SECTION_ACTOR_CONTEXT, "Custom Actions")

    refresh_tool_menus()
    menus.refresh_all_widgets()
