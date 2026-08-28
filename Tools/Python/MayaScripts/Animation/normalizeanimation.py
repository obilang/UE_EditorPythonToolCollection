import math

import maya.cmds as cmds
import maya.api.OpenMaya as om


# Deliberately duplicated from normalizeskm.py -- these run standalone in Maya's
# script editor, where a cross-file import means fighting with sys.path.
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


def _is_identity(matrix):
    return matrix.isEquivalent(om.MMatrix(), 1e-9)


def _pose_str(matrix):
    """MMatrix -> "t=(...) r=(...)", for readable before/after logging."""
    t = om.MTransformationMatrix(matrix).translation(om.MSpace.kWorld)
    r = _matrix_to_euler(matrix)
    return (f"t={tuple(round(v, 4) for v in (t.x, t.y, t.z))} "
            f"r={tuple(round(v, 4) for v in r)}")


def _writable(attr):
    """Can setAttr take on this attribute, once any constant curve is removed?

    DAE imports routinely key *every* channel, so "has an animCurve" is not the
    same as "is animated" -- a curve whose keys all share one value is still a rest
    pose. Such a curve is removable; one that actually varies is not, and neither
    is a locked attribute.
    """
    if cmds.getAttr(attr, lock=True):
        return False

    if not cmds.listConnections(attr, type='animCurve'):
        return not cmds.listConnections(attr, source=True, destination=False)

    values = cmds.keyframe(attr, query=True, valueChange=True) or []
    return not (values and max(values) - min(values) > 1e-6)


def _clear_keys(attr):
    """Drop a (constant) animCurve so setAttr sticks. Check _writable first."""
    curves = cmds.listConnections(attr, type='animCurve') or []
    if curves:
        cmds.delete(curves)


def _set_static(attr, value):
    _clear_keys(attr)
    cmds.setAttr(attr, value)


def _rotate_translate(node, matrix, offset=None):
    """Transform a node's translate channels -- every keyframe on them -- by
    `matrix`, then add `offset`: t_new = t_old * M + offset.

    Translation lives in parent space, outside the joint's own rotation, so a world
    rotation has to be applied to it by hand.

    Returns the number of keyframes rewritten (0 when the channels were static).
    """
    attrs = [f"{node}.translate{axis}" for axis in 'XYZ']
    off = om.MVector(0.0, 0.0, 0.0) if offset is None else om.MVector(offset)

    key_times = set()
    for attr in attrs:
        if cmds.listConnections(attr, type='animCurve'):
            key_times.update(cmds.keyframe(attr, query=True, timeChange=True) or [])

    if not key_times:
        vec = om.MVector(*[cmds.getAttr(a) for a in attrs]) * matrix + off
        for attr, value in zip(attrs, (vec.x, vec.y, vec.z)):
            cmds.setAttr(attr, value)
        return 0

    current_time = cmds.currentTime(query=True)

    # Read every key before writing any of them -- writing a key changes what
    # getAttr returns at later times.
    rotated = {}
    for key_time in sorted(key_times):
        cmds.currentTime(key_time)
        rotated[key_time] = om.MVector(*[cmds.getAttr(a) for a in attrs]) * matrix + off

    # Key all three channels even if only one was animated -- the rotation mixes
    # them, so a channel that was static generally isn't any more.
    for key_time, vec in rotated.items():
        for attr, value in zip(attrs, (vec.x, vec.y, vec.z)):
            cmds.setKeyframe(attr, value=value, time=key_time)

    cmds.currentTime(current_time)
    return len(rotated)


