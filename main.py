
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
        self.title("CoCo MAX/CM3/CLP DSK Viewer")
        self.geometry("800x600")
        self.dsk = None

        self.btn_open = tk.Button(self, text="Open DSK File", command=self.open_dsk)
        self.btn_open.pack(pady=10)

        self.file_list = tk.Listbox(self)
        self.file_list.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        self.file_list.bind("<<ListboxSelect>>", self.on_file_select)

        self.image_label = tk.Label(self)
        self.image_label.pack(pady=10)

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
                        self.photo = ImageTk.PhotoImage(img)
                        self.image_label.config(image=self.photo)
                    except Exception as e:
                        print(f"Error displaying image: {e}")

        elif selected_entry.extension.upper() == "CM3":
            cm3_data = self.dsk.extract_file(selected_entry)
            if cm3_data:
                try:
                    ppm_data, width, height = convert_cm3_to_ppm(cm3_data)
                    img = Image.open(BytesIO(ppm_data))
                    self.photo = ImageTk.PhotoImage(img)
                    self.image_label.config(image=self.photo)
                except Exception as e:
                    print(f"Error displaying CM3 image: {e}")

        elif selected_entry.extension.upper() == "CLP":
            clp_data = self.dsk.extract_file(selected_entry)
            if clp_data:
                try:
                    ppm_data, width, height = convert_clp_to_ppm(clp_data)
                    if ppm_data:
                        img = Image.open(BytesIO(ppm_data))
                        self.photo = ImageTk.PhotoImage(img)
                        self.image_label.config(image=self.photo)
                    else:
                        print("No picture found in CLP file")
                except Exception as e:
                    print(f"Error displaying CLP image: {e}")

# --- CLI Application ---

def main():
    parser = argparse.ArgumentParser(description="CoCo MAX/CM3/CLP DSK Tool")
    subparsers = parser.add_subparsers(dest="command")

    gui_parser = subparsers.add_parser("gui", help="Launch the GUI application")

    list_parser = subparsers.add_parser("list", help="List files in a DSK image")
    list_parser.add_argument("dsk_file", help="Path to the DSK file")

    extract_parser = subparsers.add_parser("extract", help="Extract and convert a MAX, CM3, or CLP file to PNG")
    extract_parser.add_argument("dsk_file", help="Path to the DSK file")
    extract_parser.add_argument("image_file", help="Name of the MAX, CM3, or CLP file to extract")
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
