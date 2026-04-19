"""
MAX (CoCo MAX) image format converter.
"""

from io import BytesIO

from .utils import clip, getbit, pack


def convert_max_to_ppm(
    input_image_stream, arte, newsroom, cols, rows, skip, ignore_header_errors
):
    """Convert MAX format to PPM.

    Args:
        input_image_stream: Raw bytes of the MAX file
        arte: Artifact mode (0=BW, 1=BR, 2=RB)
        newsroom: Whether this is a newsroom format
        cols: Number of columns (width)
        rows: Number of rows (height), or None to auto-detect
        skip: Bytes to skip at start
        ignore_header_errors: Whether to ignore header validation errors

    Returns:
        Tuple of (ppm_data, width, height) or (None, None, None) on error
    """
    br2 = [pack(x) for x in [[0, 0, 0], [255, 85, 0], [0, 170, 255], [255, 255, 255]]]
    br3 = [pack(x) for x in [[0, 0, 0], [255, 0, 0], [0, 0, 255], [255, 255, 255]]]
    semig = [
        pack(x)
        for x in [
            [0, 0, 0],
            [0, 255, 0],
            [255, 255, 0],
            [0, 0, 255],
            [255, 0, 0],
            [255, 255, 255],
            [0, 211, 170],
            [204, 0, 255],
            [255, 128, 0],
        ]
    ]

    f = BytesIO(input_image_stream)
    out = BytesIO()

    if skip:
        f.read(skip)

    if newsroom:
        head = f.read(2)
        cols = head[0] * 8
        rows = head[1]
    else:
        head = f.read(5)
        if head[0] != 0:
            if not ignore_header_errors:
                return None, None, None
        if not rows:
            size = head[1] * 256 + head[2]
            rows = 8 * size // cols
            if cols * rows // 8 != size:
                if not ignore_header_errors:
                    return None, None, None

    out.write(f"P6\n{cols} {rows}\n255\n".encode("ascii"))
    for jj in range(rows):
        row_data = f.read(cols >> 3)
        oy = r2 = g2 = b2 = 0
        for v in row_data:
            if arte == 0:  # PIXEL_MODE_BW
                for k in range(8):
                    out.write(br2[getbit(v, 7 - k) * 3])
            elif (arte == 1) or (arte == 2):  # PIXEL_MODE_BR or PIXEL_MODE_RB
                x = -100 if arte == 1 else 100
                for k in range(8):
                    ny = getbit(v, 7 - k) * 255
                    y = (oy + ny + (ny >> 2)) >> 1
                    i = (x * (y - oy)) >> 7
                    r = clip(int((y + 0.9563 * i)))
                    g = clip(int((y - 0.2721 * i)))
                    b = clip(int((y - 1.1070 * i)))
                    out.write(pack([(r + r2) >> 1, (g + g2) >> 1, (b + b2) >> 1]))
                    oy = ny
                    x = -x
                    r2 = r
                    g2 = g
                    b2 = b
            elif arte == 3:  # PIXEL_MODE_BR2
                for k in range(4):
                    out.write(br2[getbit(v, 7 - k - k) * 2 + getbit(v, 6 - k - k)] * 2)
            elif arte == 4:  # PIXEL_MODE_RB2
                for k in range(4):
                    out.write(br2[getbit(v, 7 - k - k) + getbit(v, 6 - k - k) * 2] * 2)
            elif arte == 5:  # PIXEL_MODE_BR3
                for k in range(4):
                    out.write(br3[getbit(v, 7 - k - k) * 2 + getbit(v, 6 - k - k)] * 2)
            elif arte == 6:  # PIXEL_MODE_RB3
                for k in range(4):
                    out.write(br3[getbit(v, 7 - k - k) + getbit(v, 6 - k - k) * 2] * 2)
            elif arte == 7:  # PIXEL_MODE_S10
                for k in range(4):
                    out.write(semig[1 + getbit(v, 7 - k - k) + getbit(v, 6 - k - k) * 2] * 2)
            elif arte == 8:  # PIXEL_MODE_S11
                for k in range(4):
                    out.write(semig[5 + getbit(v, 7 - k - k) + getbit(v, 6 - k - k) * 2] * 2)

    return out.getvalue(), cols, rows
