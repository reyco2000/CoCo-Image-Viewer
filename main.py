
import struct
from typing import Optional, List, Tuple
from dataclasses import dataclass
import argparse
import sys
from io import BytesIO
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog

# --- From coco_dsk.py ---

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
        self.data = b''
        self.fat = []
        self.directory = []

    def mount(self) -> bool:
        """Mount (open and parse) a DSK/JVC image file"""
        try:
            with open(self.filename, 'rb') as f:
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
        return self.data[offset:offset + self.SECTOR_SIZE]

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
                entry_data = sector_data[offset:offset + self.ENTRY_SIZE]
                if entry_data[0] not in (0x00, 0xFF):
                    entry = self._parse_directory_entry(entry_data)
                    if entry:
                        self.directory.append(entry)

    def _parse_directory_entry(self, data: bytes) -> Optional[DirectoryEntry]:
        """Parse a 32-byte directory entry"""
        if len(data) != self.ENTRY_SIZE:
            return None
        filename = data[0x00:0x08].decode('ascii', errors='ignore').rstrip()
        extension = data[0x08:0x0B].decode('ascii', errors='ignore').rstrip()
        file_type = data[0x0B]
        ascii_flag = data[0x0C]
        first_granule = data[0x0D]
        last_sector_bytes = struct.unpack('>H', data[0x0E:0x10])[0]
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

    def _get_granule_chain(self, first_granule: int) -> List[Tuple[int, int]]:
        """Follow the FAT chain to get all granules for a file."""
        chain = []
        current_granule = first_granule
        while current_granule != 0xFF:
            fat_entry = self.fat[current_granule]
            if 0xC0 <= fat_entry <= 0xC9:
                sectors_used = (fat_entry & 0x0F)
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

# --- From maxtoppm_source.py ---

def getbit(v, b):
    return (v >> b) & 1

def pack(c):
    return bytes(c)

def convert_max_to_ppm(
    input_image_stream,
    arte, newsroom, cols, rows, skip, ignore_header_errors
):
    def clip(v):
        return 255 if v > 255 else (0 if v < 0 else v)

    br2 = [pack(x) for x in [[0, 0, 0], [255, 85, 0], [0, 170, 255], [255, 255, 255]]]
    br3 = [pack(x) for x in [[0, 0, 0], [255, 0, 0], [0, 0, 255], [255, 255, 255]]]
    semig = [
        pack(x)
        for x in [
            [0, 0, 0],
            [0, 255, 0],
            [255, 255, 0],
            [0, 0, 255],
            [255, 0, 0],
            [255, 255, 255],
            [0, 211, 170],
            [204, 0, 255],
            [255, 128, 0],
        ]
    ]

    f = BytesIO(input_image_stream)
    out = BytesIO()

    if skip:
        f.read(skip)

    if newsroom:
        head = f.read(2)
        cols = head[0] * 8
        rows = head[1]
    else:
        head = f.read(5)
        if head[0] != 0:
            if not ignore_header_errors:
                return None, None, None
        if not rows:
            size = head[1] * 256 + head[2]
            rows = 8 * size // cols
            if cols * rows // 8 != size:
                if not ignore_header_errors:
                    return None, None, None

    out.write(f"P6\n{cols} {rows}\n255\n".encode('ascii'))
    for jj in range(rows):
        row_data = f.read(cols >> 3)
        oy = r2 = g2 = b2 = 0
        for v in row_data:
            if arte == 0: # PIXEL_MODE_BW
                for k in range(8):
                    out.write(br2[getbit(v, 7 - k) * 3])
            elif (arte == 1) or (arte == 2): # PIXEL_MODE_BR or PIXEL_MODE_RB
                x = -100 if arte == 1 else 100
                for k in range(8):
                    ny = getbit(v, 7 - k) * 255
                    y = (oy + ny + (ny >> 2)) >> 1
                    i = (x * (y - oy)) >> 7
                    r = clip(int((y + 0.9563 * i)))
                    g = clip(int((y - 0.2721 * i)))
                    b = clip(int((y - 1.1070 * i)))
                    out.write(pack([(r + r2) >> 1, (g + g2) >> 1, (b + b2) >> 1]))
                    oy = ny
                    x = -x
                    r2 = r
                    g2 = g
                    b2 = b
            # Add other pixel modes if needed

    return out.getvalue(), cols, rows

