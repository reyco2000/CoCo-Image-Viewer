#!/usr/bin/env python3
"""
MGE file viewer for CoCo 3 ANIMTOOL-style MGE files.

- Supports 320x200x16 images (res byte = 0)
- Reads 16-entry palette of GIME color numbers (0–63)
- Converts between RGB and Composite palettes using the same
  RGBCMP / CMPRGB tables as the 6809 ANIMTOOL
- Decodes compressed (RLE) or uncompressed bitmap
- Outputs a 320x200 RGB PNG or shows it with Pillow

Usage:
  python mge_viewer.py file.mge [output.png] [R|C]

  R|C = target monitor type (RGB or Composite), default = R
"""

import sys
from pathlib import Path
from PIL import Image


# ---------------------------------------------------------------------------
# Original 6809 RGBCMP / CMPRGB tables (64 entries each)
# ---------------------------------------------------------------------------

RGBCMP = [
    0x00, 0x0E, 0x02, 0x0E, 0x05, 0x10, 0x03, 0x10,
    0x0D, 0x0B, 0x1E, 0x1C, 0x0B, 0x0C, 0x1E, 0x1D,
    0x11, 0x11, 0x12, 0x22, 0x14, 0x13, 0x22, 0x21,
    0x2E, 0x2D, 0x2F, 0x1F, 0x2E, 0x2D, 0x2F, 0x2E,
    0x07, 0x06, 0x15, 0x06, 0x07, 0x18, 0x26, 0x1D,
    0x1A, 0x2B, 0x1B, 0x2B, 0x19, 0x09, 0x29, 0x2A,
    0x24, 0x23, 0x32, 0x33, 0x35, 0x36, 0x24, 0x25,
    0x20, 0x3C, 0x31, 0x3D, 0x38, 0x3B, 0x34, 0x3F,
]

CMPRGB = [
    0x00, 0x02, 0x02, 0x06, 0x00, 0x04, 0x21, 0x20,
    0x20, 0x2D, 0x05, 0x09, 0x0D, 0x08, 0x01, 0x00,
    0x07, 0x10, 0x12, 0x15, 0x14, 0x22, 0x26, 0x24,
    0x25, 0x2C, 0x28, 0x2A, 0x0B, 0x0F, 0x0A, 0x1B,
    0x38, 0x17, 0x13, 0x31, 0x30, 0x37, 0x26, 0x27,
    0x25, 0x2E, 0x2F, 0x29, 0x0B, 0x19, 0x18, 0x1A,
    0x3F, 0x3A, 0x32, 0x33, 0x3E, 0x34, 0x35, 0x3C,
    0x3C, 0x2E, 0x3D, 0x3D, 0x39, 0x3B, 0x3A, 0x3F,
]


# ---------------------------------------------------------------------------
# GIME palette value (0–63) -> RGB888
# According to CoCo 3 docs:
#   Bit 5 = high Red, Bit 2 = low Red
#   Bit 4 = high Green, Bit 1 = low Green
#   Bit 3 = high Blue, Bit 0 = low Blue
# ---------------------------------------------------------------------------

def gime_to_rgb(v: int):
    v &= 0x3F  # ensure 0-63

    r = (((v >> 5) & 1) << 1) | ((v >> 2) & 1)
    g = (((v >> 4) & 1) << 1) | ((v >> 1) & 1)
    b = (((v >> 3) & 1) << 1) | ((v >> 0) & 1)

    scale = 85  # 0, 85, 170, 255
    return (r * scale, g * scale, b * scale)


# ---------------------------------------------------------------------------
# Palette conversion logic (matches 6809 ANIMTOOL)
# file_monitor: 0=RGB, 1=Composite
# target_monitor: 0=RGB, 1=Composite
# ---------------------------------------------------------------------------

def convert_palette(pal16, file_monitor, target_monitor):
    """
    Convert 16-entry palette of GIME values if monitor types differ.
    """
    if file_monitor == target_monitor:
        return pal16[:]

    # 6809 logic:
    #   if file type == 0 (RGB)   -> use RGBCMP (RGB -> Composite)
    #   if file type != 0 (CMP)   -> use CMPRGB (Composite -> RGB)
    if file_monitor == 0:
        table = RGBCMP
    else:
        table = CMPRGB

    converted = []
    for v in pal16:
        v6 = v & 0x3F
        converted.append(table[v6])
    return converted


