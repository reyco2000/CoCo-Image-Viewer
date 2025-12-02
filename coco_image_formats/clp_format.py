"""
CLP (MAX-10 clipboard picture) image format converter.
"""

import struct
from io import BytesIO
from .utils import pack


def convert_clp_to_ppm(input_image_stream):
    """Convert CLP (MAX-10 clipboard picture) format to PPM.

    CLP files are MAX-10 word processor clipboard files that can contain
    text, rulers, page breaks, and pictures. This function extracts the
    first picture paragraph found in the file.

    Format specification:
    - 11-byte header with metadata
    - Tagged paragraphs (tag 1 = picture)
    - Picture data: position, size, and monochrome bitmap (0=white, 1=black)

    Returns:
        Tuple of (ppm_data, width, height) or (None, 0, 0) on error
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
