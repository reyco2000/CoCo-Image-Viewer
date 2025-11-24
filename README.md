# CoCo Image Viewer

A modern Python-based viewer for TRS-80 Color Computer (CoCo) graphics file formats. View and convert MAX, CM3, CLP, MGE, MAC, PCX, and GIF image files from vintage Color Computer disk images.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)

## Features

- **Multiple Format Support**: MAX (CoCoMax 1/2), CM3 (CoCoMax 3), CLP (MAX-10 Clipboard), MGE (Graphics Exchange), MAC (MacPaint), PCX (PC Paintbrush), and GIF
- **Dual Interface**: GUI viewer and command-line tools
- **DSK Image Support**: Browse and extract files from Color Computer disk images
- **High-Quality Conversion**: Export to modern PNG format
- **NTSC Artifact Colors**: Supports MAX artifact color modes (BR/RB)
- **Comprehensive Documentation**: Technical format specifications for developers

## Supported Formats

### MAX Format (CoCoMax 1/2)
- Monochrome and artifact-colored bitmap images
- 256×192 resolution (typical)
- 1 bit per pixel with NTSC color artifact support
- Simple 5-byte header format

### CM3 Format (CoCoMax 3)
- 16-color palette-based images
- 320×192 or 320×384 resolution
- Run-length compression
- Advanced color palette system

### CLP Format (MAX-10 Clipboard)
- Embedded pictures from MAX-10 word processor
- Container format with text, rulers, and graphics
- Monochrome bitmap pictures
- Variable dimensions

### MGE Format (Graphics Exchange)
- ANIMTOOL-style graphics exchange format
- 320x200x16 resolution
- RLE compression or raw bitmap
- RGB/Composite monitor type support
- 32-character title field

### MAC Format (MacPaint)
- Classic Macintosh bitmap format
- 576×720 monochrome resolution
- PackBits RLE compression
- 512-byte header (or PNTG variant with 640-byte header)
- 1 bit per pixel (black and white)

### PCX Format (PC Paintbrush)
- ZSoft PC Paintbrush format
- Multiple color depths: 1-bit, 4-bit (EGA), 8-bit (VGA), 24-bit
- Run-length encoding compression
- 128-byte header with embedded EGA palette
- Optional 256-color VGA palette at file end

### GIF Format
- Standard GIF89a/GIF87a format
- Natively supported via PIL/Pillow library
- Indexed color (up to 256 colors)
- LZW compression

## Requirements

- Python 3.7 or higher
- Pillow (PIL) library for image processing

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/reyco2000/CoCo-Image-Viewer.git
cd CoCo-Image-Viewer
```

### 2. Install dependencies

```bash
pip install pillow
```

Or create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install pillow
```

## Usage

### GUI Mode

Launch the interactive GUI viewer:

```bash
python3 main.py gui
```

1. Click "Open DSK File" to browse for a disk image
2. Navigate to the `DSK-sample` directory
3. Select a DSK file (e.g., `CM3PIC01.DSK`, `CCMAX.DSK`, `CLIPART3.dsk`)
4. Click on any MAX, CM3, CLP, MGE, MAC, PCX, or GIF file to view it
5. Images display instantly in the viewer

![Screenshot](documentation/shared.png)

### Command-Line Interface

#### List files in a DSK image

```bash
python3 main.py list DSK-sample/CLIPART3.dsk
```

Output:
```
CATCHER.CLP
BATTER.CLP
RUNNER.CLP
SURFER.CLP
...
```

#### Extract and convert to PNG

**MAX files:**
```bash
python3 main.py extract DSK-sample/CCMAX.DSK TITLE.MAX output.png
```

**CM3 files:**
```bash
python3 main.py extract DSK-sample/CM3PIC01.DSK Jinx.CM3 output.png
```

**CLP files:**
```bash
python3 main.py extract DSK-sample/CLIPART3.dsk SOCCER.CLP soccer.png
```

**MGE files:**
```bash
python3 main.py extract DSK-sample/CLRMAX-1.DSK PICTURE.MGE output.png
```

**MAC files (MacPaint):**
```bash
python3 main.py extract DSK-sample/MACPICS.DSK IMAGE.MAC output.png
```

**PCX files:**
```bash
python3 main.py extract DSK-sample/PCXPICS.DSK IMAGE.PCX output.png
```

**GIF files:**
```bash
python3 main.py extract DSK-sample/GIFPICS.DSK IMAGE.GIF output.png
```

## Sample Files

The repository includes sample disk images in the `DSK-sample/` directory:

