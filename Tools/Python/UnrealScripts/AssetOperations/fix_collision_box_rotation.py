"""
Fix Collision Box Rotation Tool

This tool provides two functions for managing collision primitives on static mesh actors:

1. CHECK Mode (check_selected_actors):
   - Analyzes and reports all collision primitives in selected meshes
   - Shows box, sphere, capsule, convex collision details
   - Does NOT modify anything
   - Usage: Run with argument "check"

2. FIX Mode (process_selected_actors):
   - Fixes box collision rotations to (0,0,0)
   - Recalculates bounding box dimensions to preserve volume
   - Enables collision generation checkbox
   - Usage: Run with no arguments or "fix"

Usage in Unreal:
  - Check only: py AssetOperations/fix_collision_box_rotation.py check
  - Fix: py AssetOperations/fix_collision_box_rotation.py
"""

import unreal

# Get subsystems
editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor_asset_subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
static_mesh_editor_subsystem = unreal.StaticMeshEditorSubsystem()


def is_rotation_zero(rotation):
    """Check if rotation is approximately (0,0,0)"""
    if not rotation:
        return True
    
    tolerance = 0.0001
    return (abs(rotation.roll) < tolerance and 
            abs(rotation.pitch) < tolerance and 
            abs(rotation.yaw) < tolerance)


