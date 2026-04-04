import traceback

import unreal
import sys
import time
import math
import os
from PIL import Image


TEST_IMAGE_PATH = ""

def load_and_get_r_channel(image_path):
    if not os.path.isfile(image_path):
        return None
    image = Image.open(image_path).convert("L")
    if image:
        channel = image.split()[0]
        return channel

def merge_grayscale_images(merged_out_path, r_path, g_path, b_path, a_path=''):
    r_channel = load_and_get_r_channel(r_path)
    g_channel = load_and_get_r_channel(g_path)
    b_channel = load_and_get_r_channel(b_path)
    a_channel = load_and_get_r_channel(a_path)
    
    print(r_channel)
    print(g_channel)
    print(b_channel)
    print(a_channel)
    print(merged_out_path)
    
    if r_channel and g_channel and b_channel:
        if a_channel:
            merged_image = Image.merge("RGBA", (r_channel, g_channel, b_channel, a_channel))
        else:
            merged_image = Image.merge("RGB", (r_channel, g_channel, b_channel))
    
    if merged_image:
        result = merged_image.save(merged_out_path)
        print(result)
        
    

if __name__ == "__main__":
    merge_grayscale_images(
        "G:\\*.tga",
        "G:\\*.tga",
        "G:\\*.tga",
        "G:\\*.tga",
        "G:\\*.tga"
    )
