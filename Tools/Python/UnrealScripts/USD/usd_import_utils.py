import unreal
import os

def batch_import_usd(source_path, destination_path):
    import_options = unreal.UsdStageImportOptions()
    import_options.import_actors = False   # Assets only, no level actors
    import_options.import_geometry = True
    import_options.import_materials = True
    import_options.merge_identical_material_slots = True

    if os.path.isfile(source_path):
        files = [source_path]
    else:
        files = [
            os.path.join(source_path, f)
            for f in os.listdir(source_path)
            if f.endswith((".usd", ".usda", ".usdc"))
        ]

    tasks = []
    for file_path in files:
        task = unreal.AssetImportTask()
        task.filename = file_path
        task.destination_path = destination_path
        task.replace_existing = True
        task.automated = True
        task.save = False
        task.factory = unreal.UsdStageImportFactory()
        task.options = import_options
        tasks.append(task)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)

    for task in tasks:
        print(f"Imported: {os.path.basename(task.filename)}")

batch_import_usd(r"F:\UE57\UnrealEngine-release\Test\Raw\TestAssembly_TreeB_converted.usda", "/Game/TestNaniteFoliage/new")