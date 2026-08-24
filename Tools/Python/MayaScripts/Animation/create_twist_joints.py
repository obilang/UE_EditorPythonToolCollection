"""
Create Twist Joint Chain with Cubes
This script creates a joint chain named twist_01, twist_02, etc.
Each joint is 10cm apart in a straight line.
A 9x9x9 cm cube is created and skin bound to each joint.
"""

import maya.cmds as cmds


def create_twist_joints(num_joints=5, spacing=10.0, cube_size=9.0):
    """
    Create a chain of twist joints with cubes bound to each joint.
    
    Args:
        num_joints (int): Number of joints to create (default: 5)
        spacing (float): Distance between joints in cm (default: 10.0)
        cube_size (float): Size of the cube in cm (default: 9.0)
    
    Returns:
        tuple: (list of joints, list of cubes, list of skin clusters)
    """
    joints = []
    cubes = []
    skin_clusters = []
    
    # Clear selection
    cmds.select(clear=True)
    
    # Create joints along X axis
    for i in range(num_joints):
        joint_name = f"twist_{i+1:02d}"
        
        # Position joint at interval along X axis
        x_pos = i * spacing
        
        # Create joint
        joint = cmds.joint(name=joint_name, position=(x_pos, 0, 0))
        joints.append(joint)
    
    # Orient joints properly
    if len(joints) > 1:
        cmds.select(joints[0], replace=True)
        cmds.joint(edit=True, orientJoint='xyz', secondaryAxisOrient='yup', children=True, zeroScaleOrient=True)
    
    # Create cubes and bind them to joints
    for i, joint in enumerate(joints):
        # Create cube
        cube_name = f"twist_cube_{i+1:02d}"
        cube = cmds.polyCube(name=cube_name, width=cube_size, height=cube_size, depth=cube_size)[0]
        
        # Get joint position
        joint_pos = cmds.xform(joint, query=True, worldSpace=True, translation=True)
        
        # Move cube to joint position
        cmds.xform(cube, worldSpace=True, translation=joint_pos)
        
        cubes.append(cube)
        
        # Skin bind cube to joint
        skin_cluster = cmds.skinCluster(joint, cube, name=f"{cube_name}_skinCluster", 
                                       toSelectedBones=True, bindMethod=0, 
                                       skinMethod=0, normalizeWeights=1)[0]
        skin_clusters.append(skin_cluster)
    
    # Select all created objects for visibility
    cmds.select(joints + cubes, replace=True)
    
    print(f"Created {len(joints)} twist joints with bound cubes:")
    print(f"  Joints: {', '.join(joints)}")
    print(f"  Cubes: {', '.join(cubes)}")
    
    return joints, cubes, skin_clusters


if __name__ == "__main__":
    # Run with default settings: 5 joints, 10cm spacing, 9cm cubes
    create_twist_joints(num_joints=5, spacing=10.0, cube_size=9.0)
