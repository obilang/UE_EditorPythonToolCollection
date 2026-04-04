import unreal
import path_util
import json
import os
from typing import List

TEXTURE_SETTING_FILE = "AssetImport/texture_import_settings.json"

COMPRESSION_MAP = {
    "HDR": unreal.TextureCompressionSettings.TC_HDR,
    "VectorDisplacement": unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP,
    "BC1": unreal.TextureCompressionSettings.TC_DEFAULT,
    "BC7": unreal.TextureCompressionSettings.TC_BC7,
    "Normal": unreal.TextureCompressionSettings.TC_NORMALMAP,
    "HDRCompressed": unreal.TextureCompressionSettings.TC_HDR_COMPRESSED,
}

MIP_GEN_MAP = {
    "NoMip": unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS,
    "FromTextureGroup": unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP
}

FILTER_MAP = {
    "nearest": unreal.TextureFilter.TF_NEAREST,
    "default": unreal.TextureFilter.TF_DEFAULT
}


def LOG_SETTING(log_str):
    unreal.log("[Texture Setting]: {}".format(log_str))


class TextureSetting:
    def __init__(self, data_dict):
        self.id = data_dict["id"]
        self.name = data_dict["name"]
        self.pattern = data_dict["pattern"]
        self.properties = data_dict["properties"]
        self.description = data_dict["description"]
        

def get_texture_import_settings() -> List[TextureSetting]:
    setting_file_path = os.path.join(path_util.ue_tool_python_path(), TEXTURE_SETTING_FILE)
    with open(setting_file_path, "r") as setting_file:
        setting = json.load(setting_file)
    
    texture_settings = []
    if setting is not None:
        for item in setting:
            texture_setting = TextureSetting(item)
            texture_settings.append(texture_setting)
            
    return texture_settings
        

def set_texture_as(texture_obj: unreal.Texture2D, texture_setting: TextureSetting, texture_group: unreal.TextureGroup):
    texture_obj.set_editor_property("lod_group", texture_group)
    texture_obj.set_editor_property("virtual_texture_streaming", False)
    for property_key, property_value in texture_setting.properties.items():
        if property_key == "compression_settings":
            texture_obj.set_editor_property(property_key, COMPRESSION_MAP[property_value])
        elif property_key == "mip_gen_settings":
            texture_obj.set_editor_property(property_key, MIP_GEN_MAP[property_value])
        elif property_key == "filter":
            texture_obj.set_editor_property(property_key, FILTER_MAP[property_value])
        else:
            texture_obj.set_editor_property(property_key, property_value)
            
        LOG_SETTING("Setting Property [{}] to: {}".format(property_key, property_value))
        

if __name__ == "__main__":
    get_texture_import_settings()

