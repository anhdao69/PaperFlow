"""Non-blocking production figure extraction and publication."""

from __future__ import annotations

import os
import shutil
import tempfile
import urllib.request
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageOps

from paperflow.figures.adapters.base import FigureExtractorAdapter
from paperflow.figures.models import ExtractionResult
from paperflow.figures.score import rank_hero_candidates
from paperflow.models import FigureAsset, FigureStatus, SelectedPaper


class PDFDownloader(Protocol):
    def download(self, url: str, destination: Path, *, timeout: float) -> None: ...


class FigureImageWriter(Protocol):
    def write_webp(
        self,
        source: Path,
        destination: Path,
        *,
        max_long_edge: int,
        quality: int,
    ) -> tuple[int, int]: ...


class URLPDFDownloader:
    """Download one PDF without exposing credentials or retaining partial files."""

    def download(self, url: str, destination: Path, *, timeout: float) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/pdf", "User-Agent": "PaperFlow/1.0"},
        )
        temporary = destination.with_suffix(destination.suffix + ".part")
        try:
            with (
                urllib.request.urlopen(request, timeout=timeout) as response,
                temporary.open("wb") as output,
            ):
                shutil.copyfileobj(response, output)
            _validate_pdf(temporary)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)


class PillowFigureImageWriter:
    """Bound a crop and encode it as an RGB WebP for static publication."""

    def write_webp(
        self,
        source: Path,
        destination: Path,
        *,
        max_long_edge: int,
        quality: int,
    ) -> tuple[int, int]:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.thumbnail((max_long_edge, max_long_edge), Image.Resampling.LANCZOS)
            image.save(destination, format="WEBP", quality=quality, method=6)
            return image.size


@dataclass(frozen=True)
class FigureProductionSettings:
    concurrency: int = 2
    download_timeout_seconds: float = 60
    max_long_edge: int = 1600
    webp_quality: int = 88

    def __post_init__(self) -> None:
        if not 1 <= self.concurrency <= 4:
            raise ValueError("figure concurrency must be between 1 and 4")
        if self.download_timeout_seconds <= 0:
            raise ValueError("figure download timeout must be positive")
        if not 320 <= self.max_long_edge <= 2400:
            raise ValueError("figure long edge must be between 320 and 2400")
        if not 1 <= self.webp_quality <= 100:
            raise ValueError("WebP quality must be between 1 and 100")


class FigureProductionService:
    """Run independent per-paper jobs; every failure becomes a safe paper state."""

    def __init__(
        self,
        *,
        adapter: FigureExtractorAdapter,
        cache_root: Path,
        settings: FigureProductionSettings | None = None,
        downloader: PDFDownloader | None = None,
        image_writer: FigureImageWriter | None = None,
    ) -> None:
        self.adapter = adapter
        self.cache_root = cache_root
        self.settings = settings or FigureProductionSettings()
        self.downloader = downloader or URLPDFDownloader()
        self.image_writer = image_writer or PillowFigureImageWriter()

    def process(
        self,
        papers: Mapping[str, SelectedPaper],
        *,
        publication_root: Path,
        only_ids: Sequence[str] = (),
        force: bool = False,
    ) -> dict[str, SelectedPaper]:
        requested = set(only_ids)
        unknown = requested - set(papers)
        if unknown:
            raise ValueError(f"unknown selected paper: {sorted(unknown)[0]}")
        targets = [
            paper
            for paper_id, paper in sorted(papers.items())
            if (not requested or paper_id in requested)
            and (force or not _ready_assets_exist(paper, publication_root))
        ]
        updated = dict(papers)
        with ThreadPoolExecutor(max_workers=self.settings.concurrency) as executor:
            futures = {
                executor.submit(self._process_one, paper, publication_root): paper
                for paper in targets
            }
            for future in as_completed(futures):
                paper = futures[future]
                try:
                    updated[paper.arxiv_id] = future.result()
                except Exception:
                    updated[paper.arxiv_id] = _failed(paper)
        return updated

    def _process_one(
        self, paper: SelectedPaper, publication_root: Path
    ) -> SelectedPaper:
        safe_id = paper.arxiv_id.replace("/", "_")
        pdf_path = self.cache_root / "pdf" / f"{safe_id}.pdf"
        if not pdf_path.is_file():
            self.downloader.download(
                str(paper.pdf_url),
                pdf_path,
                timeout=self.settings.download_timeout_seconds,
            )
        _validate_pdf(pdf_path)
        result = self.adapter.extract(
            pdf_path,
            arxiv_id=paper.arxiv_id,
            work_dir=self.cache_root / "figure-work",
        )
        if result.error_type is not None or not result.figures:
            return _failed(paper)
        return self._publish_result(paper, result, publication_root)

    def _publish_result(
        self,
        paper: SelectedPaper,
        result: ExtractionResult,
        publication_root: Path,
    ) -> SelectedPaper:
        safe_id = paper.arxiv_id.replace("/", "_")
        ranked = rank_hero_candidates(result.figures)
        destination = publication_root / "figures" / safe_id
        destination.mkdir(parents=True, exist_ok=True)
        work_root = self.cache_root / "figure-work"
        with tempfile.TemporaryDirectory(
            dir=self.cache_root, prefix=f"publish-{safe_id}-"
        ) as temporary:
            staging = Path(temporary)
            assets: list[FigureAsset] = []
            for index, figure in enumerate(ranked, start=1):
                filename = f"{figure.kind.value}-{index:03d}.webp"
                staged = staging / filename
                width, height = self.image_writer.write_webp(
                    work_root / figure.image_path,
                    staged,
                    max_long_edge=self.settings.max_long_edge,
                    quality=self.settings.webp_quality,
                )
                relative = Path("figures", safe_id, filename).as_posix()
                assets.append(
                    FigureAsset(
                        figure_id=figure.figure_id,
                        figure_number=figure.figure_number,
                        kind=figure.kind.value,
                        page=figure.page,
                        caption=figure.caption,
                        image_path=relative,
                        width=width,
                        height=height,
                    )
                )
            hero_staged = staging / "hero.webp"
            shutil.copyfile(staging / Path(assets[0].image_path).name, hero_staged)
            for staged in sorted(staging.glob("*.webp")):
                os.replace(staged, destination / staged.name)
        updated = paper.model_copy(
            update={
                "hero_figure": Path("figures", safe_id, "hero.webp").as_posix(),
                "figures": assets,
                "figure_status": FigureStatus.READY,
            }
        )
        return SelectedPaper.model_validate(updated.model_dump())


def resolve_executable_command(command: str, *, working_directory: Path) -> str:
    """Keep PATH commands unchanged and absolutize an existing file command."""
    candidate = Path(command).expanduser()
    if not candidate.is_absolute():
        candidate = working_directory / candidate
    return str(candidate.resolve()) if candidate.is_file() else command


def _validate_pdf(path: Path) -> None:
    with path.open("rb") as source:
        if source.read(5) != b"%PDF-":
            raise ValueError("downloaded document is not a PDF")


def _ready_assets_exist(paper: SelectedPaper, root: Path) -> bool:
    return (
        paper.figure_status == FigureStatus.READY
        and paper.hero_figure is not None
        and (root / paper.hero_figure).is_file()
        and all((root / figure.image_path).is_file() for figure in paper.figures)
    )


def _failed(paper: SelectedPaper) -> SelectedPaper:
    updated = paper.model_copy(
        update={
            "hero_figure": None,
            "figures": [],
            "figure_status": FigureStatus.FAILED,
        }
    )
    return SelectedPaper.model_validate(updated.model_dump())