def strip_top_node(top_node="skeleton"):
    """Delete a wrapper transform above the real root and promote its children.

    DAE/FBX imports drop the whole rig under a wrapper -- "skeleton" in the FF16
    exports, giving skeleton -> n_root -> n_center -- and that wrapper is typically
    where the importer's up-axis conversion ends up.

    It can't simply be deleted. A joint's jointOrient cannot affect its *own*
    translate, so the wrapper is what's actually converting the root's position;
    dropping it would leave root motion pointing the old way. Its world transform
    gets baked into each child first. For W = S * T(s), the same R * JO * T split
    used elsewhere gives:

        L_child_new = L_child_old * W   <=>   JO * S,  t * S + s

    Then the children are unparented with -relative, which keeps the local values
    just written instead of letting Maya compute its own compensation.

    Returns the promoted joints, or [] when there was nothing to strip.
    """
    if not top_node or not cmds.objExists(top_node):
        return []

    children = cmds.listRelatives(top_node, children=True, type='transform') or []
    if not children:
        print(f"WARNING: {top_node} has no transform children -- leaving it alone")
        return []

    parent = cmds.listRelatives(top_node, parent=True, fullPath=True)
    if parent:
        print(f"WARNING: {top_node} is itself parented under {parent[0]}, which stays "
              "in the scene; its world matrix is baked in, so the result is still correct")

    world = om.MMatrix(cmds.xform(top_node, query=True, worldSpace=True, matrix=True))
    xform = om.MTransformationMatrix(world)

    scale = xform.scale(om.MSpace.kWorld)
    if any(abs(v - 1.0) > 1e-6 for v in scale):
        print(f"ERROR: {top_node} has a non-unit scale {tuple(round(v, 6) for v in scale)}.")
        print("       Scale can't ride along in a jointOrient -- it has to be pushed into")
        print("       *every* descendant's translate, which is a different job.")
        print(f'       Run normalize_skeleton_with_animation(root_bone="{top_node}") first')
        print("       (note: the wrapper, not the joint under it), or just call")
        print("       normalize_animation(), which runs the whole thing in order.")
        return []

    # The bake is a single constant matrix, so the wrapper has to be static in time.
    # (_writable doubles as "holds one constant value" -- see its docstring.)
    channels = ['translate', 'rotate', 'scale']
    if cmds.nodeType(top_node) == 'joint':
        channels.append('jointOrient')
    if not all(_writable(f"{top_node}.{ch}{axis}")
               for ch in channels for axis in 'XYZ'):
        print(f"ERROR: {top_node} has genuinely animated transform channels.")
        print("       Collapsing it into its children only works for a static wrapper.")
        return []

    rot = xform.rotation(asQuaternion=True).asMatrix()
    offset = xform.translation(om.MSpace.kWorld)

    joints = [c for c in children if cmds.nodeType(c) == 'joint']
    others = [c for c in children if cmds.nodeType(c) != 'joint']

    blocked = [f"{j}.jointOrient{axis}" for j in joints for axis in 'XYZ'
               if not _writable(f"{j}.jointOrient{axis}")]
    if blocked:
        print(f"ERROR: cannot rewrite {blocked} -- locked or genuinely animated")
        return []

    identity = _is_identity(world)
    fmt = lambda v: tuple(round(x, 4) for x in v)
    print(f"\nStripping {top_node} (world matrix is "
          f"{'identity -- a plain reparent' if identity else 'non-identity -- baking it in'})")

    for joint in joints:
        before = om.MMatrix(cmds.xform(joint, query=True, worldSpace=True, matrix=True))
        jo_new = None

        if not identity:
            jo_old = cmds.getAttr(f"{joint}.jointOrient")[0]
            jo_new = _matrix_to_euler(_euler_to_matrix(jo_old) * rot)
            for axis, value in zip('XYZ', jo_new):
                _set_static(f"{joint}.jointOrient{axis}", value)

            keys = _rotate_translate(joint, rot, offset)
            print(f"  {joint}.jointOrient {fmt(jo_old)} -> {fmt(jo_new)}, "
                  f"translate baked ({keys or 'static'})")

        cmds.parent(joint, world=True, relative=True)

        # -relative is documented to keep local values, but Maya has a habit of
        # folding reparent compensation into a joint's jointOrient anyway. Re-assert
        # it, then check the invariant that actually matters: the strip is supposed
        # to leave every child's world matrix exactly where it was.
        if jo_new is not None:
            for axis, value in zip('XYZ', jo_new):
                _set_static(f"{joint}.jointOrient{axis}", value)

        after = om.MMatrix(cmds.xform(joint, query=True, worldSpace=True, matrix=True))
        if after.isEquivalent(before, 1e-6):
            print(f"  {joint} promoted to root (world matrix preserved)")
        else:
            print(f"  WARNING: {joint} moved. Expected its world matrix to be unchanged.")
            print(f"           before {_pose_str(before)}")
            print(f"           after  {_pose_str(after)}")

    for other in others:
        # No jointOrient to absorb the bake, so hand these to Maya's own
        # world-preserving reparent and say so.
        cmds.parent(other, world=True)
        print(f"  {other} reparented to world by Maya (non-joint; local channels rewritten)")

    cmds.delete(top_node)
    print(f"  deleted {top_node}")

    return joints