def convert_cm3_to_ppm(input_image_stream):
    """Convert CM3 (CoCoMax 3) format to PPM"""

    def dump(palette_index, palette, out):
        """Output RGB values for a palette index"""
        c = palette[palette_index]
        r = (getbit(c, 5) * 2 + getbit(c, 2)) * 85
        g = (getbit(c, 4) * 2 + getbit(c, 1)) * 85
        b = (getbit(c, 3) * 2 + getbit(c, 0)) * 85
        out.write(pack([r, g, b]))

    f = BytesIO(input_image_stream)
    out = BytesIO()

    # Read picture type byte
    cols = 320
    pictyp = f.read(1)[0]
    rows = (getbit(pictyp, 7) + 1) * 192  # 192 or 384 rows
    sans_motifs = getbit(pictyp, 0) != 0

    # Read palette (16 bytes)
    palette = [f.read(1)[0] for _ in range(16)]

    # Read animation and cycle data
    anirat = f.read(1)[0]
    cycrat = f.read(1)[0]
    cm3cyc = [f.read(1)[0] for _ in range(8)]
    aniflg = (f.read(1)[0] & 0x80) != 0
    cycflg = (f.read(1)[0] & 0x80) != 0

    # Skip motif data if present
    if not sans_motifs:
        f.read(243)

    # Initialize buffers for decompression
    linbuf = [0] * 160
    buff1 = [0] * 20
    buff2 = []

    # Write PPM header
    out.write(f"P6\n{cols} {rows}\n255\n".encode('ascii'))

    # Process image data
    for page in range(getbit(pictyp, 7) + 1):
        lines = f.read(1)[0]
        for line_idx in range(lines):
            u = 0
            y = 0
            bitu = 7
            bity = 7
            x = 0

            # Read control byte
            contr = f.read(1)[0]

            if contr < 128:
                # Compressed mode: read reference buffers
                for k in range(20):
                    buff1[k] = f.read(1)[0]
                buff2 = []
                for k in range(contr):
                    buff2.append(f.read(1)[0])

            # Decode 160 bytes (320 pixels, 2 pixels per byte)
            for k in range(160):
                if contr >= 128:
                    # Uncompressed mode: read directly
                    a = f.read(1)[0]
                else:
                    # Compressed mode: use reference buffers
                    cc = getbit(buff1[u], bitu)
                    bitu -= 1
                    if bitu < 0:
                        bitu = 7
                        u += 1

                    if cc == 0:
                        # Copy from previous pixel in line
                        a = linbuf[(x - 1) % 160]
                    else:
                        # Check second buffer
                        cc = getbit(buff2[y], bity)
                        bity -= 1
                        if bity < 0:
                            bity = 7
                            y += 1

                        if cc == 0:
                            # Copy from same position in previous line
                            a = linbuf[x]
                        else:
                            # Read new byte
                            a = f.read(1)[0]

                linbuf[x] = a
                # Each byte contains 2 pixels (4 bits each)
                dump(a >> 4, palette, out)  # High nibble
                dump(a & 15, palette, out)  # Low nibble
                x += 1

    return out.getvalue(), cols, rows

# ---------------------------------------------------------------------------
# MGE Format Conversion (ANIMTOOL-style MGE files)
# ---------------------------------------------------------------------------

# RGBCMP / CMPRGB tables (64 entries each) from 6809 ANIMTOOL
MGE_RGBCMP = [
    0x00, 0x0E, 0x02, 0x0E, 0x05, 0x10, 0x03, 0x10,
    0x0D, 0x0B, 0x1E, 0x1C, 0x0B, 0x0C, 0x1E, 0x1D,
    0x11, 0x11, 0x12, 0x22, 0x14, 0x13, 0x22, 0x21,
    0x2E, 0x2D, 0x2F, 0x1F, 0x2E, 0x2D, 0x2F, 0x2E,
    0x07, 0x06, 0x15, 0x06, 0x07, 0x18, 0x26, 0x1D,
    0x1A, 0x2B, 0x1B, 0x2B, 0x19, 0x09, 0x29, 0x2A,
    0x24, 0x23, 0x32, 0x33, 0x35, 0x36, 0x24, 0x25,
    0x20, 0x3C, 0x31, 0x3D, 0x38, 0x3B, 0x34, 0x3F,
]

MGE_CMPRGB = [
    0x00, 0x02, 0x02, 0x06, 0x00, 0x04, 0x21, 0x20,
    0x20, 0x2D, 0x05, 0x09, 0x0D, 0x08, 0x01, 0x00,
    0x07, 0x10, 0x12, 0x15, 0x14, 0x22, 0x26, 0x24,
    0x25, 0x2C, 0x28, 0x2A, 0x0B, 0x0F, 0x0A, 0x1B,
    0x38, 0x17, 0x13, 0x31, 0x30, 0x37, 0x26, 0x27,
    0x25, 0x2E, 0x2F, 0x29, 0x0B, 0x19, 0x18, 0x1A,
    0x3F, 0x3A, 0x32, 0x33, 0x3E, 0x34, 0x35, 0x3C,
    0x3C, 0x2E, 0x3D, 0x3D, 0x39, 0x3B, 0x3A, 0x3F,
]


