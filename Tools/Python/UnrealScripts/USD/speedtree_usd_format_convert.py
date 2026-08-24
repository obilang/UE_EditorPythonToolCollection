"""
SpeedTree USD to Unreal Format Converter

This script converts USD files exported from SpeedTree to Unreal-compatible format.

Key conversions:
1. Change root from Scope to Xform and add apiSchemas = ["NaniteAssemblyRootAPI"]
2. Add apiSchemas = ["MaterialBindingAPI"] to material GeomSubsets
3. Move PointInstancers to root level
4. Restructure leaf meshes inside PointInstancer: 
   PointInstancer -> Scope:Prototypes -> Xform:meshname -> Mesh:SM_meshname
"""

from pxr import Usd, UsdGeom, Sdf, Gf, Kind
import os
import sys


class SpeedTreeToUnrealConverter:
    """Convert SpeedTree USD files to Unreal-compatible format."""
    
    def __init__(self, input_path, output_path=None):
        """
        Initialize converter.
        
        Args:
            input_path: Path to input USD file from SpeedTree
            output_path: Path to output USD file (optional, defaults to input_converted.usda)
        """
        self.input_path = input_path
        if output_path is None:
            base, ext = os.path.splitext(input_path)
            self.output_path = f"{base}_converted.usda"
        else:
            self.output_path = output_path
        
        self.stage = None
        self.point_instancers = []  # Store info about PointInstancers to relocate
        self.leaf_meshes = {}  # Map prototype paths to mesh prims
        
    def convert(self):
        """Perform the full conversion process."""
        print(f"Converting {self.input_path} to Unreal format...")
        
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
        
        # Step 1: Convert root from Scope to Xform with NaniteAssemblyRootAPI
        self._convert_root_to_xform(root_prim)
        
        # Step 2: Find and collect PointInstancers and their referenced meshes
        self._collect_point_instancers(root_prim)
        
        # Step 3: Add MaterialBindingAPI to all GeomSubsets
        self._add_material_binding_api(root_prim)
        
        # Step 4: Restructure PointInstancers and their meshes
        self._restructure_point_instancers(root_prim)
        
        # Save the converted stage
        print(f"  Saving to {self.output_path}")
        self.stage.GetRootLayer().Export(self.output_path)
        print("Conversion complete!")
        
        return self.output_path
    
    def _convert_root_to_xform(self, root_prim):
        """Convert root prim from Scope to Xform and add NaniteAssemblyRootAPI."""
        print("  Converting root to Xform with NaniteAssemblyRootAPI...")
        
        root_path = root_prim.GetPath()
        root_name = root_prim.GetName()
        
        # We need to redefine the prim with the correct type
        # First, collect all children and attributes
        children_specs = []
        prim_spec = self.stage.GetRootLayer().GetPrimAtPath(root_path)
        
        if prim_spec:
            # Change the type specifier to Xform
            prim_spec.specifier = Sdf.SpecifierDef
            prim_spec.typeName = 'Xform'
            
            # Add API schemas
            if not prim_spec.HasInfo('apiSchemas'):
                api_list = Sdf.TokenListOp()
                api_list.prependedItems = ['NaniteAssemblyRootAPI']
                prim_spec.SetInfo('apiSchemas', api_list)
            
            # Add kind
            prim_spec.SetInfo('kind', 'group')
            
            # Add nanite assembly mesh type attribute
            attr_spec = Sdf.AttributeSpec(prim_spec, 'unreal:naniteAssembly:meshType', Sdf.ValueTypeNames.Token, Sdf.VariabilityUniform)
            attr_spec.default = 'staticMesh'
            attr_spec.custom = False
        
        # Re-get the prim
        root_prim = self.stage.GetPrimAtPath(root_path)
        
    def _collect_point_instancers(self, root_prim):
        """Find all PointInstancers and their referenced meshes."""
        print("  Collecting PointInstancers...")
        
        for prim in Usd.PrimRange(root_prim):
            if prim.IsA(UsdGeom.PointInstancer):
                instancer = UsdGeom.PointInstancer(prim)
                prototypes_rel = instancer.GetPrototypesRel()
                prototype_paths = prototypes_rel.GetTargets()
                
                self.point_instancers.append({
                    'path': prim.GetPath(),
                    'prim': prim,
                    'prototype_paths': prototype_paths
                })
                
                print(f"    Found PointInstancer: {prim.GetPath()}")
                print(f"      Prototypes: {prototype_paths}")
                
                # Collect the mesh prims referenced by prototypes
                for proto_path in prototype_paths:
                    proto_prim = self.stage.GetPrimAtPath(proto_path)
                    if proto_prim:
                        self.leaf_meshes[proto_path] = proto_prim
    
    def _add_material_binding_api(self, root_prim):
        """Add MaterialBindingAPI to GeomSubsets and their parent Meshes, and add familyName to GeomSubsets."""
        print("  Adding MaterialBindingAPI to GeomSubsets and Meshes...")
        
        meshes_with_materials = set()
        
        for prim in Usd.PrimRange(root_prim):
            if prim.GetTypeName() == 'GeomSubset':
                prim_spec = self.stage.GetRootLayer().GetPrimAtPath(prim.GetPath())
                if prim_spec:
                    # Add MaterialBindingAPI to apiSchemas
                    if prim_spec.HasInfo('apiSchemas'):
                        api_list = prim_spec.GetInfo('apiSchemas')
                        if 'MaterialBindingAPI' not in api_list.prependedItems:
                            new_list = Sdf.TokenListOp()
                            new_list.prependedItems = list(api_list.prependedItems) + ['MaterialBindingAPI']
                            prim_spec.SetInfo('apiSchemas', new_list)
                    else:
                        api_list = Sdf.TokenListOp()
                        api_list.prependedItems = ['MaterialBindingAPI']
                        prim_spec.SetInfo('apiSchemas', api_list)
                    
                    # Add familyName attribute if not present
                    if not prim_spec.GetAttributeAtPath(prim.GetPath().AppendProperty('familyName')):
                        attr_spec = Sdf.AttributeSpec(prim_spec, 'familyName', Sdf.ValueTypeNames.Token, Sdf.VariabilityUniform)
                        attr_spec.default = 'materialBind'
                        print(f"    Added familyName to {prim.GetPath()}")
                    
                    print(f"    Added MaterialBindingAPI to {prim.GetPath()}")
                    
                    # Track parent mesh that needs MaterialBindingAPI
                    parent_prim = prim.GetParent()
                    if parent_prim and parent_prim.IsA(UsdGeom.Mesh):
                        meshes_with_materials.add(parent_prim.GetPath())
        
        # Add MaterialBindingAPI to meshes that have material GeomSubsets
        for mesh_path in meshes_with_materials:
            mesh_spec = self.stage.GetRootLayer().GetPrimAtPath(mesh_path)
            if mesh_spec:
                if mesh_spec.HasInfo('apiSchemas'):
                    api_list = mesh_spec.GetInfo('apiSchemas')
                    if 'MaterialBindingAPI' not in api_list.prependedItems:
                        new_list = Sdf.TokenListOp()
                        new_list.prependedItems = list(api_list.prependedItems) + ['MaterialBindingAPI']
                        mesh_spec.SetInfo('apiSchemas', new_list)
                        print(f"    Added MaterialBindingAPI to mesh {mesh_path}")
                else:
                    api_list = Sdf.TokenListOp()
                    api_list.prependedItems = ['MaterialBindingAPI']
                    mesh_spec.SetInfo('apiSchemas', api_list)
                    print(f"    Added MaterialBindingAPI to mesh {mesh_path}")
    
    def _restructure_point_instancers(self, root_prim):
        """
        Move PointInstancers to root and restructure their mesh references.
        
        Structure: PointInstancer -> Scope:Prototypes -> Xform:meshname -> Mesh:SM_meshname
        """
        print("  Restructuring PointInstancers...")
        
        root_path = root_prim.GetPath()
        
        for instancer_info in self.point_instancers:
            instancer_path = instancer_info['path']
            instancer_prim = instancer_info['prim']
            prototype_paths = instancer_info['prototype_paths']
            
            # Skip if already at root level
            if instancer_prim.GetParent().GetPath() == root_path:
                print(f"    PointInstancer {instancer_prim.GetName()} already at root")
                continue
            
            # Create new PointInstancer at root level
            new_instancer_name = instancer_prim.GetName()
            new_instancer_path = root_path.AppendChild(new_instancer_name)
            
            print(f"    Moving {instancer_path} to {new_instancer_path}")
            
            # Copy the PointInstancer to root
            self._copy_prim_to_new_location(instancer_prim, new_instancer_path)
            
            # Set kind on new instancer
            new_instancer_prim = self.stage.GetPrimAtPath(new_instancer_path)
            Usd.ModelAPI(new_instancer_prim).SetKind(Kind.Tokens.group)
            
            # Create Prototypes scope under the new PointInstancer
            prototypes_scope_path = new_instancer_path.AppendChild('Prototypes')
            prototypes_scope = UsdGeom.Scope.Define(self.stage, prototypes_scope_path)
            Usd.ModelAPI(prototypes_scope.GetPrim()).SetKind(Kind.Tokens.group)
            
            # Process each prototype mesh
            new_prototype_paths = []
            for proto_path in prototype_paths:
                mesh_prim = self.stage.GetPrimAtPath(proto_path)
                if not mesh_prim:
                    print(f"    Warning: Prototype mesh not found: {proto_path}")
                    continue
                
                mesh_name = mesh_prim.GetName()
                
                # Create Xform under Prototypes
                xform_path = prototypes_scope_path.AppendChild(mesh_name)
                xform = UsdGeom.Xform.Define(self.stage, xform_path)
                Usd.ModelAPI(xform.GetPrim()).SetKind(Kind.Tokens.component)
                
                # Create Mesh under Xform with SM_ prefix
                sm_mesh_name = f"SM_{mesh_name}" if not mesh_name.startswith('SM_') else mesh_name
                sm_mesh_path = xform_path.AppendChild(sm_mesh_name)
                
                # Copy the mesh data
                self._copy_mesh_to_new_location(mesh_prim, sm_mesh_path)
                
                new_prototype_paths.append(xform_path)
                
                print(f"      Copied mesh {proto_path} to {sm_mesh_path}")
            
            # Update the prototypes relationship
            new_instancer = UsdGeom.PointInstancer(new_instancer_prim)
            prototypes_rel = new_instancer.GetPrototypesRel()
            prototypes_rel.SetTargets(new_prototype_paths)
            
            # Remove the old instancer
            self.stage.RemovePrim(instancer_path)
        
        # Clean up old LeafMeshes container if it exists
        leaf_meshes_path = root_path.AppendChild('LeafMeshes')
        if self.stage.GetPrimAtPath(leaf_meshes_path):
            print(f"  Removing old LeafMeshes container: {leaf_meshes_path}")
            self.stage.RemovePrim(leaf_meshes_path)
        
        # Clean up Leaf scope under Trunk if it exists
        trunk_leaf_path = root_path.AppendChild('Trunk').AppendChild('Leaf')
        if self.stage.GetPrimAtPath(trunk_leaf_path):
            print(f"  Removing Leaf scope under Trunk: {trunk_leaf_path}")
            self.stage.RemovePrim(trunk_leaf_path)
    
    def _copy_prim_to_new_location(self, source_prim, dest_path):
        """Copy a prim and all its content to a new location."""
        # Use SdfCopySpec to copy the entire prim spec
        source_path = source_prim.GetPath()
        layer = self.stage.GetRootLayer()
        
        Sdf.CopySpec(layer, source_path, layer, dest_path)
    
    def _copy_mesh_to_new_location(self, source_mesh_prim, dest_path):
        """Copy a mesh prim to a new location."""
        layer = self.stage.GetRootLayer()
        source_path = source_mesh_prim.GetPath()
        
        # Copy the mesh spec
        Sdf.CopySpec(layer, source_path, layer, dest_path)
        
        # Update material binding paths if needed (they should be absolute, so should work)
        dest_prim = self.stage.GetPrimAtPath(dest_path)
        if dest_prim:
            # Ensure GeomSubsets maintain their material bindings
            for child in dest_prim.GetChildren():
                if child.GetTypeName() == 'GeomSubset':
                    # Material bindings should already be correct as they're absolute paths
                    pass


def convert_speedtree_to_unreal(input_path, output_path=None):
    """
    Convert a SpeedTree USD file to Unreal format.
    
    Args:
        input_path: Path to input USD file from SpeedTree
        output_path: Path to output USD file (optional)
        
    Returns:
        Path to the converted file
    """
    converter = SpeedTreeToUnrealConverter(input_path, output_path)
    return converter.convert()


def main():
    """Command-line interface."""
    if len(sys.argv) < 2:
        print("Usage: python speedtree_usd_format_convert.py <input_usd> [output_usd]")
        print("\nConverts SpeedTree USD exports to Unreal-compatible format.")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(input_path):
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)
    
    try:
        result = convert_speedtree_to_unreal(input_path, output_path)
        print(f"\nSuccess! Converted file saved to: {result}")
    except Exception as e:
        print(f"Error during conversion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

