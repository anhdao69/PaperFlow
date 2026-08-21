"""Docling CLI adapter using the current DoclingDocument JSON contract."""

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


class DoclingAdapter:
    """Run Docling as isolated optional tooling through its stable CLI boundary."""

    def __init__(
        self,
        command_prefix: Sequence[str] = ("docling", "convert"),
        *,
        runner: CommandRunner | None = None,
        timeout_seconds: float = 180,
        extractor_version: str | None = None,
    ) -> None:
        if not command_prefix:
            raise ValueError("Docling command prefix cannot be empty")
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

        output_dir = work_dir / ExtractorName.DOCLING.value / _safe_id(arxiv_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            *self.command_prefix,
            str(pdf_path.resolve()),
            "--to",
            "json",
            "--image-export-mode",
            "referenced",
            "--output",
            str(output_dir.resolve()),
            "--document-timeout",
            str(self.timeout_seconds),
            "--device",
            "cpu",
            "--quiet",
        ]
        try:
            completed = self.runner.run(
                command,
                cwd=output_dir,
                timeout=self.timeout_seconds + 5,
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

        metadata_path = output_dir / f"{pdf_path.stem}.json"
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            figures = self._parse_payload(
                payload, metadata_path=metadata_path, work_dir=work_dir
            )
        except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError):
            return self._failure(
                arxiv_id, started, "invalid_output", "extractor output is invalid"
            )
        return ExtractionResult(
            arxiv_id=arxiv_id,
            extractor=ExtractorName.DOCLING,
            extractor_version=self.extractor_version,
            runtime_seconds=time.monotonic() - started,
            figures=figures,
            ranked_figure_ids=rank_figures(figures),
        )

    def _parse_payload(
        self,
        payload: Any,
        *,
        metadata_path: Path,
        work_dir: Path,
    ) -> list[ExtractedFigure]:
        if not isinstance(payload, dict):
            raise ValueError("Docling output must be an object")
        texts = payload.get("texts", [])
        if not isinstance(texts, list):
            raise ValueError("Docling texts must be a list")
        pages = payload.get("pages", {})
        if not isinstance(pages, dict):
            raise ValueError("Docling pages must be an object")

        candidates: list[tuple[FigureKind, dict[str, Any]]] = []
        item_groups = (
            ("pictures", FigureKind.FIGURE),
            ("tables", FigureKind.TABLE),
        )
        for key, kind in item_groups:
            items = payload.get(key, [])
            if not isinstance(items, list):
                raise ValueError(f"Docling {key} must be a list")
            if any(not isinstance(item, dict) for item in items):
                raise ValueError(f"Docling {key} items must be objects")
            candidates.extend((kind, item) for item in items)

        figures: list[ExtractedFigure] = []
        for index, (kind, raw) in enumerate(candidates):
            # Current Docling exports referenced images for pictures, but table
            # items can be metadata-only. A missing image means the item was not
            # extracted as a usable crop; it must not invalidate valid pictures.
            if not _has_referenced_image(raw):
                continue
            provenance = raw.get("prov")
            if not isinstance(provenance, list) or not provenance:
                raise ValueError("Docling item has no provenance")
            prov = provenance[0]
            if not isinstance(prov, dict):
                raise ValueError("Docling provenance must be an object")
            page = int(prov["page_no"])
            page_data = pages.get(str(page), pages.get(page))
            if not isinstance(page_data, dict):
                raise ValueError("Docling page metadata is missing")
            size = page_data.get("size")
            if not isinstance(size, dict):
                raise ValueError("Docling page size is missing")
            page_height = float(size["height"])
            bbox = _docling_bbox(prov["bbox"], page_height=page_height)
            image = _docling_image_path(raw, metadata_path.parent)
            image = image.resolve()
            relative_image = image.relative_to(work_dir.resolve()).as_posix()
            width, height = png_dimensions(image)
            figure_number = _figure_number(raw, index=index)
            figures.append(
                ExtractedFigure(
                    figure_id=f"{kind.value}-{figure_number or index + 1}-{index + 1}",
                    figure_number=figure_number,
                    kind=kind,
                    page=page,
                    caption=_caption_text(raw, texts),
                    bbox=bbox,
                    image_path=relative_image,
                    width=width,
                    height=height,
                    extractor=ExtractorName.DOCLING,
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
            extractor=ExtractorName.DOCLING,
            extractor_version=self.extractor_version,
            runtime_seconds=time.monotonic() - started,
            error_type=error_type,
            error_message=error_message,
        )


def _safe_id(arxiv_id: str) -> str:
    return arxiv_id.replace("/", "_")


def _docling_bbox(value: object, *, page_height: float) -> BoundingBox:
    if not isinstance(value, dict):
        raise ValueError("Docling bounding box must be an object")
    left = float(value["l"])
    right = float(value["r"])
    top = float(value["t"])
    bottom = float(value["b"])
    origin = str(value.get("coord_origin", "TOPLEFT")).upper()
    if origin == "BOTTOMLEFT":
        top, bottom = page_height - top, page_height - bottom
    elif origin != "TOPLEFT":
        raise ValueError("unsupported Docling coordinate origin")
    return BoundingBox(
        x1=min(left, right),
        y1=min(top, bottom),
        x2=max(left, right),
        y2=max(top, bottom),
    )


def _docling_image_path(raw: dict[str, Any], base_dir: Path) -> Path:
    image = raw.get("image")
    candidate: object = image
    if isinstance(image, dict):
        candidate = image.get("uri", image.get("path"))
    if not isinstance(candidate, str) or not candidate or candidate.startswith("data:"):
        raise ValueError("Docling referenced image is missing")
    path = Path(candidate)
    return path if path.is_absolute() else base_dir / path


def _has_referenced_image(raw: dict[str, Any]) -> bool:
    image = raw.get("image")
    candidate: object = image
    if isinstance(image, dict):
        candidate = image.get("uri", image.get("path"))
    return (
        isinstance(candidate, str)
        and bool(candidate)
        and not candidate.startswith("data:")
    )


def _caption_text(raw: dict[str, Any], texts: list[object]) -> str | None:
    captions = raw.get("captions", [])
    if not isinstance(captions, list):
        raise ValueError("Docling captions must be a list")
    parts: list[str] = []
    for caption in captions:
        if not isinstance(caption, dict):
            continue
        reference = caption.get("$ref", caption.get("cref"))
        if not isinstance(reference, str) or not reference.startswith("#/texts/"):
            continue
        item = texts[int(reference.rsplit("/", 1)[1])]
        if not isinstance(item, dict):
            continue
        text = item.get("text", item.get("orig"))
        if isinstance(text, str) and text.strip():
            parts.append(" ".join(text.split()))
    return " ".join(parts) or None


def _figure_number(raw: dict[str, Any], *, index: int) -> str | None:
    for key in ("name", "figure_number"):
        value = raw.get(key)
        if value is not None and str(value).strip():
            return " ".join(str(value).split())
    self_ref = raw.get("self_ref")
    if isinstance(self_ref, str) and self_ref.rsplit("/", 1)[-1].isdigit():
        return str(int(self_ref.rsplit("/", 1)[-1]) + 1)
    return str(index + 1)
