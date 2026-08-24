"""
Simple launcher for USD Import Tool
Run this script in Unreal to open the USD Import Tool GUI
"""

import unreal
import sys
import os

# Ensure the USD directory is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import and show the tool
from usd_import_tool_UI import show_usd_import_tool

# Launch the tool
unreal.log("Launching USD Import Tool...")
window = show_usd_import_tool()
unreal.log("USD Import Tool opened successfully")
