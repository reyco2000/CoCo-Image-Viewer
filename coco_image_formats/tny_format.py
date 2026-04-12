"""
Atari ST Tiny format (.TNY, .TN1, .TN2, .TN3) image converter.

The Tiny format is a compressed image format for Atari ST computers created by David Mumper.
It uses RLE-based compression optimized for vertical column data and supports all three
Atari ST graphics modes.
"""

import struct
from io import BytesIO

from .utils import pack


def decode_tny(data: bytes):
    """Decode Atari ST Tiny format file.

    File structure:
    - 1 byte: Resolution (0=low 320x200, 1=medium 640x200, 2=high 640x400)
              Add 3 for animated/rotated images
    - [4 bytes]: Optional animation data (only if resolution > 2)
    - 32 bytes: Palette (16 words, big-endian)
    - 2 bytes: Control byte count (big-endian word)
    - 2 bytes: Data word count (big-endian word)
    - Variable: Control bytes (compression instructions)
    - Variable: Data words (compressed image data, big-endian)

    Returns:
        Tuple of (decompressed_bytes, width, height, palette_rgb_tuples) or (None, 0, 0, None)
    """
    if len(data) < 42:  # Minimum file size
        return None, 0, 0, None

    pos = 0

    # Read resolution byte
    resolution = data[pos]
    pos += 1

    # Handle animation flag (resolution > 2 means animation data present)
    if resolution > 2:
        resolution -= 3
        pos += 4  # Skip 4 bytes of animation data

    # Determine dimensions and format
    if resolution == 0:  # Low resolution
        width, height = 320, 200
        words_per_line = 80
    elif resolution == 1:  # Medium resolution
        width, height = 640, 200
        words_per_line = 80
    elif resolution == 2:  # High resolution
        width, height = 640, 400
        words_per_line = 80
    else:
        return None, 0, 0, None

    # Read palette (16 words, big-endian)
    # Atari ST uses 3 bits per color channel (0-7), NOT 4 bits!
    # Format: 0x0RGB where each component is 3 bits
    palette = []
    for i in range(16):
        if pos + 2 > len(data):
            return None, 0, 0, None
        color_word = struct.unpack(">H", data[pos : pos + 2])[0]
        pos += 2

        # Extract 3-bit color components
        r = ((color_word >> 8) & 0x07) * 36  # Bits 8-6
        g = ((color_word >> 4) & 0x07) * 36  # Bits 4-2
        b = (color_word & 0x07) * 36  # Bits 2-0
        palette.append((r, g, b))

    # Read counts
    if pos + 4 > len(data):
        return None, 0, 0, None
    control_count = struct.unpack(">H", data[pos : pos + 2])[0]
    pos += 2
    data_count = struct.unpack(">H", data[pos : pos + 2])[0]
    pos += 2

    # Read control bytes
    if pos + control_count > len(data):
        return None, 0, 0, None
    control_bytes = data[pos : pos + control_count]
    pos += control_count

    # Read data words
    if pos + (data_count * 2) > len(data):
        return None, 0, 0, None
    data_words = []
    for i in range(data_count):
        word = struct.unpack(">H", data[pos : pos + 2])[0]
        pos += 2
        data_words.append(word)

    # Decompress using Tiny RLE algorithm
    decompressed = []
    control_pos = 0
    data_pos = 0

    while control_pos < len(control_bytes):
        # Read control byte as signed
        control = struct.unpack("b", bytes([control_bytes[control_pos]]))[0]
        control_pos += 1

        if control < 0:
            # Negative: Copy -control unique words from data section (1-128)
            count = -control
            for _ in range(count):
                if data_pos < len(data_words):
                    decompressed.append(data_words[data_pos])
                    data_pos += 1

        elif control == 0:
            # Read 16-bit count from control section, repeat next data word
            if control_pos + 2 <= len(control_bytes):
                count = struct.unpack(
                    ">H", control_bytes[control_pos : control_pos + 2]
                )[0]
                control_pos += 2
                if data_pos < len(data_words):
                    word = data_words[data_pos]
                    data_pos += 1
                    decompressed.extend([word] * count)

        elif control == 1:
            # Read 16-bit count from control section, copy unique words
            if control_pos + 2 <= len(control_bytes):
                count = struct.unpack(
                    ">H", control_bytes[control_pos : control_pos + 2]
                )[0]
                control_pos += 2
                for _ in range(count):
                    if data_pos < len(data_words):
                        decompressed.append(data_words[data_pos])
                        data_pos += 1

        else:  # control > 1
            # Repeat next data word control times (2-127)
            if data_pos < len(data_words):
                word = data_words[data_pos]
                data_pos += 1
                decompressed.extend([word] * control)

    # Reorder columns from vertical format to scanline format
    # Decompressed data is organized as 4 sets of vertical columns
    total_words = words_per_line * height
    screen_words = [0] * total_words
    decomp_pos = 0

    for set_num in range(4):
        for col_offset in range(set_num, words_per_line, 4):
            for scanline in range(height):
                if decomp_pos < len(decompressed):
                    screen_pos = scanline * words_per_line + col_offset
                    if screen_pos < total_words:
                        screen_words[screen_pos] = decompressed[decomp_pos]
                    decomp_pos += 1

    # Convert words to bytes (big-endian)
    output_bytes = bytearray()
    for word in screen_words:
        output_bytes.extend(struct.pack(">H", word))

    return bytes(output_bytes), width, height, palette


