import math
import os

import maya.cmds as cmds
import maya.api.OpenMaya as om


# ---------------------------------------------------------------------------
# Shared helpers
#
# Any change to a joint's world matrix while a mesh is bound will double
# transform that mesh, because the skinCluster caches each influence's inverse
# bind matrix (bindPreMatrix). So every operation below follows the same shape:
# export weights -> unbind -> move things -> rebind -> re-import weights.
# ---------------------------------------------------------------------------

def _find_root_bone(root_bone=None):
    """Return the root joint, auto-detecting it when not supplied."""
    if root_bone is not None:
        return root_bone

    all_joints = cmds.ls(type='joint')
    if not all_joints:
        print("No joints found in scene")
        return None

    root_joints = [j for j in all_joints
                   if not cmds.listRelatives(j, parent=True, type='joint')]

    if not root_joints:
        print("No root joint found")
        return None
    elif len(root_joints) > 1:
        print(f"Multiple root joints found: {root_joints}")
        print("Please specify which one to use")
        return None

    print(f"Found root bone: {root_joints[0]}")
    return root_joints[0]


def _get_hierarchy(root_bone):
    """Return (all descendant transforms, all joints including the root)."""
    all_children = cmds.listRelatives(root_bone, allDescendents=True, type='transform') or []
    all_joints = [root_bone] + [c for c in all_children if cmds.nodeType(c) == 'joint']
    return all_children, all_joints


def _euler_to_matrix(degrees_xyz):
    """XYZ-order euler in degrees -> MMatrix."""
    euler = om.MEulerRotation([math.radians(v) for v in degrees_xyz],
                              om.MEulerRotation.kXYZ)
    return euler.asMatrix()


def _matrix_to_euler(matrix):
    """MMatrix -> XYZ-order euler in degrees."""
    euler = om.MTransformationMatrix(matrix).rotation(asQuaternion=False)
    euler.reorderIt(om.MEulerRotation.kXYZ)
    return [math.degrees(v) for v in (euler.x, euler.y, euler.z)]


def _rotation_carriers(root_bone, pelvis_bone=None):
    """The joints that absorb the world rotation on the root's behalf.

    Default is *every* direct child of the root -- the pelvis (n_center) plus any
    sibling attach/weapon/IK joints. They all have to turn together; leaving one
    behind tears that branch off the rest of the rig.
    """
    children = cmds.listRelatives(root_bone, children=True, type='transform') or []
    joints = [c for c in children if cmds.nodeType(c) == 'joint']

    others = [c for c in children if cmds.nodeType(c) != 'joint']
    if others:
        print(f"WARNING: non-joint child(ren) of {root_bone} will NOT be rotated: {others}")

    if pelvis_bone is None:
        return joints

    if pelvis_bone not in joints:
        print(f"ERROR: {pelvis_bone} is not a direct child of {root_bone} "
              f"(direct joint children: {joints})")
        return []

    skipped = [j for j in joints if j != pelvis_bone]
    if skipped:
        print(f"WARNING: only {pelvis_bone} will be rotated -- these siblings stay "
              f"behind and will no longer line up with the rig: {skipped}")

    return [pelvis_bone]


def _local_rotation(node):
    """The node's own total local rotation (rotate * jointOrient) as an MMatrix."""
    rotate = cmds.getAttr(f"{node}.rotate")[0]

    if cmds.getAttr(f"{node}.rotateOrder") != 0 and any(abs(v) > 1e-6 for v in rotate):
        print(f"WARNING: {node} has a non-XYZ rotateOrder and a non-zero rotate -- "
              "the euler math here assumes XYZ")

    rot = _euler_to_matrix(rotate)
    if cmds.nodeType(node) == 'joint':
        rot = rot * _euler_to_matrix(cmds.getAttr(f"{node}.jointOrient")[0])

    return rot


def _blocked_attrs(node, channels):
    """Channels on `node` that setAttr can't write -- locked or driven."""
    blocked = []
    for channel in channels:
        for axis in 'XYZ':
            attr = f"{node}.{channel}{axis}"
            if (cmds.getAttr(attr, lock=True)
                    or cmds.listConnections(attr, source=True, destination=False)):
                blocked.append(attr)
    return blocked


def _world_matrix(node):
    return om.MMatrix(cmds.xform(node, query=True, worldSpace=True, matrix=True))


def _pose_str(matrix):
    xform = om.MTransformationMatrix(matrix)
    t = xform.translation(om.MSpace.kWorld)
    r = _matrix_to_euler(matrix)
    return (f"t=({t.x:.3f}, {t.y:.3f}, {t.z:.3f}) "
            f"r=({r[0]:.3f}, {r[1]:.3f}, {r[2]:.3f})")


def _is_identity(matrix):
    return matrix.isEquivalent(om.MMatrix(), 1e-9)


def _bbox_close(a, b, factor=1e-4):
    """Compare world bounding boxes with a tolerance scaled to the rig's size.

    factor=1e-4 asks "did this move at all" -- tight enough to catch a freeze that
    silently did nothing. Use a much looser factor when the question is "did this
    snap back 90 degrees": binding a mesh shifts its bounding box by a fraction of
    a unit all on its own (weight normalization, dual-quaternion blending), and
    calling that a failure is a false alarm.
    """
    span = max((abs(v) for v in list(a) + list(b)), default=1.0) or 1.0
    tol = max(1e-3, span * factor)
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _influence_centroid(cluster, fallback_influences=None):
    """Mean world position of the joints that actually carry weight in `cluster`."""
    joints = cmds.skinCluster(cluster, query=True, weightedInfluence=True) or []
    if not joints:
        joints = fallback_influences or []
    joints = [j for j in joints if cmds.objExists(j)]
    if not joints:
        return None

    total = om.MVector()
    for joint in joints:
        total += om.MTransformationMatrix(_world_matrix(joint)).translation(om.MSpace.kWorld)
    return total / float(len(joints))


