from __future__ import annotations

import json
import struct
import subprocess
import zlib
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from pydantic import ValidationError

from paperflow.figures.adapters.docling import DoclingAdapter
from paperflow.figures.adapters.pdffigures2 import PDFFigures2Adapter
from paperflow.figures.models import BoundingBox, ExtractorName, FigureKind


class FakeRunner:
    def __init__(
        self,
        callback: Callable[[Sequence[str]], None] | None = None,
        *,
        returncode: int = 0,
        error: Exception | None = None,
    ) -> None:
        self.callback = callback
        self.returncode = returncode
        self.error = error
        self.commands: list[tuple[str, ...]] = []

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, timeout
        self.commands.append(tuple(command))
        if self.error is not None:
            raise self.error
        if self.callback is not None:
            self.callback(command)
        return subprocess.CompletedProcess(command, self.returncode, "", "")


def _write_png(path: Path, *, width: int = 320, height: int = 180) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(
            b"IHDR",
            struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00",
        )
        + chunk(
            b"IDAT",
            zlib.compress((b"\x00" + b"\x00\x00\x00" * width) * height),
        )
        + chunk(b"IEND", b"")
    )


def test_pdffigures2_normalizes_metadata_and_uses_current_batch_cli(tmp_path: Path):
    pdf = tmp_path / "2608.12345.pdf"
    pdf.write_bytes(b"%PDF-test")

    def emit(command: Sequence[str]) -> None:
        data_prefix = Path(command[command.index("-d") + 1])
        image_prefix = Path(command[command.index("-m") + 1])
        image = image_prefix.parent / f"{image_prefix.name}{pdf.stem}-Figure2-1.png"
        _write_png(image)
        Path(f"{data_prefix}{pdf.stem}.json").write_text(
            json.dumps(
                [
                    {
                        "name": "2",
                        "figType": "Figure",
                        "page": 1,
                        "caption": " Figure 2.  System overview. ",
                        "imageText": [],
                        "captionBoundary": {
                            "x1": 10,
                            "y1": 220,
                            "x2": 590,
                            "y2": 250,
                        },
                        "regionBoundary": {
                            "x1": 72,
                            "y1": 90,
                            "x2": 540,
                            "y2": 215,
                        },
                        "renderURL": str(image),
                        "renderDpi": 150,
                    }
                ]
            ),
            encoding="utf-8",
        )

    runner = FakeRunner(emit)
    result = PDFFigures2Adapter(
        ("java", "-jar", "pdffigures2.jar"),
        runner=runner,
        extractor_version="2.0.1",
    ).extract(pdf, arxiv_id="2608.12345", work_dir=tmp_path / "work")

    assert result.error_type is None
    assert result.ranked_figure_ids == ["figure-2-1"]
    assert result.figures[0].page == 2  # PDFFigures2 is zero-based.
    assert result.figures[0].caption == "Figure 2. System overview."
    assert (result.figures[0].width, result.figures[0].height) == (320, 180)
    assert result.figures[0].image_path.startswith("pdffigures2/2608.12345/")
    assert runner.commands[0][-1] == "-q"


