# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python/tkinter-based reverse engineering tool for analyzing and decoding vintage image formats from retro computing systems (Apple II, CGA/EGA/VGA, TRS-80 CoCo, Amiga, etc.). The tool provides interactive exploration of unknown binary image files through configurable parameters, multiple decompression algorithms, and real-time rendering.

## Architecture

### Single-File Application Structure

The entire application is contained in `vintage_image_analyzer.py` with four main classes:

1. **DecompressionEngine** - Implements 5 compression algorithms:
   - Nibble RLE (4-bit run-length encoding)
   - Byte Count RLE (PackBits-style)
   - CoCo RLE (TRS-80 Color Computer format)
   - LZW (GIF-compatible with auto-extraction)
   - Custom RLE (high-bit marker style)

2. **ImageDecoder** - Handles 7 color depth modes:
   - 1-bit monochrome (8 pixels/byte)
   - 2-bit CGA (4 pixels/byte)
   - 4-bit EGA/VGA (2 pixels/byte)
   - 8-bit indexed (1 pixel/byte)
   - 16-bit RGB565 and RGB555
   - 24-bit RGB

3. **HeaderAnalyzer** - File analysis utilities:
   - Shannon entropy calculation for header detection
   - Hex dump generation
   - GIF LZW data extraction

4. **VintageImageAnalyzer** - Main GUI application:
   - Multi-tab interface for multiple files
   - Left panel: All parameter controls
   - Right panel: Tabbed image display with scrollable canvas
   - Per-tab state management (ImageTab class)

### Render Pipeline

```
Raw Binary File
    ↓
Extract Data at Offset
    ↓
Decompress (if compression selected)
    ↓
Decode Pixels (based on color depth + palette)
    ↓
Apply Rotation (0°/90°/180°/270°)
    ↓
Apply Zoom (25%-800%)
    ↓
Display in Canvas
```

**Critical**: Zoom and rotation are display-only operations - they do not trigger re-decompression or re-decoding. Only clicking "RENDER IMAGE" runs the full pipeline.

### State Management

- Each open file has an `ImageTab` object storing: dimensions, offset, color depth, compression type, palette, zoom, rotation
- UI controls sync bidirectionally with the current tab's state
- Tab switching updates all UI controls to match the selected tab's parameters

## Development Commands

### Running the Application
```bash
python vintage_image_analyzer.py
```

### Requirements
```bash
pip install pillow
```

No other dependencies required - uses standard library tkinter.

### Making Executable (Unix/Linux)
```bash
chmod +x vintage_image_analyzer.py
./vintage_image_analyzer.py
```

## Key Implementation Details

### PIL Rotation Quirk
Due to PIL's coordinate system, the rotation constants are counter-intuitive:
- 90° clockwise = `Image.ROTATE_270`
- 270° clockwise = `Image.ROTATE_90`
- 180° = `Image.ROTATE_180`

This is handled correctly in `update_display()`.

### Palette System
- Default palette is 16-color CGA
- Stored as list of RGB tuples: `[(r, g, b), ...]`
- Used for all indexed color modes (1-bit, 2-bit, 4-bit, 8-bit)
- Editable via color picker buttons in UI
- 16-bit and 24-bit modes ignore palette

### Error Handling Patterns
All user-facing operations (load, render, export, config) wrapped in try/except with messagebox alerts. No silent failures.

### Config File Format
JSON format storing current tab parameters:
```json
{
  "width": 320,
  "height": 200,
  "offset": 0,
  "color_depth": "4-bit",
  "compression": "None",
  "palette": [[r,g,b], ...],
  "zoom_level": 100,
  "rotation": 0
}
```

## Common Tasks

### Adding a New Decompression Algorithm
1. Add method to `DecompressionEngine` class
2. Add algorithm name to `COMPRESSION_TYPES` list in `VintageImageAnalyzer`
3. Add elif clause in `render_image()` method to call new decompressor
4. Update README with algorithm description

### Adding a New Color Depth
1. Add decoder method to `ImageDecoder` class
2. Add mode name to `COLOR_DEPTHS` list
3. Add elif clause in `render_image()` to call new decoder
4. Update README documentation

### Modifying UI Layout
Controls are in `setup_controls()` method using ttk.LabelFrame sections:
- Header Analysis
- Image Dimensions
- Data Offset
- Color Depth (radio buttons)
- Decompression (radio buttons)
- Palette Editor
- Zoom
- Rotation
- Render Button

All sections pack vertically in a scrollable frame.

## Testing Approach

Manual testing workflow:
1. Load sample binary files from vintage systems
2. Try various dimension/offset combinations
3. Test each compression algorithm with appropriate files
4. Verify all color depths render correctly
5. Test zoom/rotation at various settings
6. Verify config save/load preserves all parameters
7. Test multi-tab functionality

No automated tests currently - this is an interactive exploration tool where visual verification is essential.