def normalize_skeleton_with_animation(root_bone=None, target_scale=1.0, bone_radius=3.0):
    """
    Normalize root bone scale from 100 to 1 while preserving all animations
    Works on skeletons without skinned meshes

    Args:
        root_bone (str): Name of the root bone. If None, will try to find it automatically
        target_scale (float): Target scale value (default: 1.0)
        bone_radius (float): Joint display radius applied after normalizing (default: 3.0)
    """
    
    root_bone = _find_root_bone(root_bone)
    if root_bone is None:
        return

    # Get current scale
    current_scale = cmds.getAttr(f"{root_bone}.scaleX")
    print(f"Current root bone scale: {current_scale}")
    
    if abs(current_scale - target_scale) < 0.001:
        print(f"Root bone is already at scale {target_scale}")
        # Still enforce the uniform joint radius
        children = cmds.listRelatives(root_bone, allDescendents=True, type='transform') or []
        for joint in [root_bone] + [c for c in children if cmds.nodeType(c) == 'joint']:
            try:
                cmds.setAttr(f"{joint}.radius", bone_radius)
            except:
                pass
        print(f"Set radius to {bone_radius} on all joints")
        return

    # Calculate scale factor
    scale_factor = current_scale / target_scale
    
    # Get all children
    all_children = cmds.listRelatives(root_bone, allDescendents=True, type='transform') or []
    all_joints = [root_bone] + [child for child in all_children if cmds.nodeType(child) == 'joint']
    
    print(f"Found {len(all_joints)} joints in hierarchy")
    
    # Get time range for animation
    start_time = cmds.playbackOptions(query=True, minTime=True)
    end_time = cmds.playbackOptions(query=True, maxTime=True)
    
    print(f"Animation range: {start_time} to {end_time}")
    
    # Store current time
    current_time = cmds.currentTime(query=True)
    
    # Check if there are keyframes on the skeleton
    has_animation = False
    for joint in all_joints:
        connections = cmds.listConnections(joint, type='animCurve') or []
        if connections:
            has_animation = True
            break
    
    if has_animation:
        print("Animation detected on skeleton")
    else:
        print("No animation curves found")
    
    # Set root bone scale to target value. A DAE import keys every channel it can,
    # so the scale is often sitting on a flat animCurve rather than a plain value --
    # _set_static drops the curve first, and _writable refuses if it really varies.
    blocked = [f"{root_bone}.scale{axis}" for axis in 'XYZ'
               if not _writable(f"{root_bone}.scale{axis}")]
    if blocked:
        print(f"ERROR: cannot write {blocked}")
        print("       Locked, driven, or a genuinely animated scale -- aborting before")
        print("       anything is touched, since the translates below would then be")
        print("       scaled to match a scale that never changed.")
        return

    for axis in 'XYZ':
        _set_static(f"{root_bone}.scale{axis}", target_scale)

    print(f"Set root bone scale to {target_scale}")
    
    # Scale all child joints' translate values
    joints_scaled = 0
    for child in all_children:
        if cmds.nodeType(child) == 'joint':
            # Check if translate attributes have animation
            has_tx_anim = cmds.listConnections(f"{child}.translateX", type='animCurve')
            has_ty_anim = cmds.listConnections(f"{child}.translateY", type='animCurve')
            has_tz_anim = cmds.listConnections(f"{child}.translateZ", type='animCurve')
            
            if has_tx_anim or has_ty_anim or has_tz_anim:
                # Has animation - need to scale keyframes
                print(f"Scaling animated translate values for {child}")
                
                # Get all keyframe times
                all_keys = set()
                if has_tx_anim:
                    all_keys.update(cmds.keyframe(f"{child}.translateX", query=True, timeChange=True) or [])
                if has_ty_anim:
                    all_keys.update(cmds.keyframe(f"{child}.translateY", query=True, timeChange=True) or [])
                if has_tz_anim:
                    all_keys.update(cmds.keyframe(f"{child}.translateZ", query=True, timeChange=True) or [])
                
                # Scale values at each keyframe
                for key_time in all_keys:
                    cmds.currentTime(key_time)
                    
                    tx = cmds.getAttr(f"{child}.translateX")
                    ty = cmds.getAttr(f"{child}.translateY")
                    tz = cmds.getAttr(f"{child}.translateZ")
                    
                    cmds.setKeyframe(f"{child}.translateX", value=tx * scale_factor, time=key_time)
                    cmds.setKeyframe(f"{child}.translateY", value=ty * scale_factor, time=key_time)
                    cmds.setKeyframe(f"{child}.translateZ", value=tz * scale_factor, time=key_time)
            else:
                # No animation - just scale the static values
                tx = cmds.getAttr(f"{child}.translateX")
                ty = cmds.getAttr(f"{child}.translateY")
                tz = cmds.getAttr(f"{child}.translateZ")
                
                cmds.setAttr(f"{child}.translateX", tx * scale_factor)
                cmds.setAttr(f"{child}.translateY", ty * scale_factor)
                cmds.setAttr(f"{child}.translateZ", tz * scale_factor)
            
            joints_scaled += 1

    # Restore original time
    cmds.currentTime(current_time)

    # Set a uniform joint display radius after normalizing
    radius_set = 0
    for joint in all_joints:
        try:
            cmds.setAttr(f"{joint}.radius", bone_radius)
            radius_set += 1
        except:
            pass

    print(f"\n=== Summary ===")
    print(f"- Normalized root bone to scale {target_scale}")
    print(f"- Scaled {joints_scaled} child joints")
    print(f"- Set radius to {bone_radius} on {radius_set} joints")
    print(f"- Scale factor applied: {scale_factor}")
    if has_animation:
        print("- Animation keyframes preserved and scaled")
    print("Done!")


