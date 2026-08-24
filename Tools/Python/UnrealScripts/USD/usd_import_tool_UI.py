"""
USD Import Tool for Unreal Engine

A GUI tool to browse, preview, and import USD files into Unreal Engine.
Supports generic USD import and specialized converters (e.g., SpeedTree).
"""

import sys
import os
import unreal

from PySide6 import QtCore, QtGui, QtWidgets
from QtUtil import qt_util

# Try to import USD library
try:
    from pxr import Usd, UsdGeom, UsdShade, Gf
    HAS_USD = True
except ImportError:
    HAS_USD = False
    print("Warning: USD Python library not found. USD preview features will be limited.")


WINDOW_TITLE = "USD Import Tool"
WINDOW_MIN_WIDTH = 800
WINDOW_MIN_HEIGHT = 700


class USDMeshItem(QtWidgets.QTreeWidgetItem):
    """Tree widget item representing a USD prim (assembly, instancer, or mesh)."""
    
    def __init__(self, prim_path, prim_data):
        super().__init__()
        self.prim_path = prim_path
        self.prim_data = prim_data
        self.prim_type = prim_data.get('type', 'Unknown')
        
        # Set the display text based on type
        if self.prim_type == 'Assembly':
            self.setText(0, f"[Assembly] {prim_path}")
            self.setForeground(0, QtGui.QBrush(QtGui.QColor(255, 150, 50)))  # Orange
            self.setCheckState(0, QtCore.Qt.Checked)
        elif self.prim_type == 'ExternalRef':
            ref_path = prim_data.get('mesh_asset_path', 'Not Set')
            self.setText(0, f"[External Ref] {prim_path}")
            self.setForeground(0, QtGui.QBrush(QtGui.QColor(200, 100, 200)))  # Purple
            self.setCheckState(0, QtCore.Qt.Checked)
        elif self.prim_type == 'PointInstancer':
            instance_count = prim_data.get('instance_count', 0)
            self.setText(0, f"[Instances: {instance_count}] {prim_path}")
            self.setForeground(0, QtGui.QBrush(QtGui.QColor(100, 200, 100)))  # Green
            self.setCheckState(0, QtCore.Qt.Checked)
        elif self.prim_type == 'Mesh':
            self.setText(0, f"[Mesh] {prim_path}")
            self.setCheckState(0, QtCore.Qt.Checked)
        else:
            self.setText(0, prim_path)
            self.setCheckState(0, QtCore.Qt.Checked)
        
        # Add material information as child items
        materials = prim_data.get('materials', [])
        if materials:
            for mat in materials:
                mat_item = QtWidgets.QTreeWidgetItem(self)
                mat_item.setText(0, f"  Material: {mat}")
                mat_item.setForeground(0, QtGui.QBrush(QtGui.QColor(100, 150, 255)))
        
        # Add prototype information for PointInstancers
        if self.prim_type == 'PointInstancer':
            prototypes = prim_data.get('prototypes', [])
            if prototypes:
                proto_item = QtWidgets.QTreeWidgetItem(self)
                proto_item.setText(0, f"  Prototypes: {', '.join([p.split('/')[-1] for p in prototypes])}")
                proto_item.setForeground(0, QtGui.QBrush(QtGui.QColor(150, 150, 150)))


