"""
Shared utility functions for image format conversion.
"""

from io import BytesIO


def getbit(v: int, b: int) -> int:
    """Get bit at position b from value v."""
    return (v >> b) & 1


def pack(c) -> bytes:
    """Pack a list of integers into bytes."""
    return bytes(c)


def clip(v: int) -> int:
    """Clip value to 0-255 range."""
    return 255 if v > 255 else (0 if v < 0 else v)
