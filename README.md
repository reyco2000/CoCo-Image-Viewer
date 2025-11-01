# CoCo Image Viewer

A modern Python-based viewer for TRS-80 Color Computer (CoCo) graphics file formats. View and convert MAX, CM3, and CLP image files from vintage Color Computer disk images.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)

## Features

- **Multiple Format Support**: MAX (CoCoMax 1/2), CM3 (CoCoMax 3), and CLP (MAX-10 Clipboard)
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
2. Select a DSK file (e.g., `CLIPART1.DSK`, `CM3PIC01.DSK`, `CCMAX.DSK`)
3. Click on any MAX, CM3, or CLP file to view it
4. Images display instantly in the viewer

### Command-Line Interface

#### List files in a DSK image

```bash
python3 main.py list CLIPART1.DSK
```

Output:
```
AL.CLP
AK.CLP
FL.CLP
...
```

#### Extract and convert to PNG

**MAX files:**
```bash
python3 main.py extract CCMAX.DSK GIRL1.MAX output.png
```

**CM3 files:**
```bash
python3 main.py extract CM3PIC01.DSK Jinx.CM3 output.png
```

**CLP files:**
```bash
python3 main.py extract CLIPART1.DSK AL.CLP output.png
```

### Using coco_dsk.py Standalone

The DSK image handler can be used independently:

```bash
# List directory contents
python3 coco_dsk.py mydisk.dsk -l

# Extract file from DSK to PC
python3 coco_dsk.py mydisk.dsk -g HELLO.BAS -o hello.bas

# Upload file from PC to DSK
python3 coco_dsk.py mydisk.dsk -p program.bin -n PROG.BIN -t 2
```

## Sample Files

The repository includes sample disk images for testing:

| File | Description | Contains |
|------|-------------|----------|
| `CCMAX.DSK` | CoCoMax 1/2 images | MAX format files (GIRL1-4.MAX) |
| `CM3PIC01.DSK` | CoCoMax 3 images | CM3 format files (Jinx.CM3, Snail.CM3, etc.) |
| `CLIPART1.DSK` | MAX-10 clip art | CLP format files (state outlines) |
| `GIRLS1.DSK` | More CoCoMax images | Additional MAX files |

## Architecture

### Module Structure

**main.py** - Primary entry point
- Embeds DSK parsing (DSKImage, DirectoryEntry classes)
- MAX-to-PPM conversion (artifact colors with YIQ color space)
- CM3-to-PPM conversion (decompression and palette handling)
- CLP-to-PPM conversion (MAX-10 clipboard picture extraction)
- Tkinter GUI application
- CLI with three subcommands: `gui`, `list`, `extract`

**coco_dsk.py** - Standalone DSK manipulation library
- DSKImage class for reading/writing DSK/JVC images
- DECB file system implementation
- FAT parsing and granule chain traversal
- File extraction and upload capabilities

**COCO-PICS-FORMATS.md** - Technical documentation
- Complete format specifications for programmers
- Byte-by-byte header breakdowns
- Code examples and algorithms
- Common pitfalls and optimization tips

## Technical Details

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

## Format Documentation

For detailed technical specifications, see [COCO-PICS-FORMATS.md](COCO-PICS-FORMATS.md):
- Complete header structures
- Compression algorithms
- Color palette encoding
- Implementation examples
- Error handling guidelines

## Project Structure

```
CoCo-Image-Viewer/
├── main.py                    # Main application (GUI + CLI)
├── coco_dsk.py                # DSK image handler
├── COCO-PICS-FORMATS.md       # Technical format documentation
├── CLAUDE.md                  # Project development guide
├── README.md                  # This file
├── LICENSE                    # MIT License
├── .gitignore                 # Git ignore patterns
├── CCMAX.DSK                  # Sample MAX images
├── CM3PIC01.DSK               # Sample CM3 images
├── CLIPART1.DSK               # Sample CLP clip art
├── GIRLS1.DSK                 # Additional MAX images
├── GIRL1.MAX - GIRL4.MAX      # Individual MAX files
└── CLP File.txt               # MAX-10 format specification
```

## Development

### Testing

```bash
# Test MAX format
python3 main.py extract CCMAX.DSK GIRL1.MAX test.png

# Test CM3 format (192 rows)
python3 main.py extract CM3PIC01.DSK Snail.CM3 test.png

# Test CM3 format (384 rows)
python3 main.py extract CM3PIC01.DSK Jinx.CM3 test.png

# Test CLP format
python3 main.py extract CLIPART1.DSK AL.CLP test.png
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

### "No picture found in CLP file"
- CLP files may contain only text, rulers, or page breaks
- Only files with picture paragraphs (tag 0x01) will display

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

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

### Format Specifications
- **MAX/CM3**: Based on CoCoMax software by Colorware
- **CLP**: MAX-10 Word Processor format by Dave Stampe

### Tools & Libraries
- [coco-tools](https://github.com/jamieleecho/coco-tools) by Jamie Cho - Reference implementations
- [Pillow](https://python-pillow.org/) - Python Imaging Library
- Color Computer community for format documentation

### Special Thanks
- Mathieu Bouchard - cm3toppm implementation reference
- Jamie Cho (jamieleecho) - coco-tools package and format knowledge
- Dave Stampe - MAX-10 CLP format technical documentation
- Color Computer Archive - Sample files and documentation

## Resources

### Color Computer Links
- [Color Computer Archive](https://colorcomputerarchive.com/) - Software and documentation
- [CoCopedia](https://www.cocopedia.com/) - Color Computer wiki
- [coco-tools GitHub](https://github.com/jamieleecho/coco-tools) - Format conversion utilities

### Related Projects
- **maxtoppm** - MAX/ART to PPM converter
- **cm3toppm** - CM3 to PPM converter
- **veftopng** - VEF to PNG converter
- **Toolshed** - CoCo disk utilities

## Version History

### v1.0.0 (Initial Release)
- ✅ MAX format support with artifact colors
- ✅ CM3 format support with compression
- ✅ CLP format support for MAX-10 pictures
- ✅ GUI viewer for browsing DSK images
- ✅ CLI tools for extraction and conversion
- ✅ Comprehensive programmer documentation
- ✅ Sample disk images included

---

**Made with ❤️ for the TRS-80 Color Computer community**

🤖 *Developed with assistance from [Claude Code](https://claude.com/claude-code)*
