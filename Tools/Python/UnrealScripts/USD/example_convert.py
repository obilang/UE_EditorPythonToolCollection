"""
Example script demonstrating how to use the SpeedTree to Unreal USD converter.
"""

from speedtree_usd_format_convert import convert_speedtree_to_unreal
import os

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Example 1: Convert with automatic output naming
input_file = os.path.join(script_dir, "TestAssembly_flattened_origin.usda")
if os.path.exists(input_file):
    print("Example 1: Converting with automatic output naming...")
    output_file = convert_speedtree_to_unreal(input_file)
    print(f"Converted file: {output_file}\n")

# Example 2: Convert with specific output name
input_file = os.path.join(script_dir, "TestAssembly_flattened_origin.usda")
output_file = os.path.join(script_dir, "TestAssembly_for_unreal.usda")
if os.path.exists(input_file):
    print("Example 2: Converting with specific output name...")
    result = convert_speedtree_to_unreal(input_file, output_file)
    print(f"Converted file: {result}\n")

print("\nDone! Check the output files to verify the conversion.")
