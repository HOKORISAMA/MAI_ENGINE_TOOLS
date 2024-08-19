import os
import sys
import argparse
from struct import unpack
from PIL import Image

def read_cm_metadata(file):
    header = file.read(0x20)
    if header[0:2] != b'CM' or header[0x0E] != 1:
        return None
    
    size = unpack('<I', header[2:6])[0]
    if size != os.path.getsize(file.name):
        return None
    
    return {
        'width': unpack('<H', header[6:8])[0],
        'height': unpack('<H', header[8:10])[0],
        'colors': unpack('<H', header[0x0A:0x0C])[0],
        'bpp': header[0x0C],
        'is_compressed': bool(header[0x0D]),
        'data_offset': unpack('<I', header[0x10:0x14])[0],
        'data_length': unpack('<I', header[0x14:0x18])[0]
    }

def rle_decode(input_data, pixel_size):
    output = bytearray()
    i = 0
    while i < len(input_data):
        code = input_data[i]
        i += 1
        if code < 0x80:
            output.extend(input_data[i:i+code*pixel_size])
            i += code * pixel_size
        else:
            count = code & 0x7f
            pixel = input_data[i:i+pixel_size]
            i += pixel_size
            output.extend(pixel * count)
    return output

from PIL import Image

def convert_cm_to_png(input_path, output_path):
    with open(input_path, 'rb') as file:
        metadata = read_cm_metadata(file)
        if not metadata:
            print(f"Invalid CM file: {input_path}")
            return
        
        file.seek(0x20)
        if metadata['colors'] > 0:
            palette = file.read(metadata['colors'] * 3)
            # Swap R and B in the palette
            palette = b''.join(palette[i:i+3][::-1] for i in range(0, len(palette), 3))
        else:
            palette = None
        
        file.seek(metadata['data_offset'])
        image_data = file.read(metadata['data_length'])
        
        if metadata['is_compressed']:
            image_data = rle_decode(image_data, metadata['bpp'] // 8)
        
        if metadata['bpp'] == 24:
            # Swap R and B for 24-bit images
            image_data = b''.join(image_data[i:i+3][::-1] for i in range(0, len(image_data), 3))
            mode = 'RGB'
        else:
            mode = 'P'
        
        image = Image.frombytes(mode, (metadata['width'], metadata['height']), image_data)
        
        if palette:
            image.putpalette(palette)
        
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
        
        if mode == 'P':
            # Convert indexed image to RGB
            image = image.convert('RGB')
        
        image.save(output_path, 'PNG')
        print(f"Converted: {input_path} -> {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Convert CM files to PNG format.")
    parser.add_argument("input_dir", help="Input directory containing CM files")
    parser.add_argument("output_dir", help="Output directory for PNG files")
    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist.")
        sys.exit(1)

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    for filename in os.listdir(args.input_dir):
        if filename.lower().endswith('.cm'):
            input_path = os.path.join(args.input_dir, filename)
            output_path = os.path.join(args.output_dir, os.path.splitext(filename)[0] + '.png')
            convert_cm_to_png(input_path, output_path)

if __name__ == "__main__":
    main()
