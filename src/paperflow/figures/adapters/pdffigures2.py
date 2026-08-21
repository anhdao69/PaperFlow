"""PDFFigures2 batch-CLI adapter with normalized failure handling."""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from paperflow.figures.adapters.base import CommandRunner, SubprocessCommandRunner
from paperflow.figures.adapters.common import png_dimensions, rank_figures
from paperflow.figures.models import (
    BoundingBox,
    ExtractedFigure,
    ExtractionResult,
    ExtractorName,
    FigureKind,
)
from paperflow.models import validate_canonical_arxiv_id


class PDFFigures2Adapter:
    """Run a locally installed PDFFigures2 CLI without adding a core dependency."""

    def __init__(
        self,
        command_prefix: Sequence[str],
        *,
        runner: CommandRunner | None = None,
        timeout_seconds: float = 180,
        extractor_version: str | None = None,
    ) -> None:
        if not command_prefix:
            raise ValueError("PDFFigures2 command prefix cannot be empty")
        self.command_prefix = tuple(command_prefix)
        self.runner = runner or SubprocessCommandRunner()
        self.timeout_seconds = timeout_seconds
        self.extractor_version = extractor_version

    def extract(
        self,
        pdf_path: Path,
        *,
        arxiv_id: str,
        work_dir: Path,
    ) -> ExtractionResult:
        validate_canonical_arxiv_id(arxiv_id)
        started = time.monotonic()
        if not pdf_path.is_file():
            return self._failure(arxiv_id, started, "missing_pdf", "PDF is missing")

        output_dir = work_dir / ExtractorName.PDFFIGURES2.value / _safe_id(arxiv_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        stats_path = output_dir / "stats.json"
        image_prefix = output_dir / "figure-"
        data_prefix = output_dir / "data-"
        command = [
            *self.command_prefix,
            str(pdf_path.resolve()),
            "-s",
            str(stats_path.resolve()),
            "-m",
            str(image_prefix.resolve()),
            "-d",
            str(data_prefix.resolve()),
            "-q",
        ]
        try:
            completed = self.runner.run(
                command,
                cwd=output_dir,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return self._failure(arxiv_id, started, "timeout", "extractor timed out")
        except OSError:
            return self._failure(
                arxiv_id, started, "process_unavailable", "extractor could not start"
            )
        if completed.returncode != 0:
            return self._failure(
                arxiv_id, started, "process_failed", "extractor exited unsuccessfully"
            )

        metadata_path = output_dir / f"data-{pdf_path.stem}.json"
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            figures = self._parse_payload(payload, work_dir=work_dir)
        except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError):
            return self._failure(
                arxiv_id, started, "invalid_output", "extractor output is invalid"
            )
        return ExtractionResult(
            arxiv_id=arxiv_id,
            extractor=ExtractorName.PDFFIGURES2,
            extractor_version=self.extractor_version,
            runtime_seconds=time.monotonic() - started,
            figures=figures,
            ranked_figure_ids=rank_figures(figures),
        )

    def _parse_payload(
        self, payload: Any, *, work_dir: Path
    ) -> list[ExtractedFigure]:
        if not isinstance(payload, list):
            raise ValueError("PDFFigures2 output must be a list")
        figures: list[ExtractedFigure] = []
        for index, raw in enumerate(payload):
            if not isinstance(raw, dict):
                raise ValueError("PDFFigures2 item must be an object")
            kind = FigureKind(str(raw["figType"]).lower())
            image = Path(str(raw["renderURL"]))
            if not image.is_absolute():
                image = work_dir / image
            image = image.resolve()
            relative_image = image.relative_to(work_dir.resolve()).as_posix()
            width, height = png_dimensions(image)
            boundary = raw["regionBoundary"]
            if not isinstance(boundary, dict):
                raise ValueError("regionBoundary must be an object")
            figure_number = _optional_text(raw.get("name"))
            figures.append(
                ExtractedFigure(
                    figure_id=f"{kind.value}-{figure_number or index + 1}-{index + 1}",
                    figure_number=figure_number,
                    kind=kind,
                    page=int(raw["page"]) + 1,
                    caption=_optional_text(raw.get("caption")),
                    bbox=BoundingBox(
                        x1=float(boundary["x1"]),
                        y1=float(boundary["y1"]),
                        x2=float(boundary["x2"]),
                        y2=float(boundary["y2"]),
                    ),
                    image_path=relative_image,
                    width=width,
                    height=height,
                    extractor=ExtractorName.PDFFIGURES2,
                    extractor_version=self.extractor_version,
                )
            )
        return figures

    def _failure(
        self,
        arxiv_id: str,
        started: float,
        error_type: str,
        error_message: str,
    ) -> ExtractionResult:
        return ExtractionResult(
            arxiv_id=arxiv_id,
            extractor=ExtractorName.PDFFIGURES2,
            extractor_version=self.extractor_version,
            runtime_seconds=time.monotonic() - started,
            error_type=error_type,
            error_message=error_message,
        )


def _safe_id(arxiv_id: str) -> str:
    return arxiv_id.replace("/", "_")


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split())
    return normalized or None
