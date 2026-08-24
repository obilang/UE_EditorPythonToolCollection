# USD Import Tool UI Updates - Summary

## Changes Made

### 1. Fixed Input Path Display Issue
**Problem**: After loading SpeedTree USD, the input field changed to show the converted file path instead of the original user-selected file.

**Solution**: 
- Added two separate variables:
  - `self.current_usd_path` - Stores the original user-selected file (displayed in UI)
  - `self.loaded_usd_path` - Stores the actual file to use for import (may be converted)
- The UI path field always shows the original file, while conversions happen internally

### 2. Merged Combo Box and Load Button
**Problem**: The source type combo box and separate "Load SpeedTree USD" / "Load Generic USD" buttons were confusing.

**Solution**:
- Removed separate load buttons
- Combined functionality into a single "Load USD" button
- Workflow now: Select source type from combo box → Click "Load USD"
- The button intelligently applies the correct converter based on selection

### 3. Improved UI Layout
**Changes**:
- Removed separate "USD Source/Converter" group box
- Integrated source type selector into the main file selection area
- Added styled "Load USD" button with blue color scheme
- More compact and intuitive layout

### 4. Fixed Material Detection
**Problem**: Materials were showing as "No material" even though materials existed in the USD file.

**Solution**:
- Changed from `GetDirectBinding().GetMaterialPath()` to `ComputeBoundMaterial()[0]`
- `ComputeBoundMaterial()` is more reliable and handles inherited bindings
- Added proper handling of GeomSubsets (per-face material assignments)
- Now properly detects materials bound to both meshes and geom subsets

### 5. Fixed Import Path Usage
**Problem**: Import was using the wrong path after conversion.

**Solution**:
- Import now uses `self.loaded_usd_path` (converted file) if available
- Falls back to `self.current_usd_path` if no conversion was applied
- Ensures the correct file is sent to Unreal's import system

## New Workflow

1. **Select USD File**: Click "Browse..." to select a USD file
2. **Choose Source**: Select the source type from the dropdown:
   - Generic USD
   - SpeedTree
   - Maya
   - Blender
   - Houdini
3. **Load**: Click "Load USD" button
   - For SpeedTree: Converts the file automatically and loads the converted version
   - For others: Loads the original file directly
4. **Preview**: View all meshes and their materials in the tree
5. **Select**: Check/uncheck meshes you want to import
6. **Configure**: Set destination path and import options
7. **Import**: Click "Import Selected Meshes"

## Code Changes

### Key Method: `on_load_usd()`
```python
def on_load_usd(self):
    """Load USD file with selected converter."""
    source_type = self.converter_combo.currentText()
    
    if source_type == "SpeedTree":
        # Convert SpeedTree USD
        converter = SpeedTreeToUnrealConverter(self.current_usd_path)
        converted_path = converter.convert()
        self.loaded_usd_path = converted_path  # Store internally
        # self.current_usd_path remains unchanged (shown in UI)
    else:
        self.loaded_usd_path = self.current_usd_path
    
    self.load_usd_preview(self.loaded_usd_path)
```

### Key Method: `get_bound_materials()`
```python
def get_bound_materials(self, prim):
    """Get materials bound to a USD prim."""
    binding_api = UsdShade.MaterialBindingAPI(prim)
    
    # Use ComputeBoundMaterial instead of GetDirectBinding
    bound_material = binding_api.ComputeBoundMaterial()[0]
    if bound_material:
        mat_prim = bound_material.GetPrim()
        materials.append(str(mat_prim.GetPath()))
    
    # Also check GeomSubsets for per-face materials
    geom_subsets = UsdGeom.Subset.GetGeomSubsets(mesh)
    for subset in geom_subsets:
        # Get material for each subset
```

## Testing with Provided USD File

The tool was tested with the SpeedTree USD file that contains:
- **Trunk mesh**: `/TestAssembly/Trunk` with material `/TestAssembly/Materials/Default_Mat`
- **Leaf mesh**: `/TestAssembly/LeafReferences/.../SM_Sample_Leaf_Mat_Sample_Leaf_Cutout_lod1` with material `/TestAssembly/Materials/Sample_Leaf_Mat`

Both materials are now correctly detected and displayed in the preview tree.

## Files Modified

- `usd_import_tool_UI.py` - Main UI implementation with all fixes applied

## Backward Compatibility

The tool maintains compatibility with:
- Systems without USD Python library (pxr) - preview will be limited but import still works
- Generic USD files from any source
- Future converter additions through the combo box
