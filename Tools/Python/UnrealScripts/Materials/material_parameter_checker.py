import unreal
from enum import Enum

mat_edit_lib = unreal.MaterialEditingLibrary()
editor_asset_lib = unreal.EditorAssetLibrary()
asset_registry = unreal.AssetRegistryHelpers().get_asset_registry()


class EParameterType(Enum):
    SCALAR = 'scalar'
    VECTOR = 'vector'
    TEXTURE = 'texture'
    STATIC_SWITCH = 'static switch'
    
    
def get_association_display_name(entry: unreal.MaterialParameterAssociation):
    if entry == unreal.MaterialParameterAssociation.LAYER_PARAMETER:
        return "Layer"
    elif entry == unreal.MaterialParameterAssociation.BLEND_PARAMETER:
        return "Blend"
    elif entry == unreal.MaterialParameterAssociation.GLOBAL_PARAMETER:
        return "Global(Default)"
    else:
        return "unknown"


def get_asset_data_path(assetData):
    return str(str(assetData.package_name) + "." + str(assetData.asset_name))


def get_all_material_instances():
    assets = editor_asset_lib.list_assets("/Game/Art/", True, False)
    filtered_assets = []
    for asset in assets:
        asset = asset[0: asset.rindex('.')]
        asset_data = editor_asset_lib.find_asset_data(asset)
        if asset_data and asset_data.asset_class_path.asset_name == "MaterialInstanceConstant":
            filtered_assets.append(asset)
    return filtered_assets


def get_base_material(material_instance_data):
    parent = material_instance_data.get_tag_value("parent")
    if parent is None or parent == "None":
        return None
    
    parent_package_name = parent[parent.index("'") + 1: parent.rindex('.')]
    if parent_package_name != '' and not editor_asset_lib.does_asset_exist(parent_package_name):
        return None
    
    parent_data = editor_asset_lib.find_asset_data(parent_package_name)
    if parent_data.asset_class_path.asset_name == "Material":
        return parent_data
    else:
        return get_base_material(parent_data)


def get_material_child_instances(parent_mat_path):
    child_instances = []
    for material_instance in get_all_material_instances():
        material_instance_data: unreal.AssetData = editor_asset_lib.find_asset_data(material_instance)
        base_material_data = get_base_material(material_instance_data)
        if base_material_data is not None and get_asset_data_path(base_material_data) == parent_mat_path:
            child_instances.append(material_instance)
    return child_instances


def check_parameter_value_of_material_instance(mat_instance_path, parameter_name, parameter_type: EParameterType, association: unreal.MaterialParameterAssociation):
    mat_instance_obj = editor_asset_lib.load_asset(mat_instance_path)
    if parameter_type == EParameterType.SCALAR:
        properties = mat_instance_obj.get_editor_property("scalar_parameter_values")
    if parameter_type == EParameterType.VECTOR:
        properties = mat_instance_obj.get_editor_property("vector_parameter_values")
    if parameter_type == EParameterType.TEXTURE:
        properties = mat_instance_obj.get_editor_property("texture_parameter_values")
        
    # print(properties)

    mat_para_infos = []
    for p in properties:
        para_info = p.parameter_info
        if para_info.name != parameter_name:
            continue
        if para_info.association != association:
            continue
        mat_para_infos.append([para_info, p.parameter_value])
        
    return mat_para_infos
    

def check_static_switch_value_of_material_instance(mat_instance_path, parameter_name, parameter_value: bool, association: unreal.MaterialParameterAssociation):
    mat_instance_obj = editor_asset_lib.load_asset(mat_instance_path)
    # print(mat_instance_obj)
    
    # somehow the association input will be an int type, force it back to enum again
    if association == unreal.MaterialParameterAssociation.GLOBAL_PARAMETER:
        association_enum = unreal.MaterialParameterAssociation.GLOBAL_PARAMETER
    elif association == unreal.MaterialParameterAssociation.LAYER_PARAMETER:
        association_enum = unreal.MaterialParameterAssociation.LAYER_PARAMETER
    elif association == unreal.MaterialParameterAssociation.BLEND_PARAMETER:
        association_enum = unreal.MaterialParameterAssociation.BLEND_PARAMETER
    
    mat_para_infos = []
    
    if association == unreal.MaterialParameterAssociation.GLOBAL_PARAMETER:
        target_value = unreal.PythonFunctionLibrary.get_material_instance_static_switch_parameter_value(
            mat_instance_obj,
            parameter_name,
            association_enum,
            -1
        )
        # print(target_value)
        if target_value == parameter_value:
            mat_para_info = unreal.MaterialParameterInfo(parameter_name, association_enum, -1)
            mat_para_infos.append([mat_para_info, parameter_value])
    else:
        # should be no material have more than 10 layers
        for index in range(10):
            target_value = unreal.PythonFunctionLibrary.get_material_instance_static_switch_parameter_value(
                mat_instance_obj,
                parameter_name,
                association_enum,
                index
            )
            # print(target_value)
            if target_value == parameter_value:
                mat_para_info = unreal.MaterialParameterInfo(parameter_name, association_enum, index)
                mat_para_infos.append([mat_para_info, parameter_value])
        
    return mat_para_infos
            

def check_parameter_value_in_child_instances(
    parent_mat_path,
    parameter_name,
    parameter_type: EParameterType, 
    parameter_value,
    association: unreal.MaterialParameterAssociation
):
    unreal.log("Start checking [{}] in [{}] for base material {}".format(
        parameter_name, get_association_display_name(association), parent_mat_path))
    with unreal.ScopedSlowTask(1, "Finding Child Material Instances...") as slow_task:
        # display the dialog
        slow_task.make_dialog(True)
        child_instances = get_material_child_instances(parent_mat_path)
   
    modified_materials = {}
    with unreal.ScopedSlowTask(len(child_instances), "Checking on material instance...") as slow_task:
        # display the dialog
        slow_task.make_dialog(True)
        for child_instance in child_instances:
            if slow_task.should_cancel():
                break
            slow_task.enter_progress_frame(1, "Checking on material instance {}".format(child_instance))
            
            if parameter_type == EParameterType.STATIC_SWITCH:
                result = check_static_switch_value_of_material_instance(child_instance, parameter_name, parameter_value, association)
            else:
                result = check_parameter_value_of_material_instance(child_instance, parameter_name, parameter_type, association)
            if len(result) > 0:
                modified_materials[child_instance] = result
        return modified_materials


if __name__ == "__main__":
    assets = unreal.EditorUtilityLibrary.get_selected_assets()
    
    result = check_parameter_value_in_child_instances(
        '/Game/Art/Materials/Environmental_Material/Base_Master_Material/LayeredMaterial/M_LayeredMaterial_Base.M_LayeredMaterial_Base',
        "Base Color Tint",
        EParameterType.VECTOR,
        True,
        unreal.MaterialParameterAssociation.LAYER_PARAMETER
    )
    print(result)