def _misfit(skin_info, delta=None):
    """
    How far each mesh sits from the joints that drive it, in multiples of the mesh's
    own diagonal. Small means the geometry and the skeleton describe the same
    creature; large means one of them is somewhere the other isn't.

    `delta` rotates the joint positions about the world origin before comparing, so
    the same function answers "what would happen if only the skeleton turned?"
    without turning anything. Returns [(mesh, misfit), ...].

    Deliberately shape-independent: it compares positions, not which axis is
    longest, so a T-posed character (wider than tall) is not mistaken for one lying
    down. Needs the skin still bound -- call it before the unbind.
    """
    rows = []
    for info in skin_info:
        mesh = info['mesh']
        if not cmds.objExists(mesh) or not cmds.objExists(info['skin_cluster']):
            continue

        x0, y0, z0, x1, y1, z1 = cmds.exactWorldBoundingBox(mesh)
        center = om.MVector((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0)
        diagonal = om.MVector(x1 - x0, y1 - y0, z1 - z0).length() or 1.0

        centroid = _influence_centroid(info['skin_cluster'], info.get('influences'))
        if centroid is None:
            continue
        if delta is not None:
            centroid = centroid * delta

        rows.append((mesh, (center - centroid).length() / diagonal))

    return rows


def _worst_misfit(rows):
    return max((value for _, value in rows), default=0.0)


def _mesh_deformers(mesh):
    """Deformers still upstream of `mesh`.

    A history delete is the only reliable way to make makeIdentity() reach the
    shape a later rebind will read from -- but it would also destroy any of these,
    so their presence is a hard stop rather than something to work around.
    """
    history = cmds.listHistory(mesh, pruneDagObjects=True) or []
    deformers = ('skinCluster', 'blendShape', 'cluster', 'ffd', 'wire', 'wrap',
                 'nonLinear', 'sculpt', 'jiggle', 'deltaMush', 'softMod',
                 'textureDeformer', 'deformBend', 'deformTwist', 'deformFlare',
                 'deformSine', 'deformSquash', 'deformWave')
    return [n for n in history if cmds.nodeType(n) in deformers]


def _bake_mesh_rotation(mesh, rotation):
    """Rotate a mesh about the world origin and bake it into the vertices.

    Returns the post-bake world bounding box, or None if it could not be done
    safely. The freeze is the fragile part: applying it to a mesh that still has
    construction history rotates the shape you can see while leaving the upstream
    intermediate shape alone, and everything looks correct right up until a rebind
    reads that upstream shape and the mesh snaps back -- mesh lying down, skeleton
    standing up. So: clear the history first, then freeze, then check the geometry
    really did stay put.
    """
    parent = cmds.listRelatives(mesh, parent=True, fullPath=True)
    if parent:
        print(f"  WARNING: {mesh} is parented under {parent[0]} -- freezing only "
              "bakes the mesh's own transform, not the parent's")

    cmds.rotate(rotation[0], rotation[1], rotation[2], mesh,
                relative=True, worldSpace=True, pivot=(0, 0, 0))
    rotated = cmds.exactWorldBoundingBox(mesh)

    leftovers = _mesh_deformers(mesh)
    if leftovers:
        print(f"  ERROR: {mesh} still has deformer(s) upstream: {leftovers}")
        print("         Freezing would silently leave the shape they feed unrotated.")
        return None

    try:
        cmds.delete(mesh, constructionHistory=True)
    except Exception as e:
        print(f"  WARNING: could not clear history on {mesh}: {e}")

    try:
        cmds.makeIdentity(mesh, apply=True, translate=True, rotate=True,
                          scale=True, normal=False)
    except Exception as e:
        print(f"  ERROR: could not freeze {mesh}: {e}")
        return None

    frozen = cmds.exactWorldBoundingBox(mesh)
    if not _bbox_close(rotated, frozen):
        print(f"  ERROR: freezing moved {mesh} in world -- history was not fully baked")
        print(f"         rotated {tuple(round(v, 3) for v in rotated)}")
        print(f"         frozen  {tuple(round(v, 3) for v in frozen)}")
        return None

    residual = [cmds.getAttr(f"{mesh}.{c}{a}") for c in ('translate', 'rotate') for a in 'XYZ']
    if any(abs(v) > 1e-4 for v in residual):
        print(f"  WARNING: {mesh} still has a non-zero transform after freezing: "
              f"{tuple(round(v, 4) for v in residual)}")

    print(f"  Baked {mesh}")
    return frozen


def _collect_skin_info(all_joints):
    """Gather every skinCluster driven by these joints, plus its settings."""
    skin_info = []
    processed_clusters = set()

    for joint in all_joints:
        skin_clusters = cmds.listConnections(joint, type='skinCluster') or []
        for skin_cluster in skin_clusters:
            if skin_cluster in processed_clusters:
                continue

            processed_clusters.add(skin_cluster)

            geometry = cmds.skinCluster(skin_cluster, query=True, geometry=True)
            if not geometry:
                continue

            for geo in geometry:
                mesh_transform = cmds.listRelatives(geo, parent=True, type='transform')[0]

                skin_info.append({
                    'mesh': mesh_transform,
                    'skin_cluster': skin_cluster,
                    'influences': cmds.skinCluster(skin_cluster, query=True, influence=True),
                    'skin_method': cmds.getAttr(f"{skin_cluster}.skinningMethod"),
                    'normalize_weights': cmds.getAttr(f"{skin_cluster}.normalizeWeights"),
                    'max_influences': cmds.getAttr(f"{skin_cluster}.maxInfluences"),
                })

                print(f"Found skin cluster: {skin_cluster} on {mesh_transform}")

    return skin_info


def _export_weights(skin_info, temp_dir):
    """Dump each skinCluster's weights to XML. Returns {cluster: filename}."""
    print("\nExporting skin weights...")
    weight_files = {}

    for info in skin_info:
        skin_cluster = info['skin_cluster']
        weight_file_name = f"{skin_cluster}_weights.xml"

        cmds.deformerWeights(weight_file_name,
                             export=True,
                             deformer=skin_cluster,
                             path=temp_dir)

        weight_files[skin_cluster] = weight_file_name
        print(f"Exported weights for {skin_cluster}")

    return weight_files


def _unbind(skin_info):
    print("\nUnbinding skin clusters...")
    for info in skin_info:
        cmds.skinCluster(info['mesh'], edit=True, unbind=True)
        print(f"Unbound {info['mesh']}")


def _delete_bind_poses(all_joints):
    """Drop stale dagPose nodes so the rebind writes a clean bind pose."""
    poses = set()
    for joint in all_joints:
        poses.update(cmds.listConnections(joint, type='dagPose') or [])

    if poses:
        cmds.delete(list(poses))
        print(f"Deleted stale bind pose(s): {sorted(poses)}")


def _rebind(skin_info, weight_files, temp_dir):
    """Recreate each skinCluster with its original settings and weights."""
    print("\nRebinding skin clusters...")

    for info in skin_info:
        mesh = info['mesh']
        old_skin_cluster = info['skin_cluster']

        new_skin = cmds.skinCluster(info['influences'], mesh,
                                    toSelectedBones=True,
                                    skinMethod=info['skin_method'],
                                    normalizeWeights=info['normalize_weights'],
                                    maximumInfluences=info['max_influences'],
                                    name=old_skin_cluster)[0]

        # Maya appends a suffix if the old name is somehow still taken, so record what
        # it actually made -- anything checking the result afterwards queries this.
        info['skin_cluster'] = new_skin
        print(f"Created new skin cluster {new_skin} on {mesh}")

        try:
            cmds.deformerWeights(weight_files[old_skin_cluster],
                                 im=True,
                                 deformer=new_skin,
                                 path=temp_dir)
            print(f"Imported weights for {mesh}")
        except Exception as e:
            print(f"Error importing weights for {mesh}: {e}")


def _cleanup_weight_files(weight_files, temp_dir):
    print("\nCleaning up temp files...")
    for weight_file in weight_files.values():
        try:
            full_path = os.path.join(temp_dir, weight_file)
            if os.path.exists(full_path):
                os.remove(full_path)
                print(f"Deleted {full_path}")
        except Exception as e:
            print(f"Could not delete temp file: {e}")


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def normalize_root_freeze_100(root_bone=None, target_scale=1.0):
    """
    Normalize root bone scale: unbind, set mesh to scale 100, freeze, rebind with weights

    Args:
        root_bone (str): Name of the root bone
        target_scale (float): Target scale value (default: 1.0)
    """
    root_bone = _find_root_bone(root_bone)
    if root_bone is None:
        return

    current_scale = cmds.getAttr(f"{root_bone}.scaleX")
    print(f"Current root bone scale: {current_scale}")

    scale_factor = current_scale / target_scale

    all_children, all_joints = _get_hierarchy(root_bone)
    skin_info = _collect_skin_info(all_joints)
    temp_dir = cmds.internalVar(userTmpDir=True)

    weight_files = _export_weights(skin_info, temp_dir)
    _unbind(skin_info)

    # After unbinding, mesh scales will be at 10000 (100 * 100)
    # Set them to 100 instead
    print("\nSetting mesh scales to 100...")
    for info in skin_info:
        mesh = info['mesh']

        current_mesh_scale = cmds.getAttr(f"{mesh}.scaleX")
        print(f"Mesh {mesh} current scale: {current_mesh_scale}")

        for axis in 'XYZ':
            cmds.setAttr(f"{mesh}.scale{axis}", 100)

        print(f"Set {mesh} scale to 100")

    # Freeze transforms on meshes (bake scale 100 into vertices, scale becomes 1).
    # History has to go first: freezing a mesh that still has an intermediate shape
    # bakes the visible one and leaves the shape the rebind reads from alone, which
    # shows up only later as a mesh sitting at the wrong scale under a correct rig.
    print("\nFreezing transforms on meshes...")
    for info in skin_info:
        mesh = info['mesh']
        before = cmds.exactWorldBoundingBox(mesh)

        try:
            cmds.delete(mesh, constructionHistory=True)
        except Exception as e:
            print(f"WARNING: could not clear history on {mesh}: {e}")

        try:
            cmds.makeIdentity(mesh, apply=True, translate=True, rotate=True, scale=True, normal=False)
            print(f"Froze transforms on {mesh}")
        except Exception as e:
            print(f"Error freezing {mesh}: {e}")

        if not _bbox_close(before, cmds.exactWorldBoundingBox(mesh)):
            print(f"WARNING: freezing moved {mesh} in world -- history was not fully baked")

    # Adjust skeleton
    print("\nAdjusting skeleton...")
    for axis in 'XYZ':
        cmds.setAttr(f"{root_bone}.scale{axis}", target_scale)

    joints_scaled = 0
    for child in all_children:
        if cmds.nodeType(child) != 'joint':
            continue

        for axis in 'XYZ':
            t = cmds.getAttr(f"{child}.translate{axis}")
            cmds.setAttr(f"{child}.translate{axis}", t * scale_factor)

        try:
            radius = cmds.getAttr(f"{child}.radius")
            cmds.setAttr(f"{child}.radius", radius * scale_factor)
        except:
            pass

        joints_scaled += 1

    print(f"Scaled {joints_scaled} child joints")

    _delete_bind_poses(all_joints)
    _rebind(skin_info, weight_files, temp_dir)
    _cleanup_weight_files(weight_files, temp_dir)

    print(f"\n=== Summary ===")
    print(f"- Normalized root bone to scale {target_scale}")
    print(f"- Scaled {joints_scaled} child joints")
    print(f"- Froze {len(skin_info)} mesh(es) at scale 100")
    print(f"- Rebound {len(skin_info)} mesh(es) with original weights")
    print("Done! Meshes now at scale 1, skeleton at scale 1, weights preserved!")


def strip_top_node(top_node="skeleton", skin_info=None):
    """
    Collapse the wrapper joint above the real root -- the "skeleton"/armature node a
    DAE or FBX import leaves on top -- and delete it, promoting n_root to root.

    The wrapper has to go before the rotation normalize, not after. While it exists
    it *is* the root as far as _find_root_bone is concerned, so the rotation gets
    handed from the wrapper to n_root instead of from n_root to n_center, and the
    thing left "identity" is a node that was about to be deleted anyway.

    Nothing moves in world: the wrapper's own rotation and translation are folded
    into each child's jointOrient and translate first (L_new = L_old * W, i.e.
    JO * W_rot and t * W_rot + W_trans), so the promoted joints keep their exact
    world matrices. Call this while the skin is UNBOUND -- the world matrices are
    preserved, but the wrapper disappearing from the influence list is not
    something a live skinCluster survives.

    Args:
        top_node (str): Wrapper transform to collapse. Ignored when absent.
        skin_info (list): Optional _collect_skin_info() result; the wrapper is
            removed from each entry's influence list so a later rebind doesn't ask
            for a node that no longer exists.

    Returns:
        list: the joints promoted to root (normally just ["n_root"]), or [] if
        nothing was done.
    """
    if not top_node or not cmds.objExists(top_node):
        print(f"No {top_node!r} wrapper node to strip")
        return []

    world = _world_matrix(top_node)
    xform = om.MTransformationMatrix(world)

    scale = xform.scale(om.MSpace.kWorld)
    if any(abs(v - 1.0) > 1e-6 for v in scale):
        print(f"ERROR: {top_node} has a non-unit scale {tuple(round(v, 6) for v in scale)}.")
        print("       Scale can't be folded into a jointOrient -- it has to be pushed")
        print("       into every descendant's translate, and the meshes have to be")
        print("       frozen to match. That is what normalize_root_freeze_100() does.")
        print("       Run that first, then come back.")
        return []

    blocked = _blocked_attrs(top_node, ('translate', 'rotate', 'scale'))
    if cmds.nodeType(top_node) == 'joint':
        blocked += _blocked_attrs(top_node, ('jointOrient',))
    if blocked:
        print(f"ERROR: {top_node} is driven on {blocked} -- it is animated or "
              "constrained, so it is not just a static wrapper. Aborting.")
        return []

    children = cmds.listRelatives(top_node, children=True, type='transform') or []
    joints = [c for c in children if cmds.nodeType(c) == 'joint']
    others = [c for c in children if cmds.nodeType(c) != 'joint']

    if not joints:
        print(f"ERROR: {top_node} has no joint children -- nothing to promote")
        return []
    if others:
        print(f"WARNING: non-joint child(ren) of {top_node} will be left where they "
              f"are and lose the wrapper's transform: {others}")

    for joint in joints:
        blocked = _blocked_attrs(joint, ('jointOrient', 'translate'))
        if blocked:
            print(f"ERROR: cannot rewrite {blocked} -- aborting before anything moves")
            return []

    rot = om.MTransformationMatrix()
    rot.setRotation(xform.rotation(asQuaternion=True))
    rot = rot.asMatrix()
    offset = xform.translation(om.MSpace.kWorld)

    print(f"\nCollapsing {top_node}: {_pose_str(world)}")

    promoted = []
    for joint in joints:
        before = _world_matrix(joint)

        jo_old = cmds.getAttr(f"{joint}.jointOrient")[0]
        jo_new = _matrix_to_euler(_euler_to_matrix(jo_old) * rot)
        for axis, value in zip('XYZ', jo_new):
            cmds.setAttr(f"{joint}.jointOrient{axis}", value)

        t_old = [cmds.getAttr(f"{joint}.translate{axis}") for axis in 'XYZ']
        vec = om.MVector(*t_old) * rot + offset
        for axis, value in zip('XYZ', (vec.x, vec.y, vec.z)):
            cmds.setAttr(f"{joint}.translate{axis}", value)

        # relative=True keeps the local values we just wrote instead of letting Maya
        # compute its own compensation on top of them.
        cmds.parent(joint, world=True, relative=True)

        # Maya still likes to fold its own compensation into jointOrient during the
        # reparent, so put ours back and then check the world matrix actually held.
        for axis, value in zip('XYZ', jo_new):
            cmds.setAttr(f"{joint}.jointOrient{axis}", value)
        for axis, value in zip('XYZ', (vec.x, vec.y, vec.z)):
            cmds.setAttr(f"{joint}.translate{axis}", value)

        after = _world_matrix(joint)
        if not after.isEquivalent(before, 1e-3):
            print(f"WARNING: {joint} moved while being promoted")
            print(f"         before {_pose_str(before)}")
            print(f"         after  {_pose_str(after)}")
        else:
            print(f"  {joint} promoted to root, world matrix preserved")

        promoted.append(joint)

    if skin_info:
        for info in skin_info:
            influences = info.get('influences') or []
            if top_node in influences:
                info['influences'] = [i for i in influences if i != top_node]
                print(f"  Dropped {top_node} from {info['skin_cluster']}'s influences")

    cmds.delete(top_node)
    print(f"Deleted {top_node}")

    return promoted


def normalize_root_rotate(root_bone=None, rotation=(90.0, 0.0, 0.0), pelvis_bone=None,
                          top_node="skeleton", rotate_meshes=None):
    """
    Bake a world-space rotation into the rig so the rest pose is Z-up, while
    leaving the root joint perfectly clean: rotate AND jointOrient both read 0.

    The rotation has to live somewhere. Freezing it into the root -- the obvious
    move -- gives you rotateX 0 / jointOrientX 90, so the root exports with a 90
    pre-rotation. Engines that want a world-aligned root (UE) want that channel
    empty, so the root's direct children absorb it instead: the pelvis (n_center)
    plus any siblings.

    A joint's local matrix is R * JO * T in Maya's row-vector order, so applying a
    rotation M in the parent's frame is just

        L_new = L_old * M   <=>   JO_new = JO_old * M,  t_new = t_old * M

    with the rotate channel untouched. Post-multiplying applies M in the parent's
    (root's) frame, which is exactly where the old whole-rig rotation put each
    child, and everything below them rides along for free. Their rotate channels
    stay valid because rotate is applied *inside* jointOrient, in the joint's own
    frame, which didn't move relative to the root.

    M is R * D, not just D: since the root is emptied afterwards, whatever
    orientation it already carried has to be transferred as well. On a clean rig
    R is identity and M is exactly the requested rotation.

    No reweighting happens: skin weights are per-vertex scalars and a rigid
    rotation of mesh + skeleton together leaves every value identical. The
    unbind/rebind exists only to refresh the cached bind matrices.

    Whether the *geometry* has to turn as well is measured, not assumed, because
    both cases are real and they need opposite treatment:

      - A genuinely Y-up asset has its mesh and its bones agreeing with each other
        and both lying down. Turning the skeleton alone would tear them apart, so
        the vertices get baked too.
      - A rig whose bones lie down inside standing geometry (an import that turned
        the mesh transforms and left the joints raw, or an earlier pass that zeroed
        a root rotation without handing it down) is asking for a repair. Here the
        vertices are already right and touching them is what breaks the rig.

    _misfit() tells the two apart by measuring how far each mesh sits from the
    joints that drive it, once as-is and once with the joints rotated, and the
    smaller answer wins. rotate_meshes overrides that if you disagree.

    The root itself keeps nothing but its (rotated) translate: rotate and
    jointOrient are both zeroed, and at rest the translate is already 0.

    The wrapper joint an import leaves on top ("skeleton" / an armature node) is
    collapsed first, so the rotation is handed from the real root to the pelvis
    rather than from the wrapper to the real root. It has to be gone before the
    transfer, and it has to go while the skin is unbound -- see strip_top_node.

    Args:
        root_bone (str): Name of the root bone, e.g. "n_root". Auto-detected after
            the wrapper is stripped.
        rotation (tuple): World-space XYZ degrees. Default (90, 0, 0) = Y-up -> Z-up.
            Pass (0, 0, 0) if the rig already stands up correctly and only needs its
            root emptied.
        pelvis_bone (str): Single child to carry the rotation, e.g. "n_center".
            None (default) rotates every direct child of the root, which is what
            you want unless the root has siblings you deliberately want left out.
        top_node (str): Wrapper joint above the real root. Ignored when absent;
            None to skip the strip entirely.
        rotate_meshes (bool): Whether to bake `rotation` into the vertices as well.
            None (default) measures which way round it is -- see above. True for a
            whole-asset turn, False to rotate the skeleton alone and leave the
            geometry exactly where it is.
    """
    # The wrapper is still in the scene at this point, so _find_root_bone would pick
    # *it* rather than the real root. Work out what the root will be after the strip
    # and pre-flight that instead -- everything below wants the real root.
    stripping = bool(top_node) and cmds.objExists(top_node)
    if stripping and root_bone is None:
        below = [c for c in cmds.listRelatives(top_node, children=True, type='transform') or []
                 if cmds.nodeType(c) == 'joint']
        if len(below) != 1:
            print(f"ERROR: expected exactly one joint under {top_node}, found {below}")
            print("       Name the root explicitly: normalize_root_rotate(root_bone=...)")
            return
        root_bone = below[0]
        print(f"{top_node} wrapper found -- {root_bone} will be the root")

    root_bone = _find_root_bone(root_bone)
    if root_bone is None:
        return

    # Hierarchy is gathered from the wrapper down so its skinClusters are found too.
    hierarchy_top = top_node if stripping else root_bone
    _, all_joints = _get_hierarchy(hierarchy_top)

    carriers = _rotation_carriers(root_bone, pelvis_bone)
    if not carriers:
        print(f"ERROR: no joint under {root_bone} to carry the rotation -- aborting")
        return

    print(f"Rotation will be carried by: {carriers}")

    # Bail before unbinding rather than half way through it.
    blocked = _blocked_attrs(root_bone, ('rotate', 'jointOrient', 'translate'))
    for carrier in carriers:
        blocked += _blocked_attrs(carrier, ('jointOrient', 'translate'))
    if blocked:
        print(f"ERROR: these channels are locked or driven and cannot be rewritten: "
              f"{blocked}")
        print("       Aborting before the skin is touched.")
        return

    if stripping:
        scale = om.MTransformationMatrix(_world_matrix(top_node)).scale(om.MSpace.kWorld)
        if any(abs(v - 1.0) > 1e-6 for v in scale):
            print(f"ERROR: {top_node} has a non-unit scale "
                  f"{tuple(round(v, 6) for v in scale)}.")
            print("       Run normalize_root_freeze_100() first -- it normalizes the")
            print("       scale and freezes the meshes to match. Then run this.")
            print("       Or call normalize_skm(), which does both in order.")
            return

    skin_info = _collect_skin_info(all_joints)

    # A mesh with a live blendShape (or any other deformer) can't be frozen safely:
    # the freeze would rotate the visible shape and leave the deformer's input alone,
    # and the mismatch only shows up after the rebind -- mesh flat on the floor,
    # skeleton standing. Refuse now, while the scene is still untouched.
    stuck = {}
    for info in skin_info:
        extra = [n for n in _mesh_deformers(info['mesh'])
                 if n != info['skin_cluster']]
        if extra:
            stuck[info['mesh']] = extra
    if stuck:
        print("ERROR: these meshes have deformers besides their skinCluster:")
        for mesh, extra in stuck.items():
            print(f"       {mesh}: {extra}")
        print("       Freezing them would break those deformers. Aborting.")
        return

    if not skin_info:
        print("WARNING: no skinClusters found on this hierarchy -- the skeleton will")
        print("         be rotated but no mesh will follow. If the meshes ARE bound,")
        print("         they are bound to joints outside this hierarchy.")

    if stripping and any(top_node in (cmds.skinCluster(info['skin_cluster'],
                                                      query=True,
                                                      weightedInfluence=True) or [])
                         for info in skin_info):
        print(f"ERROR: {top_node} carries actual skin weight, so deleting it would")
        print("       lose that weight. Transfer it to the root first.")
        return

    if any(root_bone in (info['influences'] or []) for info in skin_info):
        print(f"NOTE: {root_bone} is a skin influence. It ends up identity while the "
              "mesh rotates, so any weight actually painted on it will be off by the "
              "delta -- normally it holds none.")

    # Does the geometry need turning too, or only the skeleton? Measure it while the
    # skin is still bound: compare where each mesh sits against where its own joints
    # are, once as they stand (which is also the answer for turning both together,
    # since a rigid rotation of both preserves the relationship) and once with the
    # joints rotated by the delta. Whichever ends up better aligned is the truth.
    delta = _euler_to_matrix(rotation)
    misfit_before = _misfit(skin_info)

    if _is_identity(delta):
        if rotate_meshes:
            print("NOTE: rotate_meshes ignored -- no rotation was asked for")
        rotate_meshes = False
    elif not skin_info:
        if rotate_meshes is None:
            rotate_meshes = False
            print("No skin to measure against -- rotating the skeleton only. Pass "
                  "rotate_meshes=True if the geometry has to turn as well.")
    else:
        err_together = _worst_misfit(misfit_before)
        misfit_joints_only = _misfit(skin_info, delta)
        err_joints_only = _worst_misfit(misfit_joints_only)
        measured = err_together < err_joints_only

        print("\nMesh vs rig, worst mesh (distance from the joints that drive it, in "
              "multiples of its own size):")
        print(f"  turn mesh and skeleton together : {err_together:.2f}"
              f"{'   <-- better' if measured else ''}")
        print(f"  turn the skeleton only          : {err_joints_only:.2f}"
              f"{'   <-- better' if not measured else ''}")

        if rotate_meshes is None:
            rotate_meshes = measured
            if rotate_meshes:
                print("  => mesh and bones agree today, so both get turned "
                      "(a genuinely Y-up asset)")
                print(f"     NOTE: that means the whole character turns by {rotation} "
                      "in world. If it")
                print("     already stands up the way you want, you wanted "
                      "rotation=(0, 0, 0) --")
                print("     that empties the root without moving anything.")
            else:
                print("  => the bones are the only thing out of place, so the geometry "
                      "is left alone")
                print("     (turning it too is what puts the mesh on the floor under a "
                      "standing rig)")
        elif rotate_meshes != measured:
            print(f"  => overridden: rotate_meshes={rotate_meshes} was asked for, but "
                  "the measurement disagrees")

        chosen = err_together if rotate_meshes else err_joints_only
        if chosen > 1.0:
            print(f"\nWARNING: even the better option leaves a misfit of {chosen:.2f} "
                  "mesh-widths.")
            print("         Neither turning the geometry nor leaving it makes the mesh "
                  "and the")
            print(f"         bones line up, so {rotation} is probably not the rotation "
                  "this rig needs.")
            print("         Run diagnose_meshes() and check the rotation before "
                  "continuing.")

    temp_dir = cmds.internalVar(userTmpDir=True)

    weight_files = _export_weights(skin_info, temp_dir)
    _unbind(skin_info)

    # Collapse the wrapper now that nothing is bound. World matrices are preserved,
    # so this is invisible -- but it moves the wrapper's orientation down into the
    # root, which is why root_rot is measured afterwards and not before.
    if stripping:
        promoted = strip_top_node(top_node, skin_info)
        if not promoted:
            print("\nERROR: the strip failed and the skin is already unbound.")
            print("       Undo (Ctrl+Z) and fix what it reported before retrying.")
            return
        all_joints = [j for j in all_joints if j != top_node]

    # Whatever orientation the root carries -- its own, plus whatever the wrapper
    # just handed it -- has to be transferred as well, since the root gets emptied.
    root_rot = _local_rotation(root_bone)
    if not _is_identity(root_rot):
        print(f"\nNOTE: {root_bone} carries "
              f"{tuple(round(v, 4) for v in _matrix_to_euler(root_rot))}; that gets "
              "transferred to the carriers too, so the root still ends up identity")

    # Snapshot the world so the result can be checked instead of assumed.
    joints_before = {j: _world_matrix(j) for j in all_joints if cmds.objExists(j)}
    mesh_boxes = {info['mesh']: cmds.exactWorldBoundingBox(info['mesh'])
                  for info in skin_info if cmds.objExists(info['mesh'])}

    # Rotate the meshes about the world origin and bake it into the vertices -- but
    # only when the measurement above says the geometry is out of place too. Every
    # box in mesh_boxes is where that mesh is meant to be from here on, rotated or
    # not, and the rebind is checked against it.
    if rotate_meshes:
        print(f"\nRotating meshes by {rotation} about the world origin...")
        for info in skin_info:
            box = _bake_mesh_rotation(info['mesh'], rotation)
            if box is None:
                print("\nERROR: a mesh could not be baked and the skin is already unbound.")
                print("       Undo (Ctrl+Z) -- rebinding now would bind a half-rotated rig.")
                return
            mesh_boxes[info['mesh']] = box
    elif _is_identity(delta):
        print("\nNo world rotation requested -- meshes left completely alone")
    else:
        print("\nGeometry left alone -- only the skeleton is moving to meet it")

    # Same rotation on the skeleton, one level down. Descendants of a carrier ride
    # along for free -- their local matrices are relative to the carrier, which is
    # the thing that just turned.
    print("\nRotating skeleton (root left identity)...")

    # The root is going to be left identity, so the carriers absorb the requested
    # delta *and* whatever the root was already carrying: R * D, not just D.
    carrier_delta = root_rot * delta

    fmt = lambda v: tuple(round(x, 4) for x in v)

    # The root's translate lives in parent (world) space, outside its own rotation,
    # so it has to follow the world rotation by hand. Normally it's 0 at rest.
    t_root = [cmds.getAttr(f"{root_bone}.translate{axis}") for axis in 'XYZ']
    if any(abs(v) > 1e-6 for v in t_root):
        vec = om.MVector(*t_root) * delta
        for axis, value in zip('XYZ', (vec.x, vec.y, vec.z)):
            cmds.setAttr(f"{root_bone}.translate{axis}", value)
        print(f"  {root_bone}.translate {fmt(t_root)} -> {fmt((vec.x, vec.y, vec.z))}")

    for carrier in carriers:
        jo_old = cmds.getAttr(f"{carrier}.jointOrient")[0]
        jo_new = _matrix_to_euler(_euler_to_matrix(jo_old) * carrier_delta)
        for axis, value in zip('XYZ', jo_new):
            cmds.setAttr(f"{carrier}.jointOrient{axis}", value)

        t_old = [cmds.getAttr(f"{carrier}.translate{axis}") for axis in 'XYZ']
        vec = om.MVector(*t_old) * carrier_delta
        for axis, value in zip('XYZ', (vec.x, vec.y, vec.z)):
            cmds.setAttr(f"{carrier}.translate{axis}", value)

        print(f"  {carrier}.jointOrient {fmt(jo_old)} -> {fmt(jo_new)}")
        print(f"  {carrier}.translate   {fmt(t_old)} -> {fmt((vec.x, vec.y, vec.z))}")

    # The root gives up its orientation entirely -- the carriers took it above.
    for channel in ('rotate', 'jointOrient'):
        for axis in 'XYZ':
            cmds.setAttr(f"{root_bone}.{channel}{axis}", 0.0)

    print(f"  {root_bone}.rotate      = {fmt(cmds.getAttr(f'{root_bone}.rotate')[0])}")
    print(f"  {root_bone}.jointOrient = {fmt(cmds.getAttr(f'{root_bone}.jointOrient')[0])}")

    # Every joint should now sit at old_world * D. Whether that lands on the meshes
    # depends on the decision above; this check is only that the transfer arithmetic
    # did what it claimed, which is worth knowing before the rebind rather than from
    # the viewport afterwards.
    print("\nChecking the skeleton landed where it was told to...")

    # Only the root plus the carrier branches are supposed to move. When pelvis_bone
    # pins a single carrier the other branches deliberately stay behind (already
    # warned about above), and their world matrices legitimately end up elsewhere --
    # checking them here would turn a documented choice into an abort.
    expected_to_move = {root_bone}
    for carrier in carriers:
        expected_to_move.add(carrier)
        expected_to_move.update(
            cmds.listRelatives(carrier, allDescendents=True, type='transform') or [])

    left_behind = [j for j in joints_before if j not in expected_to_move]
    if left_behind:
        print(f"  {len(left_behind)} joint(s) outside the carrier branches, not checked")

    drifted = []
    for joint, before in joints_before.items():
        if not cmds.objExists(joint) or joint not in expected_to_move:
            continue
        if joint == root_bone:
            # The root is the one joint that deliberately does NOT end at old * D:
            # it gives up its rotation to the carriers. Only its position has to
            # follow, so compare that alone.
            want = om.MTransformationMatrix(before * delta).translation(om.MSpace.kWorld)
            got = om.MTransformationMatrix(_world_matrix(joint)).translation(om.MSpace.kWorld)
            if not got.isEquivalent(want, 1e-2):
                drifted.append(joint)
            continue
        if not _world_matrix(joint).isEquivalent(before * delta, 1e-2):
            drifted.append(joint)

    if drifted:
        print(f"ERROR: {len(drifted)} joint(s) did not land at old_world * {rotation}:")
        for joint in drifted[:8]:
            print(f"       {joint}")
            print(f"         expected {_pose_str(joints_before[joint] * delta)}")
            print(f"         actual   {_pose_str(_world_matrix(joint))}")
        if len(drifted) > 8:
            print(f"       ... and {len(drifted) - 8} more")
        print("       Skin left unbound on purpose -- undo (Ctrl+Z) rather than rebind.")
        return

    print(f"  {len(expected_to_move)} joint(s) landed at old_world * {rotation}")

    _delete_bind_poses(all_joints)
    _rebind(skin_info, weight_files, temp_dir)
    _cleanup_weight_files(weight_files, temp_dir)

    # The rebind is where a badly frozen mesh shows itself: the new skinCluster reads
    # the shape upstream of the freeze, so the mesh snaps back to its old orientation
    # while the joints stay rotated. The tolerance is deliberately loose -- binding
    # nudges a bounding box by a fraction of a unit no matter what, and the thing
    # being looked for here is a quarter turn.
    reverted = [mesh for mesh, box in mesh_boxes.items()
                if cmds.objExists(mesh)
                and not _bbox_close(box, cmds.exactWorldBoundingBox(mesh), factor=0.01)]
    if reverted:
        print("\nERROR: these meshes moved during the rebind:")
        for mesh in reverted:
            print(f"       {mesh}")
            print(f"         expected {tuple(round(v, 3) for v in mesh_boxes[mesh])}")
            print(f"         actual   {tuple(round(v, 3) for v in cmds.exactWorldBoundingBox(mesh))}")
        if rotate_meshes:
            print("       The rotation did not reach the shape the skinCluster reads")
            print("       from, so the mesh is back where it started while the rig is")
            print("       rotated. Undo (Ctrl+Z) and check that mesh's history.")
        else:
            print("       The geometry was not touched, so the rebind itself moved it --")
            print("       the imported weights are landing on the wrong influences.")
            print("       Undo (Ctrl+Z).")
        return

    # And finally the question the whole thing exists to answer: is the mesh now
    # wrapped around its own bones? Same measure as the pre-flight, so the two
    # numbers are directly comparable.
    misfit_after = _misfit(skin_info)
    if misfit_after:
        worst_mesh, worst = max(misfit_after, key=lambda row: row[1])
        was = dict(misfit_before).get(worst_mesh, worst)
        print(f"\nMesh vs rig afterwards: worst is {worst_mesh} at {worst:.2f} "
              f"(was {was:.2f})")
        if worst > 1.0:
            print("WARNING: the mesh still does not sit on its own joints. The rig is")
            print("         internally consistent but it is not the shape you wanted --")
            print("         undo and try a different rotation.")

    print(f"\n=== Summary ===")
    if stripping:
        print(f"- Collapsed the {top_node} wrapper; {root_bone} is now the root")
    if rotate_meshes:
        print(f"- Baked {rotation} into {len(mesh_boxes)} mesh(es)")
    elif _is_identity(delta):
        print("- No mesh geometry touched (no world rotation requested)")
    else:
        print("- No mesh geometry touched (it was already in the right place)")
    print(f"- Transferred {fmt(_matrix_to_euler(carrier_delta))} to {carriers} "
          "(jointOrient * M, translate * M)")
    print(f"- {root_bone} left identity: rotate 0 and jointOrient 0")
    print(f"- Verified {len(expected_to_move)} joint(s) against the mesh rotation")
    print(f"- Rebound {len(skin_info)} mesh(es) with original weights")
    print("Done! Rig is Z-up with a clean root, weights untouched.")


def inspect_rig(top_node="skeleton"):
    """
    Print what the scene actually looks like, changing nothing.

    Worth running first on any new import: it shows which node the scripts would
    treat as the root, where the scale and the up-axis rotation are sitting, and
    whether the meshes carry deformers or history that will not survive a freeze --
    i.e. all the things that decide whether the run below will work.
    """
    print("=" * 64)
    print("RIG INSPECTION")
    print("=" * 64)

    print(f"\nScene up axis: {cmds.upAxis(query=True, axis=True)}")

    auto = _find_root_bone()
    print(f"_find_root_bone() would pick: {auto}")

    top = top_node if (top_node and cmds.objExists(top_node)) else None
    if top:
        print(f"Wrapper {top!r} is present"
              f"{' and IS what gets picked as the root' if auto == top else ''}")
    else:
        print(f"No {top_node!r} wrapper in the scene")

    print("\n--- Top of the hierarchy ---")
    node = top or auto
    depth = 0
    while node and depth < 4:
        kind = cmds.nodeType(node)
        t = tuple(round(v, 4) for v in cmds.getAttr(f"{node}.translate")[0])
        r = tuple(round(v, 4) for v in cmds.getAttr(f"{node}.rotate")[0])
        s = tuple(round(v, 6) for v in cmds.getAttr(f"{node}.scale")[0])
        print(f"{'  ' * depth}{node}  ({kind})")
        print(f"{'  ' * depth}    translate {t}")
        print(f"{'  ' * depth}    rotate    {r}")
        print(f"{'  ' * depth}    scale     {s}")
        if kind == 'joint':
            jo = tuple(round(v, 4) for v in cmds.getAttr(f"{node}.jointOrient")[0])
            print(f"{'  ' * depth}    jointOrient {jo}   <-- imports hide the up-axis "
                  "turn here; it is not in the channel box")
        print(f"{'  ' * depth}    world     {_pose_str(_world_matrix(node))}")

        children = [c for c in cmds.listRelatives(node, children=True, type='transform') or []
                    if cmds.nodeType(c) == 'joint']
        node = children[0] if len(children) == 1 else None
        if len(children) > 1:
            print(f"{'  ' * (depth + 1)}({len(children)} joint children -- branch point)")
        depth += 1

    print("\n--- Meshes ---")
    _, all_joints = _get_hierarchy(top or auto) if (top or auto) else ([], [])
    skin_info = _collect_skin_info(all_joints) if all_joints else []

    if not skin_info:
        print("No skinClusters found on this hierarchy")

    for info in skin_info:
        mesh = info['mesh']
        s = tuple(round(v, 6) for v in cmds.getAttr(f"{mesh}.scale")[0])
        extra = [n for n in _mesh_deformers(mesh) if n != info['skin_cluster']]
        weighted = cmds.skinCluster(info['skin_cluster'], query=True,
                                    weightedInfluence=True) or []
        print(f"\n{mesh}")
        print(f"    scale            {s}")
        print(f"    skinCluster      {info['skin_cluster']}")
        print(f"    influences       {len(info['influences'] or [])} "
              f"({len(weighted)} actually weighted)")
        if top and top in weighted:
            print(f"    !! {top} carries real weight -- it cannot just be deleted")
        if extra:
            print(f"    !! extra deformers: {extra} -- a freeze would break these")

    print("\n" + "=" * 64)


def diagnose_meshes(root_bone=None):
    """
    Report why the mesh is not sitting where the skeleton is. Changes nothing.

    Run this on the broken scene, right after a run that left the mesh behind. Two
    completely different causes look identical in the viewport:

      - the geometry itself was never rotated, because the freeze did not reach the
        shape the skinCluster reads from (an intermediate/orig shape survived), or
      - the geometry is correct and the skinning is what puts it back.

    The giveaway is the per-shape bounding box in LOCAL space. A standing character
    is tallest in Z; one lying down is tallest in Y. If a transform lists two shapes
    whose tall axis disagrees, the intermediate shape is the problem. If the visible
    shape is tall in Y, the rotation never reached the geometry at all.
    """
    print("=" * 64)
    print("MESH vs RIG")
    print("=" * 64)

    def extents(shape):
        try:
            (x0, x1), (y0, y1), (z0, z1) = cmds.polyEvaluate(shape, boundingBox=True)
        except Exception as e:
            return None, f"(could not evaluate: {e})"
        e = (x1 - x0, y1 - y0, z1 - z0)
        tall = 'XYZ'[e.index(max(e))]
        return tall, f"({e[0]:.2f}, {e[1]:.2f}, {e[2]:.2f}) tallest in {tall}"

    transforms = []
    for shape in cmds.ls(type='mesh') or []:
        parent = cmds.listRelatives(shape, parent=True, type='transform') or []
        if parent and parent[0] not in transforms:
            transforms.append(parent[0])

    if not transforms:
        print("No meshes in the scene")

    for mesh in transforms:
        visible = cmds.listRelatives(mesh, shapes=True, noIntermediate=True) or []
        every = cmds.listRelatives(mesh, shapes=True) or []
        intermediate = [s for s in every if s not in visible]

        t = tuple(round(v, 4) for v in cmds.getAttr(f"{mesh}.translate")[0])
        r = tuple(round(v, 4) for v in cmds.getAttr(f"{mesh}.rotate")[0])
        s = tuple(round(v, 4) for v in cmds.getAttr(f"{mesh}.scale")[0])

        print(f"\n{mesh}")
        print(f"    transform     t={t} r={r} s={s}")

        clusters = []
        for shape in every:
            clusters += cmds.listConnections(shape, type='skinCluster') or []
        print(f"    skinCluster   {sorted(set(clusters)) or 'NONE -- this mesh is not bound'}")

        for shape in visible:
            _, text = extents(shape)
            print(f"    visible shape {shape}: {text}")
        for shape in intermediate:
            _, text = extents(shape)
            print(f"    !! INTERMEDIATE {shape}: {text}")

        if intermediate:
            tall_visible = {extents(sh)[0] for sh in visible}
            tall_hidden = {extents(sh)[0] for sh in intermediate}
            if tall_visible != tall_hidden:
                print("    !! the intermediate shape disagrees with the visible one --")
                print("       the freeze did not reach the shape the skinCluster reads")

        instances = cmds.listRelatives(visible[0], allParents=True) if visible else []
        if instances and len(instances) > 1:
            print(f"    !! shape is instanced under {instances} -- freezing it once "
                  "moves every copy")

    print("\n--- Rig ---")
    root = _find_root_bone(root_bone)
    if root:
        print(f"{root}: {_pose_str(_world_matrix(root))}")
        for child in cmds.listRelatives(root, children=True, type='joint') or []:
            print(f"  {child}: {_pose_str(_world_matrix(child))}")

    # The number that matters: is each mesh actually wrapped around the joints that
    # drive it? Above ~1.0 the mesh is further from its own bones than it is wide,
    # which means the geometry and the skeleton are not describing the same pose --
    # whatever the viewport looks like, since the bind matrices hide the difference.
    bound = []
    for mesh in transforms:
        clusters = []
        for shape in cmds.listRelatives(mesh, shapes=True) or []:
            clusters += cmds.listConnections(shape, type='skinCluster') or []
        if clusters:
            bound.append({'mesh': mesh, 'skin_cluster': sorted(set(clusters))[0],
                          'influences': None})

    rows = _misfit(bound)
    if rows:
        print("\n--- Mesh vs its own joints (multiples of the mesh's size) ---")
        for mesh, value in sorted(rows, key=lambda row: -row[1]):
            flag = "   !! not on its bones" if value > 1.0 else ""
            print(f"  {value:6.2f}  {mesh}{flag}")

    print("\n" + "=" * 64)


def normalize_skm(top_node="skeleton", root_bone=None, rotation=(90.0, 0.0, 0.0),
                  pelvis_bone=None, target_scale=1.0, rotate_meshes=None):
    """
    The whole rig pass, in the one order that works: SCALE -> STRIP -> ROTATE.

    Same shape as normalizeanimation.normalize_animation(), and forced for the same
    reasons: strip_top_node() cannot fold a scale into a jointOrient, and the
    rotation has to be transferred from the real root (n_root), which only becomes
    the root once the wrapper above it is gone.

        skeleton (joint, scale 100)  ->  scale 1, then deleted
          n_root                      ->  the new root, left identity
            n_center                  ->  carries what n_root used to

    Step 1 also freezes the meshes, so scale is the one step that has to come first
    on the mesh side too. Steps 2 and 3 share a single unbind/rebind.

    Args:
        top_node (str): Wrapper joint above the real root. None to skip.
        root_bone (str): Real root, e.g. "n_root". Auto-detected after the strip.
        rotation (tuple): World XYZ degrees. Default (90, 0, 0) = Y-up -> Z-up, i.e.
            the rig is lying down and needs standing up. Pass (0, 0, 0) if it
            already stands correctly and only the root needs emptying.
        pelvis_bone (str): Single carrier, e.g. "n_center". None = every direct
            child of the root.
        target_scale (float): Scale the wrapper should end at (default 1.0).
        rotate_meshes (bool): Passed to normalize_root_rotate(). None (default)
            measures whether the geometry needs the rotation too or whether only the
            bones are out of place.
    """
    print("\n" + "=" * 64)
    print("[1/2] SCALE + MESH FREEZE")
    print("=" * 64)
    # The wrapper is where the 100 sits, so aim the scale pass at it -- pointing this
    # at n_root instead finds a scale that is already ~1 and normalizes nothing.
    scale_node = _find_root_bone(top_node if (top_node and cmds.objExists(top_node))
                                 else root_bone)
    if scale_node is None:
        return

    current = cmds.getAttr(f"{scale_node}.scaleX")
    if abs(current - target_scale) < 0.001:
        print(f"{scale_node} is already at scale {target_scale} -- skipping")
    else:
        normalize_root_freeze_100(root_bone=scale_node, target_scale=target_scale)

    print("\n" + "=" * 64)
    print("[2/2] STRIP WRAPPER + ROTATE")
    print("=" * 64)
    normalize_root_rotate(root_bone=root_bone, rotation=rotation,
                          pelvis_bone=pelvis_bone, top_node=top_node,
                          rotate_meshes=rotate_meshes)


# Execute
if __name__ == "__main__":
    # Look before touching anything -- prints which node counts as the root, where
    # the scale and the hidden jointOrient are, and whether the meshes can be frozen.
    #inspect_rig()

    # Run this AFTER a bad run, while the scene is still broken: it says whether the
    # geometry itself never rotated or the geometry is fine and the skinning undoes it.
    # diagnose_meshes()

    # Scale 100 -> 1 (and freeze the meshes to match), delete the "skeleton" wrapper
    # so n_root becomes the root, then hand n_root's orientation to n_center and
    # leave n_root identity.
    normalize_skm()

    # The rig already stands up correctly and only needs a clean root:
    # normalize_skm(rotation=(0, 0, 0))

    # Force the geometry decision if the measurement picks wrong. False = turn the
    # bones only; True = turn the vertices with them (a genuinely Y-up asset).
    # normalize_skm(rotate_meshes=False)

    # Name things explicitly / pin the carrier to the pelvis alone:
    # normalize_skm(top_node="skeleton", root_bone="n_root", pelvis_bone="n_center")

    # The steps individually, if one of them needs redoing. Same order:
    # normalize_root_freeze_100(root_bone="skeleton")            # scale, on the WRAPPER
    # normalize_root_rotate(root_bone="n_root")                  # strips, then rotates
    # normalize_root_rotate(root_bone="n_root", top_node=None)   # rotate only