| File | Size | Description | Contains |
|------|------|-------------|----------|
| `CCMAX.DSK` | 158K | CoCoMax 1/2 images | MAX format files |
| `CM3PIC01.DSK` | 158K | CoCoMax 3 images | CM3 format files (Jinx.CM3, Snail.CM3, etc.) |
| `CLIPART3.dsk` | 158K | MAX-10 clip art | CLP format files (Sports: BASEBALL, SOCCER, HOCKEY, etc.) |
| `CLRMAX-1.DSK` | 158K | ColorMax images | MGE format files |

For additional DSK files, visit: https://colorcomputerarchive.com/repo/Disks/Pictures/

### Example Commands

```bash
# Browse CCMAX.DSK
python3 main.py list DSK-sample/CCMAX.DSK

# Extract from CM3PIC01.DSK (384-row image)
python3 main.py extract DSK-sample/CM3PIC01.DSK Jinx.CM3 jinx.png

# Extract from CM3PIC01.DSK (192-row image)
python3 main.py extract DSK-sample/CM3PIC01.DSK Snail.CM3 snail.png

# Extract sports clipart
python3 main.py extract DSK-sample/CLIPART3.dsk SOCCER.CLP soccer.png
python3 main.py extract DSK-sample/CLIPART3.dsk BASEBALL.CLP baseball.png
```

## Project Structure

```
CoCo-Image-Viewer/
├── main.py                         # Main application (Tkinter GUI + CLI)
├── main_new.py                     # PyQt6 GUI with zoom and export features
│
├── coco_image_formats/             # Reusable image format library
│   ├── __init__.py                 # Package exports
│   ├── dsk.py                      # DSK image handling
│   ├── max_format.py               # MAX format converter
│   ├── cm3_format.py               # CM3 format converter
│   ├── mge_format.py               # MGE format converter
│   ├── clp_format.py               # CLP format converter
│   ├── mac_format.py               # MAC (MacPaint) format converter
│   ├── pcx_format.py               # PCX format converter
│   └── utils.py                    # Shared utilities
│
├── README.md                       # This file
├── LICENSE                         # MIT License
├── .gitignore                      # Git ignore patterns
│
├── DSK-sample/                     # Sample disk images
│   ├── CCMAX.DSK                   # CoCoMax 1/2 images (MAX format)
│   ├── CM3PIC01.DSK                # CoCoMax 3 images (CM3 format)
│   ├── CLIPART3.dsk                # MAX-10 clipart (CLP format - sports)
│   ├── CLRMAX-1.DSK                # ColorMax images (MGE format)
│   └── README.md                   # Link to more DSK files
│
└── documentation/                  # Technical documentation
    ├── COCO-PICS-FORMATS.md        # Format specifications
    ├── CLP File.txt                # MAX-10 format reference
    └── shared.png                  # Screenshot

```

### File Descriptions

#### Python Modules

- **main.py** - Tkinter GUI + CLI
  - Primary entry point with Tkinter-based GUI
  - CLI with three subcommands: `gui`, `list`, `extract`
  - Uses `coco_image_formats` library for format conversion

- **main_new.py** - PyQt6 GUI (Enhanced)
  - Modern PyQt6-based GUI with additional features
  - Zoom slider (0.25x to 2x)
  - Export single image to PNG with pre-filled filename
  - Export All to PNG batch export
  - Filter to show only supported file types
  - DSK path display