def fix_box_collision_rotations(static_mesh):
    """
    Fix box collision rotations for a static mesh.
    Returns tuple (mesh_was_modified, box_count, boxes_fixed)
    """
    if not static_mesh:
        return False, 0, 0
    
    # Get the body setup
    body_setup = static_mesh.get_editor_property('body_setup')
    if not body_setup:
        unreal.log_warning(f"[Fix Collision] No body setup found for {static_mesh.get_name()}")
        return False, 0, 0
    
    # Get the aggregated geometry
    agg_geom = body_setup.get_editor_property('agg_geom')
    if not agg_geom:
        unreal.log_warning(f"[Fix Collision] No aggregated geometry found for {static_mesh.get_name()}")
        return False, 0, 0
    
    # Check for sphere and capsule elements (log but don't modify)
    sphere_elems = agg_geom.get_editor_property('sphere_elems')
    if sphere_elems and len(sphere_elems) > 0:
        unreal.log(f"[Fix Collision] Found {len(sphere_elems)} sphere collision primitive(s) in {static_mesh.get_name()} (not modified)")
    
    sphyl_elems = agg_geom.get_editor_property('sphyl_elems')
    if sphyl_elems and len(sphyl_elems) > 0:
        unreal.log(f"[Fix Collision] Found {len(sphyl_elems)} capsule collision primitive(s) in {static_mesh.get_name()} (not modified)")
    
    # Get box elements (this returns a copy, so we need to write it back)
    box_elems = agg_geom.get_editor_property('box_elems')
    if not box_elems or len(box_elems) == 0:
        unreal.log(f"[Fix Collision] No box collision primitives found in {static_mesh.get_name()}")
        return False, 0, 0
    
    mesh_modified = False
    boxes_fixed = 0
    modified_box_elems = []  # We'll collect modified boxes
    
    unreal.log(f"[Fix Collision] Processing {len(box_elems)} box collision primitive(s) in {static_mesh.get_name()}")
    
    # Process each box element
    for i, box_elem in enumerate(box_elems):
        elem_modified = False
        
        # Get current rotation
        current_rotation = box_elem.get_editor_property('rotation')
        
        # Check if rotation needs to be fixed
        if not is_rotation_zero(current_rotation):
            unreal.log(f"  Box {i}: Rotation needs fixing: {current_rotation}")
            
            # Get current transform properties
            center = box_elem.get_editor_property('center')
            x_length = box_elem.get_editor_property('x')
            y_length = box_elem.get_editor_property('y')
            z_length = box_elem.get_editor_property('z')
            
            unreal.log(f"    Current - Center: {center}, Size: ({x_length}, {y_length}, {z_length})")
            
            # Calculate the 8 corners of the oriented box
            half_extents = [x_length / 2.0, y_length / 2.0, z_length / 2.0]
            corners = []
            for x_sign in [-1, 1]:
                for y_sign in [-1, 1]:
                    for z_sign in [-1, 1]:
                        local_corner = unreal.Vector(
                            x_sign * half_extents[0],
                            y_sign * half_extents[1],
                            z_sign * half_extents[2]
                        )
                        corners.append(local_corner)
            
            # Create transform from rotation and rotate each corner
            rotation_quat = current_rotation.quaternion()
            rotated_corners = []
            for corner in corners:
                # Rotate the corner by the rotation quaternion
                rotated = rotation_quat.rotate_vector(corner)
                rotated_corners.append(rotated)
            
            # Find min/max of rotated corners to get new axis-aligned bounding box
            min_x = min(c.x for c in rotated_corners)
            max_x = max(c.x for c in rotated_corners)
            min_y = min(c.y for c in rotated_corners)
            max_y = max(c.y for c in rotated_corners)
            min_z = min(c.z for c in rotated_corners)
            max_z = max(c.z for c in rotated_corners)
            
            # Calculate new center (in local space, relative to original center)
            new_local_center = unreal.Vector(
                (min_x + max_x) / 2.0,
                (min_y + max_y) / 2.0,
                (min_z + max_z) / 2.0
            )
            
            # Calculate new dimensions
            new_x = max_x - min_x
            new_y = max_y - min_y
            new_z = max_z - min_z
            
            # Calculate new world center
            new_center = unreal.Vector(
                center.x + new_local_center.x,
                center.y + new_local_center.y,
                center.z + new_local_center.z
            )
            
            # Update box element with new values
            box_elem.set_editor_property('center', new_center)
            box_elem.set_editor_property('x', new_x)
            box_elem.set_editor_property('y', new_y)
            box_elem.set_editor_property('z', new_z)
            
            # Reset rotation to zero
            zero_rotation = unreal.Rotator(0.0, 0.0, 0.0)
            box_elem.set_editor_property('rotation', zero_rotation)
            elem_modified = True
            
            unreal.log(f"    Fixed - Rotation: (0, 0, 0), Center: {new_center}, Size: ({new_x:.1f}, {new_y:.1f}, {new_z:.1f})")
        else:
            unreal.log(f"  Box {i}: Rotation is already (0, 0, 0)")
        
        # Always enable collision generation (toggle on the checkbox)
        # Based on Unreal Engine source, box elements have a 'is_generated' flag
        try:
            current_contrib = box_elem.get_editor_property('is_generated')
            if not current_contrib:
                box_elem.set_editor_property('is_generated', True)
                elem_modified = True
                unreal.log(f"  Box {i}: Enabled collision generation (is_generated)")
            else:
                unreal.log(f"  Box {i}: Collision generation already enabled")
        except:
            # Property might not exist or have a different name
            unreal.log(f"  Box {i}: is_generated property not found (this is normal)")
        
        # Add the box (modified or not) to our list
        modified_box_elems.append(box_elem)
        
        if elem_modified:
            boxes_fixed += 1
            mesh_modified = True
    
    if mesh_modified:
        # Write the modified box elements back to the aggregate geometry
        unreal.log(f"[Fix Collision] Writing modified collision data back to mesh")
        agg_geom.set_editor_property('box_elems', modified_box_elems)
        body_setup.set_editor_property('agg_geom', agg_geom)
        static_mesh.set_editor_property('body_setup', body_setup)
        
        # Mark the mesh as modified
        static_mesh.modify()
        
        # Save the mesh
        unreal.log(f"[Fix Collision] Saving changes to {static_mesh.get_name()}")
        unreal.EditorAssetLibrary.save_loaded_asset(static_mesh)
    
    return mesh_modified, len(box_elems), boxes_fixed


