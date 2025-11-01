#!/usr/bin/env python3
"""
TRS-80 Color Computer DSK/JVC File System Tool

Based on the dsktools library by mseminatore
https://github.com/mseminatore/dsktools/

This script allows you to:
- Mount and inspect DSK/JVC disk images
- Copy files from DSK to PC
- Upload files from PC to DSK

DSK Format Details:
- Sector size: 256 bytes
- Default format: 35 tracks, 18 sectors/track (160K)
- Directory: Track 17
- FAT: Track 17, Sector 2
- Directory entries: Track 17, Sectors 3-11
"""

import struct
import os
import sys
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass


@dataclass
class JVCHeader:
    """JVC disk image header structure"""
    sectors_per_track: int = 18
    side_count: int = 1
    sector_size: int = 256
    first_sector_id: int = 1
    sector_attribute: int = 0
    header_size: int = 0


@dataclass
class DirectoryEntry:
    """DECB directory entry structure"""
    filename: str
    extension: str
    file_type: int
    ascii_flag: int
    first_granule: int
    last_sector_bytes: int

    def __str__(self):
        file_type_names = {
            0x00: "BASIC",
            0x01: "DATA",
            0x02: "ML",
            0x03: "TEXT"
        }
        type_name = file_type_names.get(self.file_type, f"UNK({self.file_type:02X})")
        ascii_str = "ASCII" if self.ascii_flag == 0xFF else "BIN"
        full_name = f"{self.filename}.{self.extension}" if self.extension else self.filename
        return f"{full_name:<12} {type_name:<6} {ascii_str:<5} Gran:{self.first_granule:2d}"


