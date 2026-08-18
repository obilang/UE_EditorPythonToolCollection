"""
Packed Level Actor Instance Viewer
This tool displays all instanced static mesh components (ISM and HISM) within a selected Packed Level Actor.

When modifying properties:
1. The tool opens the source level asset that was used to create the Packed Level Actor
2. Applies changes to the individual StaticMeshActors in that source level
3. Saves the source level
4. The Packed Level Actor will be automatically rebuilt with the updated properties

Note: Modifying properties will temporarily open the source level. Make sure to save your work first.
"""

import unreal
from PySide6 import QtWidgets, QtCore, QtGui
from QtUtil import qt_util

# Unreal Editor subsystems
editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor_filter_lib = unreal.EditorFilterLibrary()
system_lib = unreal.SystemLibrary()
editor_asset_lib = unreal.EditorAssetLibrary()
level_editor_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
unreal_editor_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
editor_loading_saving = unreal.EditorLoadingAndSavingUtils()


class InstanceComponentData:
    """Data class to hold information about an instanced static mesh component"""
    def __init__(self, component):
        self.component = component
        self.component_name = system_lib.get_object_name(component)
        self.component_type = component.get_class().get_name()
        
        # Get static mesh if available
        self.static_mesh = None
        self.mesh_name = "None"
        try:
            self.static_mesh = component.get_editor_property("static_mesh")
            if self.static_mesh:
                self.mesh_name = self.static_mesh.get_name()
        except:
            pass
        
        # Get instance count
        self.instance_count = 0
        try:
            self.instance_count = component.get_instance_count()
        except:
            pass
        
        # Get mobility
        self.mobility = "Unknown"
        try:
            mobility_enum = component.get_editor_property("mobility")
            self.mobility = str(mobility_enum).split(".")[-1] if mobility_enum else "Unknown"
        except:
            pass
        
        # Get cast shadow
        self.cast_shadow = False
        try:
            self.cast_shadow = component.get_editor_property("cast_shadow")
        except:
            pass


