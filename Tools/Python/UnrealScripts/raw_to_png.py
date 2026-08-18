import sys
from PIL import Image
import numpy as np


def raw_to_png(raw_path, png_path, width, height, dtype='uint8'):
    """
    Convert a .raw file to a .png image using PIL.
    Args:
        raw_path (str): Path to the input .raw file.
        png_path (str): Path to save the output .png file.
        width (int): Image width.
        height (int): Image height.
        dtype (str): Data type of the raw file (default: 'uint8').
    """
        with open(raw_path, 'rb') as f:
            raw_data = f.read()
        arr = np.frombuffer(raw_data, dtype=dtype)
        # Try to guess image shape (assume square)
        size = int(np.sqrt(arr.size))
        if size * size != arr.size:
            raise ValueError(f"Cannot infer square shape from raw data of length {arr.size}.")
        arr = arr.reshape((size, size))
        img = Image.fromarray(arr)
        img.save(png_path)
        return arr


def main():
    if len(sys.argv) < 5:
        print("Usage: python raw_to_png.py <input.raw> <output.png> <width> <height> [dtype]")
        sys.exit(1)
    raw_path = sys.argv[1]
    png_path = sys.argv[2]
    width = int(sys.argv[3])
    height = int(sys.argv[4])
    dtype = sys.argv[5] if len(sys.argv) > 5 else 'uint8'
    raw_to_png(raw_path, png_path, width, height, dtype)
    print(f"Converted {raw_path} to {png_path} ({width}x{height}, dtype={dtype})")
        if len(sys.argv) < 3:
            print("Usage: python raw_to_png.py <input.raw> <output.png> [dtype]")
            sys.exit(1)
        dtype = sys.argv[3] if len(sys.argv) > 3 else 'uint8'
        arr = raw_to_png(raw_path, png_path, dtype)
        # Print bit depth
        if arr.dtype == np.uint8:
            bit_depth = 8
        elif arr.dtype == np.uint16:
            bit_depth = 16
        else:
            bit_depth = arr.dtype.itemsize * 8
        print(f"Converted {raw_path} to {png_path} (shape={arr.shape}, dtype={arr.dtype}, bit depth={bit_depth}bit)")


if __name__ == "__main__":
    main()
