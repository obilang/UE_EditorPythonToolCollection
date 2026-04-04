import unreal
from enum import Enum
from AssetOperations import asset_utils

editor_asset_lib = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
mat_edit_lib = unreal.MaterialEditingLibrary()


def create_material_instance(name, folder, parent_mat: unreal.MaterialInterface):
    mat_instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name,
        folder,
        unreal.MaterialInstanceConstant,
        unreal.MaterialInstanceConstantFactoryNew()
    )
    if mat_instance:
        mat_edit_lib.set_material_instance_parent(mat_instance, parent_mat)
    return mat_instance


def clean_up_material_instance(mat: unreal.MaterialInstanceConstant, new_parent=None):
    mat_edit_lib.clear_all_material_instance_parameters(mat)
    mat_edit_lib.set_material_instance_parent(mat, new_parent)
    mat_edit_lib.clear_all_material_instance_parameters(mat)


def set_material_texture_param_value(
    material_instance, 
    param_name,
    param_value,
    association: unreal.MaterialParameterAssociation = unreal.MaterialParameterAssociation.GLOBAL_PARAMETER,
    index=-1
):
    texture_parameters = material_instance.get_editor_property("texture_parameter_values")
    found_existing_param_info = False
    for count, texture_parameter in enumerate(texture_parameters):
        param_info: unreal.MaterialParameterInfo = texture_parameter.parameter_info
        
        if param_info.name == param_name and param_info.association == association and param_info.index == index:
            texture_parameter.parameter_value = param_value
            texture_parameters[count] = texture_parameter
            found_existing_param_info = True
            break
            
    if not found_existing_param_info:
        new_param_info: unreal.MaterialParameterInfo = unreal.MaterialParameterInfo()
        new_param_info.name = param_name
        new_param_info.association = association
        new_param_info.index = index

        new_text_para_value = unreal.TextureParameterValue()
        new_text_para_value.parameter_info = new_param_info
        new_text_para_value.parameter_value = param_value
        
        texture_parameters.append(new_text_para_value)
    
    # print(texture_parameters)
    material_instance.set_editor_property("texture_parameter_values", texture_parameters)


def get_material_texture_param_value(
    material_instance,
    param_name,
    association: unreal.MaterialParameterAssociation = unreal.MaterialParameterAssociation.GLOBAL_PARAMETER,
    index=-1
):
    texture_parameters = material_instance.get_editor_property("texture_parameter_values")
    for count, texture_parameter in enumerate(texture_parameters):
        param_info: unreal.MaterialParameterInfo = texture_parameter.parameter_info

        if param_info.name == param_name and param_info.association == association and param_info.index == index:
            return texture_parameter.parameter_value


def set_material_scalar_param_value(
    material_instance,
    param_name,
    param_value,
    association: unreal.MaterialParameterAssociation = unreal.MaterialParameterAssociation.GLOBAL_PARAMETER,
    index=-1
):
    value_has_changed = False
    scalar_parameters = material_instance.get_editor_property("scalar_parameter_values")
    found_existing_param_info = False
    for count, scalar_parameter in enumerate(scalar_parameters):
        param_info: unreal.MaterialParameterInfo = scalar_parameter.parameter_info

        if param_info.name == param_name and param_info.association == association and param_info.index == index:
            if scalar_parameter.parameter_value != param_value:
                value_has_changed = True
            scalar_parameter.parameter_value = param_value
            scalar_parameters[count] = scalar_parameter
            found_existing_param_info = True
            break
    
    if not found_existing_param_info:
        value_has_changed = True
        new_param_info: unreal.MaterialParameterInfo = unreal.MaterialParameterInfo()
        new_param_info.name = param_name
        new_param_info.association = association
        new_param_info.index = index

        new_scalar_para_value = unreal.ScalarParameterValue()
        new_scalar_para_value.parameter_info = new_param_info
        new_scalar_para_value.parameter_value = param_value

        scalar_parameters.append(new_scalar_para_value)

    # print(scalar_parameters)
    material_instance.set_editor_property("scalar_parameter_values", scalar_parameters)
    return value_has_changed


