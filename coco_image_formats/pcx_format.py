"""
PCX (PC Paintbrush) image format converter.
"""

import struct
from io import BytesIO
from .utils import pack


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