class DSKImage:
    """Handler for TRS-80 Color Computer DSK/JVC disk images"""

    SECTOR_SIZE = 256
    GRANULE_SECTORS = 9  # 9 sectors per granule
    GRANULE_SIZE = SECTOR_SIZE * GRANULE_SECTORS  # 2304 bytes

    # Directory track is always track 17
    DIR_TRACK = 17
    FAT_SECTOR = 2  # FAT is in sector 2 of track 17
    DIR_START_SECTOR = 3  # Directory entries start at sector 3
    DIR_END_SECTOR = 11  # Directory entries end at sector 11

    ENTRY_SIZE = 32  # Each directory entry is 32 bytes

    def __init__(self, filename: str):
        self.filename = filename
        self.header = JVCHeader()
        self.data = b''
        self.fat = []
        self.directory = []

    def mount(self) -> bool:
        """Mount (open and parse) a DSK/JVC image file"""
        try:
            with open(self.filename, 'rb') as f:
                self.data = f.read()

            # Parse JVC header if present
            self._parse_jvc_header()

            # Read FAT and directory
            self._read_fat()
            self._read_directory()

            return True
        except Exception as e:
            print(f"Error mounting DSK image: {e}")
            return False

    def _parse_jvc_header(self):
        """Parse JVC header (if present)"""
        file_size = len(self.data)
        header_size = file_size % 256

        self.header.header_size = header_size

        if header_size > 0:
            # Read header bytes
            if header_size >= 1:
                self.header.sectors_per_track = self.data[0]
            if header_size >= 2:
                self.header.side_count = self.data[1]
            if header_size >= 3:
                sector_size_code = self.data[2]
                self.header.sector_size = 128 << sector_size_code
            if header_size >= 4:
                self.header.first_sector_id = self.data[3]
            if header_size >= 5:
                self.header.sector_attribute = self.data[4]

    def _get_sector_offset(self, track: int, sector: int) -> int:
        """Calculate byte offset for a given track and sector"""
        # Skip JVC header
        offset = self.header.header_size

        # Calculate sector number (sectors are numbered from 1)
        sectors_per_track = self.header.sectors_per_track
        sector_num = (track * sectors_per_track) + (sector - 1)

        offset += sector_num * self.SECTOR_SIZE
        return offset

    def read_sector(self, track: int, sector: int) -> bytes:
        """Read a specific sector from the disk image"""
        offset = self._get_sector_offset(track, sector)
        return self.data[offset:offset + self.SECTOR_SIZE]

    def write_sector(self, track: int, sector: int, data: bytes):
        """Write data to a specific sector"""
        if len(data) != self.SECTOR_SIZE:
            raise ValueError(f"Sector data must be {self.SECTOR_SIZE} bytes")

        offset = self._get_sector_offset(track, sector)
        # Convert to bytearray for modification
        data_array = bytearray(self.data)
        data_array[offset:offset + self.SECTOR_SIZE] = data
        self.data = bytes(data_array)

    def _read_fat(self):
        """Read the File Allocation Table from track 17, sector 2"""
        fat_sector = self.read_sector(self.DIR_TRACK, self.FAT_SECTOR)
        # FAT is first 68 bytes
        self.fat = list(fat_sector[:68])

    def _read_directory(self):
        """Read directory entries from track 17, sectors 3-11"""
        self.directory = []

        for sector_num in range(self.DIR_START_SECTOR, self.DIR_END_SECTOR + 1):
            sector_data = self.read_sector(self.DIR_TRACK, sector_num)

            # Each sector can hold 8 directory entries (256 / 32 = 8)
            for i in range(8):
                offset = i * self.ENTRY_SIZE
                entry_data = sector_data[offset:offset + self.ENTRY_SIZE]

                # Check if entry is valid (first byte != 0x00 and != 0xFF)
                if entry_data[0] not in (0x00, 0xFF):
                    entry = self._parse_directory_entry(entry_data)
                    if entry:
                        self.directory.append(entry)

    def _parse_directory_entry(self, data: bytes) -> Optional[DirectoryEntry]:
        """Parse a 32-byte directory entry"""
        if len(data) != self.ENTRY_SIZE:
            return None

        # Extract fields
        filename = data[0x00:0x08].decode('ascii', errors='ignore').rstrip()
        extension = data[0x08:0x0B].decode('ascii', errors='ignore').rstrip()
        file_type = data[0x0B]
        ascii_flag = data[0x0C]
        first_granule = data[0x0D]
        last_sector_bytes = struct.unpack('>H', data[0x0E:0x10])[0]

        # Validate first granule (must be 0-67)
        if first_granule > 67:
            return None

        return DirectoryEntry(
            filename=filename,
            extension=extension,
            file_type=file_type,
            ascii_flag=ascii_flag,
            first_granule=first_granule,
            last_sector_bytes=last_sector_bytes
        )

    def list_files(self):
        """Display directory listing"""
        if not self.directory:
            print("No files found.")
            return

        print(f"\nDirectory of {self.filename}")
        print("=" * 60)
        print(f"{'Filename':<12} {'Type':<6} {'Mode':<5} {'Info'}")
        print("-" * 60)

        for entry in self.directory:
            print(entry)

        print("-" * 60)
        print(f"Total files: {len(self.directory)}")

        # Calculate free space
        free_granules = sum(1 for g in self.fat if g == 0xFF)
        free_bytes = free_granules * self.GRANULE_SIZE
        print(f"Free granules: {free_granules} ({free_bytes} bytes)")

    def _get_granule_chain(self, first_granule: int) -> List[Tuple[int, int]]:
        """
        Follow the FAT chain starting from first_granule.
        Returns list of (granule_num, sectors_used) tuples.
        """
        chain = []
        current_granule = first_granule

        while current_granule != 0xFF:
            fat_entry = self.fat[current_granule]

            # Check if this is the last granule in the chain
            if fat_entry >= 0xC0 and fat_entry <= 0xC9:
                # Last granule - lower 4 bits indicate sectors used
                sectors_used = (fat_entry & 0x0F)
                if sectors_used == 0:
                    sectors_used = self.GRANULE_SECTORS
                chain.append((current_granule, sectors_used))
                break
            elif fat_entry <= 67:
                # Points to next granule
                chain.append((current_granule, self.GRANULE_SECTORS))
                current_granule = fat_entry
            else:
                # Invalid FAT entry
                break

        return chain

    def _granule_to_track_sector(self, granule: int) -> Tuple[int, int]:
        """Convert granule number to starting track and sector"""
        # Each track has 2 granules, track 17 is reserved for directory
        # Granules 0-1 are on track 0, 2-3 on track 1, etc.
        # But skip track 17 (granules 34-35)

        if granule < 34:  # Before directory track
            track = granule // 2
        else:  # After directory track
            track = (granule // 2) + 1

        granule_on_track = granule % 2
        start_sector = (granule_on_track * self.GRANULE_SECTORS) + 1

        return track, start_sector

    def extract_file(self, entry: DirectoryEntry) -> bytes:
        """Extract file data from the disk image"""
        file_data = bytearray()

        # Get the granule chain
        chain = self._get_granule_chain(entry.first_granule)

        for granule_num, sectors_used in chain:
            track, start_sector = self._granule_to_track_sector(granule_num)

            # Read sectors from this granule
            for i in range(sectors_used):
                sector_data = self.read_sector(track, start_sector + i)
                file_data.extend(sector_data)

        # Trim to actual file size based on last_sector_bytes
        if entry.last_sector_bytes > 0 and len(file_data) > 0:
            # Calculate actual file size
            full_sectors = (len(file_data) // self.SECTOR_SIZE) - 1
            actual_size = (full_sectors * self.SECTOR_SIZE) + entry.last_sector_bytes
            file_data = file_data[:actual_size]

        return bytes(file_data)

    def copy_to_pc(self, dsk_filename: str, pc_path: str) -> bool:
        """Copy a file from DSK image to PC"""
        # Find the file in directory
        entry = None
        for e in self.directory:
            full_name = f"{e.filename}.{e.extension}" if e.extension else e.filename
            if full_name.upper() == dsk_filename.upper():
                entry = e
                break

        if not entry:
            print(f"File '{dsk_filename}' not found in DSK image.")
            return False

        try:
            # Extract file data
            file_data = self.extract_file(entry)

            # Write to PC file
            with open(pc_path, 'wb') as f:
                f.write(file_data)

            print(f"Copied '{dsk_filename}' to '{pc_path}' ({len(file_data)} bytes)")
            return True
        except Exception as e:
            print(f"Error copying file: {e}")
            return False

    def _find_free_granules(self, count: int) -> List[int]:
        """Find specified number of free granules"""
        free = []
        for i, fat_entry in enumerate(self.fat):
            if fat_entry == 0xFF:
                free.append(i)
                if len(free) >= count:
                    break
        return free

    def _find_free_directory_slot(self) -> Optional[Tuple[int, int]]:
        """Find a free directory entry slot. Returns (sector, offset) or None"""
        for sector_num in range(self.DIR_START_SECTOR, self.DIR_END_SECTOR + 1):
            sector_data = self.read_sector(self.DIR_TRACK, sector_num)

            for i in range(8):
                offset = i * self.ENTRY_SIZE
                first_byte = sector_data[offset]

                # Empty slot is marked with 0x00 or 0xFF
                if first_byte in (0x00, 0xFF):
                    return (sector_num, offset)

        return None

    def upload_from_pc(self, pc_path: str, dsk_filename: Optional[str] = None,
                      file_type: int = 0x02, ascii_flag: int = 0x00) -> bool:
        """
        Upload a file from PC to DSK image.

        Args:
            pc_path: Path to PC file
            dsk_filename: Name to use in DSK (default: use PC filename)
            file_type: 0x00=BASIC, 0x01=DATA, 0x02=ML, 0x03=TEXT
            ascii_flag: 0x00=binary, 0xFF=ASCII
        """
        try:
            # Read PC file
            with open(pc_path, 'rb') as f:
                file_data = f.read()

            file_size = len(file_data)

            # Determine DSK filename
            if not dsk_filename:
                dsk_filename = os.path.basename(pc_path).upper()

            # Split into name and extension (8.3 format)
            if '.' in dsk_filename:
                name, ext = dsk_filename.rsplit('.', 1)
            else:
                name, ext = dsk_filename, ''

            name = name[:8].ljust(8)
            ext = ext[:3].ljust(3)

            # Calculate granules needed
            granules_needed = (file_size + self.GRANULE_SIZE - 1) // self.GRANULE_SIZE

            # Find free granules
            free_granules = self._find_free_granules(granules_needed)
            if len(free_granules) < granules_needed:
                print(f"Not enough free space. Need {granules_needed} granules, found {len(free_granules)}")
                return False

            # Find free directory slot
            dir_slot = self._find_free_directory_slot()
            if not dir_slot:
                print("Directory is full")
                return False

            # Write file data to granules
            data_offset = 0
            for i, granule_num in enumerate(free_granules):
                track, start_sector = self._granule_to_track_sector(granule_num)

                # Determine how many sectors to write in this granule
                remaining = file_size - data_offset
                sectors_to_write = min(self.GRANULE_SECTORS,
                                      (remaining + self.SECTOR_SIZE - 1) // self.SECTOR_SIZE)

                # Write sectors
                for s in range(sectors_to_write):
                    sector_data = file_data[data_offset:data_offset + self.SECTOR_SIZE]
                    # Pad last sector if needed
                    if len(sector_data) < self.SECTOR_SIZE:
                        sector_data = sector_data.ljust(self.SECTOR_SIZE, b'\x00')

                    self.write_sector(track, start_sector + s, sector_data)
                    data_offset += len(file_data[data_offset:data_offset + self.SECTOR_SIZE])

                # Update FAT
                if i < len(free_granules) - 1:
                    # Point to next granule
                    self.fat[granule_num] = free_granules[i + 1]
                else:
                    # Last granule - mark with 0xC0 + sectors used
                    last_sector_size = file_size % self.SECTOR_SIZE
                    sectors_in_last = sectors_to_write if last_sector_size == 0 else sectors_to_write
                    self.fat[granule_num] = 0xC0 | sectors_in_last

            # Calculate last sector bytes
            last_sector_bytes = file_size % self.SECTOR_SIZE
            if last_sector_bytes == 0 and file_size > 0:
                last_sector_bytes = self.SECTOR_SIZE

            # Create directory entry
            entry_data = bytearray(self.ENTRY_SIZE)
            entry_data[0x00:0x08] = name.encode('ascii')
            entry_data[0x08:0x0B] = ext.encode('ascii')
            entry_data[0x0B] = file_type
            entry_data[0x0C] = ascii_flag
            entry_data[0x0D] = free_granules[0]
            entry_data[0x0E:0x10] = struct.pack('>H', last_sector_bytes)
            entry_data[0x10:0x20] = b'\xFF' * 16

            # Write directory entry
            dir_sector_num, dir_offset = dir_slot
            sector_data = bytearray(self.read_sector(self.DIR_TRACK, dir_sector_num))
            sector_data[dir_offset:dir_offset + self.ENTRY_SIZE] = entry_data
            self.write_sector(self.DIR_TRACK, dir_sector_num, bytes(sector_data))

            # Write updated FAT
            fat_sector_data = bytearray(self.read_sector(self.DIR_TRACK, self.FAT_SECTOR))
            fat_sector_data[:68] = bytes(self.fat)
            self.write_sector(self.DIR_TRACK, self.FAT_SECTOR, bytes(fat_sector_data))

            print(f"Uploaded '{pc_path}' as '{name.strip()}.{ext.strip()}' ({file_size} bytes, {granules_needed} granules)")

            # Re-read directory
            self._read_directory()

            return True

        except Exception as e:
            print(f"Error uploading file: {e}")
            import traceback
            traceback.print_exc()
            return False

    def save(self, filename: Optional[str] = None):
        """Save the disk image to file"""
        save_path = filename or self.filename
        try:
            with open(save_path, 'wb') as f:
                f.write(self.data)
            print(f"DSK image saved to '{save_path}'")
        except Exception as e:
            print(f"Error saving DSK image: {e}")


def main():
    """Command-line interface"""
    import argparse

    parser = argparse.ArgumentParser(
        description='TRS-80 Color Computer DSK/JVC File System Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # List files in a DSK image
  python coco_dsk.py mydisk.dsk -l

  # Copy file from DSK to PC
  python coco_dsk.py mydisk.dsk -g HELLO.BAS -o hello.bas

  # Upload file from PC to DSK
  python coco_dsk.py mydisk.dsk -p program.bin -n PROG.BIN -t 2

File Types:
  0 = BASIC program
  1 = BASIC data
  2 = Machine code (default)
  3 = Text/ASCII
        '''
    )

    parser.add_argument('dsk_file', help='DSK/JVC image file')
    parser.add_argument('-l', '--list', action='store_true', help='List files in DSK image')
    parser.add_argument('-g', '--get', metavar='DSK_FILE', help='Copy file from DSK to PC')
    parser.add_argument('-o', '--output', metavar='PC_FILE', help='Output filename for -g')
    parser.add_argument('-p', '--put', metavar='PC_FILE', help='Upload file from PC to DSK')
    parser.add_argument('-n', '--name', metavar='DSK_NAME', help='Name to use in DSK for -p')
    parser.add_argument('-t', '--type', type=int, default=2, choices=[0,1,2,3],
                       help='File type for -p (0=BASIC, 1=DATA, 2=ML, 3=TEXT)')
    parser.add_argument('-a', '--ascii', action='store_true', help='Mark file as ASCII for -p')
    parser.add_argument('-s', '--save', metavar='OUTPUT_DSK', help='Save modified DSK to new file')

    args = parser.parse_args()

    # Mount the DSK image
    dsk = DSKImage(args.dsk_file)

    if not os.path.exists(args.dsk_file):
        print(f"Error: File '{args.dsk_file}' not found")
        return 1

    if not dsk.mount():
        return 1

    # Execute commands
    if args.list:
        dsk.list_files()

    if args.get:
        output = args.output or args.get
        dsk.copy_to_pc(args.get, output)

    if args.put:
        ascii_flag = 0xFF if args.ascii else 0x00
        if dsk.upload_from_pc(args.put, args.name, args.type, ascii_flag):
            # Save changes
            save_file = args.save or args.dsk_file
            dsk.save(save_file)

    if args.save and not args.put:
        dsk.save(args.save)

    return 0


if __name__ == '__main__':
    sys.exit(main())