def test_docling_normalizes_bottom_left_bbox_caption_and_image(tmp_path: Path):
    pdf = tmp_path / "2608.12346.pdf"
    pdf.write_bytes(b"%PDF-test")

    def emit(command: Sequence[str]) -> None:
        output = Path(command[command.index("--output") + 1])
        image = output / "2608.12346_artifacts" / "picture-1.png"
        _write_png(image, width=640, height=360)
        (output / f"{pdf.stem}.json").write_text(
            json.dumps(
                {
                    "schema_name": "DoclingDocument",
                    "version": "1.8.0",
                    "pages": {
                        "1": {
                            "page_no": 1,
                            "size": {"width": 612, "height": 792},
                        }
                    },
                    "texts": [
                        {
                            "self_ref": "#/texts/0",
                            "label": "caption",
                            "text": "Figure 1. Architecture overview.",
                        }
                    ],
                    "pictures": [
                        {
                            "self_ref": "#/pictures/0",
                            "prov": [
                                {
                                    "page_no": 1,
                                    "bbox": {
                                        "l": 50,
                                        "t": 700,
                                        "r": 560,
                                        "b": 400,
                                        "coord_origin": "BOTTOMLEFT",
                                    },
                                }
                            ],
                            "captions": [{"$ref": "#/texts/0"}],
                            "image": {
                                "uri": "2608.12346_artifacts/picture-1.png"
                            },
                        }
                    ],
                    "tables": [
                        {
                            "self_ref": "#/tables/0",
                            "prov": [
                                {
                                    "page_no": 1,
                                    "bbox": {
                                        "l": 50,
                                        "t": 300,
                                        "r": 560,
                                        "b": 200,
                                        "coord_origin": "BOTTOMLEFT",
                                    },
                                }
                            ],
                            "captions": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    runner = FakeRunner(emit)
    result = DoclingAdapter(
        runner=runner, extractor_version="2.67.0"
    ).extract(pdf, arxiv_id="2608.12346", work_dir=tmp_path / "work")

    assert result.error_type is None
    assert result.figures[0].kind == FigureKind.FIGURE
    assert result.figures[0].bbox == BoundingBox(x1=50, y1=92, x2=560, y2=392)
    assert result.figures[0].caption == "Figure 1. Architecture overview."
    assert (result.figures[0].width, result.figures[0].height) == (640, 360)
    assert len(result.figures) == 1  # Metadata-only tables are not usable crops.
    command = runner.commands[0]
    assert command[:2] == ("docling", "convert")
    assert command[command.index("--image-export-mode") + 1] == "referenced"
    assert command[command.index("--device") + 1] == "cpu"


@pytest.mark.parametrize(
    ("adapter", "error", "expected"),
    [
        (
            PDFFigures2Adapter(
                ("pdffigures2",),
                runner=FakeRunner(error=subprocess.TimeoutExpired("extract", 1)),
            ),
            None,
            "timeout",
        ),
        (
            DoclingAdapter(runner=FakeRunner(error=FileNotFoundError())),
            None,
            "process_unavailable",
        ),
        (
            DoclingAdapter(runner=FakeRunner(returncode=2)),
            None,
            "process_failed",
        ),
    ],
)
def test_adapters_normalize_process_failures(
    tmp_path: Path, adapter: object, error: None, expected: str
):
    del error
    pdf = tmp_path / "2608.12347.pdf"
    pdf.write_bytes(b"%PDF-test")
    result = adapter.extract(  # type: ignore[attr-defined]
        pdf, arxiv_id="2608.12347", work_dir=tmp_path / "work"
    )
    assert result.error_type == expected
    assert result.figures == []


def test_missing_pdf_and_invalid_extractor_output_are_non_throwing(tmp_path: Path):
    missing = PDFFigures2Adapter(("extract",), runner=FakeRunner()).extract(
        tmp_path / "missing.pdf",
        arxiv_id="2608.12348",
        work_dir=tmp_path / "work",
    )
    assert missing.error_type == "missing_pdf"

    pdf = tmp_path / "2608.12348.pdf"
    pdf.write_bytes(b"%PDF-test")
    invalid = DoclingAdapter(runner=FakeRunner()).extract(
        pdf, arxiv_id="2608.12348", work_dir=tmp_path / "work"
    )
    assert invalid.error_type == "invalid_output"


def test_bbox_and_image_path_schema_reject_invalid_metadata():
    with pytest.raises(ValidationError, match="positive area"):
        BoundingBox(x1=10, y1=10, x2=5, y2=20)

    with pytest.raises(ValidationError, match="safe relative"):
        from paperflow.figures.models import ExtractedFigure

        ExtractedFigure(
            figure_id="figure-1",
            kind=FigureKind.FIGURE,
            page=1,
            bbox=BoundingBox(x1=1, y1=1, x2=10, y2=10),
            image_path="../secret.png",
            width=10,
            height=10,
            extractor=ExtractorName.DOCLING,
        )