def rotate_skeleton_with_animation(root_bone=None, rotation=(0.0, 0.0, 0.0),
                                   pelvis_bone=None, top_node="skeleton"):
    """
    Leave an animated skeleton's root joint identity -- rotate AND jointOrient both
    0 -- by handing whatever orientation it carries down to its direct children:
    the pelvis (n_center) plus any siblings. Matches a rig normalized by
    normalizeskm.normalize_root_rotate().

    This does NOT assume the rig needs a 90 to reach Z-up. Importing a DAE into a
    scene that is already Z-up converts the rig on the way in and parks the result
    in the root's jointOrient, so adding another 90 would double it. Instead the
    root's *existing* rotation R is measured and transferred, with `rotation` as an
    optional extra world delta D on top:

        carrier absorbs R * D        root ends at identity

    D = identity (the default) is a pure transfer: nothing moves in world at all,
    the root just gets emptied. Pass (90, 0, 0) only when the rig genuinely still
    needs the Y-up -> Z-up turn, i.e. it was imported into a Y-up scene.

    Almost nothing needs baking. A joint's local matrix is R * JO * T in Maya's
    row-vector order, so applying a rotation M in the parent's frame is just

        L_new = L_old * M   <=>   JO_new = JO_old * M,  t_new = t_old * M

    A carrier's rotate curves stay valid untouched, because rotate is applied
    *inside* jointOrient -- in the joint's own frame, which didn't move relative to
    the root. Everything below a carrier never moves at all, for the same reason.

    The root's translate is only touched when D is a real rotation: it lives in
    parent space, outside the joint's own rotation, so it does not follow R (which
    is why the wrapper node, not the root's jointOrient, is what converts root
    motion -- see strip_top_node).

    Run the scale normalize FIRST when the wrapper carries it (the usual case: a
    "skeleton" node at scale 100). The rotation itself commutes with a uniform
    scale, but collapsing the wrapper does not -- see normalize_animation(), which
    just does the three steps in order for you.

    Args:
        root_bone (str): Name of the root bone. Auto-detected when None, after the
            wrapper node is stripped.
        rotation (tuple): EXTRA world-space XYZ degrees on top of the transfer.
            Default (0, 0, 0) = transfer only, for an already-Z-up import.
        pelvis_bone (str): Single child to carry the rotation, e.g. "n_center".
            None (default) uses every direct child of the root.
        top_node (str): Wrapper transform to collapse first, e.g. the "skeleton"
            node above n_root. Ignored when it doesn't exist; None to skip.
    """
    promoted = strip_top_node(top_node)
    if top_node and cmds.objExists(top_node):
        # The strip bailed (see its own error above). Carrying on would measure and
        # empty a root that is still hanging under the wrapper, so the transfer would
        # be in the wrapper's space instead of world -- wrong, and hard to undo.
        print(f"ERROR: {top_node} is still in the scene -- aborting the rotation too.")
        return
    if root_bone is None and len(promoted) == 1:
        root_bone = promoted[0]
        print(f"Promoted {root_bone} to root")

    root_bone = _find_root_bone(root_bone)
    if root_bone is None:
        return

    parent = cmds.listRelatives(root_bone, parent=True, fullPath=True)
    if parent:
        print(f"WARNING: {root_bone} is parented under {parent[0]} -- the rotation is "
              "applied in parent space, which only matches world if that parent is identity")

    carriers = _rotation_carriers(root_bone, pelvis_bone)
    if not carriers:
        print(f"ERROR: no joint under {root_bone} to carry the rotation -- aborting")
        return

    # Everything below hinges on R being one constant rotation. If the root's rotate
    # genuinely varies over time, what each carrier absorbs changes every frame, and
    # a static jointOrient cannot hold a per-frame value -- it would have to be baked
    # into the carrier's rotate curves, silently fighting the rest pose. Refuse.
    blocked = [f"{root_bone}.{ch}{axis}"
               for ch in ('rotate', 'jointOrient') for axis in 'XYZ'
               if not _writable(f"{root_bone}.{ch}{axis}")]
    if blocked:
        print(f"ERROR: cannot clear {blocked}.")
        print("       A locked channel, or one whose curve actually varies: with the")
        print("       orientation living on the children, each absorbs R * D, which is")
        print("       frame-dependent when R is animated. Run this before extracting")
        print("       root motion, or zero the root's rotation curves first.")
        return

    blocked = [f"{c}.jointOrient{axis}" for c in carriers for axis in 'XYZ'
               if not _writable(f"{c}.jointOrient{axis}")]
    if blocked:
        print(f"ERROR: cannot rewrite {blocked} -- locked or genuinely animated")
        return

    fmt = lambda v: tuple(round(x, 4) for x in v)

    delta = _euler_to_matrix(rotation)
    root_rot = _local_rotation(root_bone)
    carrier_delta = root_rot * delta

    print(f"\nScene up axis: {cmds.upAxis(query=True, axis=True)}")
    print(f"{root_bone} carries      {fmt(_matrix_to_euler(root_rot))} "
          f"(rotate {fmt(cmds.getAttr(f'{root_bone}.rotate')[0])} * "
          f"jointOrient {fmt(cmds.getAttr(f'{root_bone}.jointOrient')[0])})")
    print(f"Extra rotation requested: {fmt(rotation)}"
          f"{' -- none, pure transfer' if _is_identity(delta) else ''}")
    print(f"Carriers absorb R * D =   {fmt(_matrix_to_euler(carrier_delta))}: {carriers}")

    carrier_keys = 0
    if _is_identity(carrier_delta):
        # Note this is R * D, not R: a root already at identity with no extra
        # rotation lands here, but so does the rare case where D happens to undo R.
        print("\nNothing for the carriers to absorb -- R * D is identity.")
    else:
        for carrier in carriers:
            jo_old = cmds.getAttr(f"{carrier}.jointOrient")[0]
            jo_new = _matrix_to_euler(_euler_to_matrix(jo_old) * carrier_delta)
            for axis, value in zip('XYZ', jo_new):
                _set_static(f"{carrier}.jointOrient{axis}", value)

            keys = _rotate_translate(carrier, carrier_delta)
            carrier_keys += keys

            print(f"\n{carrier}.jointOrient {fmt(jo_old)} -> {fmt(jo_new)}")
            print(f"{carrier}.translate   transformed ({keys} keyframe(s))" if keys
                  else f"{carrier}.translate   transformed (static)")

    # Root motion only moves if a real world rotation was asked for. With D
    # identity the curves are left completely alone -- no rewritten tangents, no
    # keys added to channels that had none.
    root_keys = 0
    if _is_identity(delta):
        print(f"\n{root_bone}.translate left untouched (no extra world rotation)")
    else:
        root_keys = _rotate_translate(root_bone, delta)
        print(f"\n{root_bone}.translate rotated by D "
              f"({root_keys} keyframe(s))" if root_keys
              else f"\n{root_bone}.translate rotated by D (static)")

    # The root gives up its orientation entirely. Safe even when R * D was identity:
    # the children only ever saw the root's *total* rotation, so if that was already
    # identity, splitting it out of the channels changes nothing in world.
    for channel in ('rotate', 'jointOrient'):
        for axis in 'XYZ':
            _set_static(f"{root_bone}.{channel}{axis}", 0.0)

    print(f"\n=== Summary ===")
    print(f"- Transferred {fmt(_matrix_to_euler(carrier_delta))} to {carriers}")
    print(f"- {root_bone} left identity: rotate 0 and jointOrient 0")
    print(f"- Rotated {root_keys} root motion keyframe(s)" if root_keys
          else f"- Root motion curves untouched")
    print(f"- Rewrote {carrier_keys} carrier translate keyframe(s)")
    print("- Rotate curves left untouched everywhere (still valid against the new orient)")
    print("- Joints below the carriers untouched")
    print("Done!")


