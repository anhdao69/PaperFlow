"""Optional, non-critical-path scientific figure extraction support."""

from paperflow.figures.models import (
    BoundingBox,
    ExtractedFigure,
    ExtractionResult,
    ExtractorName,
    FigureKind,
)

__all__ = [
    "BoundingBox",
    "ExtractedFigure",
    "ExtractionResult",
    "ExtractorName",
    "FigureKind",
]