def check_collision_primitives(static_mesh):
    """
    Check and report all collision primitives for a static mesh.
    Returns tuple (has_collision, collision_info_dict)
    """
    if not static_mesh:
        return False, {}
    
    # Get the body setup
    body_setup = static_mesh.get_editor_property('body_setup')
    if not body_setup:
        unreal.log(f"[Check Collision] No body setup found for {static_mesh.get_name()}")
        return False, {}
    
    # Get the aggregated geometry
    agg_geom = body_setup.get_editor_property('agg_geom')
    if not agg_geom:
        unreal.log(f"[Check Collision] No aggregated geometry found for {static_mesh.get_name()}")
        return False, {}
    
    collision_info = {}
    has_any_collision = False
    
    unreal.log(f"[Check Collision] Analyzing collision for: {static_mesh.get_name()}")
    
    # Check box elements
    box_elems = agg_geom.get_editor_property('box_elems')
    if box_elems and len(box_elems) > 0:
        # Filter to only boxes that are NOT auto-generated
        non_generated_boxes = []
        for box_elem in box_elems:
            try:
                is_gen = box_elem.get_editor_property('is_generated')
                if not is_gen:
                    non_generated_boxes.append(box_elem)
            except:
                # If property doesn't exist, include the box
                non_generated_boxes.append(box_elem)
        
        if non_generated_boxes:
            has_any_collision = True
            collision_info['boxes'] = len(non_generated_boxes)
            unreal.log(f"  Box Collision: {len(non_generated_boxes)} primitive(s) (custom, non-generated)")
            for i, box_elem in enumerate(non_generated_boxes):
                rotation = box_elem.get_editor_property('rotation')
                center = box_elem.get_editor_property('center')
                x = box_elem.get_editor_property('x')
                y = box_elem.get_editor_property('y')
                z = box_elem.get_editor_property('z')
                rotation_status = "aligned" if is_rotation_zero(rotation) else "rotated"
                unreal.log(f"    Box {i}: Center={center}, Size=({x:.1f}, {y:.1f}, {z:.1f}), Rotation={rotation} [{rotation_status}]")
    
    # Check sphere elements
    sphere_elems = agg_geom.get_editor_property('sphere_elems')
    if sphere_elems and len(sphere_elems) > 0:
        has_any_collision = True
        collision_info['spheres'] = len(sphere_elems)
        unreal.log(f"  Sphere Collision: {len(sphere_elems)} primitive(s)")
        for i, sphere_elem in enumerate(sphere_elems):
            center = sphere_elem.get_editor_property('center')
            radius = sphere_elem.get_editor_property('radius')
            unreal.log(f"    Sphere {i}: Center={center}, Radius={radius:.1f}")
    
    # Check capsule (sphyl) elements
    sphyl_elems = agg_geom.get_editor_property('sphyl_elems')
    if sphyl_elems and len(sphyl_elems) > 0:
        has_any_collision = True
        collision_info['capsules'] = len(sphyl_elems)
        unreal.log(f"  Capsule Collision: {len(sphyl_elems)} primitive(s)")
        for i, sphyl_elem in enumerate(sphyl_elems):
            center = sphyl_elem.get_editor_property('center')
            radius = sphyl_elem.get_editor_property('radius')
            length = sphyl_elem.get_editor_property('length')
            rotation = sphyl_elem.get_editor_property('rotation')
            unreal.log(f"    Capsule {i}: Center={center}, Radius={radius:.1f}, Length={length:.1f}, Rotation={rotation}")
    
    # Check tapered capsule elements
    tapered_capsule_elems = agg_geom.get_editor_property('tapered_capsule_elems')
    if tapered_capsule_elems and len(tapered_capsule_elems) > 0:
        has_any_collision = True
        collision_info['tapered_capsules'] = len(tapered_capsule_elems)
        unreal.log(f"  Tapered Capsule Collision: {len(tapered_capsule_elems)} primitive(s)")
    
    # Check collision trace flag
    collision_trace_flag = body_setup.get_editor_property('collision_trace_flag')
    unreal.log(f"  Collision Trace Flag: {collision_trace_flag}")
    
    if not has_any_collision:
        unreal.log(f"  No simple collision primitives found")
    
    return has_any_collision, collision_info