def mge_gime_to_rgb(v: int):
    """Convert GIME palette value (0-63) to RGB888.

    Bit layout:
      Bit 5 = high Red, Bit 2 = low Red
      Bit 4 = high Green, Bit 1 = low Green
      Bit 3 = high Blue, Bit 0 = low Blue
    """
    v &= 0x3F  # ensure 0-63

    r = (((v >> 5) & 1) << 1) | ((v >> 2) & 1)
    g = (((v >> 4) & 1) << 1) | ((v >> 1) & 1)
    b = (((v >> 3) & 1) << 1) | ((v >> 0) & 1)

    scale = 85  # 0, 85, 170, 255
    return (r * scale, g * scale, b * scale)


def mge_convert_palette(pal16, file_monitor, target_monitor):
    """Convert 16-entry palette of GIME values if monitor types differ."""
    if file_monitor == target_monitor:
        return pal16[:]

    # 6809 logic:
    #   if file type == 0 (RGB)   -> use RGBCMP (RGB -> Composite)
    #   if file type != 0 (CMP)   -> use CMPRGB (Composite -> RGB)
    if file_monitor == 0:
        table = MGE_RGBCMP
    else:
        table = MGE_CMPRGB

    converted = []
    for v in pal16:
        v6 = v & 0x3F
        converted.append(table[v6])
    return converted


def mge_decode_bitmap(bitmap_data: bytes, compressed_flag: int) -> bytes:
    """Decode MGE bitmap data.

    compressed_flag == 0 : RLE (count,value) pairs, terminated by count=0
    compressed_flag != 0 : raw 32000 bytes
    """
    if compressed_flag == 0:
        out = []
        i = 0
        n = len(bitmap_data)
        while True:
            if i + 2 > n:
                break
            count = bitmap_data[i]
            value = bitmap_data[i + 1]
            i += 2

            if count == 0:
                break

            out.extend([value] * count)

        # Pad or truncate to 32000 bytes
        if len(out) < 32000:
            out.extend([0] * (32000 - len(out)))
        return bytes(out[:32000])
    else:
        if len(bitmap_data) < 32000:
            # Pad if too small
            return bitmap_data + bytes(32000 - len(bitmap_data))
        return bitmap_data[:32000]


def convert_mge_to_ppm(input_image_stream, target_monitor="R"):
    """Convert MGE (Graphics Exchange) format to PPM.

    MGE files are CoCo 3 ANIMTOOL-style 320x200x16 images.

    Args:
        input_image_stream: Raw bytes of the MGE file
        target_monitor: "R" for RGB or "C" for Composite display

    Returns:
        Tuple of (ppm_data, width, height) or (None, 0, 0) on error
    """
    f = BytesIO(input_image_stream)
    out = BytesIO()

    try:
        # 1. Resolution byte
        res_byte = f.read(1)
        if not res_byte:
            return None, 0, 0
        res = res_byte[0]
        if res != 0:
            print(f"Warning: MGE resolution byte {res} (expected 0 for 320x200)")
            return None, 0, 0

        # 2. 16-byte palette (GIME values 0-63)
        pal_data = f.read(16)
        if len(pal_data) != 16:
            return None, 0, 0
        pal16 = list(pal_data)

        # 3. File monitor type (0=RGB, 1=CMP)
        mon_byte = f.read(1)
        if not mon_byte:
            return None, 0, 0
        file_mon = 0 if mon_byte[0] == 0 else 1

        # 4. Compression flag
        comp_byte = f.read(1)
        if not comp_byte:
            return None, 0, 0
        comp_flag = comp_byte[0]

        # 5. 32-byte title string (skip for conversion)
        title_bytes = f.read(32)
        if len(title_bytes) != 32:
            return None, 0, 0

        # 6. Bitmap data
        bitmap_raw_data = f.read()
        bitmap_raw = mge_decode_bitmap(bitmap_raw_data, comp_flag)

        # 7. Palette conversion
        target_mon = 0 if target_monitor.upper() == "R" else 1
        pal_conv = mge_convert_palette(pal16, file_mon, target_mon)

        # 8. Build RGB palette
        rgb_palette = [mge_gime_to_rgb(v) for v in pal_conv]

        # 9. Expand bitmap -> 320x200 RGB pixels
        width, height = 320, 200

        # Write PPM header
        out.write(f"P6\n{width} {height}\n255\n".encode('ascii'))

        idx = 0
        for _y in range(height):
            for _x in range(0, width, 2):
                b = bitmap_raw[idx]
                idx += 1
                hi = (b >> 4) & 0x0F
                lo = b & 0x0F
                out.write(pack(list(rgb_palette[hi])))
                out.write(pack(list(rgb_palette[lo])))

        return out.getvalue(), width, height

    except Exception as e:
        print(f"Error converting MGE: {e}")
        return None, 0, 0


