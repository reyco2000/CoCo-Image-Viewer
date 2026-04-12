"""
TRS-80 Color Computer DSK/JVC disk image handler.
"""

import struct
from dataclasses import dataclass
from typing import List, Optional, Tuple


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


class DSKImage:
    """Handler for TRS-80 Color Computer DSK/JVC disk images"""

    SECTOR_SIZE = 256
    GRANULE_SECTORS = 9
    GRANULE_SIZE = SECTOR_SIZE * GRANULE_SECTORS

    DIR_TRACK = 17
    FAT_SECTOR = 2
    DIR_START_SECTOR = 3
    DIR_END_SECTOR = 11
    ENTRY_SIZE = 32

    def __init__(self, filename: str):
        self.filename = filename
        self.header = JVCHeader()
        self.data = b""
        self.fat = []
        self.directory = []

    def mount(self) -> bool:
        """Mount (open and parse) a DSK/JVC image file"""
        try:
            with open(self.filename, "rb") as f:
                self.data = f.read()
            self._parse_jvc_header()
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
        offset = self.header.header_size
        sectors_per_track = self.header.sectors_per_track
        sector_num = (track * sectors_per_track) + (sector - 1)
        offset += sector_num * self.SECTOR_SIZE
        return offset

    def read_sector(self, track: int, sector: int) -> bytes:
        """Read a specific sector from the disk image"""
        offset = self._get_sector_offset(track, sector)
        return self.data[offset : offset + self.SECTOR_SIZE]

    def _read_fat(self):
        """Read the File Allocation Table from track 17, sector 2"""
        fat_sector = self.read_sector(self.DIR_TRACK, self.FAT_SECTOR)
        self.fat = list(fat_sector[:68])

    def _read_directory(self):
        """Read directory entries from track 17, sectors 3-11"""
        self.directory = []
        for sector_num in range(self.DIR_START_SECTOR, self.DIR_END_SECTOR + 1):
            sector_data = self.read_sector(self.DIR_TRACK, sector_num)
            for i in range(8):
                offset = i * self.ENTRY_SIZE
                entry_data = sector_data[offset : offset + self.ENTRY_SIZE]
                if entry_data[0] not in (0x00, 0xFF):
                    entry = self._parse_directory_entry(entry_data)
                    if entry:
                        self.directory.append(entry)

    def _parse_directory_entry(self, data: bytes) -> Optional[DirectoryEntry]:
        """Parse a 32-byte directory entry"""
        if len(data) != self.ENTRY_SIZE:
            return None
        filename = data[0x00:0x08].decode("ascii", errors="ignore").rstrip()
        extension = data[0x08:0x0B].decode("ascii", errors="ignore").rstrip()
        file_type = data[0x0B]
        ascii_flag = data[0x0C]
        first_granule = data[0x0D]
        last_sector_bytes = struct.unpack(">H", data[0x0E:0x10])[0]
        if first_granule > 67:
            return None
        return DirectoryEntry(
            filename=filename,
            extension=extension,
            file_type=file_type,
            ascii_flag=ascii_flag,
            first_granule=first_granule,
            last_sector_bytes=last_sector_bytes,
        )

    def _get_granule_chain(self, first_granule: int) -> List[Tuple[int, int]]:
        """Follow the FAT chain to get all granules for a file."""
        chain = []
        current_granule = first_granule
        while current_granule != 0xFF:
            fat_entry = self.fat[current_granule]
            if 0xC0 <= fat_entry <= 0xC9:
                sectors_used = fat_entry & 0x0F
                if sectors_used == 0:
                    sectors_used = self.GRANULE_SECTORS
                chain.append((current_granule, sectors_used))
                break
            elif fat_entry <= 67:
                chain.append((current_granule, self.GRANULE_SECTORS))
                current_granule = fat_entry
            else:
                break
        return chain

    def _granule_to_track_sector(self, granule: int) -> Tuple[int, int]:
        """Convert granule number to starting track and sector"""
        if granule < 34:
            track = granule // 2
        else:
            track = (granule // 2) + 1
        granule_on_track = granule % 2
        start_sector = (granule_on_track * self.GRANULE_SECTORS) + 1
        return track, start_sector

    def extract_file(self, entry: DirectoryEntry) -> bytes:
        """Extract file data from the disk image"""
        file_data = bytearray()
        chain = self._get_granule_chain(entry.first_granule)
        for granule_num, sectors_used in chain:
            track, start_sector = self._granule_to_track_sector(granule_num)
            for i in range(sectors_used):
                sector_data = self.read_sector(track, start_sector + i)
                file_data.extend(sector_data)
        if entry.last_sector_bytes > 0 and len(file_data) > 0:
            full_sectors = (len(file_data) // self.SECTOR_SIZE) - 1
            actual_size = (full_sectors * self.SECTOR_SIZE) + entry.last_sector_bytes
            file_data = file_data[:actual_size]
        return bytes(file_data)