def check_selected_actors():
    """Check and report collision primitives for all selected static mesh actors"""
    # Get selected actors in the level
    selected_actors = editor_actor_subsystem.get_selected_level_actors()
    
    if not selected_actors or len(selected_actors) == 0:
        unreal.log_warning("[Check Collision] No actors selected!")
        unreal.EditorDialog.show_message(
            "Warning",
            "No actors selected. Please select one or more Static Mesh Actors in the level.",
            unreal.AppMsgType.OK
        )
        return
    
    # Filter to only Static Mesh Actors
    static_mesh_actors = []
    for actor in selected_actors:
        if isinstance(actor, unreal.StaticMeshActor):
            static_mesh_actors.append(actor)
    
    if len(static_mesh_actors) == 0:
        unreal.log_warning("[Check Collision] No Static Mesh Actors in selection!")
        unreal.EditorDialog.show_message(
            "Warning",
            f"No Static Mesh Actors found in selection. Selected {len(selected_actors)} actor(s), but none are Static Mesh Actors.",
            unreal.AppMsgType.OK
        )
        return
    
    unreal.log("=" * 80)
    unreal.log(f"[Check Collision] Checking {len(static_mesh_actors)} Static Mesh Actor(s)")
    unreal.log("=" * 80)
    
    meshes_processed = set()
    meshes_with_collision = 0
    meshes_without_collision = 0
    collision_mesh_list = []  # Track meshes with collision for summary
    
    # Process each static mesh actor
    for actor in static_mesh_actors:
        # Get the static mesh component
        static_mesh_comp = actor.static_mesh_component
        if not static_mesh_comp:
            continue
        
        # Get the static mesh asset
        static_mesh = static_mesh_comp.get_editor_property('static_mesh')
        if not static_mesh:
            continue
        
        # Get the mesh path to avoid processing duplicates
        mesh_path = static_mesh.get_path_name()
        if mesh_path in meshes_processed:
            continue
        
        meshes_processed.add(mesh_path)
        unreal.log(f"\n[Check Collision] Actor: {actor.get_actor_label()}")
        
        # Check collision
        has_collision, collision_info = check_collision_primitives(static_mesh)
        if has_collision:
            meshes_with_collision += 1
            collision_mesh_list.append({
                'name': static_mesh.get_name(),
                'actor': actor.get_actor_label(),
                'info': collision_info
            })
        else:
            meshes_without_collision += 1
    
    # Print list of meshes with collision
    unreal.log("\n" + "=" * 80)
    if collision_mesh_list:
        unreal.log("[Check Collision] Meshes with collision primitives:")
        for mesh_data in collision_mesh_list:
            types = []
            if 'boxes' in mesh_data['info']:
                types.append(f"{mesh_data['info']['boxes']} box(es)")
            if 'spheres' in mesh_data['info']:
                types.append(f"{mesh_data['info']['spheres']} sphere(s)")
            if 'capsules' in mesh_data['info']:
                types.append(f"{mesh_data['info']['capsules']} capsule(s)")
            if 'tapered_capsules' in mesh_data['info']:
                types.append(f"{mesh_data['info']['tapered_capsules']} tapered capsule(s)")
            
            collision_summary = ", ".join(types)
            unreal.log(f"  - {mesh_data['name']} (Actor: {mesh_data['actor']}): {collision_summary}")
    else:
        unreal.log("[Check Collision] No meshes with collision primitives found")
    
    # Show summary
    unreal.log("\n" + "=" * 80)
    summary_msg = (
        f"Collision Check Complete\n\n"
        f"Static Mesh Actors selected: {len(static_mesh_actors)}\n"
        f"Unique meshes checked: {len(meshes_processed)}\n"
        f"Meshes with collision: {meshes_with_collision}\n"
        f"Meshes without collision: {meshes_without_collision}\n\n"
        f"See Output Log for detailed collision information."
    )
    
    unreal.log(f"[Check Collision] Summary:\n{summary_msg}")
    unreal.log("=" * 80)
    
    unreal.EditorDialog.show_message(
        "Collision Check Complete",
        summary_msg,
        unreal.AppMsgType.OK
    )


