"""
CM3 (CoCoMax 3) image format converter.
"""

from io import BytesIO

from .utils import getbit, pack


def convert_cm3_to_ppm(input_image_stream):
    """Convert CM3 (CoCoMax 3) format to PPM.

    Args:
        input_image_stream: Raw bytes of the CM3 file

    Returns:
        Tuple of (ppm_data, width, height)
    """
    f = BytesIO(input_image_stream)
    out = BytesIO()

    # Read picture type byte
    cols = 320
    pictyp = f.read(1)[0]
    rows = (getbit(pictyp, 7) + 1) * 192  # 192 or 384 rows
    sans_motifs = getbit(pictyp, 0) != 0

    # Read palette (16 bytes)
    palette = list(f.read(16))

    # Precalculate RGB tuples for the palette to save time in the loop
    ppm_palette = [b""] * 16
    for i, c in enumerate(palette):
        r = (getbit(c, 5) * 2 + getbit(c, 2)) * 85
        g = (getbit(c, 4) * 2 + getbit(c, 1)) * 85
        b = (getbit(c, 3) * 2 + getbit(c, 0)) * 85
        ppm_palette[i] = pack([r, g, b])

<<<<<<< HEAD
    # Read animation and cycle data
    anirat = f.read(1)[0]
    cycrat = f.read(1)[0]
    cm3cyc = list(f.read(8))
    aniflg = (f.read(1)[0] & 0x80) != 0
    cycflg = (f.read(1)[0] & 0x80) != 0
=======
    # Read animation and cycle data (values unused but must advance stream)
    _anirat = f.read(1)[0]
    _cycrat = f.read(1)[0]
    _cm3cyc = [f.read(1)[0] for _ in range(8)]
    _aniflg = (f.read(1)[0] & 0x80) != 0
    _cycflg = (f.read(1)[0] & 0x80) != 0
>>>>>>> a628ae3 (Add typechecking and liting, automate package creation)

    # Skip motif data if present
    if not sans_motifs:
        f.read(243)

    # Initialize buffers for decompression
    linbuf = [0] * 160
    buff1 = [0] * 20
    buff2 = []

    # Write PPM header
    out.write(f"P6\n{cols} {rows}\n255\n".encode("ascii"))

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
                buff1 = list(f.read(20))
                buff2 = list(f.read(contr))

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
                out.write(ppm_palette[a >> 4])  # High nibble
                out.write(ppm_palette[a & 15])  # Low nibble
                x += 1

    return out.getvalue(), cols, rows
