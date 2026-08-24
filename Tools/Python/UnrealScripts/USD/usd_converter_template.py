"""
Generic USD Converter Template

This is a template for creating custom USD converters for different DCC sources.
Copy this file and modify it to support your specific DCC application.

Usage:
1. Copy this file to a new file (e.g., maya_usd_converter.py)
2. Implement the conversion logic in the convert() method
3. Import and use in usd_import_tool_UI.py
"""

from pxr import Usd, UsdGeom, Sdf, UsdShade
import os
import sys


class GenericUSDConverter:
    """
    Template converter for DCC-specific USD format conversions.
    
    Modify this class to handle specific requirements from different DCC tools
    like Maya, Blender, Houdini, etc.
    """
    
    def __init__(self, input_path, output_path=None):
        """
        Initialize converter.
        
        Args:
            input_path: Path to input USD file from your DCC
            output_path: Path to output USD file (optional, defaults to input_converted.usda)
        """
        self.input_path = input_path
        if output_path is None:
            base, ext = os.path.splitext(input_path)
            self.output_path = f"{base}_converted.usda"
        else:
            self.output_path = output_path
        
        self.stage = None
    
    def convert(self):
        """
        Perform the conversion process.
        
        Override this method with your specific conversion logic.
        
        Returns:
            str: Path to the converted USD file
        """
        print(f"Converting {self.input_path} for Unreal Engine...")
        
        # Open the input stage
        self.stage = Usd.Stage.Open(self.input_path)
        if not self.stage:
            raise RuntimeError(f"Failed to open USD file: {self.input_path}")
        
        # Get root prim
        root_prim = self.stage.GetDefaultPrim()
        if not root_prim:
            # Try to get the first prim
            for prim in self.stage.Traverse():
                if prim.GetParent() == self.stage.GetPseudoRoot():
                    root_prim = prim
                    break
        
        if not root_prim:
            raise RuntimeError("Could not find root prim")
        
        print(f"  Root prim: {root_prim.GetPath()}")
        
        # ===== ADD YOUR CONVERSION LOGIC HERE =====
        
        # Example conversions you might need:
        
        # 1. Convert coordinate system (Y-up to Z-up or vice versa)
        # self._convert_coordinate_system(root_prim)
        
        # 2. Fix material bindings
        # self._fix_material_bindings(root_prim)
        
        # 3. Adjust mesh hierarchy
        # self._restructure_hierarchy(root_prim)
        
        # 4. Convert specific geometry types
        # self._convert_geometry(root_prim)
        
        # 5. Add Unreal-specific metadata
        # self._add_unreal_metadata(root_prim)
        
        # ============================================
        
        # Save the converted stage
        print(f"  Saving to {self.output_path}")
        self.stage.GetRootLayer().Export(self.output_path)
        print("Conversion complete!")
        
        return self.output_path
    
    def _convert_coordinate_system(self, root_prim):
        """
        Example: Convert coordinate system.
        
        Many DCC tools use Y-up while Unreal uses Z-up.
        """
        print("  Converting coordinate system...")
        
        # Example: Set up axis to Z
        UsdGeom.SetStageUpAxis(self.stage, UsdGeom.Tokens.z)
        
        # You might also need to transform geometry
        # xform = UsdGeom.Xformable(root_prim)
        # xform.AddRotateXOp().Set(90)  # Rotate 90 degrees around X
    
    def _fix_material_bindings(self, root_prim):
        """
        Example: Fix material bindings for Unreal.
        
        Unreal requires MaterialBindingAPI on certain prims.
        """
        print("  Fixing material bindings...")
        
        for prim in self.stage.Traverse():
            # Add MaterialBindingAPI to all mesh prims
            if prim.IsA(UsdGeom.Mesh):
                if not prim.HasAPI(UsdShade.MaterialBindingAPI):
                    UsdShade.MaterialBindingAPI.Apply(prim)
            
            # Check GeomSubsets (per-face material assignments)
            if prim.IsA(UsdGeom.Subset):
                if not prim.HasAPI(UsdShade.MaterialBindingAPI):
                    UsdShade.MaterialBindingAPI.Apply(prim)
    
    def _restructure_hierarchy(self, root_prim):
        """
        Example: Restructure scene hierarchy.
        
        Some DCCs export flat hierarchies that need reorganization.
        """
        print("  Restructuring hierarchy...")
        
        # Example: Group all meshes under a common parent
        # This is just an example - modify based on your needs
        
        meshes_to_group = []
        for prim in self.stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                meshes_to_group.append(prim)
        
        # Create a group if needed
        if meshes_to_group:
            group_path = root_prim.GetPath().AppendChild("Meshes")
            UsdGeom.Xform.Define(self.stage, group_path)
            
            # Reparent meshes (this is complex - just an example)
            # In practice, you'd need to handle transforms, etc.
    
    def _convert_geometry(self, root_prim):
        """
        Example: Convert specific geometry types.
        
        Convert NURBS, subdivision surfaces, etc. to polygon meshes.
        """
        print("  Converting geometry...")
        
        for prim in self.stage.Traverse():
            # Example: Convert all NurbsCurves to meshes
            # if prim.IsA(UsdGeom.NurbsCurves):
            #     # Conversion logic here
            #     pass
            
            # Example: Triangulate all meshes
            if prim.IsA(UsdGeom.Mesh):
                mesh = UsdGeom.Mesh(prim)
                # Check subdivision scheme
                scheme = mesh.GetSubdivisionSchemeAttr().Get()
                if scheme and scheme != "none":
                    # Set to none (no subdivision)
                    mesh.GetSubdivisionSchemeAttr().Set("none")
    
    def _add_unreal_metadata(self, root_prim):
        """
        Example: Add Unreal Engine specific metadata.
        
        Add metadata that helps Unreal import the USD correctly.
        """
        print("  Adding Unreal metadata...")
        
        # Example: Add Nanite support (for Unreal 5+)
        # This is just an example - actual implementation may vary
        
        # Check if root should be a Nanite assembly
        root_spec = self.stage.GetRootLayer().GetPrimAtPath(root_prim.GetPath())
        if root_spec:
            # Add API schema for Nanite
            api_schemas = root_spec.GetInfo('apiSchemas')
            if api_schemas:
                if 'NaniteAssemblyRootAPI' not in str(api_schemas):
                    # Note: This is simplified - actual implementation varies
                    pass
    
    def _process_materials(self, root_prim):
        """
        Example: Process material definitions.
        
        Convert DCC-specific materials to UsdPreviewSurface or other
        Unreal-compatible material representations.
        """
        print("  Processing materials...")
        
        for prim in self.stage.Traverse():
            if prim.IsA(UsdShade.Material):
                material = UsdShade.Material(prim)
                
                # Example: Ensure material has a surface output
                surface_output = material.GetSurfaceOutput()
                if not surface_output:
                    print(f"    Warning: Material {prim.GetPath()} has no surface output")
                
                # You might want to convert to UsdPreviewSurface
                # or add additional outputs for Unreal


