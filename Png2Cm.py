import os
import sys
import argparse
from struct import pack
from PIL import Image

def write_cm_metadata(file, metadata):
    header = bytearray(0x20)
    header[0:2] = b'CM'
    header[2:6] = pack('<I', metadata['size'])
    header[6:8] = pack('<H', metadata['width'])
    header[8:10] = pack('<H', metadata['height'])
    header[0x0A:0x0C] = pack('<H', metadata['colors'])
    header[0x0C] = metadata['bpp']
    header[0x0D] = int(metadata['is_compressed'])
    header[0x0E] = 1
    header[0x10:0x14] = pack('<I', metadata['data_offset'])
    header[0x14:0x18] = pack('<I', metadata['data_length'])
    file.write(header)

def rle_encode(input_data, pixel_size):
    output = bytearray()
    i = 0
    while i < len(input_data):
        # Find run of identical pixels
        run_start = i
        while i + pixel_size <= len(input_data) and i - run_start < 127 * pixel_size:
            if input_data[i:i+pixel_size] != input_data[run_start:run_start+pixel_size]:
                break
            i += pixel_size
        run_length = (i - run_start) // pixel_size

        if run_length > 1:
            # Encode run
            output.append(0x80 | run_length)
            output.extend(input_data[run_start:run_start+pixel_size])
        else:
            # Find literal run
            literal_start = run_start
            i = literal_start + pixel_size
            while i + pixel_size <= len(input_data) and i - literal_start < 127 * pixel_size:
                if i + pixel_size * 2 <= len(input_data) and input_data[i:i+pixel_size] == input_data[i+pixel_size:i+pixel_size*2] == input_data[i+pixel_size*2:i+pixel_size*3]:
                    break
                i += pixel_size
            literal_length = (i - literal_start) // pixel_size

            output.append(literal_length)
            output.extend(input_data[literal_start:i])

    return output

def convert_png_to_cm(input_path, output_path):
    with Image.open(input_path) as img:
        width, height = img.size
        
        # Determine the bits per pixel and mode
        if img.mode == 'P':
            bpp = 8
            palette = img.getpalette()
            colors = len(palette) // 3
            # Convert palette from RGB to BGR
            palette = b''.join(palette[i+2:i+3] + palette[i+1:i+2] + palette[i:i+1] for i in range(0, len(palette), 3))
        else:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            bpp = 24
            colors = 0
            palette = None
        
        # Flip the image vertically
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
        
        # Convert to bytes
        image_data = img.tobytes()
        
        if bpp == 24:
            # Convert RGB to BGR for 24-bit images
            image_data = b''.join(image_data[i+2:i+3] + image_data[i+1:i+2] + image_data[i:i+1] 
                                  for i in range(0, len(image_data), 3))
        
        # Compress the data using RLE
        compressed_data = rle_encode(image_data, bpp // 8)
        
        data_offset = 0x20 + (colors * 3 if palette else 0)
        
        metadata = {
            'size': data_offset + len(compressed_data),
            'width': width,
            'height': height,
            'colors': colors,
            'bpp': bpp,
            'is_compressed': True,
            'data_offset': data_offset,
            'data_length': len(compressed_data)
        }
        
        with open(output_path, 'wb') as file:
            write_cm_metadata(file, metadata)
            if palette:
                file.write(palette)
            file.write(compressed_data)
        
        print(f"Converted: {input_path} -> {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Convert PNG files to CM format.")
    parser.add_argument("input_dir", help="Input directory containing PNG files")
    parser.add_argument("output_dir", help="Output directory for CM files")
    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist.")
        sys.exit(1)

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    for filename in os.listdir(args.input_dir):
        if filename.lower().endswith('.png'):
            input_path = os.path.join(args.input_dir, filename)
            output_path = os.path.join(args.output_dir, os.path.splitext(filename)[0] + '.cm')
            convert_png_to_cm(input_path, output_path)

if __name__ == "__main__":
    main()
