# TRS-80 Color Computer Graphics File Formats

**Technical Reference for Programmers**

This document provides comprehensive technical specifications for three graphics file formats used on the TRS-80 Color Computer (CoCo): MAX, CM3, and CLP.

---

## Table of Contents

1. [MAX Format (CoCoMax 1/2)](#max-format-cocomax-12)
2. [CM3 Format (CoCoMax 3)](#cm3-format-cocomax-3)
3. [CLP Format (MAX-10 Clipboard)](#clp-format-max-10-clipboard)
4. [Implementation Notes](#implementation-notes)
5. [References](#references)

---

## MAX Format (CoCoMax 1/2)

### Overview

MAX files are simple bitmap graphics created by CoCoMax 1 and CoCoMax 2 software. They store monochrome or artifact-colored images with a minimal header structure.

### File Structure

```
┌─────────────────────────────────────┐
│ Header (5 bytes)                    │
├─────────────────────────────────────┤
│ Bitmap Data (variable length)      │
└─────────────────────────────────────┘
```

### Header Format (5 bytes)

| Offset | Size | Type    | Description                           |
|--------|------|---------|---------------------------------------|
| 0x00   | 1    | uint8   | Magic byte (should be 0x00)          |
| 0x01   | 2    | uint16  | File size in bytes (big-endian)      |
| 0x03   | 2    | uint16  | Reserved (typically 0x00 0x00)       |

### Bitmap Data

- **Format**: 1 bit per pixel (0 = black, 1 = white in monochrome mode)
- **Default Width**: 256 pixels
- **Default Height**: Calculated as `(size * 8) / width` rows
- **Layout**: Row-major order, left-to-right, top-to-bottom
- **Byte Encoding**: Each byte represents 8 horizontal pixels, MSB first

#### Calculating Dimensions

```c
// Given header values
uint16_t size = (header[1] << 8) | header[2];  // Big-endian
uint16_t width = 256;  // Default standard width
uint16_t rows = (size * 8) / width;

// Bytes per row
uint16_t bytes_per_row = width / 8;  // 32 bytes for 256-pixel width
```

### Artifact Colors (NTSC Composite Video)

MAX files can display colors on composite monitors through NTSC artifact coloring. This occurs because adjacent pixels create specific phase relationships in the composite video signal.

#### Arte Modes

| Mode | Name | Description                                    |
|------|------|------------------------------------------------|
| 0    | BW   | Black and white (no artifact colors)          |
| 1    | BR   | Blue-Red artifacts                            |
| 2    | RB   | Red-Blue artifacts (phase reversed)           |

#### NTSC Artifact Color Generation

When mode = 1 (BR) or mode = 2 (RB):

```c
// YIQ color space conversion for artifact colors
int x_phase = (mode == 1) ? -100 : 100;  // Phase alternates per pixel

for (int k = 0; k < 8; k++) {
    int ny = get_bit(byte_val, 7 - k) * 255;  // Current pixel luminance
    int y = (old_y + ny + (ny >> 2)) >> 1;    // Smooth luminance
    int i = (x_phase * (y - old_y)) >> 7;      // Color phase component

    // YIQ to RGB conversion
    int r = clip(y + 0.9563 * i);
    int g = clip(y - 0.2721 * i);
    int b = clip(y - 1.1070 * i);

    // Blend with previous pixel for smoothing
    output_rgb((r + old_r) >> 1, (g + old_g) >> 1, (b + old_b) >> 1);

    x_phase = -x_phase;  // Alternate phase
    old_y = ny;
    old_r = r; old_g = g; old_b = b;
}
```

### Example MAX File

```
Offset    Hex                                          ASCII
00000000  00 18 00 00 00 ff ff ff ff ff ff ff ff ...  .....ÿÿÿÿÿÿÿÿ
          │  └──┬──┘ └──┬──┘ └────── bitmap data
          │     │       └──── reserved
          │     └─────────── size = 0x1800 = 6144 bytes
          └─────────────── magic = 0x00

Dimensions: 256 × 192 pixels (6144 bytes × 8 bits / 256 width = 192 rows)
```

---

## CM3 Format (CoCoMax 3)

### Overview

CM3 files are compressed, 16-color palette-based images created by CoCoMax 3 for the TRS-80 Color Computer 3. They support two resolutions and include animation/cycling metadata.

### File Structure

```
┌─────────────────────────────────────┐
│ Picture Type Byte (1 byte)          │
├─────────────────────────────────────┤
│ Palette (16 bytes)                  │
├─────────────────────────────────────┤
│ Animation Rate (1 byte)             │
├─────────────────────────────────────┤
│ Cycle Rate (1 byte)                 │
├─────────────────────────────────────┤
│ Cycle Data (8 bytes)                │
├─────────────────────────────────────┤
│ Animation Flag (1 byte)             │
├─────────────────────────────────────┤
│ Cycle Flag (1 byte)                 │
├─────────────────────────────────────┤
│ Motif Data (243 bytes) [optional]   │
├─────────────────────────────────────┤
│ Compressed Image Data (variable)    │
└─────────────────────────────────────┘
```

### Header Format (29 bytes + optional 243 bytes)

| Offset | Size | Type     | Description                              |
|--------|------|----------|------------------------------------------|
| 0x00   | 1    | uint8    | Picture type byte                        |
| 0x01   | 16   | uint8[16]| 16-color palette (6-bit RGB)            |
| 0x11   | 1    | uint8    | Animation rate                           |
| 0x12   | 1    | uint8    | Cycle rate                               |
| 0x13   | 8    | uint8[8] | Cycle data (cm3cyc)                     |
| 0x1B   | 1    | uint8    | Animation flag (bit 7)                   |
| 0x1C   | 1    | uint8    | Cycle flag (bit 7)                       |
| 0x1D   | 243  | uint8[]  | Motif/pattern data (if sans_motifs = 0) |

#### Picture Type Byte (Byte 0)

```
Bit 7: Resolution flag
   0 = 192 rows (320 × 192)
   1 = 384 rows (320 × 384)

Bit 0: Sans motifs flag
   0 = Motif data present (243 bytes follow header)
   1 = No motif data (image data immediately follows header)

Bits 1-6: Reserved
```

**Calculating Resolution:**
```c
uint8_t pictyp = header[0];
uint16_t rows = ((pictyp >> 7) & 1) + 1) * 192;  // 192 or 384
bool sans_motifs = (pictyp & 1) != 0;
uint16_t cols = 320;  // Always 320 pixels wide
```

### Palette Format (16 bytes)

Each palette entry is a 6-bit RGB value packed into one byte:

```
Bit Layout:  7  6  5  4  3  2  1  0
             -  -  R1 G1 B1 R0 G0 B0

R = (bit[5] << 1) | bit[2]  → 0-3 (2-bit red)
G = (bit[4] << 1) | bit[1]  → 0-3 (2-bit green)
B = (bit[3] << 1) | bit[0]  → 0-3 (2-bit blue)
```

**Converting to 8-bit RGB:**
```c
uint8_t palette_byte = palette[index];

uint8_t r2 = (palette_byte >> 5) & 1;  // High bit of red
uint8_t g2 = (palette_byte >> 4) & 1;  // High bit of green
uint8_t b2 = (palette_byte >> 3) & 1;  // High bit of blue
uint8_t r1 = (palette_byte >> 2) & 1;  // Low bit of red
uint8_t g1 = (palette_byte >> 1) & 1;  // Low bit of green
uint8_t b1 = (palette_byte >> 0) & 1;  // Low bit of blue

uint8_t red   = (r2 * 2 + r1) * 85;  // Scale 0-3 to 0-255
uint8_t green = (g2 * 2 + g1) * 85;
uint8_t blue  = (b2 * 2 + b1) * 85;
```

**Standard CoCo 3 Palette:**
```
Index  Binary    RGB565   RGB888      Color Name
────────────────────────────────────────────────
  0    000000    0,0,0    0,0,0       Black
  1    000001    0,0,1    0,0,85      Dark Blue
  2    000010    0,1,0    0,85,0      Dark Green
  3    000011    0,1,1    0,85,85     Dark Cyan
  ...
 15    111111    3,3,3    255,255,255 White
```

### Image Data Compression

CM3 uses a sophisticated two-stage compression algorithm with reference buffers.

#### Page Structure

```c
for (int page = 0; page < num_pages; page++) {
    uint8_t lines = read_byte();  // Number of lines in this page

    for (int line = 0; line < lines; line++) {
        uint8_t control = read_byte();  // Control byte

        if (control < 128) {
            // COMPRESSED MODE
            decompress_line(control);
        } else {
            // UNCOMPRESSED MODE (control >= 128)
            read_direct_line();
        }
    }
}
```

#### Compression Modes

**Mode 1: Uncompressed (control >= 128)**
```c
// Read 160 bytes directly (320 pixels, 2 pixels per byte)
for (int i = 0; i < 160; i++) {
    uint8_t byte = read_byte();
    uint8_t pixel1 = (byte >> 4) & 0x0F;  // High nibble
    uint8_t pixel2 = byte & 0x0F;          // Low nibble
    output_pixel(palette[pixel1]);
    output_pixel(palette[pixel2]);
}
```

**Mode 2: Compressed (control < 128)**

Uses two reference buffers to reconstruct the line:

```c
// Read reference buffers
uint8_t buff1[20];   // 160 bits for control
uint8_t buff2[control];  // Variable length data

for (int i = 0; i < 20; i++) buff1[i] = read_byte();
for (int i = 0; i < control; i++) buff2[i] = read_byte();

// Decode 160 bytes using reference buffers
int u = 0, bitu = 7;  // buff1 position
int y = 0, bity = 7;  // buff2 position

for (int x = 0; x < 160; x++) {
    // Read control bit from buff1
    int bit1 = (buff1[u] >> bitu) & 1;
    if (--bitu < 0) { bitu = 7; u++; }

    if (bit1 == 0) {
        // Copy from previous pixel
        linbuf[x] = linbuf[x - 1];
    } else {
        // Read second control bit from buff2
        int bit2 = (buff2[y] >> bity) & 1;
        if (--bity < 0) { bity = 7; y++; }

        if (bit2 == 0) {
            // Copy from previous line
            linbuf[x] = linbuf[x];  // (unchanged)
        } else {
            // New data
            linbuf[x] = read_byte();
        }
    }

    // Output 2 pixels from this byte
    output_pixel(palette[linbuf[x] >> 4]);
    output_pixel(palette[linbuf[x] & 0x0F]);
}
```

### Pixel Format

Each byte encodes **2 pixels** as 4-bit palette indices:

```
Byte: 0xA5 = 1010 0101
         │    │    │
         │    │    └──► Pixel 2: index 5 (right pixel)
         │    │
         │    └───────► Pixel 1: index 10 (left pixel)
```

### Example CM3 File

```
Offset    Hex                                          Description
00000000  80 00 12 24 36 09 1B 2D 3F 08 1A 2C 3E ...  Pictyp=0x80 (384 rows)
00000001  00 12 24 36 09 1B 2D 3F ...                 16-byte palette
00000011  00                                           Animation rate
00000012  00                                           Cycle rate
00000013  00 00 00 00 00 00 00 00                     Cycle data
0000001B  00                                           Animation flag
0000001C  00                                           Cycle flag
0000001D  C0 14 15 16 ...                             Page 0 start
```

---

## CLP Format (MAX-10 Clipboard)

### Overview

CLP files are clipboard format files from MAX-10, a word processor for the Color Computer. They can contain text, rulers, page breaks, and embedded monochrome pictures. This format is container-based with tagged paragraphs.

### File Structure

```
┌─────────────────────────────────────┐
│ Header (11 bytes)                   │
├─────────────────────────────────────┤
│ Paragraph 1 (tagged)                │
├─────────────────────────────────────┤
│ Paragraph 2 (tagged)                │
├─────────────────────────────────────┤
│ ...                                 │
├─────────────────────────────────────┤
│ End Tag (0x64)                      │
└─────────────────────────────────────┘
```

### Header Format (11 bytes)

| Offset | Size | Type    | Description                                    |
|--------|------|---------|------------------------------------------------|
| 0x00   | 1    | uint8   | Start word boundary flag (0 or non-zero)      |
| 0x01   | 1    | uint8   | End word boundary flag (0 or non-zero)        |
| 0x02   | 2    | uint16  | Number of paragraphs (big-endian)             |
| 0x04   | 2    | uint16  | Estimated memory size in bytes (big-endian)   |
| 0x06   | 1    | uint8   | String only flag (0 = full document)          |
| 0x07   | 2    | uint16  | First paragraph size in bytes (big-endian)    |
| 0x09   | 2    | uint16  | Last string size in bytes (big-endian)        |

**Word Boundary Flags**: Used by the Paste operation to determine when to insert spaces. Set to 0 if creating a full file from scratch.

**Estimated Memory Size**: File size + ~9 bytes per paragraph (for memory allocation check).

### Paragraph Tag System

Each paragraph begins with a tag byte that identifies its type:

| Tag  | Name       | Description                                   |
|------|------------|-----------------------------------------------|
| 0x00 | Text       | Full text paragraph (includes Return)         |
| 0x20 | String     | Partial text paragraph (no trailing Return)   |
| 0x01 | Picture    | Embedded bitmap image                         |
| 0x02 | Page Break | Page break marker (no additional data)        |
| 0xFF | Ruler      | Formatting ruler (27 bytes of data)           |
| 0x64 | End of Data| Marks end of clipboard data                   |

### Picture Paragraph Format (Tag 0x01)

After the 0x01 tag byte:

| Offset | Size | Type    | Description                                    |
|--------|------|---------|------------------------------------------------|
| 0x00   | 2    | uint16  | Paragraph size in bytes (big-endian)          |
| 0x02   | 2    | uint16  | Left position (8-576 pixels, 1/80 inch)       |
| 0x04   | 2    | uint16  | Vertical size in lines (1/72 inch)            |
| 0x06   | 2    | uint16  | Horizontal width in pixels (1/80 inch)        |
| 0x08   | 2    | uint16  | Bit image height in scan lines                |
| 0x0A   | 2    | uint16  | Bit image width in pixels                     |
| 0x0C   | 1    | uint8   | Bytes per line (with padding)                 |
| 0x0D   | var  | uint8[] | Bitmap data (height × bytes_per_line)         |

**Paragraph Size**: Should be `20 + (image_height × bytes_per_line)`

**Bitmap Format**:
- 1 bit per pixel: 0 = white, 1 = black
- MSB first (leftmost pixel is bit 7)
- Each line must have at least 1 blank byte (8 pixels) of padding
- Maximum image size: 7660 bytes total

**Calculating Bytes Per Line**:
```c
uint16_t bytes_per_line = (image_width + 7) / 8;  // Round up
if ((image_width % 8) != 0) {
    bytes_per_line++;  // Add blank padding byte
}
```

### Bitmap Data Encoding

```c
// Example: 32-pixel wide image
// Each row is 5 bytes: 4 bytes (32 pixels) + 1 blank padding byte

Row data: 0x00 0x00 0x0F 0xFF 0x00
          │    │    │    │    │
          │    │    │    │    └──► Padding (8 blank pixels)
          │    │    │    └───────► Pixels 25-32: 11111111
          │    │    └────────────► Pixels 17-24: 00001111
          │    └─────────────────► Pixels 9-16:  00000000
          └──────────────────────► Pixels 1-8:   00000000

Bitmap layout:
  Byte 0, Bit 7 = Pixel 0 (leftmost)
  Byte 0, Bit 0 = Pixel 7
  Byte 1, Bit 7 = Pixel 8
  ...
```

### Text Paragraph Format (Tag 0x00 or 0x20)

After the tag byte:

| Offset | Size | Type    | Description                                    |
|--------|------|---------|------------------------------------------------|
| 0x00   | 2    | uint16  | Text length in bytes (big-endian)             |
| 0x02   | 1    | uint8   | Starting font tag (0xA0 + font_number)        |
| 0x03   | 1    | uint8   | Starting style byte                           |
| 0x04   | var  | uint8[] | Text with embedded font/style tag pairs       |

**Style Byte Format**:
```
Bit Layout: 1 0 0 L H U I B

B = Bold
I = Italic
U = Underline
H = Superscript
L = Subscript
(H and L should never both be set)
```

**Font Tags**: 0xA0 to 0xA7 (fonts 0-7)

### Ruler Paragraph Format (Tag 0xFF)

Fixed 27 bytes of formatting data:

| Offset | Size | Type    | Description                                    |
|--------|------|---------|------------------------------------------------|
| 0x00   | 2    | uint16  | Right margin (8-576 pixels)                   |
| 0x02   | 2    | uint16  | Indent (first line left margin)               |
| 0x04   | 2    | uint16  | Left margin (subsequent lines)                |
| 0x06   | 16   | uint16[8]| Tab positions (40000 = unused)               |
| 0x16   | 1    | uint8   | Tab enable flag (0 = no tabs, 1 = tabs)       |
| 0x17   | 1    | uint8   | Justification (0=Full, 1=Left, 2=Center, 255=Right) |
| 0x18   | 1    | uint8   | Line spacing (0=Single, 100=1.5, 200=Double)  |
| 0x19   | 2    | uint16  | Reserved (always 0)                           |

All measurements in pixels at 1/80 inch per pixel.

### Example CLP File (Picture Clipart)

```
Offset    Hex                                          Description
────────────────────────────────────────────────────────────────────
00000000  00 00                                        Word boundary flags
00000002  00 03                                        3 paragraphs
00000004  01 5E                                        350 bytes estimated memory
00000006  00                                           Not string-only
00000007  00 20                                        First para size = 32
00000009  00 20                                        Last para size = 32
0000000B  01                                           Tag: Picture paragraph
0000000C  01 2C                                        Para size = 300 bytes
0000000E  00 0A                                        Left position = 10 pixels
00000010  00 38                                        Vertical size = 56 lines
00000012  00 20                                        Width = 32 pixels
00000014  00 38                                        Image height = 56 lines
00000016  00 20                                        Image width = 32 pixels
00000018  05                                           5 bytes per line
00000019  00 00 0F FF 00 00 00 08 00 ...              Bitmap (56 rows × 5 bytes)
00000131  64                                           Tag: End of data
```

---

## Implementation Notes

### Common Pitfalls

1. **Endianness**:
   - MAX/CLP formats use **big-endian** (MSB first) for multi-byte values
   - Always use proper byte order conversion when reading 16-bit values

2. **Bit Order**:
   - All bitmap formats use **MSB first** for pixel data
   - Leftmost pixel is bit 7, rightmost is bit 0

3. **Padding**:
   - CLP images require at least 8 blank pixels at the end of each row
   - Don't forget to account for padding when calculating buffer sizes

4. **Color Space**:
   - CM3 uses 6-bit RGB (64 colors max), not 8-bit RGB (256 per channel)
   - Scale appropriately: `rgb8 = rgb2 * 85` (0→0, 1→85, 2→170, 3→255)

5. **Compression State**:
   - CM3 decompression maintains line buffers between rows
   - Must preserve `linbuf` state when decoding compressed lines

### Performance Optimization

**Memory Management**:
```c
// Pre-allocate output buffer to avoid reallocations
int width = 320, height = 192;
int buffer_size = width * height * 3;  // RGB
uint8_t* output = malloc(buffer_size);
```

**Bit Extraction Macro**:
```c
#define GET_BIT(byte, bit) (((byte) >> (bit)) & 1)
```

**Efficient Palette Lookup**:
```c
// Pre-compute RGB palette at file load
typedef struct { uint8_t r, g, b; } RGB;
RGB palette_rgb[16];

void build_palette(uint8_t* palette_data) {
    for (int i = 0; i < 16; i++) {
        uint8_t c = palette_data[i];
        palette_rgb[i].r = ((c >> 5) & 1) * 2 + ((c >> 2) & 1)) * 85;
        palette_rgb[i].g = ((c >> 4) & 1) * 2 + ((c >> 1) & 1)) * 85;
        palette_rgb[i].b = ((c >> 3) & 1) * 2 + ((c >> 0) & 1)) * 85;
    }
}
```

### Error Handling

**Validation Checks**:
```c
// MAX format
if (header[0] != 0x00) {
    return ERROR_INVALID_MAGIC;
}

// CM3 format
if (width != 320) {
    return ERROR_INVALID_WIDTH;
}
if (rows != 192 && rows != 384) {
    return ERROR_INVALID_HEIGHT;
}

// CLP format
if (tag == 0x01) {  // Picture
    if (bytes_per_line < (image_width + 7) / 8) {
        return ERROR_INVALID_LINE_SIZE;
    }
}
```

### Output Formats

**PPM (Portable Pixmap)**:
```c
// P6 = binary RGB
fprintf(out, "P6\n%d %d\n255\n", width, height);
fwrite(rgb_data, 1, width * height * 3, out);
```

**PNG**:
Use a library like libpng or stb_image_write for PNG output.

---

## References

### Source Files

- `main.py` - Reference implementation for all three formats
- `coco_dsk.py` - DSK image handler for extracting files
- `maxtoppm_source.py` - Original MAX converter from coco-tools
- `CLP File.txt` - MAX-10 technical reference guide

### Format Origins

- **MAX**: CoCoMax 1/2 by Colorware
- **CM3**: CoCoMax 3 by Colorware
- **CLP**: MAX-10 Word Processor by Dave Stampe

### External Resources

- coco-tools: https://github.com/jamieleecho/coco-tools
- Color Computer Archive: https://colorcomputerarchive.com
- CoCopedia: https://www.cocopedia.com

### Acknowledgments

- Jamie Cho (jamieleecho) - coco-tools package
- Mathieu Bouchard - cm3toppm implementation
- Dave Stampe - MAX-10 CLP format specification
- Colorware - Original MAX and CM3 software

---

**Document Version**: 1.0
**Last Updated**: November 2025
**Maintained by**: Chipshift reyco2000@gmail part of theCoCo Community

