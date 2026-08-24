# SpeedTree to Unreal USD Format Converter

This tool converts USD files exported from SpeedTree to a format compatible with Unreal Engine's Nanite assembly system.

## Key Conversions

The converter performs the following transformations:

1. **Root Transformation**: Converts the root primitive from `Scope` to `Xform` and adds:
   - `apiSchemas = ["NaniteAssemblyRootAPI"]`
   - `kind = "group"`
   - `uniform token unreal:naniteAssembly:meshType = "staticMesh"`

2. **Material Binding API**: Adds `apiSchemas = ["MaterialBindingAPI"]` to all `GeomSubset` primitives

3. **PointInstancer Relocation**: Moves `PointInstancer` primitives from nested locations to the root level

4. **Leaf Mesh Restructuring**: Reorganizes leaf meshes into the proper hierarchy:
   ```
   PointInstancer (kind="group")
   └── Scope:Prototypes (kind="group")
       └── Xform:meshname (kind="component")
           └── Mesh:SM_meshname
               └── GeomSubset (with MaterialBindingAPI)
   ```

## Requirements

- Python 3.x
- USD Python bindings (pxr)

## Usage

### Command Line

```bash
# Basic usage - output file will be automatically named
python speedtree_usd_format_convert.py input_file.usda

# Specify output file name
python speedtree_usd_format_convert.py input_file.usda output_file.usda
```

### Python API

```python
from speedtree_usd_format_convert import convert_speedtree_to_unreal

# Convert with automatic output naming (adds _converted suffix)
output_path = convert_speedtree_to_unreal("input_file.usda")

# Convert with specific output name
output_path = convert_speedtree_to_unreal("input_file.usda", "output_file.usda")
```

### Example Script

See `example_convert.py` for usage examples:

```bash
python example_convert.py
```

## File Structure

- `speedtree_usd_format_convert.py` - Main converter script
- `example_convert.py` - Example usage demonstrations
- `README_USD_Converter.md` - This file

## Conversion Process

The converter follows these steps:

1. Opens the input USD file
2. Identifies the root primitive
3. Converts root from Scope to Xform with Nanite API schemas
4. Scans for all PointInstancer primitives and their prototype meshes
5. Adds MaterialBindingAPI to all GeomSubset primitives
6. Restructures the hierarchy:
   - Moves PointInstancers to root level
   - Creates Prototypes scope under each PointInstancer
   - Creates Xform wrappers for each mesh
   - Copies mesh data with SM_ prefix
   - Updates prototype references
   - Removes old mesh containers

## Example

**Input Structure (from SpeedTree):**
```
Scope:TestAssembly
├── Scope:Materials
│   └── Material:SomeMaterial
├── LeafMeshes
│   └── Mesh:LeafMesh (hidden, instanceable)
│       └── GeomSubset (no MaterialBindingAPI)
└── Mesh:Trunk
    └── Scope:Leaf
        └── PointInstancer:LeafReferences
            └── prototypes -> /TestAssembly/LeafMeshes/LeafMesh
```

**Output Structure (for Unreal):**
```
Xform:TestAssembly (apiSchemas=["NaniteAssemblyRootAPI"], kind="group")
├── Scope:Materials
│   └── Material:SomeMaterial
├── Mesh:Trunk
│   └── GeomSubset (apiSchemas=["MaterialBindingAPI"])
└── PointInstancer:LeafReferences (kind="group")
    └── Scope:Prototypes (kind="group")
        └── Xform:LeafMesh (kind="component")
            └── Mesh:SM_LeafMesh
                └── GeomSubset (apiSchemas=["MaterialBindingAPI"])
```

## Notes

- The converter preserves all mesh data, materials, and instancing information
- Material bindings use absolute paths and remain intact during restructuring
- The original file is never modified; a new file is always created
- Any existing GeomSubset primitives are updated with MaterialBindingAPI

## Troubleshooting

**USD library not found:**
Ensure the USD Python bindings are installed and accessible in your Python environment.

**Conversion fails:**
Check that the input file is a valid USD file from SpeedTree with the expected structure.

**Material bindings lost:**
Verify that material paths in the original file use absolute references (starting with `/`).
