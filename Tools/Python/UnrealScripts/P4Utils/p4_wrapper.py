import atexit
from P4 import P4, P4Exception
import stat
import os
import path_util
import datetime

_p4: P4 = None
_p4_server = ""
_p4_user = ""
_p4_workspace = ""


UE_SOURCE_CONTROL_CONFIG_PATH = "Saved/Config/WindowsEditor/SourceControlSettings.ini"
PERFORCE_CONFIG_SECTION = "[PerforceSourceControl.PerforceSourceControlSettings]"


def p4_init(server, user, workspace):
    """ Call this to init the p4 connect infos and do connect """
    global _p4_server
    global _p4_user
    global _p4_workspace
    _p4_server = server
    _p4_user = user
    _p4_workspace = workspace

    return _init_p4(False)


def ue_perforce_config():
    config_file_path = os.path.realpath(os.path.join(path_util.ue_project_root(), UE_SOURCE_CONTROL_CONFIG_PATH))
    if os.path.exists(config_file_path):
        with open(config_file_path, 'r') as file:
            lines = file.readlines()
            p4_config_start = False
            for line in lines:
                line = line.strip()
                if PERFORCE_CONFIG_SECTION in line:
                    p4_config_start = True
                if p4_config_start:
                    if line.startswith("Port"):
                        p4_server = line.split("=")[1]
                    elif line.startswith("UserName"):
                        p4_user = line.split("=")[1]
                    elif line.startswith("Workspace"):
                        p4_workspace = line.split("=")[1]
                        break
            return p4_server, p4_user, p4_workspace
    return None, None, None


def p4_init_ue_editor():
    p4_server, p4_user, p4_workspace = ue_perforce_config()
    if p4_server is not None:
        result = p4_init(p4_server, p4_user, p4_workspace)
        if result is None or not result.connected():
            return False
        else:
            return True
    else:
        return False


def _init_p4(force_reconnect=False):
    global _p4
    if not _p4:
        _p4 = P4()
        atexit.register(p4_exit)
    if force_reconnect and _p4.connected():
        # print("Force disconnect")
        _p4.disconnect()
    if not _p4.connected():
        # try:
        _p4.port = _p4_server
        _p4.user = _p4_user
        _p4.client = _p4_workspace
        _p4.exception_level = 1
        _p4.connect()
        info = _p4.run("info")
        # except P4Exception as err:
        # #     _log_error("Fail connect to P4: {}".format(err))
        #     return None
    return _p4


def p4_exit():
    if _p4 and _p4.connected:
        _p4.disconnect()


def _log(msg):
    print("p4 - {0}".format(msg))


def _log_warning(msg):
    print("p4 - Warning: {0}".format(msg))


def _log_error(msg, raise_exception=False):
    if raise_exception:
        raise Exception("p4 - Error: {0}".format(msg))
    else:
        print("p4 - Error: {0}".format(msg))


def get_pending_changelists(truncate_description=True):
    """ Get the pending p4 changelist of the current user. """
    if not _init_p4():
        return False
    return _p4.run(["changes", "-u", _p4.user, "-c", _p4.client, "-s", "pending", "-L" if truncate_description else "-l"])


def get_pending_changelist(description_head, description_detail=""):
    """
    Get the pending change list which descirption start with the given parameter.
    If not, create a new pending changelist
    """
    if not _init_p4():
        return False
    existing_changes = get_pending_changelists()
    found_existing_changelist = False
    for change in existing_changes:
        if change["desc"].startswith(description_head):
            found_existing_changelist = True
            return change["change"]
    if not found_existing_changelist:
        result = _p4.save_change({'Change': 'new', 'Description': description_head + description_detail})[0]
        return int(result.split()[1])


def is_file_exist(depo_path, include_delete=False):
    """ Check if file exist on P4. Path need to be the depo path"""
    if not _init_p4():
        return False

    try:
        fstat = _p4.run('fstat', depo_path)
    except P4Exception:
        return False

    if not len(fstat):
        return False
    else:
        if not include_delete:
            action = fstat[0].get('headAction')
            if action in ('delete', 'move/delete'):
                return False
        return True

    return False


def make_writable(filepath):
    """ Make file is writable on disk. """
    if os.path.isfile(filepath):
        os.chmod(str(filepath), stat.S_IWRITE)


def is_writable(filepath):
    """ Check if file is writable on disk. """
    return os.access(filepath, os.W_OK)


def sync_to_latest(file_folder):
    depo_path = get_depot_file(file_folder)
    _p4.run(["sync", "{}...#head".format(depo_path)])


def check_out_or_add_file(filepath, changelist):
    if not _init_p4():
        return False
    print("check out or edit")
    depo_file = get_depot_file(filepath)
    if is_file_exist(depo_file):
        _p4.run(["edit", ["-c", changelist], depo_file])
        # force move the file to the changelist if it's already checked out
        _p4.run(["reopen", ["-c", changelist], depo_file])
    else:
        _p4.run(["add", "-d", ["-c", changelist], depo_file])


def save_file_util(file_path, ignore_p4=False, change_list_desc=""):
    """
    If ignore p4, make file writable on disk
    Else check out or mark for add file on P4
    :param ignore_p4:
    :param change_list_desc:
    :return:
    """
    if ignore_p4:
        if not is_writable(file_path):
            make_writable(file_path)
    else:
        if os.path.isfile(file_path):
            changelist = get_pending_changelist(change_list_desc)
            check_out_or_add_file(file_path, changelist)


def get_depot_file(filepath):
    """ Get the depot file path of a local file path"""
    if not _init_p4():
        return None

    results = _p4.run(['where', [filepath]])
    # if not include_unmapped:
    #     results = [x for x in results if 'unmap' not in x]

    if results:
        return results[-1].get('depotFile')
    return None


def get_file_history(filepath):
    """
[
{
'change': '48657', 
'time': '1658750224', 
'user': 'xxx', 
'client': 'workspace name', 
'status': 'submitted', 
'changeType': 'public', 
'path': '//depopath/..', 
'desc': ''
}, 
{...}
]
    :param filepath: 
    :return: 
    """
    if not _init_p4():
        return False
    depo_file = get_depot_file(filepath)
    if is_file_exist(depo_file):
        result = _p4.run(["changes", depo_file])
        return result


def get_file_history_user_details(filepath):
    last_changed_by = ""
    created_by = ""
    modified_most_by = ""
    last_change_date = ""
    if os.path.exists(filepath):
        asset_history = get_file_history(filepath)

        users = {}
        revision_counts = len(asset_history)

        max_changes = 0
        for index in range(revision_counts):
            user = asset_history[index]["user"]
            if index == 0:
                last_changed_by = user
                last_change_date = asset_history[index]["time"]
                last_change_date = datetime.datetime.fromtimestamp(int(last_change_date))

            if index == revision_counts - 1:
                created_by = user

            if user not in users:
                users[user] = 0
            change_count = users[user] + 1
            users[user] = change_count
            if change_count >= max_changes:
                modified_most_by = "{}({})".format(user, change_count)
                max_changes = change_count

    return last_changed_by, created_by, modified_most_by, last_change_date