def process_selected_actors():
    """Main function to process all selected static mesh actors"""
    # Get selected actors in the level
    selected_actors = editor_actor_subsystem.get_selected_level_actors()
    
    if not selected_actors or len(selected_actors) == 0:
        unreal.log_warning("[Fix Collision] No actors selected!")
        unreal.EditorDialog.show_message(
            "Warning",
            "No actors selected. Please select one or more Static Mesh Actors in the level.",
            unreal.AppMsgType.OK
        )
        return
    
    # Filter to only Static Mesh Actors
    static_mesh_actors = []
    for actor in selected_actors:
        if isinstance(actor, unreal.StaticMeshActor):
            static_mesh_actors.append(actor)
    
    if len(static_mesh_actors) == 0:
        unreal.log_warning("[Fix Collision] No Static Mesh Actors in selection!")
        unreal.EditorDialog.show_message(
            "Warning",
            f"No Static Mesh Actors found in selection. Selected {len(selected_actors)} actor(s), but none are Static Mesh Actors.",
            unreal.AppMsgType.OK
        )
        return
    
    unreal.log(f"[Fix Collision] Processing {len(static_mesh_actors)} Static Mesh Actor(s)")
    
    # Track statistics
    total_actors = len(static_mesh_actors)
    actors_modified = 0
    total_boxes = 0
    total_boxes_fixed = 0
    meshes_processed = set()  # Track unique meshes to avoid processing the same mesh multiple times
    
    # Process each static mesh actor
    with unreal.ScopedEditorTransaction("Fix Collision Box Rotations"):
        for actor in static_mesh_actors:
            # Get the static mesh component
            static_mesh_comp = actor.static_mesh_component
            if not static_mesh_comp:
                unreal.log_warning(f"[Fix Collision] Actor {actor.get_actor_label()} has no static mesh component")
                continue
            
            # Get the static mesh asset
            static_mesh = static_mesh_comp.get_editor_property('static_mesh')
            if not static_mesh:
                unreal.log_warning(f"[Fix Collision] Actor {actor.get_actor_label()} has no static mesh assigned")
                continue
            
            # Get the mesh path to avoid processing duplicates
            mesh_path = static_mesh.get_path_name()
            if mesh_path in meshes_processed:
                unreal.log(f"[Fix Collision] Skipping {static_mesh.get_name()} (already processed)")
                continue
            
            meshes_processed.add(mesh_path)
            unreal.log(f"[Fix Collision] Processing actor: {actor.get_actor_label()}, mesh: {static_mesh.get_name()}")
            
            # Fix collision boxes for this mesh
            was_modified, box_count, boxes_fixed = fix_box_collision_rotations(static_mesh)
            
            if was_modified:
                actors_modified += 1
            
            total_boxes += box_count
            total_boxes_fixed += boxes_fixed
    
    # Show summary
    summary_msg = (
        f"Fix Collision Box Rotations Complete\n\n"
        f"Static Mesh Actors selected: {total_actors}\n"
        f"Unique meshes processed: {len(meshes_processed)}\n"
        f"Meshes modified: {actors_modified}\n"
        f"Total box collision primitives: {total_boxes}\n"
        f"Box primitives fixed: {total_boxes_fixed}"
    )
    
    unreal.log(f"[Fix Collision] Summary:\n{summary_msg}")
    unreal.EditorDialog.show_message(
        "Fix Collision Complete",
        summary_msg,
        unreal.AppMsgType.OK
    )


if __name__ == "__main__":
    import sys
    
    # Check if a mode argument was provided
    mode = "fix"  # Default mode
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    
    if mode == "check":
        check_selected_actors()
    else:
        process_selected_actors()
