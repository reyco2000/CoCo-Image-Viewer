"""
NIB (Nibble) format image converter.
"""

from io import BytesIO


def gime_to_rgb(val):
    """Convert a 6-bit GIME palette value to an RGB tuple."""
    r = (((val >> 5) & 1) << 1) | ((val >> 2) & 1)
    g = (((val >> 4) & 1) << 1) | ((val >> 1) & 1)
    b = (((val >> 3) & 1) << 1) | ((val >> 0) & 1)
    return (r * 85, g * 85, b * 85)


# Two standard palettes offered by the BASIC loader
PALETTE_RGB = [gime_to_rgb(v) for v in [1, 32, 38, 60]]
PALETTE_CMP = [gime_to_rgb(v) for v in [10, 8, 38, 55]]


def convert_nib_to_ppm(input_image_stream, palette_type="rgb"):
    """Convert NIB (Nibble) format to PPM.

    Args:
        input_image_stream: Raw bytes of the NIB file
        palette_type: "rgb" or "cmp" for composite monitoring matching

    Returns:
        Tuple of (ppm_data, width, height)
    """
    data = input_image_stream

    # 1. Parse DECB container
    if len(data) < 5 or data[0] != 0x00:
        raise ValueError("Not a valid DECB BIN file")

    segment_len = (data[1] << 8) | data[2]
    # Ignoring the load_addr from the DECB header as per spec

    if len(data) < 5 + segment_len:
        raise ValueError("File truncated (DECB segment length exceeds file size)")

    segment_data = data[5 : 5 + segment_len]

    # 2. Read header pointer (first two bytes of segment data, mapped to $4000)
    header_ptr = (segment_data[0] << 8) | segment_data[1]
    header_offset = header_ptr - 0x4000

    if header_offset < 0 or header_offset + 34 > len(segment_data):
        raise ValueError(f"Invalid header pointer: ${header_ptr:04X}")

    header = segment_data[header_offset : header_offset + 34]

    # Extract fields from Header
    xor_flag = header[19]
    bitmap2_src = (header[21] << 8) | header[22]
    bitmap2_dest_end = (header[23] << 8) | header[24]
    pass1_end = (header[25] << 8) | header[26]
    bitmap1_src = (header[27] << 8) | header[28]
    bitmap1_dest_end = (header[29] << 8) | header[30]

    # Calculate sizes
    bitmap1_size = bitmap1_dest_end - 0x1000
    bitmap2_size = bitmap2_dest_end - 0x1000
    pass1_out_size = pass1_end - 0x4000
    bitmap1_offset = bitmap1_src - 0x4000
    bitmap2_offset = bitmap2_src - 0x4000

    # Extract from file
    bitmap1 = segment_data[bitmap1_offset : bitmap1_offset + bitmap1_size]
    # Header bytes 0-1 replaced the segment's first two bytes during load
    pass1_packed = bytes(header[0:2]) + segment_data[2:bitmap1_offset]

    # Run Pass 1 decompression (byte-level bitmap RLE)
    pass1_output = bytearray(pass1_out_size)
    prev_value = 0
    packed_index = 0
    output_index = 0
    bit_mask = 0x80
    bitmap_index = 0

    while output_index < pass1_out_size:
        if bitmap_index >= len(bitmap1):
            break

        if bitmap1[bitmap_index] & bit_mask:
            if packed_index < len(pass1_packed):
                prev_value = pass1_packed[packed_index]
                packed_index += 1

        pass1_output[output_index] = prev_value
        output_index += 1

        bit_mask >>= 1
        if bit_mask == 0:
            bit_mask = 0x80
            bitmap_index += 1

    # Extract from pass1 output
    bitmap2 = pass1_output[bitmap2_offset : bitmap2_offset + bitmap2_size]
    nibble_data = pass1_output[0:bitmap2_offset]

    # Run Pass 2 decompression (nibble-level bitmap RLE)
    screen = bytearray(32768)
    toggle = 0
    cc = 0
    cd = 0
    nibble_index = 0
    bit_mask = 0x80
    bitmap_index = 0
    output_index = 0

    def extract_nibble():
        nonlocal toggle, cc, cd, nibble_index
        if nibble_index >= len(nibble_data):
            return

        if toggle == 0:
            byte = nibble_data[nibble_index]
            cd = byte & 0xF0
            cc = (byte >> 4) & 0x0F
            toggle = 1
        else:
            byte = nibble_data[nibble_index]
            nibble_index += 1
            cc = byte & 0x0F
            cd = (cc << 4) & 0xF0
            toggle = 0

    while output_index < 32768:
        if bitmap_index >= len(bitmap2):
            break

        bitmap_byte = bitmap2[bitmap_index]

        # --- High nibble of output byte ---
        if bitmap_byte & bit_mask:
            extract_nibble()
        screen[output_index] = cd

        # Advance bit mask
        bit_mask >>= 1
        if bit_mask == 0:
            bit_mask = 0x80
            bitmap_index += 1
            if bitmap_index < len(bitmap2):
                bitmap_byte = bitmap2[bitmap_index]

        # --- Low nibble of output byte ---
        if bitmap_byte & bit_mask:
            extract_nibble()
        screen[output_index] |= cc

        output_index += 1

        # Advance bit mask
        bit_mask >>= 1
        if bit_mask == 0:
            bit_mask = 0x80
            bitmap_index += 1

    # XOR Delta Decode
    if xor_flag != 0:
        for i in range(160, 32000):
            screen[i] ^= screen[i - 160]

    # Render image to PPM stream
    width, height = 640, 200
    out = BytesIO()

    # Write PPM Header P6
    out.write(f"P6\n{width} {height}\n255\n".encode("ascii"))

    pal = PALETTE_RGB if palette_type.lower() == "rgb" else PALETTE_CMP

    for y in range(height):
        for x_byte in range(160):
            byte = screen[y * 160 + x_byte]

            p0 = (byte >> 6) & 3
            p1 = (byte >> 4) & 3
            p2 = (byte >> 2) & 3
            p3 = byte & 3

            out.write(bytes(pal[p0]))
            out.write(bytes(pal[p1]))
            out.write(bytes(pal[p2]))
            out.write(bytes(pal[p3]))

    return out.getvalue(), width, height