- **coco_image_formats/** - Reusable Library Package
  - DSK parsing logic (DSKImage, DirectoryEntry, JVCHeader classes)
  - MAX-to-PPM conversion (artifact colors with YIQ color space)
  - CM3-to-PPM conversion (two-stage decompression and palette handling)
  - CLP-to-PPM conversion (MAX-10 clipboard picture extraction)
  - MGE-to-PPM conversion (RLE decompression and palette conversion)
  - MAC-to-PPM conversion (PackBits decompression, PNTG variant support)
  - PCX-to-PPM conversion (1/4/8/24-bit color depths, RLE decompression)
  - GIF support via PIL/Pillow native handling

#### Documentation

- **[COCO-PICS-FORMATS.md](documentation/COCO-PICS-FORMATS.md)** (1200+ lines)
  - Comprehensive technical reference for programmers
  - Complete format specifications: MAX, CM3, MGE, CLP, MAC, PCX, GIF
  - Byte-by-byte header breakdowns
  - Code examples and algorithms
  - Common pitfalls and optimization tips
  - Color encoding details and compression algorithms

- **[CLP File.txt](documentation/CLP%20File.txt)**
  - Original MAX-10 technical reference by Dave Stampe
  - CLP file structure specification
  - Paragraph tag system documentation
  - Picture format details

#### Sample Disk Images

All disk images are 158KB DSK/JVC format (DECB file system):

- **CCMAX.DSK** - CoCoMax 1/2 pictures (MAX format)
- **CM3PIC01.DSK** - CoCoMax 3 pictures with 16-color palettes
- **CLIPART3.dsk** - Sports clipart: SOCCER, BASEBALL, HOCKEY, SURFER, etc.
- **CLRMAX-1.DSK** - MGE format images (ColorMax/ANIMTOOL format)

## Architecture

### Module Design

`main.py` is intentionally self-contained with all functionality embedded:
- **No external dependencies** except Pillow (PIL)
- **Embedded DSK parser**: Complete DECB file system implementation
- **Embedded format converters**: MAX, CM3, CLP, and MGE conversion logic
- **Single-file distribution**: Easy to deploy and understand

### DSK File System (DECB)

- **Granules**: 9 sectors × 256 bytes = 2,304 bytes
- **FAT**: Track 17, Sector 2 (granule chain tracking)
- **Directory**: Track 17, Sectors 3-11 (72 entry capacity)
- **Granule Mapping**: 2 granules per track, skipping Track 17

### Color Encoding

**MAX Artifact Colors (NTSC)**:
- BR Mode: Blue-Red phase artifacts
- RB Mode: Red-Blue phase artifacts (reversed)
- YIQ color space conversion for composite video simulation

**CM3 Palette**:
- 6-bit RGB encoding (2 bits per channel)
- 16 colors from 64 possible combinations
- Scaling: `rgb8 = rgb2 × 85` (0→0, 1→85, 2→170, 3→255)

**CLP Bitmaps**:
- 1 bit per pixel: 0=white, 1=black
- MSB first (bit 7 = leftmost pixel)
- Padding byte required at end of each line

## Technical Details

### Image Format Conversion Pipeline

```
DSK Image → Extract File → Parse Format → Convert to PPM → Save as PNG
     ↓            ↓              ↓               ↓              ↓
  JVC/DECB    granules   MAX/CM3/CLP/MGE   RGB pixels    Pillow library
```

### Supported Operations

| Operation | MAX | CM3 | CLP | MGE | MAC | PCX | GIF |
|-----------|-----|-----|-----|-----|-----|-----|-----|
| View in GUI | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Extract to PNG | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Artifact colors | ✅ (BR/RB) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Palette support | ❌ | ✅ (16) | ❌ | ✅ (16) | ❌ | ✅ (16/256) | ✅ (256) |
| Compression | ❌ | ✅ (RLE) | ❌ | ✅ (RLE) | ✅ (PackBits) | ✅ (RLE) | ✅ (LZW) |

## Development

### Testing

```bash
# Test MAX format
python3 main.py list DSK-sample/CCMAX.DSK
python3 main.py extract DSK-sample/CCMAX.DSK <filename>.MAX test.png

# Test CM3 format (192 rows)
python3 main.py extract DSK-sample/CM3PIC01.DSK Snail.CM3 test.png

# Test CM3 format (384 rows)
python3 main.py extract DSK-sample/CM3PIC01.DSK Jinx.CM3 test.png

# Test CLP format (sports clipart)
python3 main.py extract DSK-sample/CLIPART3.dsk SOCCER.CLP test.png
python3 main.py extract DSK-sample/CLIPART3.dsk CATCHER.CLP test.png

# Test MGE format
python3 main.py list DSK-sample/CLRMAX-1.DSK
python3 main.py extract DSK-sample/CLRMAX-1.DSK <filename>.MGE test.png
```

### Adding New Formats

To add support for additional Color Computer graphics formats:

1. Implement a `convert_XXX_to_ppm()` function in `main.py`
2. Add format detection in GUI (`on_file_select()` method)
3. Add format support in CLI (`extract` command)
4. Update help text and documentation
5. Add test cases with sample files

## Known Limitations

- MAX format only supports arte modes 0, 1, and 2 (BW, BR, RB)
- CM3 motif/pattern data is read but not used in rendering
- CLP files only extract the first picture paragraph
- Maximum CLP image size: 7,660 bytes (per MAX-10 specification)
- MGE format only supports resolution byte 0 (320x200)
- GUI displays one image at a time (no multi-image gallery view)

## Troubleshooting

### "No module named 'PIL'"
```bash
pip install pillow
```

### "Error displaying image"
- Ensure the file is a valid MAX/CM3/CLP format
- Check that the DSK image is not corrupted
- Verify the file extension matches the actual format
- Check file paths - DSK samples are in `DSK-sample/` directory

### "No picture found in CLP file"
- CLP files may contain only text, rulers, or page breaks
- Only files with picture paragraphs (tag 0x01) will display

### GUI not launching
- Ensure tkinter is installed: `sudo apt install python3-tk` (Linux)
- On macOS, tkinter comes with Python
- On Windows, tkinter is included with Python installation

## Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines for Python code
- Add docstrings to all functions and classes
- Update documentation for new features
- Test with sample files before submitting
- Include format specifications for new file types

### Future Enhancement Ideas

- [x] Add MGE format support (ColorMax/ANIMTOOL)
- [x] Add MAC format support (MacPaint)
- [x] Add PCX format support (PC Paintbrush)
- [x] Add GIF format support
- [x] Zoom and pan controls in GUI (PyQt6 version)
- [x] Add batch conversion mode (Export All to PNG)
- [ ] Implement multi-image gallery view in GUI
- [ ] Support for other CoCo formats (RAT, HRS, VEF, PIX)
- [ ] Image preview thumbnails in file list
- [ ] Color palette editor for CM3/MGE images
- [ ] Drag-and-drop DSK file loading

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

### Format Specifications
- **MAX/CM3**: Based on CoCoMax software by Colorware
- **CLP**: MAX-10 Word Processor format by Dave Stampe

### Tools & Libraries
- [coco-tools](https://github.com/jamieleecho/coco-tools) by Jamie Cho - Reference implementations
- [Pillow](https://python-pillow.org/) - Python Imaging Library
- Color Computer community for format documentation and sample files

### Special Thanks
- Mathieu Bouchard - cm3toppm implementation reference
- Jamie Cho (jamieleecho) - coco-tools package and format knowledge
- Dave Stampe - MAX-10 CLP format technical documentation
- Color Computer Archive - Sample files and documentation
- Colorware - Original MAX and CM3 software
- 🤖 *Developed with assistance from [Claude Code](https://claude.com/claude-code)*

## Resources

### Color Computer Links
- [Color Computer Archive](https://colorcomputerarchive.com/) - Software and documentation
- [Color Computer Archive - Pictures](https://colorcomputerarchive.com/repo/Disks/Pictures/) - More DSK files
- [CoCopedia](https://www.cocopedia.com/) - Color Computer wiki
- [coco-tools GitHub](https://github.com/jamieleecho/coco-tools) - Format conversion utilities

### Related Projects
- **maxtoppm** - MAX/ART to PPM converter
- **cm3toppm** - CM3 to PPM converter
- **veftopng** - VEF to PNG converter
- **Toolshed** - CoCo disk utilities

### Documentation in This Repository
- **[COCO-PICS-FORMATS.md](documentation/COCO-PICS-FORMATS.md)** - Deep dive into MAX, CM3, MGE, CLP, MAC, PCX, and GIF formats
- **[CLP File.txt](documentation/CLP%20File.txt)** - Original MAX-10 format specification

## Version History

### v1.2.0 (November 2025)
- ✅ MAC format support (MacPaint with PackBits decompression)
- ✅ PCX format support (1-bit, 4-bit EGA, 8-bit VGA, 24-bit true color)
- ✅ GIF format support (native PIL/Pillow handling)
- ✅ PyQt6 GUI version (main_new.py) with zoom controls
- ✅ Export to PNG with pre-filled filename
- ✅ Export All to PNG batch functionality
- ✅ Reusable `coco_image_formats` library package
- ✅ Updated documentation with MAC, PCX, and GIF specifications

### v1.1.0 (November 2025)
- ✅ MGE format support (ColorMax/ANIMTOOL)
- ✅ RLE decompression for MGE files
- ✅ RGB/Composite monitor palette conversion
- ✅ Updated documentation with MGE specifications

### v1.0.0 (November 2025)
- ✅ MAX format support with artifact colors
- ✅ CM3 format support with compression
- ✅ CLP format support for MAX-10 pictures
- ✅ GUI viewer for browsing DSK images
- ✅ CLI tools for extraction and conversion
- ✅ Comprehensive programmer documentation
- ✅ Sample disk images included (4 DSK files)
- ✅ Self-contained single-file design

### About the Author
Made with ❤️ by Reinaldo Torres — a proud CoCo enthusiast 📧 reyco2000@gmail.com

🟢 Proud member and co-creator of the CoCoByte Club https://cocobyte.co/

🔗 See more on @ChipShift https://github.com/reyco2000/