class PackedLevelActorInstanceViewer(QtWidgets.QDialog):
    """Main window for viewing instanced components in a Packed Level Actor"""
    
    WINDOW_TITLE = "Packed Level Actor - Instance Viewer"
    WINDOW_WIDTH = 900
    WINDOW_HEIGHT = 600
    
    def __init__(self, parent=None):
        super(PackedLevelActorInstanceViewer, self).__init__(parent)
        
        self.packed_level_actor = None
        self.component_data_list = []
        
        self.setup_ui()
        self.refresh_data()
    
    def setup_ui(self):
        """Build the UI layout"""
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumWidth(self.WINDOW_WIDTH)
        self.setMinimumHeight(self.WINDOW_HEIGHT)
        
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Header section
        header_layout = QtWidgets.QHBoxLayout()
        
        header_label = QtWidgets.QLabel("<b>Packed Level Actor Instance Viewer</b>")
        header_label.setStyleSheet("font-size: 14px; color: #4A9EFF;")
        header_layout.addWidget(header_label)
        
        header_layout.addStretch()
        
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.setMaximumWidth(100)
        self.refresh_btn.clicked.connect(self.refresh_data)
        header_layout.addWidget(self.refresh_btn)
        
        main_layout.addLayout(header_layout)
        
        # Selected actor info section
        info_group = QtWidgets.QGroupBox("Selected Actor Info")
        info_layout = QtWidgets.QVBoxLayout()
        
        self.actor_info_label = QtWidgets.QLabel("No Packed Level Actor selected")
        self.actor_info_label.setWordWrap(True)
        info_layout.addWidget(self.actor_info_label)
        
        info_group.setLayout(info_layout)
        info_group.setMaximumHeight(100)
        main_layout.addWidget(info_group)
        
        # Statistics section
        stats_layout = QtWidgets.QHBoxLayout()
        
        self.total_components_label = QtWidgets.QLabel("Total Components: 0")
        stats_layout.addWidget(self.total_components_label)
        
        self.total_instances_label = QtWidgets.QLabel("Total Instances: 0")
        stats_layout.addWidget(self.total_instances_label)
        
        stats_layout.addStretch()
        
        main_layout.addLayout(stats_layout)
        
        # Property modification section
        prop_group = QtWidgets.QGroupBox("Modify Component Properties")
        prop_layout = QtWidgets.QGridLayout()
        
        # Info label
        info_label = QtWidgets.QLabel(
            "<i>Note: Modifying properties will open and edit the source level that was packed into this actor.</i>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888; font-size: 10px;")
        prop_layout.addWidget(info_label, 0, 0, 1, 4)
        
        # Cast Shadow
        prop_layout.addWidget(QtWidgets.QLabel("Cast Shadow:"), 1, 0)
        self.cast_shadow_combo = QtWidgets.QComboBox()
        self.cast_shadow_combo.addItems(["No Change", "Enable", "Disable"])
        prop_layout.addWidget(self.cast_shadow_combo, 1, 1)
        
        # Receive Decals
        prop_layout.addWidget(QtWidgets.QLabel("Receive Decals:"), 1, 2)
        self.receive_decals_combo = QtWidgets.QComboBox()
        self.receive_decals_combo.addItems(["No Change", "Enable", "Disable"])
        prop_layout.addWidget(self.receive_decals_combo, 1, 3)
        
        # Cast Shadow as Two Sided
        prop_layout.addWidget(QtWidgets.QLabel("Cast Shadow Two Sided:"), 2, 0)
        self.cast_shadow_two_sided_combo = QtWidgets.QComboBox()
        self.cast_shadow_two_sided_combo.addItems(["No Change", "Enable", "Disable"])
        prop_layout.addWidget(self.cast_shadow_two_sided_combo, 2, 1)
        
        # Affect Distance Field Lighting
        prop_layout.addWidget(QtWidgets.QLabel("Affect Distance Field:"), 2, 2)
        self.affect_distance_field_combo = QtWidgets.QComboBox()
        self.affect_distance_field_combo.addItems(["No Change", "Enable", "Disable"])
        prop_layout.addWidget(self.affect_distance_field_combo, 2, 3)
        
        # Apply buttons
        apply_btn_layout = QtWidgets.QHBoxLayout()
        
        self.apply_to_selected_btn = QtWidgets.QPushButton("Apply to Selected")
        self.apply_to_selected_btn.clicked.connect(self.apply_properties_to_selected)
        apply_btn_layout.addWidget(self.apply_to_selected_btn)
        
        self.apply_to_all_btn = QtWidgets.QPushButton("Apply to All")
        self.apply_to_all_btn.clicked.connect(self.apply_properties_to_all)
        apply_btn_layout.addWidget(self.apply_to_all_btn)
        
        apply_btn_layout.addStretch()
        
        prop_layout.addLayout(apply_btn_layout, 3, 0, 1, 4)
        
        prop_group.setLayout(prop_layout)
        main_layout.addWidget(prop_group)
        
        # Table for displaying components
        self.table = QtWidgets.QTableWidget()
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        
        # Set up columns
        columns = ["Component Name", "Type", "Static Mesh", "Instance Count", "Mobility", "Cast Shadow"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)  # Component Name
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # Type
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)  # Static Mesh
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)  # Instance Count
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)  # Mobility
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)  # Cast Shadow
        
        self.table.itemDoubleClicked.connect(self.on_table_double_clicked)
        
        main_layout.addWidget(self.table)
        
        # Button section
        button_layout = QtWidgets.QHBoxLayout()
        
        self.select_component_btn = QtWidgets.QPushButton("Select Component in Actor")
        self.select_component_btn.clicked.connect(self.on_select_component)
        button_layout.addWidget(self.select_component_btn)
        
        button_layout.addStretch()
        
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.setMaximumWidth(100)
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        main_layout.addLayout(button_layout)
    
    def get_selected_packed_level_actor(self):
        """Get the first selected Packed Level Actor in the level"""
        selected_actors = editor_actor_subsystem.get_selected_level_actors()
        
        for actor in selected_actors:
            if isinstance(actor, unreal.PackedLevelActor):
                return actor
        
        return None
    
    def get_instance_components(self, actor):
        """Get all instanced static mesh components from an actor"""
        if not actor:
            return []
        
        components = []
        
        # Get InstancedStaticMeshComponent (base class)
        ismc_components = actor.get_components_by_class(unreal.InstancedStaticMeshComponent)
        components.extend(ismc_components)
        
        return components
    
    def refresh_data(self):
        """Refresh the data from the selected Packed Level Actor"""
        # Get selected actor
        self.packed_level_actor = self.get_selected_packed_level_actor()
        
        if not self.packed_level_actor:
            self.actor_info_label.setText(
                "<span style='color: orange;'>⚠ No Packed Level Actor selected. "
                "Please select a Packed Level Actor in the level.</span>"
            )
            self.component_data_list = []
            self.update_table()
            return
        
        # Update actor info
        actor_name = self.packed_level_actor.get_actor_label()
        actor_class = self.packed_level_actor.get_class().get_name()
        level_name = system_lib.get_outer_object(self.packed_level_actor).get_name()
        
        # Get source level info
        world_asset = self.packed_level_actor.get_editor_property("world_asset")
        source_level = "Unknown"
        if world_asset:
            source_level = world_asset.get_path_name()
        
        info_text = f"<b>Actor:</b> {actor_name}<br>"
        info_text += f"<b>Class:</b> {actor_class}<br>"
        info_text += f"<b>Level:</b> {level_name}<br>"
        info_text += f"<b>Source Level:</b> {source_level}"
        
        self.actor_info_label.setText(info_text)
        
        # Get all instanced components
        components = self.get_instance_components(self.packed_level_actor)
        
        # Create data objects
        self.component_data_list = []
        for comp in components:
            comp_data = InstanceComponentData(comp)
            self.component_data_list.append(comp_data)
        
        # Update table
        self.update_table()
        
        unreal.log(f"[PackedLevelActorInstanceViewer] Found {len(self.component_data_list)} "
                  f"instanced components in '{actor_name}'")
    
    def update_table(self):
        """Update the table with component data"""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        
        if not self.component_data_list:
            self.total_components_label.setText("Total Components: 0")
            self.total_instances_label.setText("Total Instances: 0")
            return
        
        # Calculate statistics
        total_instances = sum(comp.instance_count for comp in self.component_data_list)
        
        self.total_components_label.setText(f"Total Components: {len(self.component_data_list)}")
        self.total_instances_label.setText(f"Total Instances: {total_instances}")
        
        # Populate table
        for row, comp_data in enumerate(self.component_data_list):
            self.table.insertRow(row)
            
            # Component Name
            item = QtWidgets.QTableWidgetItem(comp_data.component_name)
            self.table.setItem(row, 0, item)
            
            # Type
            type_text = "HISM" if "Hierarchical" in comp_data.component_type else "ISM"
            item = QtWidgets.QTableWidgetItem(type_text)
            self.table.setItem(row, 1, item)
            
            # Static Mesh
            item = QtWidgets.QTableWidgetItem(comp_data.mesh_name)
            self.table.setItem(row, 2, item)
            
            # Instance Count
            item = QtWidgets.QTableWidgetItem(str(comp_data.instance_count))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            # Color code based on instance count
            if comp_data.instance_count == 0:
                item.setForeground(QtGui.QBrush(QtGui.QColor(255, 100, 100)))  # Red for zero
            elif comp_data.instance_count > 1000:
                item.setForeground(QtGui.QBrush(QtGui.QColor(100, 255, 100)))  # Green for many
            self.table.setItem(row, 3, item)
            
            # Mobility
            item = QtWidgets.QTableWidgetItem(comp_data.mobility)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, 4, item)
            
            # Cast Shadow
            shadow_text = "Yes" if comp_data.cast_shadow else "No"
            item = QtWidgets.QTableWidgetItem(shadow_text)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, 5, item)
        
        self.table.setSortingEnabled(True)
        # Sort by instance count by default (descending)
        self.table.sortItems(3, QtCore.Qt.DescendingOrder)
    
    def on_table_double_clicked(self, item):
        """Handle double-click on table row"""
        self.on_select_component()
    
    def on_select_component(self):
        """Log component details when a row is selected"""
        selected_rows = self.table.selectionModel().selectedRows()
        
        if not selected_rows:
            unreal.log_warning("[PackedLevelActorInstanceViewer] No component selected in table")
            return
        
        row = selected_rows[0].row()
        if row < 0 or row >= len(self.component_data_list):
            return
        
        comp_data = self.component_data_list[row]
        
        # Log detailed information
        unreal.log("=" * 60)
        unreal.log(f"Component: {comp_data.component_name}")
        unreal.log(f"Type: {comp_data.component_type}")
        unreal.log(f"Static Mesh: {comp_data.mesh_name}")
        unreal.log(f"Instance Count: {comp_data.instance_count}")
        unreal.log(f"Mobility: {comp_data.mobility}")
        unreal.log(f"Cast Shadow: {comp_data.cast_shadow}")
        
        # Get additional properties
        try:
            bounds = comp_data.component.get_editor_property("bounds")
            unreal.log(f"Bounds: {bounds}")
        except:
            pass
        
        unreal.log("=" * 60)
    
    def apply_property_change(self, component, property_name, combo_value):
        """Apply a property change to a component based on combo box value"""
        if combo_value == "No Change":
            return False
        
        try:
            new_value = combo_value == "Enable"
            component.set_editor_property(property_name, new_value)
            return True
        except Exception as e:
            unreal.log_warning(f"Failed to set {property_name}: {str(e)}")
            return False
    
    def apply_properties_to_selected(self):
        """Apply property changes to the selected component in the table"""
        selected_rows = self.table.selectionModel().selectedRows()
        
        if not selected_rows:
            unreal.log_warning("[PackedLevelActorInstanceViewer] No component selected in table")
            QtWidgets.QMessageBox.warning(self, "No Selection", 
                                         "Please select a component from the table first.")
            return
        
        row = selected_rows[0].row()
        if row < 0 or row >= len(self.component_data_list):
            return
        
        comp_data = self.component_data_list[row]
        self.apply_properties_to_components([comp_data])
    
    def apply_properties_to_all(self):
        """Apply property changes to all components"""
        if not self.component_data_list:
            unreal.log_warning("[PackedLevelActorInstanceViewer] No components to modify")
            return
        
        # Confirm with user
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm",
            f"Apply property changes to all {len(self.component_data_list)} components?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.apply_properties_to_components(self.component_data_list)
    
    def apply_properties_to_components(self, component_data_list):
        """Apply property changes to components by editing the source level"""
        if not component_data_list:
            return
        
        if not self.packed_level_actor:
            unreal.log_error("[PackedLevelActorInstanceViewer] No packed level actor selected")
            return
        
        # Get the source level asset path before we clear references
        try:
            world_asset = self.packed_level_actor.get_editor_property("world_asset")
            if not world_asset:
                unreal.log_error("[PackedLevelActorInstanceViewer] No world asset found for Packed Level Actor")
                QtWidgets.QMessageBox.critical(
                    self, "Error",
                    "Cannot find the source level asset for this Packed Level Actor."
                )
                return
            # Convert to string immediately to avoid holding object reference
            source_level_path = str(world_asset.get_path_name())
            world_asset = None  # Clear the reference
        except Exception as e:
            unreal.log_error(f"[PackedLevelActorInstanceViewer] Error getting source level: {e}")
            return
        
        unreal.log(f"[PackedLevelActorInstanceViewer] Source level: {source_level_path}")
        
        # Get the current level path to reload later
        try:
            current_world = unreal_editor_subsystem.get_editor_world()
            current_level_path = str(current_world.get_path_name()) if current_world else None
            current_world = None  # Clear the reference
        except:
            current_level_path = None
        
        unreal.log(f"[PackedLevelActorInstanceViewer] Current level: {current_level_path}")
        
        # Build a mapping of meshes from component data before we clear references
        mesh_filter = set()
        for comp_data in component_data_list:
            if comp_data.static_mesh:
                try:
                    mesh_filter.add(str(comp_data.static_mesh.get_path_name()))  # Store path as string
                except:
                    pass
        
        # Clear comp_data reference
        comp_data = None
        
        # Get property settings before clearing references
        cast_shadow_value = self.cast_shadow_combo.currentText()
        receive_decals_value = self.receive_decals_combo.currentText()
        cast_shadow_two_sided_value = self.cast_shadow_two_sided_combo.currentText()
        affect_distance_field_value = self.affect_distance_field_combo.currentText()
        
        # Check if any properties are set to change
        has_changes = (cast_shadow_value != "No Change" or 
                       receive_decals_value != "No Change" or
                       cast_shadow_two_sided_value != "No Change" or
                       affect_distance_field_value != "No Change")
        
        if not has_changes:
            QtWidgets.QMessageBox.information(
                self, "No Changes",
                "No property changes selected. Please select properties to change from 'No Change'."
            )
            return
        
        # Show warning about editing source level
        reply = QtWidgets.QMessageBox.question(
            self, "Edit Source Level",
            f"This will open and modify the source level:\n{source_level_path}\n\n"
            f"The Packed Level Actor will need to be rebuilt after changes.\n\n"
            f"Do you want to continue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply != QtWidgets.QMessageBox.Yes:
            return
        
        try:
            # Clear Python references to prevent memory leak
            unreal.log("[PackedLevelActorInstanceViewer] Clearing all object references...")
            
            # Clear component data objects which hold references to components
            for item in self.component_data_list:
                item.component = None
                item.static_mesh = None
            
            self.packed_level_actor = None
            self.component_data_list = []
            self.update_table()
            
            # Also clear the component_data_list parameter to break any reference chains
            component_data_list = []
            
            # Force multiple garbage collections
            import gc
            gc.collect()
            gc.collect()
            gc.collect()
            
            # Small delay to allow cleanup
            import time
            time.sleep(0.1)
            
            # Force one more garbage collection
            gc.collect()
            
            # Save current level first (only if it has a valid filename)
            if current_level_path and "/Temp/" not in current_level_path and "Untitled" not in current_level_path:
                unreal.log("[PackedLevelActorInstanceViewer] Saving current level...")
                level_editor_subsystem.save_current_level()
            else:
                unreal.log("[PackedLevelActorInstanceViewer] Skipping save of unsaved level")
            
            # Load the source level
            unreal.log(f"[PackedLevelActorInstanceViewer] Loading source level: {source_level_path}")
            success = level_editor_subsystem.load_level(source_level_path)
            
            if not success:
                unreal.log_error(f"[PackedLevelActorInstanceViewer] Failed to load level: {source_level_path}")
                QtWidgets.QMessageBox.critical(
                    self, "Error",
                    f"Failed to load source level: {source_level_path}"
                )
                return
            
            # Get all static mesh actors in the source level
            all_actors = editor_actor_subsystem.get_all_level_actors()
            static_mesh_actors = editor_filter_lib.by_class(all_actors, unreal.StaticMeshActor)
            
            unreal.log(f"[PackedLevelActorInstanceViewer] Found {len(static_mesh_actors)} static mesh actors in source level")
            
            if len(static_mesh_actors) == 0:
                unreal.log_warning("[PackedLevelActorInstanceViewer] No static mesh actors found in source level")
                QtWidgets.QMessageBox.warning(
                    self, "Warning",
                    "No static mesh actors found in the source level to modify."
                )
                return
            
            # Apply changes to matching actors
            changes_applied = 0
            property_counts = {}
            
            with unreal.ScopedEditorTransaction("Modify Packed Level Actor Source Meshes"):
                for actor in static_mesh_actors:
                    smc = actor.static_mesh_component
                    if not smc:
                        continue
                    
                    # If we have a mesh filter, only modify matching meshes
                    if mesh_filter:
                        actor_mesh = smc.get_editor_property("static_mesh")
                        if actor_mesh:
                            actor_mesh_path = str(actor_mesh.get_path_name())
                            if actor_mesh_path not in mesh_filter:
                                continue
                        else:
                            continue
                    
                    component_changes = 0
                    
                    # Cast Shadow
                    if self.apply_property_change(smc, "cast_shadow", cast_shadow_value):
                        property_counts["cast_shadow"] = property_counts.get("cast_shadow", 0) + 1
                        component_changes += 1
                    
                    # Receive Decals
                    if self.apply_property_change(smc, "receives_decals", receive_decals_value):
                        property_counts["receives_decals"] = property_counts.get("receives_decals", 0) + 1
                        component_changes += 1
                    
                    # Cast Shadow Two Sided
                    if self.apply_property_change(smc, "cast_shadow_as_two_sided", cast_shadow_two_sided_value):
                        property_counts["cast_shadow_as_two_sided"] = property_counts.get("cast_shadow_as_two_sided", 0) + 1
                        component_changes += 1
                    
                    # Affect Distance Field Lighting
                    if self.apply_property_change(smc, "affect_distance_field_lighting", affect_distance_field_value):
                        property_counts["affect_distance_field_lighting"] = property_counts.get("affect_distance_field_lighting", 0) + 1
                        component_changes += 1
                    
                    if component_changes > 0:
                        changes_applied += 1
            
            # Save the source level
            if changes_applied > 0:
                unreal.log("[PackedLevelActorInstanceViewer] Saving source level...")
                level_editor_subsystem.save_current_level()
                
                # Log results
                unreal.log("=" * 60)
                unreal.log(f"[PackedLevelActorInstanceViewer] Applied properties to {changes_applied} actor(s) in source level")
                for prop_name, count in property_counts.items():
                    unreal.log(f"  - {prop_name}: {count} actor(s) modified")
                unreal.log("=" * 60)
                
                # Reload original level if we have one
                if current_level_path and current_level_path != source_level_path:
                    unreal.log(f"[PackedLevelActorInstanceViewer] Reloading original level: {current_level_path}")
                    level_editor_subsystem.load_level(current_level_path)
                
                # Show success message
                QtWidgets.QMessageBox.information(
                    self, "Success",
                    f"Properties applied to {changes_applied} static mesh actor(s) in source level.\n\n"
                    f"Source level saved: {source_level_path}\n\n"
                    f"The Packed Level Actor has been updated automatically."
                )
                
                # Refresh the UI
                self.refresh_data()
            else:
                unreal.log_warning("[PackedLevelActorInstanceViewer] No property changes were applied")
                QtWidgets.QMessageBox.information(
                    self, "No Changes",
                    "No property changes were applied. Select properties to change from 'No Change'."
                )
                
        except Exception as e:
            unreal.log_error(f"[PackedLevelActorInstanceViewer] Error editing source level: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"An error occurred while editing the source level:\n{str(e)}"
            )


def show_packed_level_actor_instance_viewer():
    """Main entry point to show the viewer window"""
    app = qt_util.create_qt_application()
    
    # Create and show window
    global g_viewer_window
    g_viewer_window = PackedLevelActorInstanceViewer()
    g_viewer_window.show()
    
    return g_viewer_window


# Global variable to keep window alive
g_viewer_window = None


if __name__ == "__main__":
    show_packed_level_actor_instance_viewer()
