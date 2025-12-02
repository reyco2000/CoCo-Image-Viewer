"""
MAC (MacPaint) image format converter.
"""

from io import BytesIO
from .utils import pack


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
