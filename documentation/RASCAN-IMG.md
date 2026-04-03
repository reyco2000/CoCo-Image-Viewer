# RASCAN / Digiscan Image Format Specification (IMG & HR)

Technical reference for the IMG and HR image formats used by the RASCAN and Digiscan digitizer software on the TRS-80 Color Computer 3 (CoCo 3). This document contains everything needed to implement a decoder from scratch.

---

## Table of Contents

1. [Overview](#overview)
2. [IMG Format](#img-format)
   - [File Header](#img-file-header)
   - [RLE Compression](#rle-compression-algorithm)
   - [Video Modes](#video-modes)
   - [CoCo 3 Palette Decoding](#coco-3-hardware-palette-decoding)
   - [Pixel Decoding by Mode](#pixel-decoding-by-mode)
3. [HR Format](#hr-format)
   - [Multi-File Structure](#multi-file-structure)
   - [SAVEM Container](#savem-decb-bin-container)
   - [Pixel Decoding](#hr-pixel-decoding)
4. [Complete Decoder Pseudocode](#complete-decoder-pseudocode)
5. [Reference Implementation Notes](#reference-implementation-notes)

---

## Overview

The RASCAN digitizer hardware for the CoCo 3 captured real-world images (via a video camera or other analog source) and stored them in two related formats:

| Format | Extension | Resolution | Colors | Compression | Files per Image |
|--------|-----------|------------|--------|-------------|-----------------|
| IMG    | `.IMG`    | 320x200 or 640x200 | 4, 16, or 4096 | RLE | 1 |
| HR     | `.HR0`-`.HR3` | 640x200 | 4 grayscale | None (raw VRAM) | 4 |

Both formats target the CoCo 3's GIME chip video modes and store pixel data in the same byte-packing order used by the hardware.

---

## IMG Format

### IMG File Header

The IMG file begins with an 18-byte header, followed by one or more RLE-compressed data buffers.

```
Offset  Size  Description
------  ----  -----------
0       1     Dummy byte (ignored, skip it)
1       1     Video mode (0-4)
2-17    16    Palette values (one byte each, CoCo 3 hardware palette format)
18+     ...   RLE-compressed image buffer(s)
```

#### Video Mode Byte (Offset 1)

| Value | Mode Name              | Resolution | Colors | Bits/Pixel | Buffers | Buffer Size (decompressed) |
|-------|------------------------|------------|--------|------------|---------|---------------------------|
| 0     | 4-Color Grayscale      | 640x200    | 4      | 2          | 1       | 32,000 bytes              |
| 1     | 16-Color               | 320x200    | 16     | 4          | 1       | 32,000 bytes              |
| 2     | 16-Color Dithered Gray | 640x200    | 16     | 4          | 1       | 64,000 bytes              |
| 3     | 4096-Color FlikPic     | 320x200    | 4096   | 4x3        | 3       | 32,000 bytes each         |
| 4     | 3D Anaglyph            | 320x200    | 16x2   | 4x2        | 2       | 32,000 bytes each         |

#### Palette Values (Offsets 2-17)

Each of the 16 palette bytes is a CoCo 3 hardware palette value. See [CoCo 3 Hardware Palette Decoding](#coco-3-hardware-palette-decoding) below for how to convert these to RGB.

**Important**: For Mode 0 (4-color grayscale), the header palette should be **ignored** because it often contains residual garbage from memory. Use a hardcoded inverted grayscale palette instead (see [Mode 0 decoding](#mode-0-4-color-grayscale-640x200)).

---

### RLE Compression Algorithm

Image data after the header is stored as one or more RLE-compressed buffers. Each buffer is independently compressed using the same algorithm.

#### Concept

The compression uses **alternating blocks** that toggle between two types:
- **Uncompressed block**: a length byte followed by that many literal data bytes
- **Compressed (RLE) block**: a length byte followed by a single byte to repeat

The decoder starts in **uncompressed** state and toggles after each block.

#### Termination

A buffer ends when two consecutive `0x00` bytes are encountered. A single `0x00` byte (a zero-length block) toggles the state without producing any output data.

#### Step-by-Step Decompression Algorithm

```
function read_buffer(stream):
    output = empty byte array
    state = UNCOMPRESSED    # start in uncompressed mode
    last_was_zero = false

    loop:
        byte = read 1 byte from stream
        if end of stream: break

        if byte == 0x00:
            if last_was_zero:
                break           # 0x00 0x00 = end of buffer
            last_was_zero = true
            state = toggle(state)   # flip between UNCOMPRESSED and COMPRESSED
            continue                # no data produced for zero-length block

        last_was_zero = false

        if state == UNCOMPRESSED:
            data = read <byte> bytes from stream
            append data to output
        else:  # COMPRESSED (RLE)
            value = read 1 byte from stream
            append <value> repeated <byte> times to output

        state = toggle(state)       # flip state after each block

    return output
```

#### Worked Example

Given the byte sequence: `03 AA BB CC 04 DD 00 02 EE FF 00 00`

| Step | State        | Length | Action                      | Output appended  |
|------|--------------|--------|-----------------------------|------------------|
| 1    | Uncompressed | 3      | Read 3 literal bytes        | `AA BB CC`       |
| 2    | Compressed   | 4      | Repeat `DD` 4 times         | `DD DD DD DD`    |
| 3    | (zero)       | 0      | Toggle state, no data       | (nothing)        |
| 4    | Compressed   | 2      | Repeat ... wait, state toggled twice so now Uncompressed | Read 2 literal bytes `EE FF` |
| 5    | (zero+zero)  | 0x00   | Second consecutive zero: **END** | |

**Final output**: `AA BB CC DD DD DD DD EE FF`

> Note: The zero-length block toggles state without consuming data, which allows two consecutive blocks of the same type when needed.

---

### Video Modes

#### Number of Buffers per Mode

| Mode | Buffers | Description |
|------|---------|-------------|
| 0    | 1       | Single buffer, 2bpp |
| 1    | 1       | Single buffer, 4bpp |
| 2    | 1       | Single buffer, 4bpp |
| 3    | 3       | Separate Red, Green, Blue buffers (4bpp each) |
| 4    | 2       | Buffer 1 = Red channel, Buffer 2 = Cyan channel (4bpp each) |

For modes with multiple buffers, call the `read_buffer` decompression function once per buffer, sequentially from the stream. Each buffer is independently compressed and terminated with its own `0x00 0x00` sequence.

---

### CoCo 3 Hardware Palette Decoding

The CoCo 3 GIME chip uses a 6-bit palette encoding packed into a single byte. The bit layout is:

```
Bit:   7  6  5  4  3  2  1  0
       -  -  R1 G1 B1 R0 G0 B0
```

Bits 7-6 are unused. The RGB channels are each 2 bits, but the bits are **not contiguous** -- the high bit and low bit of each channel are separated:

| Channel | High Bit | Low Bit | 2-Bit Value |
|---------|----------|---------|-------------|
| Red     | Bit 5    | Bit 2   | `(bit5 * 2) + bit2` |
| Green   | Bit 4    | Bit 1   | `(bit4 * 2) + bit1` |
| Blue    | Bit 3    | Bit 0   | `(bit3 * 2) + bit0` |

Each 2-bit channel value (0-3) maps to 8-bit RGB by multiplying by 85:

| 2-Bit Value | 8-Bit Value |
|-------------|-------------|
| 0           | 0           |
| 1           | 85          |
| 2           | 170         |
| 3           | 255         |

#### Palette Decoding Formula

```
function decode_coco3_palette(byte):
    r = (getbit(byte, 5) * 2 + getbit(byte, 2)) * 85
    g = (getbit(byte, 4) * 2 + getbit(byte, 1)) * 85
    b = (getbit(byte, 3) * 2 + getbit(byte, 0)) * 85
    return (r, g, b)

function getbit(value, bit_position):
    return (value >> bit_position) & 1
```

#### Example

Palette byte `0x3F` = binary `00111111`:
- R = (bit5=0, bit2=1) = `(0*2 + 1)` = 1 -> 85
- G = (bit4=1, bit1=1) = `(1*2 + 1)` = 3 -> 255
- B = (bit3=1, bit0=1) = `(1*2 + 1)` = 3 -> 255
- Result: RGB(85, 255, 255) = bright cyan

---

### Pixel Decoding by Mode

#### Mode 0: 4-Color Grayscale (640x200)

- **1 buffer**, 32,000 bytes decompressed
- **2 bits per pixel**, 4 pixels per byte, MSB first
- **Ignore the file palette**. Use this hardcoded inverted grayscale:

| Index | RGB Value       | Shade |
|-------|-----------------|-------|
| 0     | (255, 255, 255) | White |
| 1     | (170, 170, 170) | Light gray |
| 2     | (85, 85, 85)    | Dark gray |
| 3     | (0, 0, 0)       | Black |

**Pixel extraction** (for pixel index `i` in a linear scan left-to-right, top-to-bottom):

```
byte_index = i / 4          (integer division)
pixel_in_byte = i % 4       (0 = leftmost, 3 = rightmost)
shift = 6 - (pixel_in_byte * 2)
color_index = (buffer[byte_index] >> shift) & 0x03
```

#### Mode 1: 16-Color (320x200)

- **1 buffer**, 32,000 bytes decompressed
- **4 bits per pixel**, 2 pixels per byte
- Uses the **file header palette** decoded via CoCo 3 hardware palette

**Pixel extraction** (for pixel index `i`):

```
byte_index = i / 2
if i is even:
    color_index = buffer[byte_index] >> 4       # high nibble = left pixel
else:
    color_index = buffer[byte_index] & 0x0F     # low nibble = right pixel
```

Look up `color_index` in the decoded 16-color palette to get RGB.

#### Mode 2: 16-Color Dithered Grayscale (640x200)

- **1 buffer**, 64,000 bytes decompressed
- **4 bits per pixel**, 2 pixels per byte
- Uses the **file header palette** decoded via CoCo 3 hardware palette
- Pixel extraction is **identical to Mode 1**
- The palette typically contains grayscale values; the dithering is baked into the pixel data by the digitizer

#### Mode 3: 4096-Color "FlikPic" (320x200)

- **3 buffers** (Red, Green, Blue), each 32,000 bytes decompressed
- **4 bits per pixel per channel**, 2 pixels per byte
- Does **not** use the file header palette

Each buffer stores one color channel. For pixel index `i`:

```
byte_index = i / 2
if i is even:
    red_val   = red_buffer[byte_index]   >> 4
    green_val = green_buffer[byte_index] >> 4
    blue_val  = blue_buffer[byte_index]  >> 4
else:
    red_val   = red_buffer[byte_index]   & 0x0F
    green_val = green_buffer[byte_index] & 0x0F
    blue_val  = blue_buffer[byte_index]  & 0x0F
```

Each channel value is 0-15 with **inverted intensity** (0 = brightest, 15 = darkest). Convert to 8-bit RGB:

```
R = (15 - red_val)   * 17      # maps 0->255, 15->0
G = (15 - green_val) * 17
B = (15 - blue_val)  * 17
```

The multiplier 17 maps the 0-15 range to 0-255 exactly (15 * 17 = 255).

#### Mode 4: 3D Anaglyph (320x200)

- **2 buffers** (Buffer 1 = Red eye, Buffer 2 = Cyan eye), each 32,000 bytes decompressed
- **4 bits per pixel per buffer**, 2 pixels per byte
- Designed for red/cyan 3D glasses viewing
- Does **not** use the file header palette

For pixel index `i`:

```
byte_index = i / 2
if i is even:
    red_val  = buffer1[byte_index] >> 4
    cyan_val = buffer2[byte_index] >> 4
else:
    red_val  = buffer1[byte_index] & 0x0F
    cyan_val = buffer2[byte_index] & 0x0F
```

Convert to RGB with **inverted intensity**:

```
R = (15 - red_val)  * 17       # Red channel from buffer 1
G = (15 - cyan_val) * 17       # Green channel from buffer 2 (cyan)
B = (15 - cyan_val) * 17       # Blue channel from buffer 2 (cyan)
```

---

## HR Format

### Multi-File Structure

An HR image is a 640x200, 4-shade grayscale image stored across **4 separate files** on a CoCo disk:

| File Extension | Sequence | Content |
|---------------|----------|---------|
| `.HR0`        | Part 1   | First ~8,000 bytes of VRAM data |
| `.HR1`        | Part 2   | Next ~8,000 bytes |
| `.HR2`        | Part 3   | Next ~8,000 bytes |
| `.HR3`        | Part 4   | Final ~8,000 bytes |

To decode an HR image:
1. Locate all four files (they share the same base filename)
2. Extract the raw data from each file
3. Concatenate them in order: HR0 + HR1 + HR2 + HR3
4. Strip the SAVEM container wrappers to get the raw pixel payload
5. Decode the pixel data

The total decompressed pixel payload is **32,000 bytes** (640 x 200 x 2 bits per pixel / 8 bits per byte).

### SAVEM (DECB BIN) Container

Each HR file is wrapped in a DECB SAVEM container, which is the standard CoCo machine-language binary format. The container must be stripped to extract the raw pixel data.

The container consists of a sequence of **records**. Each record begins with a 1-byte sync/type field:

#### Record Type: Payload Block (Sync = 0x00)

```
Offset  Size  Description
------  ----  -----------
0       1     Sync byte: 0x00
1-2     2     Payload length (big-endian, 16-bit)
3-4     2     Load address (big-endian, 16-bit) -- ignore for decoding
5+      N     Payload data (N = payload length)
```

#### Record Type: EOF Block (Sync = 0xFF)

```
Offset  Size  Description
------  ----  -----------
0       1     Sync byte: 0xFF
1-2     2     Always 0x00 0x00
3-4     2     Execution address (big-endian, 16-bit) -- ignore for decoding
```

#### Container Extraction Algorithm

```
function extract_payload(data):
    stream = open data as byte stream
    payload = empty byte array

    while not end of stream:
        sync = read 1 byte

        if sync == 0x00:            # Payload block
            length = read 2 bytes (big-endian unsigned 16-bit)
            address = read 2 bytes  # skip/ignore
            chunk = read <length> bytes
            append chunk to payload

        else if sync == 0xFF:       # EOF block
            skip 4 bytes            # (0x00, 0x00, exec_hi, exec_lo)

        else:
            # Not a valid container -- treat remainder as raw data
            append sync byte + all remaining bytes to payload
            break

    return payload
```

**Important**: A single concatenated HR stream may contain **multiple** SAVEM files back-to-back (one per HR part). The algorithm above handles this by processing records in a loop until all data is consumed.

### HR Pixel Decoding

After extracting the payload (32,000 bytes), pixel decoding is identical to IMG Mode 0:

- **2 bits per pixel**, 4 pixels per byte, MSB first
- **Inverted grayscale palette** (0 = white, 3 = black)

```
Palette:
    Index 0 -> RGB(255, 255, 255)   White
    Index 1 -> RGB(170, 170, 170)   Light gray
    Index 2 -> RGB(85,  85,  85)    Dark gray
    Index 3 -> RGB(0,   0,   0)     Black

For pixel i (0 to 127999):
    byte_index = i / 4
    pixel_in_byte = i % 4
    shift = 6 - (pixel_in_byte * 2)
    color_index = (payload[byte_index] >> shift) & 0x03
    rgb = palette[color_index]
```

Pixels are stored in linear order: left-to-right across each row, then top-to-bottom. The image dimensions are always 640 wide by 200 tall.

---

## Complete Decoder Pseudocode

### IMG Decoder

```
function decode_img(file_bytes):
    stream = open file_bytes

    # --- Header ---
    skip 1 byte                         # dummy
    mode = read 1 byte                  # video mode (0-4)
    palette = read 16 bytes             # CoCo 3 palette values

    # --- Determine geometry ---
    if mode in (0, 2):
        width = 640
    else:
        width = 320
    height = 200

    # --- Decompress buffer(s) ---
    if mode in (0, 1, 2):
        buffer = read_buffer(stream)

    else if mode == 3:
        red_buffer   = read_buffer(stream)
        green_buffer = read_buffer(stream)
        blue_buffer  = read_buffer(stream)

    else if mode == 4:
        red_buffer  = read_buffer(stream)
        cyan_buffer = read_buffer(stream)

    # --- Decode pixels ---
    image = new RGB image (width x height)

    if mode == 0:
        grayscale = [(255,255,255), (170,170,170), (85,85,85), (0,0,0)]
        for each pixel i in (width * height):
            byte_idx = i / 4
            shift = 6 - (i % 4) * 2
            idx = (buffer[byte_idx] >> shift) & 0x03
            image[i] = grayscale[idx]

    else if mode in (1, 2):
        colors = [decode_coco3_palette(p) for p in palette]
        for each pixel i in (width * height):
            byte_idx = i / 2
            if i is even:
                idx = buffer[byte_idx] >> 4
            else:
                idx = buffer[byte_idx] & 0x0F
            image[i] = colors[idx]

    else if mode == 3:
        for each pixel i in (width * height):
            byte_idx = i / 2
            if i is even:
                cr = red_buffer[byte_idx]   >> 4
                cg = green_buffer[byte_idx] >> 4
                cb = blue_buffer[byte_idx]  >> 4
            else:
                cr = red_buffer[byte_idx]   & 0x0F
                cg = green_buffer[byte_idx] & 0x0F
                cb = blue_buffer[byte_idx]  & 0x0F
            image[i] = ((15-cr)*17, (15-cg)*17, (15-cb)*17)

    else if mode == 4:
        for each pixel i in (width * height):
            byte_idx = i / 2
            if i is even:
                cr = red_buffer[byte_idx]  >> 4
                cc = cyan_buffer[byte_idx] >> 4
            else:
                cr = red_buffer[byte_idx]  & 0x0F
                cc = cyan_buffer[byte_idx] & 0x0F
            image[i] = ((15-cr)*17, (15-cc)*17, (15-cc)*17)

    return image
```

### HR Decoder

```
function decode_hr(hr0_bytes, hr1_bytes, hr2_bytes, hr3_bytes):
    # Concatenate all parts
    combined = hr0_bytes + hr1_bytes + hr2_bytes + hr3_bytes

    # Strip SAVEM containers
    payload = extract_payload(combined)

    # Decode 640x200 at 2bpp
    width = 640
    height = 200
    grayscale = [(255,255,255), (170,170,170), (85,85,85), (0,0,0)]

    image = new RGB image (width x height)
    for each pixel i in (width * height):
        byte_idx = i / 4
        shift = 6 - (i % 4) * 2
        idx = (payload[byte_idx] >> shift) & 0x03
        image[i] = grayscale[idx]

    return image
```

---

## Reference Implementation Notes

### Handling Short Buffers

If a decompressed buffer is shorter than the expected size for the mode, **pad with zero bytes** at the end. This handles truncated or slightly corrupted files gracefully.

### Pixel Scan Order

All modes use a simple linear scan: pixels are stored left-to-right for each row, rows are stored top-to-bottom. There is no interlacing or column reordering.

### Inverted Intensity in Modes 0, 3, and 4

The RASCAN digitizer uses **inverted intensity** for grayscale and FlikPic modes: a pixel value of 0 represents maximum brightness (white) and the maximum value represents minimum brightness (black). This is the opposite of many other graphics formats. Always apply the inversion formula when decoding these modes.

### Mode 0 Palette Override

Mode 0 files may contain arbitrary palette data in the header from uninitialized memory. A correct decoder must **always use a hardcoded 4-shade inverted grayscale palette** for Mode 0, ignoring the header palette entirely.

### DSK Container Context

IMG and HR files are typically stored on CoCo floppy disk images (`.DSK` files) using the DECB (Disk Extended Color BASIC) file system. To access them:

1. Parse the DSK/JVC disk image format
2. Read the directory on Track 17
3. Locate the file entry by name and extension
4. Follow the granule chain in the FAT (Track 17, Sector 2) to extract file data
5. Pass the extracted bytes to the IMG or HR decoder

For HR files, all four parts (HR0-HR3) must be extracted and concatenated before decoding.

### File Detection

- **IMG files**: Extension `.IMG`. The mode byte at offset 1 should be 0-4.
- **HR files**: Extensions `.HR0`, `.HR1`, `.HR2`, `.HR3`. When `.HR0` is selected, automatically load all four parts. The first byte of each part's SAVEM container should be `0x00` (payload block sync).
