"""
MGE (Graphics Exchange / ANIMTOOL) image format converter.
"""

from io import BytesIO
from .utils import pack


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
