import unreal

static_mesh_editor_subsystem = unreal.StaticMeshEditorSubsystem()

"""
apply lod on static mesh
"""
def apply_lods(static_mesh, reduction_settings: [unreal.StaticMeshReductionSettings]):
    # check if the mesh is complex enough.
    number_of_vertices = static_mesh_editor_subsystem.get_number_verts(static_mesh, 0)
    if number_of_vertices < 10:
        return
    print("[Python Tool LOD] treating asset: " + static_mesh.get_name())
    print("[Python Tool LOD] existing LOD count: " + str(static_mesh_editor_subsystem.get_lod_count(static_mesh)))
    # set up options for auto-generating the levels of detail.
    options = unreal.EditorScriptingMeshReductionOptions()
    # we request three new levels of detail. Each has:
    # - the percentage of the triangles from the fully detailed mesh that should be retained at this LOD level
    # - a screen space threshold at which this level of detail appears.
    # options.reduction_settings = [
    #     unreal.StaticMeshReductionSettings(1.0, 1.0),
    #     unreal.StaticMeshReductionSettings(0.8, 0.75),
    #     unreal.StaticMeshReductionSettings(0.6, 0.5),
    #     unreal.StaticMeshReductionSettings(0.4, 0.25)
    # ]
    options.reduction_settings = reduction_settings
    # use the screen space thresholds set above, rather than auto-computing them.
    options.auto_compute_lod_screen_size = False
    # set the options on the Static Mesh Asset.
    static_mesh_editor_subsystem.set_lods(static_mesh, options)
    # save the changes.
    print("[Python Tool LOD] new LOD count: " + str(static_mesh_editor_subsystem.get_lod_count(static_mesh)))
