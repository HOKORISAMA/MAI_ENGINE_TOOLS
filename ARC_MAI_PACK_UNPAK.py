import os
import struct
import argparse

class ArchiveFormat:
    def __init__(self):
        self.tag = None
        self.description = None
        self.signature = None
        self.is_hierarchic = False
        self.can_write = False

class ArcOpener(ArchiveFormat):
    def __init__(self):
        super().__init__()
        self.tag = "MAI"
        self.description = "MAI resource archive"
        self.signature = 0x0a49414d  # 'MAI\x0a'
        self.is_hierarchic = True
        self.can_write = False
        self.extensions = ["arc"]

    def try_open(self, file):
        file_size = self.read_uint32(file, 4)
        if file_size != os.path.getsize(file):
            return None

        count = self.read_int32(file, 8)
        if count <= 0 or count > 0xfffff:
            return None

        dir_level = self.read_byte(file, 0x0d)
        dir_entries = self.read_uint16(file, 0x0e)
        index_offset = 0x10
        index_size = count * 0x18 + dir_entries * 8
        if index_size > os.path.getsize(file) - index_offset:
            return None

        folders = None
        if dir_entries != 0 and dir_level == 2:
            folders = []
            dir_offset = index_offset + count * 0x18
            for _ in range(dir_entries):
                name = self.read_string(file, dir_offset, 4)
                index = self.read_int32(file, dir_offset + 4)
                folders.append({'name': name, 'index': index})
                dir_offset += 8

        is_mask_arc = os.path.basename(file).lower() == "mask.arc"
        dir = []
        next_folder = count if folders is None else folders[0]['index']
        folder = 0
        current_folder = ""

        for i in range(count):
            while i >= next_folder and folder < len(folders):
                current_folder = folders[folder]['name']
                folder += 1
                next_folder = count if folder == len(folders) else folders[folder]['index']

            name = self.read_string(file, index_offset, 0x10)
            if len(name) == 0:
                return None

            offset = self.read_uint32(file, index_offset + 0x10)
            size = self.read_uint32(file, index_offset + 0x14)
            entry = {
                'name': os.path.join(current_folder, name),
                'offset': offset,
                'size': size,
                'type': self.detect_file_type(file, offset) if not is_mask_arc else 'MSK/MAI'
            }

            if not self.check_placement(entry, os.path.getsize(file)):
                return None

            dir.append(entry)
            index_offset += 0x18

        return {'file': file, 'entries': dir}

    def read_uint32(self, file, offset):
        with open(file, 'rb') as f:
            f.seek(offset)
            return struct.unpack('<I', f.read(4))[0]

    def read_int32(self, file, offset):
        with open(file, 'rb') as f:
            f.seek(offset)
            return struct.unpack('<i', f.read(4))[0]

    def read_uint16(self, file, offset):
        with open(file, 'rb') as f:
            f.seek(offset)
            return struct.unpack('<H', f.read(2))[0]

    def read_byte(self, file, offset):
        with open(file, 'rb') as f:
            f.seek(offset)
            return struct.unpack('<B', f.read(1))[0]

    def read_string(self, file, offset, length):
        with open(file, 'rb') as f:
            f.seek(offset)
            return f.read(length).decode('ascii').rstrip('\x00')

    def detect_file_type(self, file, offset):
        signature = self.read_uint32(file, offset)
        signature_type = signature & 0xFFFF
        if signature_type == 0x4D43:
            return '.cm'
        elif signature_type == 0x4D41:
            return '.am'
        elif signature_type == 0x4D42:
            return '.bmp'
        elif signature_type == 0x10B4:
            return '.msk'
        else:
            return '.bin'  # Default extension for unknown types

    def check_placement(self, entry, max_offset):
        return entry['offset'] + entry['size'] <= max_offset

    def extract_files(self, arc_file, output_dir):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(arc_file['file'], 'rb') as f:
            for entry in arc_file['entries']:
                f.seek(entry['offset'])
                data = f.read(entry['size'])
                file_path = os.path.join(output_dir, entry['name'] + entry['type'])

                # Ensure the directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                with open(file_path, 'wb') as out_file:
                    out_file.write(data)

    def pack_files(self, directory, archive_name):
        entries = []
        current_offset = 0x10  # Start of the index (header size)

        # Collect all files and their data
        for root, _, files in os.walk(directory):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                # Remove file extension from relative path
                relative_path = os.path.splitext(os.path.relpath(file_path, directory).replace("\\", "/"))[0]
                with open(file_path, 'rb') as f:
                    data = f.read()
                    entries.append({
                        'name': relative_path,
                        'size': len(data),
                        'data': data
                    })

        # Calculate the index size
        index_size = len(entries) * 0x18  # 24 bytes per entry (16 bytes for name + 8 bytes for offset/size)

        # Calculate the starting offset for the file data (after the index)
        data_offset = current_offset + index_size

        # Assign offsets to each entry
        for entry in entries:
            entry['offset'] = data_offset
            data_offset += entry['size']

        # Calculate the total file size
        total_size = data_offset

        with open(archive_name, 'wb') as archive:
            # Write the signature
            archive.write(struct.pack('<I', self.signature))  # MAI signature
            # Write the total size of the archive
            archive.write(struct.pack('<I', total_size))  # Archive size
            # Write the number of entries
            archive.write(struct.pack('<I', len(entries)))  # Number of entries
            # Write reserved bytes (not used)
            archive.write(b'\x00\x01\x00\x00')

            # Write the index
            for entry in entries:
                archive.write(entry['name'].ljust(0x10, '\x00').encode('cp932'))
                archive.write(struct.pack('<I', entry['offset']))
                archive.write(struct.pack('<I', entry['size']))

            # Write the file data
            for entry in entries:
                archive.write(entry['data'])

# CLI setup
def main():
    parser = argparse.ArgumentParser(description="MAI Archive Tool")
    subparsers = parser.add_subparsers(dest='command')

    # Unpacker
    unpack_parser = subparsers.add_parser('unpack', help='Unpack a MAI archive')
    unpack_parser.add_argument("archive", help="Path to the MAI archive file")
    unpack_parser.add_argument("output_dir", help="Directory to extract files to")

    # Packer
    pack_parser = subparsers.add_parser('pack', help='Pack files into a MAI archive')
    pack_parser.add_argument("directory", help="Directory to pack into the archive")
    pack_parser.add_argument("archive", help="Name of the output MAI archive file")

    args = parser.parse_args()

    arc_opener = ArcOpener()

    if args.command == 'unpack':
        arc_file = arc_opener.try_open(args.archive)
        if arc_file:
            print(f"Extracting {len(arc_file['entries'])} files to '{args.output_dir}'")
            arc_opener.extract_files(arc_file, args.output_dir)
            print("Extraction complete")
        else:
            print("Failed to open archive")

    elif args.command == 'pack':
        print(f"Packing files from '{args.directory}' into archive '{args.archive}'")
        arc_opener.pack_files(args.directory, args.archive)
        print("Packing complete")

if __name__ == "__main__":
    main()
