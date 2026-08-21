from __future__ import annotations

from datetime import datetime
from pathlib import Path

from paperflow.figures.extract import FigureProductionService, FigureProductionSettings
from paperflow.figures.models import (
    BoundingBox,
    ExtractedFigure,
    ExtractionResult,
    ExtractorName,
    FigureKind,
)
from paperflow.models import (
    FigureStatus,
    FilterStatus,
    SelectedPaper,
    SummaryStatus,
    TopicAssignment,
)

HASH = "8" * 64


class FakeDownloader:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def download(self, url: str, destination: Path, *, timeout: float) -> None:
        del timeout
        self.calls.append(url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"%PDF-fixture")


class FakeWriter:
    def __init__(self, *, fail_for: str | None = None) -> None:
        self.fail_for = fail_for

    def write_webp(
        self,
        source: Path,
        destination: Path,
        *,
        max_long_edge: int,
        quality: int,
    ) -> tuple[int, int]:
        del max_long_edge, quality
        if self.fail_for and self.fail_for in str(source):
            raise OSError("fixture conversion failure")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"RIFF-fixture-WEBP")
        return (1200, 700)


class FakeAdapter:
    def extract(self, pdf_path: Path, *, arxiv_id: str, work_dir: Path):
        if arxiv_id.endswith("003"):
            return ExtractionResult(
                arxiv_id=arxiv_id,
                extractor=ExtractorName.PDFFIGURES2,
                runtime_seconds=0.1,
                error_type="process_failed",
                error_message="fixture failure",
            )
        output = work_dir / "pdffigures2" / arxiv_id
        output.mkdir(parents=True, exist_ok=True)
        figures = [
            _extracted(
                arxiv_id,
                output,
                "results",
                caption="Figure 2. Additional results.",
            ),
            _extracted(
                arxiv_id,
                output,
                "overview",
                caption="Figure 1. Architecture overview of the method.",
            ),
        ]
        return ExtractionResult(
            arxiv_id=arxiv_id,
            extractor=ExtractorName.PDFFIGURES2,
            runtime_seconds=0.1,
            figures=figures,
            ranked_figure_ids=[figure.figure_id for figure in figures],
        )


def _extracted(
    arxiv_id: str,
    output: Path,
    name: str,
    *,
    caption: str,
) -> ExtractedFigure:
    path = output / f"{name}.png"
    path.write_bytes(b"fixture source")
    return ExtractedFigure(
        figure_id=name,
        figure_number="1" if name == "overview" else "2",
        kind=FigureKind.FIGURE,
        page=2 if name == "overview" else 8,
        caption=caption,
        bbox=BoundingBox(x1=20, y1=20, x2=500, y2=300),
        image_path=path.relative_to(output.parents[2]).as_posix(),
        width=900,
        height=500,
        extractor=ExtractorName.PDFFIGURES2,
    )


def _paper(arxiv_id: str) -> SelectedPaper:
    seen = datetime.fromisoformat("2026-08-20T21:00:00-04:00")
    return SelectedPaper(
        arxiv_id=arxiv_id,
        source_arxiv_id=f"{arxiv_id}v1",
        title=f"Paper {arxiv_id}",
        abstract="A complete deterministic abstract.",
        authors=["Fixture Author"],
        categories=["cs.AI"],
        arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
        first_seen_at=seen,
        first_seen_date=seen.date(),
        filter_status=FilterStatus.KEPT,
        relevance=9,
        novelty=8,
        topic_assignments=[TopicAssignment(topic_id="world-models")],
        selection_reason="Fixture selection.",
        summary_status=SummaryStatus.GENERATED,
        tldr="Fixture summary.",
        bullets=["Problem.", "Method.", "Contribution."],
        figure_status=FigureStatus.NOT_IMPLEMENTED,
        taxonomy_version=1,
        taxonomy_hash=HASH,
        filter_prompt_version="filter-v3",
        filter_prompt_hash=HASH,
        summary_prompt_version="summary-v2",
        summary_prompt_hash=HASH,
        filter_model="fixture/filter",
        summary_model="fixture/summary",
    )


def test_success_publishes_ranked_gallery_and_reuses_cached_pdf(tmp_path: Path) -> None:
    downloader = FakeDownloader()
    paper = _paper("2608.30001")
    service = FigureProductionService(
        adapter=FakeAdapter(),
        cache_root=tmp_path / "cache",
        settings=FigureProductionSettings(concurrency=1),
        downloader=downloader,
        image_writer=FakeWriter(),
    )

    first = service.process({paper.arxiv_id: paper}, publication_root=tmp_path)
    ready = first[paper.arxiv_id]
    assert ready.figure_status == FigureStatus.READY
    assert ready.hero_figure == "figures/2608.30001/hero.webp"
    assert [item.figure_id for item in ready.figures] == ["overview", "results"]
    assert all((tmp_path / item.image_path).is_file() for item in ready.figures)
    assert (tmp_path / ready.hero_figure).is_file()

    second = service.process(first, publication_root=tmp_path)
    assert second == first
    assert len(downloader.calls) == 1


def test_one_extraction_failure_does_not_block_sibling_paper(tmp_path: Path) -> None:
    papers = {
        paper.arxiv_id: paper
        for paper in (_paper("2608.30002"), _paper("2608.30003"))
    }
    service = FigureProductionService(
        adapter=FakeAdapter(),
        cache_root=tmp_path / "cache",
        settings=FigureProductionSettings(concurrency=2),
        downloader=FakeDownloader(),
        image_writer=FakeWriter(),
    )

    result = service.process(papers, publication_root=tmp_path)

    assert result["2608.30002"].figure_status == FigureStatus.READY
    assert result["2608.30003"].figure_status == FigureStatus.FAILED
    assert result["2608.30003"].hero_figure is None
    assert result["2608.30003"].figures == []


def test_image_write_failure_publishes_no_contract_paths(tmp_path: Path) -> None:
    paper = _paper("2608.30004")
    service = FigureProductionService(
        adapter=FakeAdapter(),
        cache_root=tmp_path / "cache",
        downloader=FakeDownloader(),
        image_writer=FakeWriter(fail_for="overview"),
    )

    result = service.process({paper.arxiv_id: paper}, publication_root=tmp_path)

    assert result[paper.arxiv_id].figure_status == FigureStatus.FAILED
    assert result[paper.arxiv_id].figures == []


def test_rebuild_can_target_exactly_one_selected_paper(tmp_path: Path) -> None:
    first = _paper("2608.30005")
    second = _paper("2608.30006")
    papers = {paper.arxiv_id: paper for paper in (first, second)}
    service = FigureProductionService(
        adapter=FakeAdapter(),
        cache_root=tmp_path / "cache",
        downloader=FakeDownloader(),
        image_writer=FakeWriter(),
    )

    result = service.process(
        papers,
        publication_root=tmp_path,
        only_ids=[first.arxiv_id],
        force=True,
    )

    assert result[first.arxiv_id].figure_status == FigureStatus.READY
    assert result[second.arxiv_id] == second
