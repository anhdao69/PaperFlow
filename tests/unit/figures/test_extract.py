from pathlib import Path

import pytest
from PIL import Image

from paperflow.figures.extract import PillowFigureImageWriter, _validate_pdf


def test_pillow_writer_bounds_long_edge_and_emits_webp(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    destination = tmp_path / "published" / "figure.webp"
    Image.new("RGBA", (3200, 1200), (255, 255, 255, 180)).save(source)

    size = PillowFigureImageWriter().write_webp(
        source,
        destination,
        max_long_edge=1600,
        quality=88,
    )

    assert size == (1600, 600)
    with Image.open(destination) as published:
        assert published.format == "WEBP"
        assert published.mode == "RGB"
        assert published.size == size


def test_malformed_pdf_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "not-a-pdf.pdf"
    path.write_bytes(b"<html>not a PDF</html>")

    with pytest.raises(ValueError, match="not a PDF"):
        _validate_pdf(path)