# ---------------------------------------------------------------------------
# Bitmap decode (compressed / uncompressed)
# ---------------------------------------------------------------------------

def decode_bitmap(bitmap_data: bytes, compressed_flag: int) -> bytes:
    """
    compressed_flag == 0 : RLE (count,value) pairs, terminated by count=0
    compressed_flag != 0 : raw 32000 bytes
    """
    if compressed_flag == 0:
        out = []
        i = 0
        n = len(bitmap_data)
        while True:
            if i + 2 > n:
                raise ValueError("Unexpected EOF in compressed bitmap data")
            count = bitmap_data[i]
            value = bitmap_data[i + 1]
            i += 2

            if count == 0:
                break

            out.extend([value] * count)

        # ANIMTOOL doesn't check size, but we do a sanity check:
        if len(out) != 32000:
            print(f"Warning: decompressed size {len(out)} != 32000")
        return bytes(out[:32000])

    else:
        if len(bitmap_data) < 32000:
            raise ValueError("File too small for uncompressed bitmap")
        return bitmap_data[:32000]


# ---------------------------------------------------------------------------
# MGE loader
# ---------------------------------------------------------------------------

def load_mge(path, target_monitor="R"):
    data = Path(path).read_bytes()
    pos = 0

    # 1. Resolution byte
    res = data[pos]
    pos += 1
    if res != 0:
        raise ValueError(f"Incompatible resolution byte {res} (expected 0)")

    # 2. 16-byte palette (GIME values 0–63)
    if pos + 16 > len(data):
        raise ValueError("File truncated while reading palette")
    pal16 = list(data[pos:pos + 16])
    pos += 16

    # 3. File monitor type (0=RGB, 1=CMP; anything non-zero => 1)
    if pos >= len(data):
        raise ValueError("File truncated while reading monitor type")
    file_mon = data[pos]
    pos += 1
    file_mon = 0 if file_mon == 0 else 1

    # 4. Compression flag
    if pos >= len(data):
        raise ValueError("File truncated while reading compression flag")
    comp_flag = data[pos]
    pos += 1

    # 5. 32-byte title string
    if pos + 32 > len(data):
        raise ValueError("File truncated while reading title")
    title_bytes = data[pos:pos + 32]
    pos += 32
    title = title_bytes.rstrip(b"\x00").decode("ascii", errors="replace")

    # 6. Bitmap data
    bitmap_raw = decode_bitmap(data[pos:], comp_flag)

    # 7. Palette conversion
    target_mon = 0 if target_monitor.upper() == "R" else 1
    pal_conv = convert_palette(pal16, file_mon, target_mon)

    # 8. Build RGB palette
    rgb_palette = [gime_to_rgb(v) for v in pal_conv]

    # 9. Expand bitmap -> 320x200 RGB pixels
    width, height = 320, 200
    pixels = []
    idx = 0
    for _y in range(height):
        for _x in range(0, width, 2):
            b = bitmap_raw[idx]
            idx += 1
            hi = (b >> 4) & 0x0F
            lo = b & 0x0F
            pixels.append(rgb_palette[hi])
            pixels.append(rgb_palette[lo])

    img = Image.new("RGB", (width, height))
    img.putdata(pixels)

    meta = {
        "title": title,
        "resolution_byte": res,
        "file_monitor_type": file_mon,
        "target_monitor_type": target_mon,
        "compression_flag": comp_flag,
        "palette_raw": pal16,
        "palette_converted": pal_conv,
    }
    return img, meta


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: mge_viewer.py file.mge [output.png] [R|C]")
        return 1

    in_path = argv[0]
    out_path = None
    target_mon = "R"

    if len(argv) >= 2:
        # Second arg can be output filename or R/C
        if argv[1].upper() in ("R", "C"):
            target_mon = argv[1].upper()
        else:
            out_path = argv[1]

    if len(argv) >= 3:
        target_mon = argv[2].upper()

    img, meta = load_mge(in_path, target_monitor=target_mon)

    print(f"File        : {in_path}")
    print(f"Title       : {meta['title']!r}")
    print(f"File mon    : {'RGB' if meta['file_monitor_type'] == 0 else 'Composite'}")
    print(f"Target mon  : {'RGB' if meta['target_monitor_type'] == 0 else 'Composite'}")
    print(f"Compression : {'compressed' if meta['compression_flag'] == 0 else 'raw'}")

    if out_path:
        img.save(out_path)
        print(f"Saved PNG   : {out_path}")
    else:
        img.show()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