# ===== SPECIFIC DCC CONVERTER EXAMPLES =====

class MayaUSDConverter(GenericUSDConverter):
    """Converter for Maya USD exports."""
    
    def convert(self):
        print("Converting Maya USD for Unreal Engine...")
        self.stage = Usd.Stage.Open(self.input_path)
        root_prim = self.stage.GetDefaultPrim()
        
        # Maya-specific conversions
        self._convert_coordinate_system(root_prim)  # Maya is Y-up
        self._fix_material_bindings(root_prim)
        
        self.stage.GetRootLayer().Export(self.output_path)
        print("Maya USD conversion complete!")
        return self.output_path


class BlenderUSDConverter(GenericUSDConverter):
    """Converter for Blender USD exports."""
    
    def convert(self):
        print("Converting Blender USD for Unreal Engine...")
        self.stage = Usd.Stage.Open(self.input_path)
        root_prim = self.stage.GetDefaultPrim()
        
        # Blender-specific conversions
        self._convert_coordinate_system(root_prim)  # Blender is Z-up
        self._fix_material_bindings(root_prim)
        
        self.stage.GetRootLayer().Export(self.output_path)
        print("Blender USD conversion complete!")
        return self.output_path


class HoudiniUSDConverter(GenericUSDConverter):
    """Converter for Houdini USD exports."""
    
    def convert(self):
        print("Converting Houdini USD for Unreal Engine...")
        self.stage = Usd.Stage.Open(self.input_path)
        root_prim = self.stage.GetDefaultPrim()
        
        # Houdini-specific conversions
        self._fix_material_bindings(root_prim)
        # Houdini typically uses Y-up, but verify based on export settings
        
        self.stage.GetRootLayer().Export(self.output_path)
        print("Houdini USD conversion complete!")
        return self.output_path


# ===== USAGE EXAMPLE =====
if __name__ == "__main__":
    # Example: Convert a Maya USD file
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        converter = MayaUSDConverter(input_file)
        output_file = converter.convert()
        print(f"\nConverted file saved to: {output_file}")
    else:
        print("Usage: python usd_converter_template.py <input_usd_file>")
        print("\nOr import and use in your code:")
        print("  from usd_converter_template import MayaUSDConverter")
        print("  converter = MayaUSDConverter('path/to/file.usd')")
        print("  output = converter.convert()")
