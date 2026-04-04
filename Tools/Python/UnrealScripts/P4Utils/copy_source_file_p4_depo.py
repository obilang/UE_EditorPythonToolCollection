import unreal
import path_util

editor_asset_sub = unreal.EditorAssetSubsystem()
editor_util_lib = unreal.EditorUtilityLibrary()

if __name__ == "__main__":
    selected_assets_data = editor_util_lib.get_selected_asset_data()
    asset_data = selected_assets_data[0]
    tag_value = asset_data.get_tag_value("sourcefile")
    print(tag_value)