def set_material_vector_param_value(
    material_instance,
    param_name,
    param_value,
    association: unreal.MaterialParameterAssociation = unreal.MaterialParameterAssociation.GLOBAL_PARAMETER,
    index=-1
):
    vector_parameters = material_instance.get_editor_property("vector_parameter_values")
    found_existing_param_info = False
    for count, vector_parameter in enumerate(vector_parameters):
        param_info: unreal.MaterialParameterInfo = vector_parameter.parameter_info

        if param_info.name == param_name and param_info.association == association and param_info.index == index:
            vector_parameter.parameter_value = param_value
            vector_parameters[count] = vector_parameter
            found_existing_param_info = True
            break

    if not found_existing_param_info:
        new_param_info: unreal.MaterialParameterInfo = unreal.MaterialParameterInfo()
        new_param_info.name = param_name
        new_param_info.association = association
        new_param_info.index = index

        new_vector_para_value = unreal.VectorParameterValue()
        new_vector_para_value.parameter_info = new_param_info
        new_vector_para_value.parameter_value = param_value

        vector_parameters.append(new_vector_para_value)

    material_instance.set_editor_property("vector_parameter_values", vector_parameters)
    

class EChannelMask(Enum):
    RED = 'red'
    GREEN = 'green'
    BLUE = 'blue'
    ALPHA = 'alpha'
    
    
def set_material_channel_mask_param_value(
    material_instance,
    param_name,
    param_value: EChannelMask,
    association: unreal.MaterialParameterAssociation = unreal.MaterialParameterAssociation.GLOBAL_PARAMETER,
    index=-1
):
    if param_value == EChannelMask.RED:
        set_material_vector_param_value(material_instance, param_name, unreal.LinearColor(1, 0, 0, 0), association, index)
    elif param_value == EChannelMask.GREEN:
        set_material_vector_param_value(material_instance, param_name, unreal.LinearColor(0, 1, 0, 0), association, index)
    elif param_value == EChannelMask.BLUE:
        set_material_vector_param_value(material_instance, param_name, unreal.LinearColor(0, 0, 1, 0), association, index)
    elif param_value == EChannelMask.ALPHA:
        set_material_vector_param_value(material_instance, param_name, unreal.LinearColor(0, 0, 0, 1), association, index)
        
        
def set_material_static_switch_param_value(
    material_instance,
    param_name,
    param_value,
    association: unreal.MaterialParameterAssociation = unreal.MaterialParameterAssociation.GLOBAL_PARAMETER,
    index=-1
):
    unreal.PythonFunctionLibrary.set_material_instance_static_switch_parameter_value(
        material_instance,
        param_name,
        param_value,
        association,
        index
    )


def get_material_static_switch_param_value(
    material_instance,
    param_name,
    association: unreal.MaterialParameterAssociation = unreal.MaterialParameterAssociation.GLOBAL_PARAMETER,
    index=-1
) -> bool:
    return unreal.PythonFunctionLibrary.get_material_instance_static_switch_parameter_value(
        material_instance,
        param_name,
        association,
        index
    )


def get_approximate_memory_size(texture: unreal.Texture):
    BC1_2K_MEMORY_SIZE_KB = 2731
    base_line_size = BC1_2K_MEMORY_SIZE_KB
    if texture.compression_settings == unreal.TextureCompressionSettings.TC_NORMALMAP:
        base_line_size = base_line_size * 2

    max_size = texture.blueprint_get_size_x()
    lod_bias = texture.lod_bias
    max_in_game_size = max_size / pow(2, lod_bias)

    approximate_memory_size = pow(max_in_game_size, 2) / pow(2048, 2) * base_line_size
    return approximate_memory_size


def get_base_material(material_instance_data: unreal.AssetData) -> unreal.AssetData:
    parent = material_instance_data.get_tag_value("parent")
    if parent is None or str(parent) == "None":
        return None

    parent = asset_utils.object_path_to_package_path(parent)
    if parent is None or str(parent) == "None" or not editor_asset_lib.does_asset_exist(parent):
        return None

    parent_data = editor_asset_lib.find_asset_data(parent)
    if parent_data.asset_class_path.asset_name == "Material":
        return parent_data
    else:
        return get_base_material(parent_data)