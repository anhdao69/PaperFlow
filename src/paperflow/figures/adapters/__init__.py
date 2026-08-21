"""Extractor adapters kept outside PaperFlow's core dependencies."""

from paperflow.figures.adapters.docling import DoclingAdapter
from paperflow.figures.adapters.pdffigures2 import PDFFigures2Adapter

__all__ = ["DoclingAdapter", "PDFFigures2Adapter"]