# ---------------------------------------------------------------------------
# MAC (MacPaint) Format Conversion
# ---------------------------------------------------------------------------

def mac_unpack_bits(data: bytes, expected_bytes: int) -> bytes:
    """Unpack PackBits compressed data.

    PackBits format:
    - If n >= 0 and n <= 127: copy the next n+1 bytes literally
    - If n >= -127 and n < 0: repeat the next byte 1-n times
    - If n == -128: no operation (skip)
    """
    result = bytearray()
    i = 0
    data_len = len(data)

    while i < data_len and len(result) < expected_bytes:
        n = data[i]
        i += 1

        # Convert to signed byte
        if n > 127:
            n = n - 256

        if n >= 0:
            # Literal run: copy n+1 bytes
            count = n + 1
            if i + count <= data_len:
                result.extend(data[i:i + count])
                i += count
            else:
                # Not enough data, take what we can
                result.extend(data[i:])
                break
        elif n > -128:
            # Repeat run: repeat next byte 1-n times
            count = 1 - n
            if i < data_len:
                result.extend([data[i]] * count)
                i += 1
        # n == -128 is a no-op

    # Pad or truncate to expected size
    if len(result) < expected_bytes:
        result.extend([0] * (expected_bytes - len(result)))
    return bytes(result[:expected_bytes])


def convert_mac_to_ppm(input_image_stream):
    """Convert MAC (MacPaint) format to PPM.

    MacPaint format:
    - Standard: 512-byte header + PackBits compressed bitmap
    - PNTG variant: "PNTG" signature, data at offset 0x280 (640)
    - 720 scanlines of 72 bytes each (576 pixels wide, 1 bit per pixel)
    - Total uncompressed bitmap: 720 * 72 = 51840 bytes

    Returns:
        Tuple of (ppm_data, width, height) or (None, 0, 0) on error
    """
    out = BytesIO()

    try:
        file_data = input_image_stream
        data_len = len(file_data)

        # MacPaint dimensions (fixed)
        width = 576
        height = 720
        bytes_per_row = 72  # 576 / 8
        expected_bytes = height * bytes_per_row  # 51840 bytes

        # Determine data offset based on format variant
        offset = 0

        # Check for PNTG variant (Mac resource fork format)
        if b'PNTG' in file_data[:128]:
            # PNTG format: data starts at offset 0x280 (640 bytes)
            offset = 0x280
        elif data_len > 512:
            # Standard MacPaint: 512-byte header
            # Check if this looks like a valid header by examining first bytes
            # MacPaint header typically starts with version number (0, 2, or 3)
            if file_data[0] in (0, 2, 3) or file_data[:4] == b'\x00\x00\x00\x00':
                offset = 512
            else:
                # Try to auto-detect: check if data at offset 0 looks like PackBits
                # vs data at offset 512
                # If first byte at 0 looks like valid PackBits control, use 0
                # Otherwise use 512
                offset = 512

        # Ensure we have enough data
        if offset >= data_len:
            offset = 0

        image_data = file_data[offset:]

        # Detect if data is compressed or raw
        # If first byte > 128, it's likely PackBits compressed
        is_compressed = len(image_data) > 0 and image_data[0] > 128

        # Also check: if remaining data is close to expected uncompressed size,
        # it's probably uncompressed
        if len(image_data) >= expected_bytes - 100 and len(image_data) <= expected_bytes + 100:
            is_compressed = False

        if is_compressed:
            bitmap = mac_unpack_bits(image_data, expected_bytes)
        else:
            # Uncompressed data - just pad/truncate to expected size
            if len(image_data) < expected_bytes:
                bitmap = image_data + bytes(expected_bytes - len(image_data))
            else:
                bitmap = image_data[:expected_bytes]

        # Write PPM header
        out.write(f"P6\n{width} {height}\n255\n".encode('ascii'))

        # Convert bitmap to RGB (1=black, 0=white for MacPaint)
        for y in range(height):
            row_start = y * bytes_per_row
            for x_byte in range(bytes_per_row):
                byte_val = bitmap[row_start + x_byte]
                for bit in range(8):
                    # MSB first
                    pixel = (byte_val >> (7 - bit)) & 1
                    if pixel:
                        out.write(pack([0, 0, 0]))  # Black
                    else:
                        out.write(pack([255, 255, 255]))  # White

        return out.getvalue(), width, height

    except Exception as e:
        print(f"Error converting MAC: {e}")
        return None, 0, 0


# ---------------------------------------------------------------------------
# PCX (PC Paintbrush) Format Conversion
# ---------------------------------------------------------------------------

