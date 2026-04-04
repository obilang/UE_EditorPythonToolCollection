import unreal
import sys

asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
editor_asset_subsystem = unreal.EditorAssetSubsystem()

BASE_FOLDER = "/Game/"

if __name__ == '__main__':
    search_folder = sys.argv[1]
    
    filtered_assets_data = asset_registry.get_assets_by_path(search_folder, True)
    filter = unreal.ARFilter()
    filter.class_paths.append(unreal.BlueprintLibrary.get_class_path_name(unreal.StaticMesh.static_class()))
    filtered_assets_data = asset_registry.run_assets_through_filter(filtered_assets_data, filter)

    with unreal.ScopedSlowTask(len(filtered_assets_data), "Deleting Complex Collision Mesh") as slow_task:
        # display the dialog
        slow_task.make_dialog(True)
        for asset_data in filtered_assets_data:
            if slow_task.should_cancel():
                break
            slow_task.enter_progress_frame(1, "Deleting Complex Collision Mesh For {}".format(asset_data.asset_name))
            
            if asset_data.get_tag_value("NaniteEnabled") != "True":
                continue
            
            static_mesh = editor_asset_subsystem.load_asset(asset_data.package_name)
            complex_collision_mesh = static_mesh.get_editor_property("complex_collision_mesh")
            
            if complex_collision_mesh is not None:
                static_mesh.set_editor_property("complex_collision_mesh", None)
                referencers = editor_asset_subsystem.find_package_referencers_for_asset(complex_collision_mesh.get_package().get_path_name())
                if len(referencers) <= 1:
                    editor_asset_subsystem.delete_asset(complex_collision_mesh.get_package().get_path_name())
                editor_asset_subsystem.save_asset(asset_data.package_name)
                
    