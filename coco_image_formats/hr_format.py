"""
HR (RASCAN / CoCo 3 Video RAM sequence) image format converter.
"""

from io import BytesIO


def extract_payload(data: bytes) -> bytearray:
    """Extract machine language binary payload, stripping SAVEM wrappers.

    Multiple SAVEM files appended together can be fully resolved here.
    Records evaluate starting with 0x00 (Payload) or 0xFF (EOF Header).
    """
    f = BytesIO(data)
    payload = bytearray()

    try:
        while f.tell() < len(data):
            sync = f.read(1)
            if not sync:
                break

            if sync[0] == 0x00:
                # Payload Block header: (Sync=0, Len_hi, Len_lo, Addr_hi, Addr_lo)
                length_bytes = f.read(2)
                if len(length_bytes) < 2:
                    break
                length = int.from_bytes(length_bytes, "big")

                # Skip the 2-byte Address
                f.read(2)

                # Read payload
                chunk = f.read(length)
                payload.extend(chunk)

            elif sync[0] == 0xFF:
                # EOF Block header: (Sync=255, 0, 0, Exec_hi, Exec_lo)
                f.read(4)

            else:
                # Unknown structure. Dump raw remainder directly to handle raw binaries.
                payload.extend(sync)
                payload.extend(f.read())
                break
    except Exception:
        pass

    return payload


def convert_hr_to_ppm(input_image_stream: bytes) -> tuple:
    """Convert HR chunk sequence byte block to PPM format.

    Args:
        input_image_stream: Raw concatenated bytes of HR* disk images

    Returns:
        Tuple of (ppm_data, width, height)
    """
    payload = extract_payload(input_image_stream)

    # 640x200 image at 2 bits per pixel takes 32000 bytes
    width, height = 640, 200
    expected_size = 32000

    # Pad payload just in case there are missing trailing sequences
    if len(payload) < expected_size:
        payload.extend(bytearray(expected_size - len(payload)))

    # Standard 4-shade Grayscale Palette (Inverted: 0 is White, 3 is Black)
    colors = [(255, 255, 255), (170, 170, 170), (85, 85, 85), (0, 0, 0)]

    # Build the target pixels
    rgb_data = bytearray(width * height * 3)

    for i in range(width * height):
        b_idx = i // 4
        pixel_in_byte = i % 4
        shift = 6 - (pixel_in_byte * 2)

        idx = (payload[b_idx] >> shift) & 0x03

        r, g, b = colors[idx]
        rgb_data[i * 3] = r
        rgb_data[i * 3 + 1] = g
        rgb_data[i * 3 + 2] = b

    ppm_header = f"P6\n{width} {height}\n255\n".encode("ascii")

    return bytes(ppm_header) + bytes(rgb_data), width, height