def pcx_decode_rle(data: bytes, expected_bytes: int) -> bytes:
    """Decode PCX RLE compressed data.

    PCX RLE format:
    - If byte >= 0xC0: the lower 6 bits give the count, next byte is the value
    - Otherwise: the byte is a literal value (count = 1)
    """
    result = bytearray()
    i = 0
    data_len = len(data)

    while i < data_len and len(result) < expected_bytes:
        byte = data[i]
        i += 1

        if byte >= 0xC0:
            # Run-length encoded
            count = byte & 0x3F
            if i < data_len:
                value = data[i]
                i += 1
                result.extend([value] * count)
        else:
            # Literal value
            result.append(byte)

    # Pad if needed
    if len(result) < expected_bytes:
        result.extend([0] * (expected_bytes - len(result)))

    return bytes(result[:expected_bytes])


def convert_pcx_to_ppm(input_image_stream):
    """Convert PCX (PC Paintbrush) format to PPM.

    PCX format:
    - 128-byte header
    - RLE compressed bitmap data
    - Optional 256-color VGA palette at end (769 bytes: 0x0C marker + 768 bytes)

    Supports:
    - 1-bit monochrome
    - 4-bit EGA (16 colors, planar)
    - 8-bit VGA (256 colors)
    - 24-bit true color (3 planes)

    Returns:
        Tuple of (ppm_data, width, height) or (None, 0, 0) on error
    """
    f = BytesIO(input_image_stream)
    out = BytesIO()

    try:
        # Read 128-byte header
        header = f.read(128)
        if len(header) < 128:
            return None, 0, 0

        # Parse header
        manufacturer = header[0]
        version = header[1]
        encoding = header[2]
        bits_per_pixel = header[3]

        x_min = struct.unpack('<H', header[4:6])[0]
        y_min = struct.unpack('<H', header[6:8])[0]
        x_max = struct.unpack('<H', header[8:10])[0]
        y_max = struct.unpack('<H', header[10:12])[0]

        h_dpi = struct.unpack('<H', header[12:14])[0]
        v_dpi = struct.unpack('<H', header[14:16])[0]

        # 16-color EGA palette (48 bytes at offset 16)
        ega_palette = []
        for i in range(16):
            r = header[16 + i * 3]
            g = header[16 + i * 3 + 1]
            b = header[16 + i * 3 + 2]
            ega_palette.append((r, g, b))

        # reserved byte at 64
        num_planes = header[65]
        bytes_per_line = struct.unpack('<H', header[66:68])[0]
        palette_info = struct.unpack('<H', header[68:70])[0]

        # Calculate dimensions
        width = x_max - x_min + 1
        height = y_max - y_min + 1

        if width <= 0 or height <= 0:
            return None, 0, 0

        # Read compressed data
        compressed_data = f.read()

        # Calculate expected bytes per scanline (all planes)
        scanline_bytes = bytes_per_line * num_planes
        total_expected = scanline_bytes * height

        # Decode RLE data
        decoded = pcx_decode_rle(compressed_data, total_expected)

        # Check for VGA palette at end of file (256 colors)
        vga_palette = None
        file_data = input_image_stream
        if len(file_data) >= 769 and file_data[-769] == 0x0C:
            vga_palette = []
            palette_data = file_data[-768:]
            for i in range(256):
                r = palette_data[i * 3]
                g = palette_data[i * 3 + 1]
                b = palette_data[i * 3 + 2]
                vga_palette.append((r, g, b))

        # Write PPM header
        out.write(f"P6\n{width} {height}\n255\n".encode('ascii'))

        # Convert based on format
        if bits_per_pixel == 1 and num_planes == 1:
            # Monochrome
            for y in range(height):
                row_start = y * scanline_bytes
                for x in range(width):
                    byte_idx = x // 8
                    bit_idx = 7 - (x % 8)
                    byte_val = decoded[row_start + byte_idx]
                    pixel = (byte_val >> bit_idx) & 1
                    if pixel:
                        out.write(pack([0, 0, 0]))
                    else:
                        out.write(pack([255, 255, 255]))

        elif bits_per_pixel == 1 and num_planes == 4:
            # 16-color EGA (4 planes)
            for y in range(height):
                row_start = y * scanline_bytes
                for x in range(width):
                    byte_idx = x // 8
                    bit_idx = 7 - (x % 8)

                    # Read bit from each plane
                    color_idx = 0
                    for plane in range(4):
                        plane_offset = row_start + plane * bytes_per_line
                        byte_val = decoded[plane_offset + byte_idx]
                        bit = (byte_val >> bit_idx) & 1
                        color_idx |= (bit << plane)

                    r, g, b = ega_palette[color_idx & 0x0F]
                    out.write(pack([r, g, b]))

        elif bits_per_pixel == 8 and num_planes == 1:
            # 256-color VGA
            palette = vga_palette if vga_palette else ega_palette
            for y in range(height):
                row_start = y * scanline_bytes
                for x in range(width):
                    color_idx = decoded[row_start + x]
                    if color_idx < len(palette):
                        r, g, b = palette[color_idx]
                    else:
                        r, g, b = 0, 0, 0
                    out.write(pack([r, g, b]))

        elif bits_per_pixel == 8 and num_planes == 3:
            # 24-bit true color
            for y in range(height):
                row_start = y * scanline_bytes
                for x in range(width):
                    r = decoded[row_start + x]
                    g = decoded[row_start + bytes_per_line + x]
                    b = decoded[row_start + 2 * bytes_per_line + x]
                    out.write(pack([r, g, b]))

        else:
            # Unsupported format - try to handle as 8-bit indexed
            print(f"Warning: Unusual PCX format (bpp={bits_per_pixel}, planes={num_planes})")
            palette = vga_palette if vga_palette else ega_palette
            for y in range(height):
                row_start = y * scanline_bytes
                for x in range(width):
                    if row_start + x < len(decoded):
                        color_idx = decoded[row_start + x]
                        if color_idx < len(palette):
                            r, g, b = palette[color_idx]
                        else:
                            r, g, b = 0, 0, 0
                    else:
                        r, g, b = 0, 0, 0
                    out.write(pack([r, g, b]))

        return out.getvalue(), width, height

    except Exception as e:
        print(f"Error converting PCX: {e}")
        return None, 0, 0


