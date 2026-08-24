import unreal

registry = unreal.AssetRegistryHelpers.get_asset_registry()

# Correct: use TopLevelAssetPath with package_name and asset_name
class_path = unreal.TopLevelAssetPath("/Game/TestNaniteFoliage/TestA/TestAssembly_flattened/StaticMeshes", "UsdAssetCache2")
caches = registry.get_assets_by_class(class_path)

for c in caches:
    print(c.object_path)