def normalize_animation(top_node="skeleton", root_bone=None, rotation=(0.0, 0.0, 0.0),
                        pelvis_bone=None, target_scale=1.0, bone_radius=3.0):
    """
    The whole pass, in the one order that works: SCALE -> STRIP -> ROTATE.

        skeleton (scale 100)        ->  scale 1, gone
          n_root                    ->  the new root, identity
            n_center                ->  carries what n_root used to

    Why the order is forced:

    1. SCALE FIRST, and on the wrapper, because that is where the 100 usually sits.
       A scale cannot be collapsed the way a rotation can: rotating a child is
       JO * M, but unscaling a parent means multiplying *every* descendant's
       translate (and every translate keyframe) by the factor. So strip_top_node()
       refuses a non-unit scale rather than silently dropping it.
    2. STRIP SECOND. The wrapper's leftover rotation/translation is baked into
       n_root, and n_root is promoted to root. This is also the step that converts
       root motion: a joint's own jointOrient cannot rotate its own translate, so
       the wrapper -- not the root's orient -- is what turns the root's path.
    3. ROTATE LAST, so what gets handed to n_center already includes the wrapper's
       contribution from step 2. Rotating first would transfer the wrong node's
       orientation, and would then have to be redone after the strip.

    `rotation` is an EXTRA world delta, not the total. A DAE imported into a Z-up
    scene is converted on the way in and the result lands in the root's jointOrient
    -- the default (0, 0, 0) transfers that, and nothing moves in the viewport.
    Only pass (90, 0, 0) if the rig is still visibly Y-up, i.e. it came into a Y-up
    scene. The printout says which up axis the scene is on.

    Args:
        top_node (str): Wrapper transform above the real root, e.g. "skeleton".
            Ignored when absent; None to skip the strip entirely.
        root_bone (str): Real root, e.g. "n_root". Auto-detected after the strip.
        rotation (tuple): Extra world XYZ degrees. (0, 0, 0) = pure transfer.
        pelvis_bone (str): Single carrier, e.g. "n_center". None = every direct
            child of the root (pelvis plus any attach/weapon joints).
        target_scale (float): Scale the wrapper/root should end at (default 1.0).
        bone_radius (float): Joint display radius applied after normalizing.
    """
    print("\n" + "=" * 64)
    print("[1/3] SCALE")
    print("=" * 64)
    scale_node = root_bone
    if top_node and cmds.objExists(top_node):
        # Normally the wrapper is the node holding the 100 -- aiming this at n_root
        # instead finds a scale that is already ~1 and normalizes nothing, which is
        # exactly the trap. But the 100 does sometimes sit on the real root, so if
        # the wrapper is clean, look one level down before giving up on it.
        scale_node = top_node
        if abs(cmds.getAttr(f"{top_node}.scaleX") - target_scale) < 0.001:
            children = cmds.listRelatives(top_node, children=True, type='joint') or []
            below = [c for c in children
                     if abs(cmds.getAttr(f"{c}.scaleX") - target_scale) >= 0.001]
            if below:
                scale_node = below[0]
                print(f"{top_node} is already at scale {target_scale}, but "
                      f"{scale_node} is not -- normalizing from there instead")
    elif top_node:
        print(f"No {top_node!r} wrapper in the scene -- scaling from the root instead")

    normalize_skeleton_with_animation(root_bone=scale_node,
                                      target_scale=target_scale,
                                      bone_radius=bone_radius)

    print("\n" + "=" * 64)
    print("[2/3] STRIP + [3/3] ROTATE")
    print("=" * 64)
    rotate_skeleton_with_animation(root_bone=root_bone, rotation=rotation,
                                   pelvis_bone=pelvis_bone, top_node=top_node)


# Execute the function
if __name__ == "__main__":
    # Scale 100 -> 1 on "skeleton", delete it so n_root becomes the root, then hand
    # n_root's orientation down to n_center and leave n_root identity.
    normalize_animation()

    # The rig is still visibly Y-up after import (came into a Y-up scene), so it
    # needs the turn on top of the transfer:
    # normalize_animation(rotation=(90, 0, 0))

    # Name things explicitly / pin the carrier to the pelvis alone:
    # normalize_animation(top_node="skeleton", root_bone="n_root", pelvis_bone="n_center")

    # No wrapper in this file, just the rotation pass:
    # normalize_animation(top_node=None)

    # The steps individually, if one of them needs redoing on its own. Same order:
    # normalize_skeleton_with_animation(root_bone="skeleton")   # scale, on the WRAPPER
    # strip_top_node("skeleton")                                # n_root becomes root
    # rotate_skeleton_with_animation(root_bone="n_root", top_node=None)