def convert_clp_to_ppm(input_image_stream):
    """Convert CLP (MAX-10 clipboard picture) format to PPM

    CLP files are MAX-10 word processor clipboard files that can contain
    text, rulers, page breaks, and pictures. This function extracts the
    first picture paragraph found in the file.

    Format specification:
    - 11-byte header with metadata
    - Tagged paragraphs (tag 1 = picture)
    - Picture data: position, size, and monochrome bitmap (0=white, 1=black)
    """
    f = BytesIO(input_image_stream)
    out = BytesIO()

    # Parse 11-byte header
    # 2 bytes: word boundary flags (start, end)
    word_start, word_end = struct.unpack('>BB', f.read(2))

    # 2 bytes: paragraph count
    para_count = struct.unpack('>H', f.read(2))[0]

    # 2 bytes: estimated memory size
    mem_size = struct.unpack('>H', f.read(2))[0]

    # 1 byte: string only flag
    string_only = struct.unpack('B', f.read(1))[0]

    # 2 bytes: first paragraph size
    first_para = struct.unpack('>H', f.read(2))[0]

    # 2 bytes: last string size
    last_string = struct.unpack('>H', f.read(2))[0]

    # Parse paragraphs to find picture (tag 1)
    cols = rows = 0
    while True:
        tag_byte = f.read(1)
        if not tag_byte:
            break
        tag = tag_byte[0]

        if tag == 100:  # End of data
            break
        elif tag == 1:  # Picture paragraph
            # 2 bytes: paragraph size
            para_size = struct.unpack('>H', f.read(2))[0]

            # 2 bytes: left position (8-576 pixels)
            left_pos = struct.unpack('>H', f.read(2))[0]

            # 2 bytes: vertical size in lines
            vert_size = struct.unpack('>H', f.read(2))[0]

            # 2 bytes: horizontal width
            horiz_width = struct.unpack('>H', f.read(2))[0]

            # 2 bytes: bit image height in lines
            img_height = struct.unpack('>H', f.read(2))[0]

            # 2 bytes: bit image width in pixels
            img_width = struct.unpack('>H', f.read(2))[0]

            # 1 byte: bytes per line
            line_bytes = struct.unpack('B', f.read(1))[0]

            # Set dimensions
            cols = img_width
            rows = img_height

            # Write PPM header
            out.write(f"P6\n{cols} {rows}\n255\n".encode('ascii'))

            # Read and convert bitmap data
            # Format: 0=white (255,255,255), 1=black (0,0,0)
            for row in range(rows):
                row_data = f.read(line_bytes)
                for byte_idx in range((cols + 7) // 8):  # Process enough bytes for image width
                    if byte_idx < len(row_data):
                        byte_val = row_data[byte_idx]
                        # Process each bit in the byte
                        for bit_idx in range(8):
                            pixel_x = byte_idx * 8 + bit_idx
                            if pixel_x < cols:  # Only process pixels within image width
                                bit = (byte_val >> (7 - bit_idx)) & 1
                                if bit == 0:
                                    out.write(pack([255, 255, 255]))  # White
                                else:
                                    out.write(pack([0, 0, 0]))  # Black

            # Found and processed picture, return
            return out.getvalue(), cols, rows
        elif tag == 0:  # Text paragraph
            # Skip text paragraphs - would need to parse length and skip content
            # For simplicity, we'll just break if we hit text
            break
        elif tag == 32:  # String paragraph
            break
        elif tag == 2:  # Page break
            continue
        elif tag == 255:  # Ruler
            # Skip 27 bytes of ruler data
            f.read(27)
        else:
            # Unknown tag, stop parsing
            break

    # No picture found
    return None, 0, 0

# --- GUI Application ---

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CoCo MAX/CM3/CLP/MGE/MAC/PCX/GIF DSK Viewer")
        self.geometry("900x800")
        self.dsk = None

        # Top frame for button
        self.btn_open = tk.Button(self, text="Open DSK File", command=self.open_dsk)
        self.btn_open.pack(pady=5)

        # Create a paned window for file list and image
        self.paned = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left frame for file list
        self.left_frame = tk.Frame(self.paned)
        self.paned.add(self.left_frame, width=200)

        self.file_list = tk.Listbox(self.left_frame)
        self.file_list.pack(fill=tk.BOTH, expand=True)
        self.file_list.bind("<<ListboxSelect>>", self.on_file_select)

        # Right frame for image with scrollbars
        self.right_frame = tk.Frame(self.paned)
        self.paned.add(self.right_frame)

        # Create canvas with scrollbars for image display
        self.canvas = tk.Canvas(self.right_frame, bg='gray')
        self.h_scrollbar = tk.Scrollbar(self.right_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.v_scrollbar = tk.Scrollbar(self.right_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)

        # Grid layout for canvas and scrollbars
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.v_scrollbar.grid(row=0, column=1, sticky='ns')
        self.h_scrollbar.grid(row=1, column=0, sticky='ew')

        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        self.photo = None
        self.canvas_image = None

    def open_dsk(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("DSK files", "*.DSK"), ("All files", "*.*")]
        )
        if not filepath:
            return

        self.dsk = DSKImage(filepath)
        if self.dsk.mount():
            self.file_list.delete(0, tk.END)
            for entry in self.dsk.directory:
                filename = f"{entry.filename}.{entry.extension}" if entry.extension else entry.filename
                self.file_list.insert(tk.END, filename)

    def display_image(self, img):
        """Display a PIL Image on the scrollable canvas."""
        self.photo = ImageTk.PhotoImage(img)

        # Clear previous image
        if self.canvas_image:
            self.canvas.delete(self.canvas_image)

        # Update canvas scroll region to image size
        width, height = img.size
        self.canvas.configure(scrollregion=(0, 0, width, height))

        # Create image at top-left corner
        self.canvas_image = self.canvas.create_image(0, 0, anchor='nw', image=self.photo)

        # Update window title with image dimensions
        self.title(f"CoCo Image Viewer - {width}x{height}")

    def on_file_select(self, event):
        selection = event.widget.curselection()
        if not selection:
            return

        selected_index = selection[0]
        selected_entry = self.dsk.directory[selected_index]

        if selected_entry.extension.upper() == "MAX":
            max_data = self.dsk.extract_file(selected_entry)
            if max_data:
                ppm_data, width, height = convert_max_to_ppm(max_data, 1, False, 256, None, 0, True)
                if ppm_data:
                    try:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)
                    except Exception as e:
                        print(f"Error displaying image: {e}")

        elif selected_entry.extension.upper() == "CM3":
            cm3_data = self.dsk.extract_file(selected_entry)
            if cm3_data:
                try:
                    ppm_data, width, height = convert_cm3_to_ppm(cm3_data)
                    img = Image.open(BytesIO(ppm_data))
                    self.display_image(img)
                except Exception as e:
                    print(f"Error displaying CM3 image: {e}")

        elif selected_entry.extension.upper() == "CLP":
            clp_data = self.dsk.extract_file(selected_entry)
            if clp_data:
                try:
                    ppm_data, width, height = convert_clp_to_ppm(clp_data)
                    if ppm_data:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)
                    else:
                        print("No picture found in CLP file")
                except Exception as e:
                    print(f"Error displaying CLP image: {e}")

        elif selected_entry.extension.upper() == "MGE":
            mge_data = self.dsk.extract_file(selected_entry)
            if mge_data:
                try:
                    ppm_data, width, height = convert_mge_to_ppm(mge_data)
                    if ppm_data:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)
                    else:
                        print("Failed to convert MGE file")
                except Exception as e:
                    print(f"Error displaying MGE image: {e}")

        elif selected_entry.extension.upper() == "MAC":
            mac_data = self.dsk.extract_file(selected_entry)
            if mac_data:
                try:
                    ppm_data, width, height = convert_mac_to_ppm(mac_data)
                    if ppm_data:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)
                    else:
                        print("Failed to convert MAC file")
                except Exception as e:
                    print(f"Error displaying MAC image: {e}")

        elif selected_entry.extension.upper() == "PCX":
            pcx_data = self.dsk.extract_file(selected_entry)
            if pcx_data:
                try:
                    ppm_data, width, height = convert_pcx_to_ppm(pcx_data)
                    if ppm_data:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)
                    else:
                        print("Failed to convert PCX file")
                except Exception as e:
                    print(f"Error displaying PCX image: {e}")

        elif selected_entry.extension.upper() == "GIF":
            gif_data = self.dsk.extract_file(selected_entry)
            if gif_data:
                try:
                    # PIL natively supports GIF format
                    img = Image.open(BytesIO(gif_data))
                    # Convert to RGB if needed (for consistency)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    self.display_image(img)
                except Exception as e:
                    print(f"Error displaying GIF image: {e}")

