# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CoCo MAX/CM3 DSK Viewer is a Python tool for working with TRS-80 Color Computer disk images and graphics files (MAX and CM3 formats). It provides both GUI and CLI interfaces to browse DSK images, extract MAX and CM3 graphics files, and convert them to modern image formats (PNG/PPM).

## Key Commands

### Development Setup
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install pillow
```

### Running the Application
```bash
# Launch GUI viewer
python main.py gui

# List files in a disk image
python main.py list CCMAX.DSK

# Extract and convert MAX file to PNG
python main.py extract CCMAX.DSK GIRL1.MAX output.png

# Extract and convert CM3 file to PNG
python main.py extract CM3PIC01.DSK Jinx.CM3 output.png
```

### Using coco_dsk.py Standalone
```bash
# List directory contents
python coco_dsk.py mydisk.dsk -l

# Extract file from DSK to PC
python coco_dsk.py mydisk.dsk -g HELLO.BAS -o hello.bas

# Upload file from PC to DSK
python coco_dsk.py mydisk.dsk -p program.bin -n PROG.BIN -t 2
```

## Architecture

### Module Structure

**main.py** - Primary entry point that consolidates all functionality
- Embeds disk parsing logic from `coco_dsk.py` (DSKImage, DirectoryEntry, JVCHeader classes)
- Embeds MAX-to-PPM conversion from `maxtoppm_source.py` (convert_max_to_ppm function)
- Implements CM3-to-PPM conversion (convert_cm3_to_ppm function) for CoCoMax 3 format
- Provides CLI with three subcommands: `gui`, `list`, `extract`
- Contains Tkinter GUI application (App class) for interactive viewing of both MAX and CM3 files

**coco_dsk.py** - Standalone disk image manipulation library
- DSKImage class handles DSK/JVC disk image reading and writing
- Implements DECB file system: FAT parsing, directory entries, granule chains
- Supports file extraction (copy_to_pc) and upload (upload_from_pc)
- Can be used independently as a command-line tool

**maxtoppm_source.py** - Original MAX/ART graphics decoder
- Converts CoCo MAX and ART graphics formats to PPM
- Supports multiple pixel modes (BW, BR, RB, BR2/3, RB2/3, S10/11) for artifact color handling
- Part of a larger "coco" package (imports from coco.util and coco.__version__)
- Note: main.py has a simplified embedded version that only implements essential modes

### DSK File System Details

The CoCo DECB (Disk Extended Color BASIC) file system uses:
- **Granules**: Fixed allocation units of 9 sectors × 256 bytes = 2304 bytes
- **FAT (File Allocation Table)**: Located at Track 17, Sector 2; tracks granule chains
- **Directory**: Track 17, Sectors 3-11; holds up to 72 entries (9 sectors × 8 entries)
- **Granule mapping**: 2 granules per track, skipping Track 17 (reserved for directory)

FAT encoding:
- 0x00-0x43: Points to next granule in chain
- 0xC0-0xC9: Last granule marker; lower 4 bits = sectors used (0 means all 9)
- 0xFF: Free granule

### Graphics Format Handling

**MAX Format** - CoCoMax 1/2 files use a simple header structure:
- Byte 0: Should be 0x00
- Bytes 1-2: Size in bytes (big-endian)
- Bytes 3-4: Reserved
- Following data: Raw bitmap (1 bit per pixel for 256-pixel width)
- Resolution: 256 × 192 pixels (typically)

Conversion process (convert_max_to_ppm):
- Reads 5-byte header, validates format
- Calculates rows from size and width (default 256 cols)
- Processes row-by-row, applying color interpretation based on arte mode
- Outputs PPM format (P6 binary) with RGB pixels
- Mode 1 (BR) simulates NTSC color artifacts with YIQ color space conversion

**CM3 Format** - CoCoMax 3 files use a more complex structure:
- Byte 0: Picture type byte (bit 7: 0=192 rows, 1=384 rows; bit 0: sans motifs flag)
- Bytes 1-16: 16-color palette (6-bit RGB encoding)
- Bytes 17-28: Animation/cycle data (anirat, cycrat, cm3cyc, flags)
- Bytes 29-271: Optional 243 bytes of motif/pattern data (if sans_motifs=0)
- Following data: Compressed image data using run-length encoding
- Resolution: 320 × 192 or 320 × 384 pixels

CM3 color encoding (6-bit per palette entry):
- RGB bits: [5,2]=red, [4,1]=green, [3,0]=blue
- Each component scaled by 85 to produce 8-bit RGB values (0, 85, 170, 255)

Conversion process (convert_cm3_to_ppm):
- Reads pictyp byte to determine dimensions and motif presence
- Reads 16-color palette and animation data
- Decompresses image data using line buffer and reference buffers
- Two compression modes: control byte < 128 (compressed) or ≥ 128 (uncompressed)
- Each byte stores 2 pixels (4 bits per pixel) as palette indices
- Outputs PPM format (P6 binary) with RGB pixels from palette

### Integration Points

When main.py runs:
1. CLI parser routes to `gui`, `list`, or `extract` command
2. For GUI: App class instantiates, user browses DSK via filedialog
3. On file selection:
   - Checks extension (.MAX or .CM3)
   - DSKImage.mount() → extract_file() → convert_max_to_ppm() or convert_cm3_to_ppm() → Pillow display
4. For extract: Same pipeline but saves to PNG file instead of displaying

## Dependencies

- **Pillow**: Required for PNG conversion and ImageTk display in GUI
- **tkinter**: Standard library, used for GUI file browser and image viewer
- No external dependencies for coco_dsk.py (works standalone)

## Testing Strategy

No automated test suite currently exists. Manual validation workflow:

**For MAX files:**
1. Run `python main.py list CCMAX.DSK` to verify directory parsing
2. Run `python main.py extract CCMAX.DSK GIRL1.MAX test.png`
3. Compare generated PNG against reference images (GIRL*.png in root)

**For CM3 files:**
1. Run `python main.py list CM3PIC01.DSK` to see CM3 files
2. Run `python main.py extract CM3PIC01.DSK Jinx.CM3 test.png` (320x384)
3. Run `python main.py extract CM3PIC01.DSK Snail.CM3 test.png` (320x192)
4. Verify both resolutions (192 and 384 rows) are handled correctly

**For GUI testing:**
1. Launch `python main.py gui` and spot-check rendering
2. Open both CCMAX.DSK and CM3PIC01.DSK to test both formats
3. Select various MAX and CM3 files to ensure proper display

Sample assets for testing:
- **Disk images**: CCMAX.DSK, CLIPART1.DSK, CM3PIC01.DSK, GIRLS1.DSK, etc.
- **MAX files**: GIRL1-4.MAX (individual MAX files)
- **CM3 files**: Available in CM3PIC01.DSK (Jinx.CM3, Snail.CM3, etc.)
- **Reference output**: GIRL1.png

## Code Organization Notes

- main.py is self-contained: all DSK, MAX, and CM3 conversion logic is embedded for single-file distribution
- coco_dsk.py and maxtoppm_source.py exist as reference/standalone tools
- maxtoppm_source.py depends on a "coco" package not included in this repo; main.py reimplements only essential features
- CM3 conversion implementation based on cm3toppm from coco-tools package (by Mathieu Bouchard and Jamie Cho)
- Keep type hints and dataclasses when modifying DSKImage/DirectoryEntry structures
