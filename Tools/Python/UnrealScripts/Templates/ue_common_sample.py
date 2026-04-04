"""
This file is for store some common unreal python lib samples for someone who
too lazy to remember!!!
"""
raise Exception("You can not execute this file directly")

import unreal

""" --------------------------- Asset Operations (Content Browser) ---------------------------- """
"""
Get tag values of the assets in content browser
Which is all the tags show in tooltip if you hover the mouse on an asset in content browser
This method won't need to load the asset object so it's fast when doing huge amount of assets checking
"""
selected_asset_data = unreal.EditorUtilityLibrary.get_selected_asset_data()[0]
tag_values = unreal.EditorAssetLibrary.get_tag_values(selected_asset_data.package_name)
print(tag_values)


"""
Find if asset exist
"""
shadow_mesh_path = "/Game/Art/Environment/Prop/Door/Mesh/SM_A.SM_A"
editor_asset_lib = unreal.EditorAssetLibrary()
editor_asset_lib.does_asset_exist(shadow_mesh_path)


""" --------------------------- Actor Operations (Level) ---------------------------- """
"""
Get Selected Actor in Level
"""
editor_actor_subsystem = unreal.EditorActorSubsystem()
editor_actor_subsystem.get_selected_level_actors()