def decode_atari_st_bitplanes(
    data: bytes, width: int, height: int, palette: list, num_planes: int
):
    """Decode Atari ST interleaved bitplane format to RGB.

    Atari ST uses interleaved bitplanes, NOT packed pixels.

    Args:
        data: Raw bitplane data
        width: Image width in pixels
        height: Image height in scanlines
        palette: List of RGB tuples
        num_planes: Number of bitplanes (1, 2, or 4)

    Returns:
        BytesIO containing PPM P6 format data
    """
    out = BytesIO()
    out.write(f"P6\n{width} {height}\n255\n".encode("ascii"))

    if num_planes == 1:
        # High resolution (640x400, monochrome, 1 bitplane)
        # Linear bitplane data, 80 bytes per scanline
        for y in range(height):
            for x in range(width):
                byte_index = (y * 80) + (x // 8)
                bit_index = 7 - (x % 8)

                if byte_index < len(data):
                    pixel_value = (data[byte_index] >> bit_index) & 1
                    r, g, b = palette[pixel_value]
                else:
                    r, g, b = 0, 0, 0

                out.write(pack([r, g, b]))

    elif num_planes == 2:
        # Medium resolution (640x200, 4 colors, 2 bitplanes)
        # 160 bytes per scanline, planes interleaved
        # 40 words per plane (640 pixels / 16 = 40)
        for y in range(height):
            scanline_offset = y * 160
            for x in range(width):
                word_index = x // 16
                bit_index = 15 - (x % 16)

                pixel_value = 0
                for plane in range(2):
                    # Interleaved: word_index * 4 bytes + plane * 2 bytes
                    word_offset = scanline_offset + (word_index * 4) + (plane * 2)

                    if word_offset + 1 < len(data):
                        word = struct.unpack(">H", data[word_offset : word_offset + 2])[
                            0
                        ]
                        bit = (word >> bit_index) & 1
                        pixel_value |= bit << plane

                if pixel_value < len(palette):
                    r, g, b = palette[pixel_value]
                else:
                    r, g, b = 0, 0, 0

                out.write(pack([r, g, b]))

    elif num_planes == 4:
        # Low resolution (320x200, 16 colors, 4 bitplanes)
        # 160 bytes per scanline, planes interleaved
        # 20 words per plane (320 pixels / 16 = 20)
        for y in range(height):
            scanline_offset = y * 160
            for x in range(width):
                word_index = x // 16
                bit_index = 15 - (x % 16)

                pixel_value = 0
                for plane in range(4):
                    # Interleaved: word_index * 8 bytes + plane * 2 bytes
                    word_offset = scanline_offset + (word_index * 8) + (plane * 2)

                    if word_offset + 1 < len(data):
                        word = struct.unpack(">H", data[word_offset : word_offset + 2])[
                            0
                        ]
                        bit = (word >> bit_index) & 1
                        pixel_value |= bit << plane

                if pixel_value < len(palette):
                    r, g, b = palette[pixel_value]
                else:
                    r, g, b = 0, 0, 0

                out.write(pack([r, g, b]))

    return out.getvalue()


def convert_tny_to_ppm(input_image_stream):
    """Convert Atari ST Tiny format to PPM.

    Supports all three Atari ST resolutions:
    - Low: 320x200, 16 colors (4 bitplanes)
    - Medium: 640x200, 4 colors (2 bitplanes)
    - High: 640x400, monochrome (1 bitplane)

    Returns:
        Tuple of (ppm_data, width, height) or (None, 0, 0) on error
    """
    try:
        # Decode TNY file
        raw_data, width, height, palette = decode_tny(input_image_stream)

        if raw_data is None:
            return None, 0, 0

        # Determine number of bitplanes based on resolution
        if width == 320 and height == 200:
            num_planes = 4  # Low resolution
        elif width == 640 and height == 200:
            num_planes = 2  # Medium resolution
        elif width == 640 and height == 400:
            num_planes = 1  # High resolution
        else:
            return None, 0, 0

        # Decode bitplanes to RGB
        ppm_data = decode_atari_st_bitplanes(
            raw_data, width, height, palette, num_planes
        )

        return ppm_data, width, height

    except Exception as e:
        print(f"Error converting TNY: {e}")
        return None, 0, 0
