"""Standard-library helpers used by optional extractor adapters."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from paperflow.figures.models import ExtractedFigure


def png_dimensions(path: Path) -> tuple[int, int]:
    payload = path.read_bytes()
    if len(payload) < 45 or payload[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"extractor image is not a valid PNG: {path.name}")
    offset = 8
    width = height = 0
    saw_idat = False
    saw_iend = False
    chunk_index = 0
    while offset + 12 <= len(payload):
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_type = payload[offset + 4 : offset + 8]
        chunk_end = offset + 12 + length
        if chunk_end > len(payload):
            break
        data = payload[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", payload[offset + 8 + length : chunk_end])[0]
        if zlib.crc32(chunk_type + data) & 0xFFFFFFFF != expected_crc:
            break
        if chunk_index == 0:
            if chunk_type != b"IHDR" or length != 13:
                break
            width, height = struct.unpack(">II", data[:8])
        elif chunk_type == b"IDAT":
            saw_idat = True
        elif chunk_type == b"IEND":
            saw_iend = length == 0 and chunk_end == len(payload)
            break
        offset = chunk_end
        chunk_index += 1
    if width <= 0 or height <= 0 or not saw_idat or not saw_iend:
        raise ValueError(f"extractor image has invalid dimensions: {path.name}")
    return width, height


def rank_figures(figures: list[ExtractedFigure]) -> list[str]:
    """Use one neutral baseline so both Phase 25 candidates are compared equally."""
    return [
        figure.figure_id
        for figure in sorted(
            figures,
            key=lambda figure: (
                figure.kind.value == "table",
                -figure.bbox.area,
                figure.page,
                figure.figure_id,
            ),
        )
    ]
