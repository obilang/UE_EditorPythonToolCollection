# USD Import Tool for Unreal Engine

A comprehensive GUI tool for importing USD files into Unreal Engine with preview capabilities and support for multiple DCC sources.

## Features

- **Browse and Select USD Files**: Easy file selection dialog for `.usd`, `.usda`, and `.usdc` files
- **USD Content Preview**: View all meshes and their material bindings before import
- **Multiple Source Support**: Generic USD import with specialized converters for:
  - SpeedTree
  - Maya
  - Blender
  - Houdini
  - Custom formats
- **Selective Import**: Choose which meshes to import using checkboxes
- **Material Preview**: See which materials are bound to each mesh
- **Configurable Import Settings**:
  - Import geometry
  - Import materials
  - Import as actors (level placement)
  - Merge identical material slots
- **SpeedTree Auto-Conversion**: One-click conversion and import for SpeedTree USD files

## Installation

The tool is already integrated into the Unreal Editor menu system. After running the `tool_menu_setup.py` script, you can access it from:

**Main Menu → PythonTools → USD → USD Import Tool**

## Usage

### Method 1: From Unreal Menu

1. Open Unreal Editor
2. Navigate to: **Main Menu → PythonTools → USD → USD Import Tool**
3. The tool window will appear

### Method 2: Run Directly via Python

In Unreal's Python console or output log, run:

```python
import sys
sys.path.append('f:/UE57/UnrealEngine-release/Test/Tools/Python/UnrealScripts/USD')
from launch_usd_import_tool import *
```

### Importing USD Files

#### Basic Workflow:

1. **Select USD File**:

   - Click "Browse..." to select a USD file
   - Or use quick load buttons:
     - "Load SpeedTree USD" - Automatically converts SpeedTree USD format
     - "Load Generic USD" - Loads standard USD without conversion
2. **Choose Source Type** (Optional):

   - Select the source application from the dropdown
   - This helps apply any required format conversions
3. **Preview Contents**:

   - The tree view shows all meshes found in the USD file
   - Materials bound to each mesh are displayed as child items
   - Use checkboxes to select which meshes to import
4. **Configure Import Settings**:

   - **Destination Path**: Unreal content browser path (e.g., `/Game/ImportedUSD`)
   - **Import Geometry**: Include mesh geometry
   - **Import Materials**: Include material definitions
   - **Import as Actors**: Create level actors (unchecked = assets only)
   - **Merge Identical Materials**: Combine duplicate material slots
5. **Import**:

   - Click "Import Selected Meshes"
   - Confirm the destination and mesh count
   - Wait for import to complete

#### SpeedTree Workflow:

1. Click "Browse..." and select your SpeedTree `.usd` file
2. Click "Load SpeedTree USD"
3. The tool will automatically:
   - Convert the USD to Unreal-compatible format
   - Show the converted mesh hierarchy
   - Prepare materials for import
4. Configure destination path
5. Click "Import Selected Meshes"

## File Structure

```
USD/
├── usd_import_tool_UI.py          # Main GUI tool
├── launch_usd_import_tool.py      # Quick launcher script
├── speedtree_usd_format_convert.py # SpeedTree converter
├── usd_import_utils.py            # Batch import utilities
└── USD_IMPORT_TOOL_README.md      # This file
```

## Requirements

- **Unreal Engine 5.7+**: With USD plugin enabled
- **PySide6**: Qt library (included in Unreal)
- **USD Python Library**: For preview features (optional but recommended)
  - If not installed, the tool will still work but with limited preview

## Extending the Tool

### Adding Custom Converters

To add support for a new DCC source:

1. Create a converter class in a new file:

```python
class MyDCCConverter:
    def __init__(self, input_path, output_path=None):
        self.input_path = input_path
        self.output_path = output_path or input_path.replace('.usd', '_converted.usd')
  
    def convert(self):
        # Your conversion logic here
        return self.output_path
```

2. Import and use in `usd_import_tool_UI.py`:

```python
from my_dcc_converter import MyDCCConverter

# In the main window class, add a new method:
def on_load_mydcc(self):
    converter = MyDCCConverter(self.current_usd_path)
    converted_path = converter.convert()
    self.load_usd_preview(converted_path)
```

3. Add a button in `build_ui()` method for your converter

### Modifying Import Options

Edit the `import_usd_to_unreal()` method to add custom import options:

```python
import_options = unreal.UsdStageImportOptions()
import_options.your_custom_option = True
```

## Troubleshooting

### USD Preview Not Working

- Ensure USD Python library is installed: `pip install usd-core`
- The tool will still import USD files even without preview capabilities

### SpeedTree Conversion Failed

- Verify `speedtree_usd_format_convert.py` is in the same directory
- Check that the USD file is from SpeedTree (correct format)
- Review Unreal output log for detailed error messages

### Import Shows No Objects

- Check that the USD file contains valid geometry
- Verify the destination path is valid (must start with `/Game/`)
- Ensure USD plugin is enabled in Unreal project settings

### Materials Not Importing

- Enable "Import Materials" checkbox
- Check that materials are properly bound in the USD file
- Some material features may require manual adjustment in Unreal

## Tips

- **Large USD Files**: Deselect unnecessary meshes before import to save time
- **Destination Organization**: Use descriptive destination paths like `/Game/Environment/Trees/`
- **Material Workflow**: Import materials first, then customize in Unreal's material editor
- **Batch Processing**: You can load multiple USD files sequentially using the GUI

## Support

For issues or questions:

1. Check the Unreal output log for detailed error messages
2. Verify USD plugin is enabled in Project Settings
3. Ensure all required Python dependencies are installed
4. Review the conversion scripts for format-specific requirements

## Version History

- **v1.0** - Initial release
  - USD file browsing and preview
  - SpeedTree conversion support
  - Selective mesh import
  - Material binding preview
  - Configurable import settings
