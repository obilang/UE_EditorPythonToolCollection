# External Mesh Reference Support

The USD Import Tool now supports the `NaniteAssemblyExternalRefAPI` schema, which allows replacing USD mesh data with references to existing static meshes in the Unreal Engine content browser.

## What is an External Reference?

An external reference allows you to:
- Replace USD mesh geometry with an existing Unreal Engine static mesh
- Avoid importing duplicate meshes when you already have the asset in your project
- Reference high-quality meshes that were imported through other pipelines
- Maintain USD scene hierarchy while using optimized engine assets

## USD Schema Format

```usda
def Xform "Box" (
    apiSchemas = ["NaniteAssemblyExternalRefAPI"]
    kind = "component"
)
{
    uniform token unreal:naniteAssembly:meshAssetPath = "/Game/MyFolder/MyMesh"
}
```

## UI Display

External references are shown in the tree view with:
- **[External Ref]** prefix in purple/magenta color
- **→ Mesh Asset:** showing the referenced asset path
- Materials bound to the reference (if any)

Example:
```
[External Ref] /TestAssembly/Box
  → Mesh Asset: /Game/TestNaniteFoliage/Concrete_Brick_udemai1iw_box
  Material: /TestAssembly/Materials/ConcreteMat
```

## Using External References

### Method 1: Right-Click on Existing External Reference

1. Load your USD file
2. Find the **[External Ref]** item in the tree
3. Right-click on it
4. Choose:
   - **Set External Mesh Reference...** - Change the referenced mesh path
   - **Clear External Reference** - Remove the reference

### Method 2: Convert Any Prim to External Reference

1. Load your USD file
2. Right-click on any prim (Mesh, Xform, etc.)
3. Select **Convert to External Reference...**
4. Enter the Unreal Engine asset path
5. The tool will:
   - Add `NaniteAssemblyExternalRefAPI` to the prim
   - Set the `unreal:naniteAssembly:meshAssetPath` attribute
   - Mark the USD as modified

### Setting the Asset Path

When prompted for the asset path, enter a valid Unreal Engine content browser path:

**Format**: `/Game/FolderPath/AssetName`

**Examples**:
- `/Game/Environment/Props/SM_Rock01`
- `/Game/TestNaniteFoliage/Concrete_Brick_udemai1iw_box`
- `/Game/Meshes/Trees/SM_Oak_Trunk`

**Note**: Do NOT include the asset extension (.uasset)

## Auto-Save Feature

When you modify external references through the UI:
- Changes are applied to the USD stage in memory
- The `stage_modified` flag is set to `true`
- **Before import**, the tool automatically saves the USD file
- You'll see "Saving USD modifications..." in the status bar

This ensures your external reference changes are preserved in the USD file.

## Workflow Example

### Scenario: Replace SpeedTree Mesh with Existing Asset

You have a SpeedTree USD but want to use a pre-existing optimized trunk mesh:

1. **Load** the SpeedTree USD
   - Select "SpeedTree" source type
   - Click "Load USD"

2. **Find the Trunk Mesh**
   - Locate `/TestAssembly/Trunk` in the tree

3. **Convert to External Reference**
   - Right-click on the trunk mesh
   - Select "Convert to External Reference..."
   - Enter: `/Game/Environment/Trees/SM_OptimizedTrunk`

4. **Verify**
   - Tree updates to show: `[External Ref] /TestAssembly/Trunk`
   - Shows: `→ Mesh Asset: /Game/Environment/Trees/SM_OptimizedTrunk`

5. **Import**
   - Tool saves the modification
   - Imports the assembly using your external trunk mesh

## Benefits

### Performance
- Reuse existing LODs and Nanite settings
- No redundant mesh imports
- Smaller USD files (geometry not embedded)

### Asset Management
- Single source of truth for meshes
- Update the referenced asset, all USDs update automatically
- Better version control (smaller USD files)

### Flexibility
- Mix USD meshes with engine assets
- Use specialized import pipelines for different asset types
- Maintain art director-approved assets

## Technical Details

### Schema Check
- External references are detected before other prim types
- The tool checks for `NaniteAssemblyExternalRefAPI` in applied schemas
- Reads the `unreal:naniteAssembly:meshAssetPath` attribute

### Import Behavior
When importing a USD with external references:
- Unreal Engine loads the referenced static mesh from the content browser
- The mesh is placed according to the USD prim's transform
- Materials from the USD are applied (if specified)
- The referenced mesh's LODs and Nanite settings are preserved

### Limitations
- The referenced asset must exist in the project before import
- Invalid paths will cause import warnings
- External references only work for mesh-type prims

## Context Menu Reference

### For External Reference Prims
- **Set External Mesh Reference...** - Update the asset path
- **Clear External Reference** - Remove the reference (converts back to regular prim)

### For Other Prims
- **Convert to External Reference...** - Add the external ref API and set asset path

## Status Indicators

The info bar shows external reference count:
```
✓ MyFile.usda | Assemblies: 1 | External Refs: 2 | Meshes: 5
```

This helps you quickly see how many external references your USD contains.

## Troubleshooting

### "Referenced asset not found" on import
- Verify the asset path is correct
- Ensure the asset exists in your project
- Check for typos in the path

### Changes not saved
- Check the status bar for "Saving USD modifications..."
- Verify you have write permissions to the USD file
- Look for error messages in the Unreal output log

### External reference not detected
- Ensure the prim has `apiSchemas = ["NaniteAssemblyExternalRefAPI"]`
- Verify the attribute name is exactly `unreal:naniteAssembly:meshAssetPath`
- Check the attribute is of type `token`

## Example USD File

Complete example with external reference:

```usda
#usda 1.0
(
    defaultPrim = "Assembly"
    upAxis = "Z"
)

def Xform "Assembly" (
    prepend apiSchemas = ["NaniteAssemblyRootAPI"]
    kind = "group"
)
{
    def Xform "TreeTrunk" (
        apiSchemas = ["NaniteAssemblyExternalRefAPI"]
        kind = "component"
    )
    {
        uniform token unreal:naniteAssembly:meshAssetPath = "/Game/Trees/SM_OakTrunk"
        
        def Material "TrunkMat"
        {
            # Material definition
        }
    }
    
    def Mesh "TreeBranches"
    {
        # Regular mesh data from USD
    }
}
```

This assembly will:
- Use the external `/Game/Trees/SM_OakTrunk` mesh for the trunk
- Import the branches mesh from USD data
- Apply the TrunkMat material to the external ref
