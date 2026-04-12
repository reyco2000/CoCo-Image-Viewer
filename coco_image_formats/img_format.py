"""
IMG (Digiscan RASCAN) image format converter.
"""

from io import BytesIO

from .utils import getbit


def get_coco_color(c: int) -> tuple:
    """Decode a CoCo 3 hardware palette value into RGB tuple."""
    r = (getbit(c, 5) * 2 + getbit(c, 2)) * 85
    g = (getbit(c, 4) * 2 + getbit(c, 1)) * 85
    b = (getbit(c, 3) * 2 + getbit(c, 0)) * 85
    return r, g, b


def read_buffer(f: BytesIO) -> bytearray:
    """Decompress a single image buffer from the input stream.

    The format uses alternating Uncompressed and Compressed blocks.
    A sequence of `00` followed by `00` terminates the buffer.
    """
    out = bytearray()
    state = (
        0  # 0 indicates expecting uncompressed length, 1 expecting compressed length
    )
    last_was_zero = False

    while True:
        b = f.read(1)
        if not b:
            break

        length = b[0]

        if length == 0:
            if last_was_zero:
                # `00 00` sequence found! Terminate the buffer loading.
                break
            last_was_zero = True
            state = 1 - state  # Toggle state but do not process data
            continue

        # Reset the terminator flag since `length != 0`
        last_was_zero = False

        if state == 0:
            # Uncompressed block
            data = f.read(length)
            out.extend(data)
        else:
            # Compressed block (RLE)
            val = f.read(1)
            if val:
                out.extend(bytes([val[0]]) * length)

        # Toggle state for next iteration
        state = 1 - state

    return out


def convert_img_to_ppm(input_image_stream: bytes) -> tuple:
    """Convert an IMG (RASCAN) format byte sequence to PPM format.

    Args:
        input_image_stream: Raw bytes of the IMG file.

    Returns:
        Tuple of (ppm_data, width, height), or (None, 0, 0) upon failure.
    """
    f = BytesIO(input_image_stream)

    # Byte 0: Dummy byte (ignored)
    _ = f.read(1)

    # Byte 1: Video MODE
    mode_byte = f.read(1)
    if not mode_byte:
        return None, 0, 0
    mode = mode_byte[0]

    # Bytes 2-17: 16 palette values
    palette = [0] * 16
    for i in range(16):
        pb = f.read(1)
        if pb:
            palette[i] = pb[0]

    # Set dimensions and buffer sizing according to the video mode
    if mode in (0, 2):
        width = 640
    else:
        width = 320

    height = 200

    if mode == 0:
        expected_size = (width * height) // 4
    else:
        expected_size = (width * height) // 2

    # Initialize the PPM pixel array
    rgb_data = bytearray(width * height * 3)

    if mode == 0:
        # Mode 0: 4 Color 640x200 (2 bits per pixel)
        buf = read_buffer(f)

        # Ensure buffer length matches geometry
        if len(buf) < expected_size:
            buf.extend(b"\x00" * (expected_size - len(buf)))

        # RASCAN 640x200 4-color mode is a grayscale digitizer capture.
        # It relies on an inverted grayscale palette (0 is White, 3 is Black).
        # We ignore the file header palette as it occasionally contains residual colors from memory.
        colors = [(255, 255, 255), (170, 170, 170), (85, 85, 85), (0, 0, 0)]

        for i in range(width * height):
            b_idx = i // 4
            pixel_in_byte = i % 4
            shift = 6 - (pixel_in_byte * 2)

            idx = (buf[b_idx] >> shift) & 0x03

            r, g, b = colors[idx]
            rgb_data[i * 3] = r
            rgb_data[i * 3 + 1] = g
            rgb_data[i * 3 + 2] = b

    elif mode in (1, 2):
        # Mode 1: 16 Colour 320x200
        # Mode 2: 16 Dithered Gray 640x200
        buf = read_buffer(f)

        # Ensure buffer length matches geometry
        if len(buf) < expected_size:
            buf.extend(b"\x00" * (expected_size - len(buf)))

        # Precompute the 16 hardware colors
        colors = [get_coco_color(c) for c in palette]

        for i in range(width * height):
            b_idx = i // 2
            is_low = i % 2

            val = buf[b_idx]
            if is_low:
                idx = val & 0x0F
            else:
                idx = val >> 4

            r, g, b = colors[idx]
            rgb_data[i * 3] = r
            rgb_data[i * 3 + 1] = g
            rgb_data[i * 3 + 2] = b

    elif mode == 3:
        # Mode 3: 4096 "FlikPic" 3x(320x200)
        # Separated as 3 buffers: Red (1), Green (2), Blue (3)
        buf1 = read_buffer(f)
        buf2 = read_buffer(f)
        buf3 = read_buffer(f)

        for b in (buf1, buf2, buf3):
            if len(b) < expected_size:
                b.extend(b"\x00" * (expected_size - len(b)))

        for i in range(width * height):
            b_idx = i // 2
            is_low = i % 2

            if is_low:
                cr = buf1[b_idx] & 0x0F
                cg = buf2[b_idx] & 0x0F
                cb = buf3[b_idx] & 0x0F
            else:
                cr = buf1[b_idx] >> 4
                cg = buf2[b_idx] >> 4
                cb = buf3[b_idx] >> 4

            # Mapping 0-15 intensity into 0-255 RGB (Inverted: 0 is White, 15 is Black)
            rgb_data[i * 3] = (15 - cr) * 17
            rgb_data[i * 3 + 1] = (15 - cg) * 17
            rgb_data[i * 3 + 2] = (15 - cb) * 17

    elif mode == 4:
        # Mode 4: 3 Dimensional 2x(320x200)
        # Separated as 2 buffers: Buffer 1 and Buffer 3
        # Buffer 1 maps to Red and Buffer 3 maps to Cyan (Green+Blue) for 3D glasses
        buf1 = read_buffer(f)
        buf3 = read_buffer(f)

        for b in (buf1, buf3):
            if len(b) < expected_size:
                b.extend(b"\x00" * (expected_size - len(b)))

        for i in range(width * height):
            b_idx = i // 2
            is_low = i % 2

            if is_low:
                cr = buf1[b_idx] & 0x0F
                cb = buf3[b_idx] & 0x0F
            else:
                cr = buf1[b_idx] >> 4
                cb = buf3[b_idx] >> 4

            # Render Buffer 1 to Red, and Buffer 3 to Cyan (Inverted)
            rgb_data[i * 3] = (15 - cr) * 17
            rgb_data[i * 3 + 1] = (15 - cb) * 17
            rgb_data[i * 3 + 2] = (15 - cb) * 17

    else:
        print(f"Unsupported video mode {mode} for IMG format")
        return None, 0, 0

    ppm_header = f"P6\n{width} {height}\n255\n".encode("ascii")

    return bytes(ppm_header) + bytes(rgb_data), width, height
