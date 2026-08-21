from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from paperflow.figures.evaluation import (
    evaluate_results,
    load_manifest,
    validate_release_corpus,
    write_report,
)
from paperflow.figures.models import (
    BoundingBox,
    EvaluationManifest,
    EvaluationPaperLabel,
    ExtractedFigure,
    ExtractionResult,
    ExtractorName,
    FigureKind,
    LabeledFigure,
    LayoutClass,
)

ZERO_HASH = "0" * 64


def _label(arxiv_id: str, *, pdf_sha256: str = ZERO_HASH) -> EvaluationPaperLabel:
    return EvaluationPaperLabel(
        arxiv_id=arxiv_id,
        pdf_sha256=pdf_sha256,
        layout_classes=[LayoutClass.TWO_COLUMN],
        figures=[
            LabeledFigure(
                label_id="hero",
                figure_number="1",
                kind=FigureKind.FIGURE,
                page=1,
                caption="Figure 1. Architecture overview.",
                bbox=BoundingBox(x1=10, y1=10, x2=110, y2=110),
            )
        ],
        desired_hero_label_id="hero",
        reviewed_by="human-reviewer",
    )


def _success(
    arxiv_id: str,
    extractor: ExtractorName,
    *,
    bbox: BoundingBox,
    caption: str = "Figure 1. Architecture overview.",
    runtime: float = 2.0,
) -> ExtractionResult:
    figure = ExtractedFigure(
        figure_id="figure-1",
        figure_number="1",
        kind=FigureKind.FIGURE,
        page=1,
        caption=caption,
        bbox=bbox,
        image_path=f"{extractor.value}/{arxiv_id}/figure.png",
        width=800,
        height=600,
        extractor=extractor,
    )
    return ExtractionResult(
        arxiv_id=arxiv_id,
        extractor=extractor,
        runtime_seconds=runtime,
        figures=[figure],
        ranked_figure_ids=[figure.figure_id],
    )


def test_metric_aggregation_is_deterministic_and_uses_iou_thresholds():
    manifest = EvaluationManifest(
        schema_version=1,
        human_reviewed=True,
        papers=[_label("2608.10001"), _label("2608.10002")],
    )
    results = {
        ExtractorName.PDFFIGURES2: {
            "2608.10001": _success(
                "2608.10001",
                ExtractorName.PDFFIGURES2,
                bbox=BoundingBox(x1=10, y1=10, x2=110, y2=110),
                caption="  figure 1. ARCHITECTURE overview. ",
                runtime=1,
            ),
            "2608.10002": ExtractionResult(
                arxiv_id="2608.10002",
                extractor=ExtractorName.PDFFIGURES2,
                runtime_seconds=3,
                error_type="timeout",
                error_message="extractor timed out",
            ),
        },
        ExtractorName.DOCLING: {
            "2608.10001": _success(
                "2608.10001",
                ExtractorName.DOCLING,
                bbox=BoundingBox(x1=20, y1=20, x2=120, y2=120),
                runtime=4,
            ),
            "2608.10002": _success(
                "2608.10002",
                ExtractorName.DOCLING,
                bbox=BoundingBox(x1=300, y1=300, x2=400, y2=400),
                runtime=6,
            ),
        },
    }

    report = evaluate_results(manifest, results)
    pdffigures = next(
        item
        for item in report.evaluations
        if item.extractor == ExtractorName.PDFFIGURES2
    ).aggregate
    docling = next(
        item
        for item in report.evaluations
        if item.extractor == ExtractorName.DOCLING
    ).aggregate

    assert pdffigures.detection_recall == 0.5
    assert pdffigures.crop_correctness == 0.5
    assert pdffigures.caption_correctness == 0.5
    assert pdffigures.hero_top1_accuracy == 0.5
    assert pdffigures.mean_runtime_seconds == 2
    assert pdffigures.failure_rate == 0.5
    assert docling.detection_recall == 0.5
    assert docling.crop_correctness == 0
    assert docling.failure_rate == 0
    assert len(report.corpus_sha256) == 64


def test_result_identity_and_completeness_are_required():
    manifest = EvaluationManifest(
        schema_version=1,
        human_reviewed=True,
        papers=[_label("2608.10003")],
    )
    with pytest.raises(ValueError, match="results do not match"):
        evaluate_results(
            manifest,
            {
                ExtractorName.PDFFIGURES2: {},
                ExtractorName.DOCLING: {},
            },
        )


def test_release_manifest_fixture_is_explicitly_not_release_ready():
    root = Path(__file__).resolve().parents[2]
    manifest = load_manifest(root / "fixtures/figures/evaluation_labels.json")
    assert manifest.papers == []
    assert manifest.human_reviewed is False
    with pytest.raises(ValueError, match="human reviewed"):
        validate_release_corpus(manifest, pdf_root=root / "missing-pdfs")


def test_release_corpus_checks_all_layouts_hashes_and_missing_pdfs(tmp_path: Path):
    layouts = list(LayoutClass)
    papers = []
    for index in range(50):
        label = _label(f"2608.{index + 10000}")
        if index == 0:
            label = label.model_copy(update={"layout_classes": layouts})
        papers.append(label)
    manifest = EvaluationManifest(
        schema_version=1,
        human_reviewed=True,
        papers=papers,
    )
    with pytest.raises(ValueError, match="evaluation PDF is missing"):
        validate_release_corpus(manifest, pdf_root=tmp_path)

    first = tmp_path / "2608.10000.pdf"
    first.write_bytes(b"wrong hash")
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_release_corpus(manifest, pdf_root=tmp_path)


def test_report_writer_emits_stable_valid_json(tmp_path: Path):
    paper = _label("2608.10004")
    manifest = EvaluationManifest(
        schema_version=1, human_reviewed=True, papers=[paper]
    )
    exact = BoundingBox(x1=10, y1=10, x2=110, y2=110)
    report = evaluate_results(
        manifest,
        {
            extractor: {
                paper.arxiv_id: _success(paper.arxiv_id, extractor, bbox=exact)
            }
            for extractor in ExtractorName
        },
    )
    path = tmp_path / "report.json"
    write_report(report, path)
    first = path.read_bytes()
    write_report(report, path)
    assert path.read_bytes() == first
    assert hashlib.sha256(first).hexdigest()
