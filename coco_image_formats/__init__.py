"""
CoCo Image Formats Library

A collection of vintage image format converters for TRS-80 Color Computer
and other retro computing platforms.

Supported formats:
- MAX: CoCo MAX format
- CM3: CoCoMax 3 format
- MGE: Graphics Exchange / ANIMTOOL format
- MAC: MacPaint format
- PCX: PC Paintbrush format
- CLP: MAX-10 clipboard picture format
- TNY: Atari ST Tiny format

Also includes DSK image handling for reading CoCo disk images.
"""

# DSK image handling
from .dsk import DSKImage, DirectoryEntry, JVCHeader

# Format converters
from .max_format import convert_max_to_ppm
from .cm3_format import convert_cm3_to_ppm
from .mge_format import convert_mge_to_ppm
from .mac_format import convert_mac_to_ppm
from .pcx_format import convert_pcx_to_ppm
from .clp_format import convert_clp_to_ppm
from .tny_format import convert_tny_to_ppm

# Utilities (for advanced use)
from .utils import getbit, pack, clip

__version__ = "1.3.0"

__all__ = [
    # DSK handling
    "DSKImage",
    "DirectoryEntry",
    "JVCHeader",
    # Converters
    "convert_max_to_ppm",
    "convert_cm3_to_ppm",
    "convert_mge_to_ppm",
    "convert_mac_to_ppm",
    "convert_pcx_to_ppm",
    "convert_clp_to_ppm",
    "convert_tny_to_ppm",
    # Utilities
    "getbit",
    "pack",
    "clip",
]
