# Repository Guidelines

## Project Structure & Module Organization
- `main.py` is the primary entry point. It exposes a CLI (`gui`, `list`, `extract`) and embeds the viewer GUI.
- `coco_dsk.py` holds the lower-level disk image parsing logic; update this when changing how granules, sectors, or headers are interpreted.
- `maxtoppm_source.py` provides CoCo MAX image-to-PPM conversion helpers. Keep color tables and bitstream helpers centralized here.
- Sample assets live at the repository root: `CCMAX.DSK` plus standalone `.MAX` images (`GIRL*.MAX`, `.png`). Use these when validating changes.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` creates and activates an isolated environment; install Pillow (`pip install pillow`) if unavailable.
- `python main.py gui` launches the Tkinter viewer for manual inspection of `.MAX` artwork inside a disk image.
- `python main.py list CCMAX.DSK` outputs all directory entries so you can confirm mounting and parsing logic.
- `python main.py extract CCMAX.DSK GIRL1.MAX GIRL1.png` converts a MAX asset to PNG. Replace names as needed when regression-testing changes.

## Coding Style & Naming Conventions
- Follow standard Python 3 style: 4-space indents, `snake_case` for functions/variables, `CapWords` for classes.
- Preserve existing type hints and dataclasses; prefer descriptive variable names over single letters outside byte-processing loops.
- Keep modules importable (no side effects at import time) to simplify future unit tests.

## Testing Guidelines
- No automated test suite yet. For functional checks, run `list` followed by `extract` and visually compare the generated PNGs to the expected output in `GIRL*.png`.
- When touching disk parsing, craft small `.MAX` fixtures or truncate `CCMAX.DSK` copies to assert boundary handling (e.g., last-sector padding).
- Document manual test cases in PR descriptions until we wire formal tests.

## Commit & Pull Request Guidelines
- There is no existing Git history; adopt concise, imperative commit subjects (e.g., “Add RGB fallback for arte mode”).
- Group related changes per commit and include short bodies describing test evidence (`list`, `extract`, GUI smoke-check).
- PRs should link relevant issues, describe the functional impact, list manual test steps, and attach before/after screenshots for GUI or image rendering changes.

## Asset & Security Notes
- Treat bundled disk images as read-only reference material; work on copies to avoid accidental corruption.
- Avoid committing new binary assets over 5 MB without confirming repo hosting limits and adding provenance notes.