# --- CLI Application ---

def main():
    parser = argparse.ArgumentParser(description="CoCo MAX/CM3/CLP/MGE/MAC/PCX/GIF DSK Tool")
    subparsers = parser.add_subparsers(dest="command")

    gui_parser = subparsers.add_parser("gui", help="Launch the GUI application")

    list_parser = subparsers.add_parser("list", help="List files in a DSK image")
    list_parser.add_argument("dsk_file", help="Path to the DSK file")

    extract_parser = subparsers.add_parser("extract", help="Extract and convert a MAX, CM3, CLP, MGE, MAC, PCX, or GIF file to PNG")
    extract_parser.add_argument("dsk_file", help="Path to the DSK file")
    extract_parser.add_argument("image_file", help="Name of the image file to extract (MAX, CM3, CLP, MGE, MAC, PCX, GIF)")
    extract_parser.add_argument("png_file", help="Path to save the output PNG file")

    args = parser.parse_args()

    if args.command == "gui":
        app = App()
        app.mainloop()
    elif args.command == "list":
        dsk = DSKImage(args.dsk_file)
        if dsk.mount():
            for entry in dsk.directory:
                filename = f"{entry.filename}.{entry.extension}" if entry.extension else entry.filename
                print(filename)
    
    elif args.command == "extract":
        dsk = DSKImage(args.dsk_file)
        if dsk.mount():
            entry_to_extract = None
            for entry in dsk.directory:
                filename = f"{entry.filename}.{entry.extension}" if entry.extension else entry.filename
                if filename.upper() == args.image_file.upper():
                    entry_to_extract = entry
                    break

            if entry_to_extract:
                image_data = dsk.extract_file(entry_to_extract)
                if image_data:
                    # Determine format based on extension
                    extension = entry_to_extract.extension.upper()

                    if extension == "MAX":
                        ppm_data, width, height = convert_max_to_ppm(image_data, 1, False, 256, None, 0, True)
                    elif extension == "CM3":
                        ppm_data, width, height = convert_cm3_to_ppm(image_data)
                    elif extension == "CLP":
                        ppm_data, width, height = convert_clp_to_ppm(image_data)
                        if not ppm_data:
                            print("No picture found in CLP file")
                    elif extension == "MGE":
                        ppm_data, width, height = convert_mge_to_ppm(image_data)
                        if not ppm_data:
                            print("Failed to convert MGE file")
                    elif extension == "MAC":
                        ppm_data, width, height = convert_mac_to_ppm(image_data)
                        if not ppm_data:
                            print("Failed to convert MAC file")
                    elif extension == "PCX":
                        ppm_data, width, height = convert_pcx_to_ppm(image_data)
                        if not ppm_data:
                            print("Failed to convert PCX file")
                    elif extension == "GIF":
                        # GIF is natively supported by PIL - save directly
                        try:
                            img = Image.open(BytesIO(image_data))
                            width, height = img.size
                            img.save(args.png_file, 'PNG')
                            print(f"Saved GIF image as {args.png_file} ({width}x{height})")
                        except Exception as e:
                            print(f"Error converting GIF to PNG: {e}")
                        ppm_data = None  # Already handled
                    else:
                        print(f"Unsupported file format: {extension}")
                        ppm_data = None

                    if ppm_data:
                        try:
                            img = Image.open(BytesIO(ppm_data))
                            img.save(args.png_file, 'PNG')
                            print(f"Saved {extension} image as {args.png_file} ({width}x{height})")
                        except Exception as e:
                            print(f"Error converting to PNG: {e}")
                    else:
                        print(f"Failed to convert {extension} data from {args.image_file}")
                else:
                    print(f"Failed to extract data from {args.image_file}")
            else:
                print(f"File not found: {args.image_file}")

if __name__ == "__main__":
    main()
