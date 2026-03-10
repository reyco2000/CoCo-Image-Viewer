# NIB Format (Nibble Compression)

### Overview
The NIB (Nibble) format is a compressed image format created for the TRS-80 Color Computer 3 (CoCo 3) by "Wolf". It stores 640x200 pixel images with 4 colors using a sophisticated two-level bitmap and nibble compression scheme. NIB files were originally loaded via the `NIBLOADR.BIN` machine language program driven by a BASIC loader. 

### File Structure
NIB files are encapsulated within a standard **DECB BIN** (Disk Extended Color BASIC binary) container format. The file contains a single data segment loaded at `$2000`, followed by an execution block. 

```text
┌─────────────────────────────────┐
│ DECB Segment Header (5 bytes)   │
│   $00 (segment flag)            │
│   $XX $XX (length)              │
│   $XX $XX (load address)        │
├─────────────────────────────────┤
│ Image Data Segment              │
│   Pointer to Header (2 bytes)   │
│   Pass 1 Packed Data            │
│   Bitmap 1                      │
│   Header (34 bytes)             │
├─────────────────────────────────┤
│ DECB Exec Block (5 bytes)       │
│   $FF (exec flag)               │
│   $00 $00 (unused)              │
│   $00 $00 (exec address)        │
└─────────────────────────────────┘
```

The underlying image data logic uses internal memory remap pointers based on the CoCo 3 MMU remapping everything to CPU address `$4000`. To find the file offset for a mapped CPU address: `file_offset = (cpu_address - $4000) + 5`.

### Header Format (34 bytes)
The header resides at the very end of the segment data. The first 2 bytes of the segment contain a big-endian pointer to this header.

| Offset | Dest | Size | Type | Description |
|--------|------|------|----------|-------------|
| 0x00 | $4000 | 2 | uint16 | Replacement bytes (overwrites $4000 ptr) |
| 0x02 | $0E3B | 16 | uint8[16] | Embedded palette (16 GIME color values) |
| 0x12 | $0E4B | 1 | uint8 | GIME border color value |
| 0x13 | $0E4C | 1 | uint8 | XOR delta flag (0=no delta, non-zero=apply XOR) |
| 0x14 | $0E4D | 1 | uint8 | (unused/padding) |
| 0x15 | $0E4E | 2 | uint16 | `bitmap2_src` - CPU addr of bitmap 2 in pass 1 output |
| 0x17 | $0E50 | 2 | uint16 | `bitmap2_dest_end` - End addr of bitmap 2 dest |
| 0x19 | $0E52 | 2 | uint16 | `pass1_end` - End addr of pass 1 output |
| 0x1B | $0E54 | 2 | uint16 | `bitmap1_src` - CPU addr of bitmap 1 in file data |
| 0x1D | $0E56 | 2 | uint16 | `bitmap1_dest_end` - End addr of bitmap 1 dest |
| 0x1F | $0E58 | 3 | uint8[3] | (unused tail bytes) |

> **Note:** All 16-bit pointers are big-endian.

### Embedded Palette Format
The header contains a 16-entry palette using standard 6-bit GIME Color Values. However, the display operates in 2bpp mode (4 colors). The BASIC loader typically overrides the first 4 palette colors with its own RGB or Composite monitor selection, making the embedded NIB file palette largely unused.

Common 4-color selections (using GIME RGB scaling `rgbrgb * 85`):
* **RGB Mode**: 1 (dark blue), 32 (dark red), 38 (orange), 60 (pinkish white)
* **CMP Mode**: 10 (medium blue), 8 (dark blue), 38 (orange), 55 (light yellow)

### Image Data Compression
The NIB format utilizes a sophisticated **Two-Pass Decompression Algorithm**.

#### Pass 1: Byte-level RLE 
The first pass expands byte-level data using `bitmap1`. Each bit in `bitmap1` corresponds to an output byte. 
- **Bit 1**: Read a new byte from `packed_data`.
- **Bit 0**: Repeat the previous byte value.

```c
uint8_t bit_mask = 0x80;
while (output_index < pass1_out_size) {
    if (bitmap1[bitmap_index] & bit_mask) {
        prev_value = read_packed_data_byte();
    }
    output[output_index++] = prev_value;
    
    // Advance mask
    bit_mask >>= 1;
    if (bit_mask == 0) { bit_mask = 0x80; bitmap_index++; }
}
```

#### Pass 2: Nibble-level RLE 
The output of Pass 1 acts as a dictionary containing both `bitmap2` and `nibble_data`. 
Pass 2 generates the 32,768 bytes of display screen RAM. Every screen byte requires exactly 2 bits from `bitmap2` (one for the high nibble, one for the low nibble).

```c
uint8_t cd = 0; // high nibble
uint8_t cc = 0; // low nibble
uint8_t toggle = 0; // toggle flag for nibble extraction

for(int i=0; i<32768; i++) {
    // High Nibble
    if (read_bitmap2_bit() == 1) extract_nibble(&cd, &cc, &toggle);
    screen[i] = cd;
    
    // Low Nibble
    if (read_bitmap2_bit() == 1) extract_nibble(&cd, &cc, &toggle);
    screen[i] |= cc;
}
```

**Nibble Extraction Toggle Logic:**
The packed nibble array contains two 4-bit values per byte. The extraction logic alternates reading the high and low nibbles, only advancing the source byte index after consuming the lower nibble.

#### XOR Delta Decode (Optional)
If the XOR delta flag (at header offset `0x13`) is non-zero, a vertical line-by-line XOR pass is applied to the fully decompressed screen RAM grid to finalize the pixel states. Each line is XOR'd with the line directly above it (160 bytes offset).

```c
for (int i = 160; i < 32000; i++) {
    screen[i] ^= screen[i - 160];
}
```

### Pixel Format
The final display uses **2bpp** (2 bits per pixel), 4 colors. It runs at standard CoCo 3 `$FF99` `0x3D` (160 bytes/row) resolution. 
Each byte contains 4 pixels, mapped from Most-Significant-Bit to Least-Significant-Bit.

```
Byte: 0x96 = 1001 0110
         │ │ │ │   │ │
         │ │ │ │   └─┴► Pixel 3: color 2
         │ │ │ │
         │ │ └─┴──────► Pixel 2: color 1
         │ │
         └─┴──────────► Pixel 1: color 2
```

### Example NIB File 
Using `RCHARLES.NIB` as a reference:

```text
Offset    Hex                                          Description
00000000  00 5B 9F 20 00                               DECB Segment ($5B9F len, $2000 load)
00000005  9B 7C ...                                    Header ptr -> $9B7C (mapped CPU)
...                                                    (Pass1 packed data)
00004F73  (Bitmap 1 data begins, offset 0x4F6E)        ...
00005B81  00 00 ...                                    Header begins (offset 0x5B7C)
00005B83  00 07 38 3F 3F 1F 09 26 ...                  Header: embedded GIME palette
...
00005B94  00                                           Header: XOR flag = 0
00005B96  80 77                                        Header: bitmap2_src = $8077
...
```