class USDImportToolWindow(QtWidgets.QDialog):
    """Main USD Import Tool Window."""
    
    def __init__(self, parent=None):
        super(USDImportToolWindow, self).__init__(parent)
        
        # Window setup
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(WINDOW_MIN_WIDTH)
        self.setMinimumHeight(WINDOW_MIN_HEIGHT)
        
        # State variables
        self.current_usd_path = None  # User-selected original file
        self.loaded_usd_path = None  # Actual file to import (may be converted)
        self.usd_stage = None
        self.prim_info = {}  # {prim_path: {materials: [], type: '', instance_count: 0}}
        self.has_valid_schema = False  # Track if USD has NaniteAssemblyRootAPI
        self.external_ref_overrides = {}  # {prim_path: asset_path} for external references
        self.scale_overrides = {}  # {prim_path: float} scale multiplier for PointInstancers
        
        # Build UI
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.build_ui()
    
    def build_ui(self):
        """Build the main user interface."""
        
        # === USD File Selection Section ===
        file_group = QtWidgets.QGroupBox("USD File Selection")
        file_layout = QtWidgets.QVBoxLayout()
        
        # Path display and browse button
        path_layout = QtWidgets.QHBoxLayout()
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setPlaceholderText("Select USD file path...")
        self.path_edit.setReadOnly(True)
        path_layout.addWidget(self.path_edit)
        
        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.clicked.connect(self.on_browse_usd)
        browse_btn.setMaximumWidth(100)
        path_layout.addWidget(browse_btn)
        file_layout.addLayout(path_layout)
        
        # Source type and load button
        load_layout = QtWidgets.QHBoxLayout()
        
        source_label = QtWidgets.QLabel("Source Type:")
        load_layout.addWidget(source_label)
        
        self.converter_combo = QtWidgets.QComboBox()
        self.converter_combo.addItems([
            "SpeedTree",
            "Generic USD",
            "Maya",
            "Blender",
            "Houdini"
        ])
        self.converter_combo.setToolTip("Select the source application for specialized conversion")
        load_layout.addWidget(self.converter_combo)
        
        load_usd_btn = QtWidgets.QPushButton("Load USD")
        load_usd_btn.setToolTip("Load and preview USD file with selected converter")
        load_usd_btn.clicked.connect(self.on_load_usd)
        load_usd_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        load_usd_btn.setMaximumWidth(150)
        load_layout.addWidget(load_usd_btn)
        load_layout.addStretch()
        
        file_layout.addLayout(load_layout)
        file_group.setLayout(file_layout)
        self.main_layout.addWidget(file_group)
        
        # === USD Content Preview Section ===
        preview_group = QtWidgets.QGroupBox("USD Contents Preview")
        preview_layout = QtWidgets.QVBoxLayout()
        
        # Info label
        self.info_label = QtWidgets.QLabel("No USD file loaded")
        self.info_label.setStyleSheet("color: gray; font-style: italic;")
        preview_layout.addWidget(self.info_label)
        
        # Tree widget for assemblies, instances, and meshes
        self.mesh_tree = QtWidgets.QTreeWidget()
        self.mesh_tree.setHeaderLabels(["Assembly / Mesh / Materials", "Mesh Source"])
        self.mesh_tree.setAlternatingRowColors(True)
        self.mesh_tree.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.mesh_tree.setToolTip(
            "[Assembly] = Nanite Assembly Root\n"
            "[External Ref] = External Static Mesh Reference\n"
            "[Instances: N] = Point Instancer with N instances\n"
            "[Mesh] = Static Mesh\n"
            "\nMesh Source column:\n"
            "  Use Imported Mesh = import data from USD as-is\n"
            "  Use Content Browser Selection = redirect to the asset selected in the CB"
        )
        self.mesh_tree.itemSelectionChanged.connect(self.on_tree_selection_changed)
        preview_layout.addWidget(self.mesh_tree)

        # Configure column widths
        _header = self.mesh_tree.header()
        _header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        _header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.mesh_tree.setColumnWidth(1, 330)
        
        # Selection buttons
        selection_layout = QtWidgets.QHBoxLayout()
        select_all_btn = QtWidgets.QPushButton("Select All")
        select_all_btn.clicked.connect(self.on_select_all)
        selection_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QtWidgets.QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self.on_deselect_all)
        selection_layout.addWidget(deselect_all_btn)
        selection_layout.addStretch()
        
        preview_layout.addLayout(selection_layout)
        preview_group.setLayout(preview_layout)
        self.main_layout.addWidget(preview_group)
        
        # === Import Settings Section ===
        import_group = QtWidgets.QGroupBox("Import Settings")
        import_layout = QtWidgets.QFormLayout()
        
        # Destination path
        self.dest_path_edit = QtWidgets.QLineEdit("/Game/ImportedUSD")
        import_layout.addRow("Destination Path:", self.dest_path_edit)
        
        # Import options
        self.import_geometry_check = QtWidgets.QCheckBox()
        self.import_geometry_check.setChecked(True)
        import_layout.addRow("Import Geometry:", self.import_geometry_check)
        
        self.import_materials_check = QtWidgets.QCheckBox()
        self.import_materials_check.setChecked(True)
        import_layout.addRow("Import Materials:", self.import_materials_check)
        
        self.import_actors_check = QtWidgets.QCheckBox()
        self.import_actors_check.setChecked(False)
        import_layout.addRow("Import as Actors:", self.import_actors_check)
        
        self.merge_materials_check = QtWidgets.QCheckBox()
        self.merge_materials_check.setChecked(True)
        import_layout.addRow("Merge Identical Materials:", self.merge_materials_check)
        
        import_group.setLayout(import_layout)
        self.main_layout.addWidget(import_group)
        
        # === Import Button ===
        import_btn = QtWidgets.QPushButton("Import Selected Meshes")
        import_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        import_btn.clicked.connect(self.on_import_usd)
        self.main_layout.addWidget(import_btn)
        
        # Status bar
        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setStyleSheet("padding: 5px; background-color: #f0f0f0;")
        self.main_layout.addWidget(self.status_label)
    
    def on_browse_usd(self):
        """Browse for a USD file."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select USD File",
            "",
            "USD Files (*.usd *.usda *.usdc);;All Files (*.*)"
        )
        
        if file_path:
            self.current_usd_path = file_path
            self.path_edit.setText(file_path)
            self.status_label.setText(f"Selected: {os.path.basename(file_path)}")
    
    def on_load_usd(self):
        """Load USD file with selected converter."""
        if not self.current_usd_path:
            self.on_browse_usd()
            if not self.current_usd_path:
                return
        
        source_type = self.converter_combo.currentText()
        
        # Apply conversion based on source type
        if source_type == "SpeedTree":
            self.status_label.setText("Converting SpeedTree USD...")
            QtWidgets.QApplication.processEvents()
            
            try:
                from USD.speedtree_usd_format_convert import SpeedTreeToUnrealConverter
                
                # Create converted file in same directory as original
                converter = SpeedTreeToUnrealConverter(self.current_usd_path)
                converted_path = converter.convert()
                
                # Store converted path internally but keep original path displayed
                self.loaded_usd_path = converted_path
                unreal.log(f"SpeedTree USD converted: {converted_path}")
                unreal.log(f"Original file: {self.current_usd_path}")
                
            except Exception as e:
                error_msg = f"Failed to convert SpeedTree USD: {str(e)}"
                self.status_label.setText("Conversion failed")
                unreal.log_error(error_msg)
                QtWidgets.QMessageBox.critical(self, "Conversion Error", error_msg)
                return
        else:
            # Generic USD - use original path
            self.loaded_usd_path = self.current_usd_path
        
        # Load preview
        self.load_usd_preview(self.loaded_usd_path)
        
        if source_type == "SpeedTree":
            self.status_label.setText(f"SpeedTree USD converted and loaded")
        else:
            self.status_label.setText(f"{source_type} USD loaded")
    
    def load_usd_preview(self, usd_path):
        """Load and preview USD file contents."""
        self.mesh_tree.clear()
        self.prim_info.clear()
        self.has_valid_schema = False
        self.external_ref_overrides.clear()  # Clear external reference overrides
        self.scale_overrides.clear()  # Clear scale multiplier overrides

        if not os.path.exists(usd_path):
            self.info_label.setText(f"File not found: {usd_path}")
            return
        
        self.status_label.setText("Loading USD preview...")
        QtWidgets.QApplication.processEvents()
        
        if not HAS_USD:
            # Limited preview without USD library
            self.info_label.setText(f"USD file: {os.path.basename(usd_path)} (Preview unavailable - USD library not found)")
            item = QtWidgets.QTreeWidgetItem(self.mesh_tree)
            item.setText(0, "Full USD file (preview not available)")
            item.setCheckState(0, QtCore.Qt.Checked)
            self.status_label.setText("Ready (limited preview)")
            return
        
        try:
            # Drop previous stage reference so the old layer can be released,
            # then force a reload from disk to bust USD's internal layer cache.
            # Without this, modifications made in on_import_usd (adding ExternalRefAPI,
            # removing children, etc.) persist in memory and appear on the next load.
            self.usd_stage = None
            from pxr import Sdf
            cached_layer = Sdf.Layer.Find(usd_path)
            if cached_layer:
                cached_layer.Reload()
            self.usd_stage = Usd.Stage.Open(usd_path)
            
            # Check for Nanite Assembly schema
            source_type = self.converter_combo.currentText()
            schema_check = self.validate_nanite_schema()
            
            if not schema_check['valid'] and source_type == "Generic USD":
                # Generic USD must have proper schema
                error_msg = (
                    "Invalid USD for Nanite Assembly Import\n\n"
                    f"Error: {schema_check['message']}\n\n"
                    "Generic USD files must have the NaniteAssemblyRootAPI schema.\n"
                    "If this is a SpeedTree or other DCC export, select the appropriate source type."
                )
                self.info_label.setText("❌ Invalid Schema")
                self.status_label.setText("Schema validation failed")
                unreal.log_error(f"Schema validation failed: {schema_check['message']}")
                QtWidgets.QMessageBox.critical(self, "Schema Validation Error", error_msg)
                return
            elif not schema_check['valid']:
                # Warning for non-generic USD
                unreal.log_warning(f"USD does not have NaniteAssemblyRootAPI: {schema_check['message']}")
            
            self.has_valid_schema = schema_check['valid']
            
            # Count elements
            assembly_count = 0
            instancer_count = 0
            mesh_count = 0
            external_ref_count = 0
            total_instances = 0
            material_count = 0
            
            # Find assemblies and build hierarchy
            root_prim = self.usd_stage.GetDefaultPrim()
            if not root_prim:
                for prim in self.usd_stage.Traverse():
                    if prim.GetParent() == self.usd_stage.GetPseudoRoot():
                        root_prim = prim
                        break
            
            if root_prim:
                # Check if root is an assembly
                if self.is_nanite_assembly(root_prim):
                    assembly_count += 1
                    assembly_info = self.process_assembly(root_prim)
                    assembly_item = USDMeshItem(str(root_prim.GetPath()), assembly_info)
                    self.mesh_tree.addTopLevelItem(assembly_item)
                    assembly_item.setExpanded(True)
                    
                    # Add children to assembly
                    for child_prim in root_prim.GetChildren():
                        self.add_prim_to_tree(child_prim, assembly_item)
                else:
                    # Not an assembly root, traverse normally
                    for prim in self.usd_stage.Traverse():
                        if prim.GetParent() == root_prim:
                            self.add_prim_to_tree(prim, None)
            
            # Count all types
            for prim_path, prim_data in self.prim_info.items():
                if prim_data['type'] == 'Assembly':
                    assembly_count += 1
                elif prim_data['type'] == 'ExternalRef':
                    external_ref_count += 1
                elif prim_data['type'] == 'PointInstancer':
                    instancer_count += 1
                    total_instances += prim_data.get('instance_count', 0)
                elif prim_data['type'] == 'Mesh':
                    mesh_count += 1
                material_count += len(prim_data.get('materials', []))
            
            # Update info label
            schema_status = "✓" if self.has_valid_schema else "⚠"
            info_parts = [f"{schema_status} {os.path.basename(usd_path)}"]
            if assembly_count > 0:
                info_parts.append(f"Assemblies: {assembly_count}")
            if external_ref_count > 0:
                info_parts.append(f"External Refs: {external_ref_count}")
            if instancer_count > 0:
                info_parts.append(f"Instancers: {instancer_count} ({total_instances} instances)")
            if mesh_count > 0:
                info_parts.append(f"Meshes: {mesh_count}")
            if material_count > 0:
                info_parts.append(f"Materials: {material_count}")
            
            self.info_label.setText(" | ".join(info_parts))
            self.status_label.setText(f"Loaded USD with {assembly_count} assemblies")
            
            unreal.log(f"USD Preview: {assembly_count} assemblies, {instancer_count} instancers, {mesh_count} meshes")
            
        except Exception as e:
            error_msg = f"Failed to load USD preview: {str(e)}"
            self.info_label.setText("Error loading USD")
            self.status_label.setText("Load failed")
            unreal.log_error(error_msg)
            QtWidgets.QMessageBox.warning(self, "USD Load Error", error_msg)
    
    def validate_nanite_schema(self):
        """Validate that the USD stage has NaniteAssemblyRootAPI schema."""
        result = {'valid': False, 'message': ''}
        
        try:
            root_prim = self.usd_stage.GetDefaultPrim()
            if not root_prim:
                for prim in self.usd_stage.Traverse():
                    if prim.GetParent() == self.usd_stage.GetPseudoRoot():
                        root_prim = prim
                        break
            
            if not root_prim:
                result['message'] = 'No root prim found in USD stage'
                return result
            
            # Check for NaniteAssemblyRootAPI
            if self.is_nanite_assembly(root_prim):
                result['valid'] = True
                result['message'] = f'Root prim {root_prim.GetPath()} has NaniteAssemblyRootAPI'
            else:
                result['message'] = f'Root prim {root_prim.GetPath()} does not have NaniteAssemblyRootAPI schema'
        
        except Exception as e:
            result['message'] = f'Error validating schema: {str(e)}'
        
        return result
    
    def is_nanite_assembly(self, prim):
        """Check if a prim has the NaniteAssemblyRootAPI schema."""
        try:
            # Check if prim has NaniteAssemblyRootAPI in its applied schemas
            if prim.HasAPI('NaniteAssemblyRootAPI'):
                return True
            
            # Also check apiSchemas metadata directly
            api_schemas = prim.GetMetadata('apiSchemas')
            if api_schemas and 'NaniteAssemblyRootAPI' in str(api_schemas):
                return True
        except:
            pass
        
        return False
    
    def process_assembly(self, prim):
        """Process a Nanite Assembly prim and return its info."""
        prim_path = str(prim.GetPath())
        materials = self.get_bound_materials(prim)
        
        prim_data = {
            'type': 'Assembly',
            'materials': materials,
            'prim': prim
        }
        
        self.prim_info[prim_path] = prim_data
        return prim_data
    
    def add_prim_to_tree(self, prim, parent_item):
        """Recursively add prim and its children to the tree."""
        prim_path = str(prim.GetPath())
        
        # Check for External Reference first
        if self.is_external_ref(prim):
            mesh_asset_path = self.get_mesh_asset_path(prim)
            materials = self.get_bound_materials(prim)
            
            prim_data = {
                'type': 'ExternalRef',
                'mesh_asset_path': mesh_asset_path,
                'materials': materials,
                'prim': prim
            }
            
            self.prim_info[prim_path] = prim_data
            item = USDMeshItem(prim_path, prim_data)

            if parent_item:
                parent_item.addChild(item)
            else:
                self.mesh_tree.addTopLevelItem(item)

            self.mesh_tree.setItemWidget(item, 1, self.create_mesh_source_widget(prim_path, prim_data))
            item.setExpanded(True)
            return

        # Determine prim type and process accordingly
        if prim.IsA(UsdGeom.PointInstancer):
            # Point Instancer
            instancer = UsdGeom.PointInstancer(prim)
            positions = instancer.GetPositionsAttr().Get()
            instance_count = len(positions) if positions else 0
            
            # Get prototype references
            prototypes_rel = instancer.GetPrototypesRel()
            prototype_paths = [str(target) for target in prototypes_rel.GetTargets()]
            
            materials = self.get_bound_materials(prim)
            
            prim_data = {
                'type': 'PointInstancer',
                'instance_count': instance_count,
                'prototypes': prototype_paths,
                'materials': materials,
                'prim': prim
            }
            
            self.prim_info[prim_path] = prim_data
            item = USDMeshItem(prim_path, prim_data)

            if parent_item:
                parent_item.addChild(item)
            else:
                self.mesh_tree.addTopLevelItem(item)

            self.mesh_tree.setItemWidget(item, 1, self.create_instancer_scale_widget(prim_path))

            # Add prototype meshes as children
            for proto_path in prototype_paths:
                proto_prim = self.usd_stage.GetPrimAtPath(proto_path)
                if proto_prim:
                    self.add_prim_to_tree(proto_prim, item)
            
            item.setExpanded(True)
            
        elif prim.IsA(UsdGeom.Mesh):
            # Mesh
            materials = self.get_bound_materials(prim)
            
            prim_data = {
                'type': 'Mesh',
                'materials': materials,
                'prim': prim
            }
            
            self.prim_info[prim_path] = prim_data
            item = USDMeshItem(prim_path, prim_data)

            if parent_item:
                parent_item.addChild(item)
            else:
                self.mesh_tree.addTopLevelItem(item)

            self.mesh_tree.setItemWidget(item, 1, self.create_mesh_source_widget(prim_path, prim_data))

        else:
            # Other prim types - check children recursively
            for child in prim.GetChildren():
                self.add_prim_to_tree(child, parent_item)
    
    def get_bound_materials(self, prim):
        """Get materials bound to a USD prim."""
        materials = []
        
        try:
            # Try to get material bindings using MaterialBindingAPI
            if hasattr(UsdShade, 'MaterialBindingAPI'):
                binding_api = UsdShade.MaterialBindingAPI(prim)
                
                # Get direct binding - use ComputeBoundMaterial for more reliable results
                bound_material = binding_api.ComputeBoundMaterial()[0]
                if bound_material:
                    mat_prim = bound_material.GetPrim()
                    if mat_prim:
                        materials.append(str(mat_prim.GetPath()))
                
                # Check for subset bindings (per-face materials)
                if prim.IsA(UsdGeom.Mesh):
                    mesh = UsdGeom.Mesh(prim)
                    geom_subsets = UsdGeom.Subset.GetGeomSubsets(mesh)
                    
                    for subset in geom_subsets:
                        subset_binding = UsdShade.MaterialBindingAPI(subset)
                        subset_material = subset_binding.ComputeBoundMaterial()[0]
                        if subset_material:
                            subset_mat_prim = subset_material.GetPrim()
                            if subset_mat_prim:
                                mat_path = str(subset_mat_prim.GetPath())
                                if mat_path not in materials:
                                    materials.append(mat_path)
        
        except Exception as e:
            unreal.log_warning(f"Could not get material bindings for {prim.GetPath()}: {e}")
        
        return materials if materials else ["No material"]
    
    def is_external_ref(self, prim):
        """Check if a prim has the NaniteAssemblyExternalRefAPI schema."""
        try:
            # Check if prim has NaniteAssemblyExternalRefAPI in its applied schemas
            if prim.HasAPI('NaniteAssemblyExternalRefAPI'):
                return True
            
            # Also check apiSchemas metadata directly
            api_schemas = prim.GetMetadata('apiSchemas')
            if api_schemas and 'NaniteAssemblyExternalRefAPI' in str(api_schemas):
                return True
        except:
            pass
        
        return False
    
    def get_mesh_asset_path(self, prim):
        """Get the unreal:naniteAssembly:meshAssetPath attribute from a prim."""
        try:
            # Try to get the mesh asset path attribute
            mesh_asset_attr = prim.GetAttribute('unreal:naniteAssembly:meshAssetPath')
            if mesh_asset_attr:
                mesh_path = mesh_asset_attr.Get()
                if mesh_path:
                    return str(mesh_path)
        except Exception as e:
            unreal.log_warning(f"Could not get mesh asset path for {prim.GetPath()}: {e}")
        
        return "Not Set"
    
    def set_mesh_asset_path(self, prim, asset_path):
        """Set the unreal:naniteAssembly:meshAssetPath attribute on a prim."""
        try:
            # Get or create the attribute
            mesh_asset_attr = prim.GetAttribute('unreal:naniteAssembly:meshAssetPath')
            if not mesh_asset_attr:
                # Create the attribute if it doesn't exist
                from pxr import Sdf
                mesh_asset_attr = prim.CreateAttribute(
                    'unreal:naniteAssembly:meshAssetPath',
                    Sdf.ValueTypeNames.Token
                )
            
            # Set the value
            mesh_asset_attr.Set(asset_path)
            unreal.log(f"Set mesh asset path for {prim.GetPath()} to {asset_path}")
            return True
            
        except Exception as e:
            unreal.log_error(f"Failed to set mesh asset path for {prim.GetPath()}: {e}")
            return False
    
    def create_instancer_scale_widget(self, prim_path):
        """Create a scale multiplier widget for PointInstancer rows (column 1)."""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(4)

        label = QtWidgets.QLabel("Scale \u00d7")
        label.setStyleSheet("color: #A5D6A7; font-size: 10px;")

        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.001, 10000.0)
        spin.setValue(self.scale_overrides.get(prim_path, 1.0))
        spin.setSingleStep(0.1)
        spin.setDecimals(3)
        spin.setMinimumWidth(90)
        spin.setToolTip("Multiply all instance scales by this value on import")
        spin.valueChanged.connect(lambda val: self._on_instancer_scale_changed(prim_path, val))

        layout.addWidget(label)
        layout.addWidget(spin)
        layout.addStretch()
        return container

    def _on_instancer_scale_changed(self, prim_path, value):
        """Store or clear a scale override for a PointInstancer."""
        if abs(value - 1.0) < 1e-9:
            self.scale_overrides.pop(prim_path, None)
        else:
            self.scale_overrides[prim_path] = value

    def create_mesh_source_widget(self, prim_path, prim_data=None):
        """Create a Mesh Source dropdown widget for column 1 of the preview tree."""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(6)

        combo = QtWidgets.QComboBox()
        combo.addItems(["Use Imported Mesh", "Use Content Browser Selection"])
        combo.setMinimumWidth(210)

        path_label = QtWidgets.QLabel()
        path_label.setStyleSheet("color: #90CAF9; font-size: 9px;")

        # Pre-populate if a known path exists (ExternalRef prims carry one from USD)
        existing_path = self.external_ref_overrides.get(prim_path)
        if not existing_path and prim_data and prim_data.get('type') == 'ExternalRef':
            candidate = prim_data.get('mesh_asset_path', '')
            if candidate and candidate != 'Not Set':
                existing_path = candidate

        if existing_path:
            combo.setCurrentIndex(1)
            self.external_ref_overrides[prim_path] = existing_path
            asset_name = existing_path.split('/')[-1] if '/' in existing_path else existing_path
            path_label.setText(asset_name)
            path_label.setToolTip(existing_path)
            path_label.setVisible(True)
        else:
            path_label.setVisible(False)

        combo.currentIndexChanged.connect(
            lambda _idx: self.on_mesh_source_changed(prim_path, combo, path_label)
        )

        layout.addWidget(combo)
        layout.addWidget(path_label, 1)
        return container

    def on_mesh_source_changed(self, prim_path, combo, path_label):
        """Handle Mesh Source dropdown change for a prim."""
        if combo.currentIndex() == 1:  # Use Content Browser Selection
            try:
                selected_assets = unreal.EditorUtilityLibrary.get_selected_asset_data()
                if selected_assets:
                    asset_data = selected_assets[0]
                    asset_path = str(asset_data.package_name)
                    self.external_ref_overrides[prim_path] = asset_path

                    asset_name = asset_path.split('/')[-1] if '/' in asset_path else asset_path
                    path_label.setText(asset_name)
                    path_label.setToolTip(asset_path)
                    path_label.setVisible(True)

                    self.status_label.setText(f"Mesh source set: {asset_path}")
                    unreal.log(f"External ref override: {prim_path} -> {asset_path}")
                else:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "No Content Browser Selection",
                        "Please select a Static Mesh in the Content Browser first, then choose this option."
                    )
                    combo.blockSignals(True)
                    combo.setCurrentIndex(0)
                    combo.blockSignals(False)
            except Exception as e:
                unreal.log_error(f"Failed to get content browser selection: {e}")
                combo.blockSignals(True)
                combo.setCurrentIndex(0)
                combo.blockSignals(False)
        else:  # Use Imported Mesh
            if prim_path in self.external_ref_overrides:
                del self.external_ref_overrides[prim_path]
            path_label.setVisible(False)
            path_label.setText("")
            self.status_label.setText("Mesh source set to: Use Imported Mesh")

    def on_tree_selection_changed(self):
        """Handle tree selection change."""
        pass
    
    def on_select_all(self):
        """Select all meshes in the tree."""
        root = self.mesh_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            item.setCheckState(0, QtCore.Qt.Checked)
    
    def on_deselect_all(self):
        """Deselect all meshes in the tree."""
        root = self.mesh_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            item.setCheckState(0, QtCore.Qt.Unchecked)
    
    def on_import_usd(self):
        """Import the selected USD meshes into Unreal."""
        # Use the loaded_usd_path (converted file) if available, otherwise use current_usd_path
        import_path = self.loaded_usd_path if self.loaded_usd_path else self.current_usd_path
        
        if not import_path or not os.path.exists(import_path):
            QtWidgets.QMessageBox.warning(
                self,
                "No USD File",
                "Please load a USD file first."
            )
            return
        
        # Get selected prims
        selected_meshes = []
        root = self.mesh_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.checkState(0) == QtCore.Qt.Checked:
                if isinstance(item, USDMeshItem):
                    selected_meshes.append(item.prim_path)
        
        if not selected_meshes:
            QtWidgets.QMessageBox.warning(
                self,
                "No Selection",
                "Please select at least one mesh to import."
            )
            return
        
        # Confirm import
        dest_path = self.dest_path_edit.text()
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Import",
            f"Import {len(selected_meshes)} mesh(es) to:\n{dest_path}\n\nContinue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply != QtWidgets.QMessageBox.Yes:
            return
        
        # Create converted USD file with external reference overrides and/or scale multipliers
        needs_conversion = bool(
            (self.external_ref_overrides or self.scale_overrides) and self.usd_stage
        )
        if needs_conversion:
            try:
                self.status_label.setText("Creating converted USD with external references...")
                QtWidgets.QApplication.processEvents()
                
                # Create converted file path
                base_path = os.path.splitext(import_path)[0]
                converted_path = f"{base_path}_with_external_refs.usda"
                
                # Apply external reference modifications
                for prim_path, asset_path in self.external_ref_overrides.items():
                    prim = self.usd_stage.GetPrimAtPath(prim_path)
                    if not prim:
                        continue
                    
                    # If it's a Mesh, we need to modify the parent Xform instead
                    if prim.IsA(UsdGeom.Mesh):
                        parent_prim = prim.GetParent()
                        if parent_prim and parent_prim.GetTypeName() == 'Xform':
                            prim = parent_prim
                            unreal.log(f"Using parent Xform {prim.GetPath()} instead of Mesh for external reference")
                    
                    # Remove all child prims
                    children_to_remove = list(prim.GetChildren())
                    for child in children_to_remove:
                        self.usd_stage.RemovePrim(child.GetPath())
                    
                    # Remove all properties except essential metadata
                    properties_to_remove = [prop.GetName() for prop in prim.GetProperties()]
                    for prop_name in properties_to_remove:
                        prim.RemoveProperty(prop_name)
                    
                    # Add API schema if not present
                    if not self.is_external_ref(prim):
                        prim.AddAppliedSchema('NaniteAssemblyExternalRefAPI')
                    
                    # Set the mesh asset path
                    if not self.set_mesh_asset_path(prim, asset_path):
                        unreal.log_warning(f"Failed to set external ref for {prim.GetPath()}")
                
                # Apply scale multipliers to PointInstancers
                for prim_path, scale_mult in self.scale_overrides.items():
                    prim = self.usd_stage.GetPrimAtPath(prim_path)
                    if not prim or not prim.IsA(UsdGeom.PointInstancer):
                        unreal.log_warning(f"Scale override skipped (prim not found or not a PointInstancer): {prim_path}")
                        continue
                    instancer = UsdGeom.PointInstancer(prim)
                    scales_attr = instancer.GetScalesAttr()
                    scales = scales_attr.Get() if scales_attr else None
                    if scales:
                        new_scales = [Gf.Vec3f(s[0] * scale_mult, s[1] * scale_mult, s[2] * scale_mult) for s in scales]
                        scales_attr.Set(new_scales)
                        unreal.log(f"Applied scale \u00d7{scale_mult} to {len(new_scales)} instances at {prim_path}")
                    else:
                        unreal.log_warning(f"No scale data found on PointInstancer: {prim_path}")

                # Save to converted file
                self.usd_stage.GetRootLayer().Export(converted_path)
                unreal.log(f"Created converted USD with modifications: {converted_path}")
                
                # Use converted file for import
                import_path = converted_path
                
            except Exception as e:
                error_msg = f"Failed to create converted USD file: {str(e)}"
                unreal.log_error(error_msg)
                QtWidgets.QMessageBox.warning(self, "Conversion Warning", error_msg + "\n\nContinuing with original file...")
        
        # Perform import
        self.status_label.setText(f"Importing {len(selected_meshes)} meshes...")
        QtWidgets.QApplication.processEvents()
        
        try:
            success = self.import_usd_to_unreal(
                import_path,
                dest_path,
                selected_meshes
            )
            
            if success:
                self.status_label.setText(f"Successfully imported {len(selected_meshes)} meshes")
                QtWidgets.QMessageBox.information(
                    self,
                    "Import Complete",
                    f"Successfully imported {len(selected_meshes)} mesh(es) to {dest_path}"
                )
            else:
                self.status_label.setText("Import completed with warnings")
                
        except Exception as e:
            error_msg = f"Import failed: {str(e)}"
            self.status_label.setText("Import failed")
            unreal.log_error(error_msg)
            QtWidgets.QMessageBox.critical(self, "Import Error", error_msg)
    
    def import_usd_to_unreal(self, usd_path, destination_path, selected_meshes=None):
        """
        Import USD file into Unreal Engine.
        
        Args:
            usd_path: Path to USD file
            destination_path: Unreal content browser path
            selected_meshes: List of mesh paths to import (None = import all)
        
        Returns:
            bool: True if import succeeded
        """
        # Set up import options
        import_options = unreal.UsdStageImportOptions()
        import_options.import_actors = self.import_actors_check.isChecked()
        import_options.import_geometry = self.import_geometry_check.isChecked()
        import_options.import_materials = self.import_materials_check.isChecked()
        import_options.merge_identical_material_slots = self.merge_materials_check.isChecked()
        
        # Create import task
        task = unreal.AssetImportTask()
        task.filename = usd_path
        task.destination_path = destination_path
        task.replace_existing = True
        task.automated = True
        task.save = True
        task.factory = unreal.UsdStageImportFactory()
        task.options = import_options
        
        # Execute import
        unreal.log(f"Importing USD from: {usd_path}")
        unreal.log(f"Destination: {destination_path}")
        if selected_meshes:
            unreal.log(f"Selected meshes: {len(selected_meshes)}")
        
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        
        # Check if import was successful
        for imported_path in task.imported_object_paths:
            unreal.log(f"Imported: {imported_path}")
        
        success = len(task.imported_object_paths) > 0
        
        if success:
            unreal.log("USD import completed successfully")
        else:
            unreal.log_warning("USD import completed but no objects were imported")
        
        return success


def show_usd_import_tool():
    """Function to show the USD import tool window."""
    app = qt_util.create_qt_application()
    
    widget = USDImportToolWindow()
    widget.show()
    unreal.parent_external_window_to_slate(widget.winId())
    
    return widget


if __name__ == "__main__":
    # Show the tool
    window = show_usd_import_tool()
