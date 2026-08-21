"""Deterministic evaluation harness for the final-workstream extractor gate."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from paperflow.figures.adapters.base import FigureExtractorAdapter
from paperflow.figures.models import (
    AggregateMetrics,
    EvaluationManifest,
    EvaluationPaperLabel,
    EvaluationReport,
    ExtractionResult,
    ExtractorEvaluation,
    ExtractorName,
    LayoutClass,
    PaperMetrics,
)

DETECTION_IOU = 0.50
CORRECT_CROP_IOU = 0.80
RELEASE_CORPUS_SIZE = 50


def load_manifest(path: Path) -> EvaluationManifest:
    return EvaluationManifest.model_validate_json(path.read_text(encoding="utf-8"))


def validate_release_corpus(
    manifest: EvaluationManifest,
    *,
    pdf_root: Path,
) -> dict[str, Path]:
    """Reject incomplete or unreviewed corpora before invoking either extractor."""
    if not manifest.human_reviewed:
        raise ValueError("release corpus must be human reviewed")
    if len(manifest.papers) < RELEASE_CORPUS_SIZE:
        raise ValueError(
            f"release corpus requires at least {RELEASE_CORPUS_SIZE} papers"
        )
    observed_layouts = {
        layout for paper in manifest.papers for layout in paper.layout_classes
    }
    missing_layouts = set(LayoutClass) - observed_layouts
    if missing_layouts:
        names = ", ".join(sorted(layout.value for layout in missing_layouts))
        raise ValueError(f"release corpus is missing layout classes: {names}")

    paths: dict[str, Path] = {}
    for paper in manifest.papers:
        path = pdf_root / f"{paper.arxiv_id.replace('/', '_')}.pdf"
        if not path.is_file():
            raise ValueError(f"evaluation PDF is missing for {paper.arxiv_id}")
        if _sha256_file(path) != paper.pdf_sha256:
            raise ValueError(f"evaluation PDF hash mismatch for {paper.arxiv_id}")
        paths[paper.arxiv_id] = path
    return paths


def run_evaluation(
    manifest: EvaluationManifest,
    *,
    pdf_root: Path,
    work_root: Path,
    adapters: Mapping[ExtractorName, FigureExtractorAdapter],
) -> EvaluationReport:
    pdf_paths = validate_release_corpus(manifest, pdf_root=pdf_root)
    required = set(ExtractorName)
    if set(adapters) != required:
        raise ValueError("evaluation requires exactly PDFFigures2 and Docling")
    results: dict[ExtractorName, dict[str, ExtractionResult]] = {}
    for extractor in sorted(required, key=lambda item: item.value):
        adapter = adapters[extractor]
        extractor_results: dict[str, ExtractionResult] = {}
        for paper in manifest.papers:
            extractor_results[paper.arxiv_id] = adapter.extract(
                pdf_paths[paper.arxiv_id],
                arxiv_id=paper.arxiv_id,
                work_dir=work_root,
            )
        results[extractor] = extractor_results
    return evaluate_results(manifest, results)


def evaluate_results(
    manifest: EvaluationManifest,
    results: Mapping[ExtractorName, Mapping[str, ExtractionResult]],
) -> EvaluationReport:
    expected_ids = {paper.arxiv_id for paper in manifest.papers}
    if not manifest.papers:
        raise ValueError("cannot evaluate an empty corpus")
    evaluations: list[ExtractorEvaluation] = []
    for extractor in sorted(results, key=lambda item: item.value):
        by_paper = results[extractor]
        if set(by_paper) != expected_ids:
            raise ValueError(f"{extractor.value} results do not match the corpus")
        metrics = [
            _paper_metrics(paper, by_paper[paper.arxiv_id], extractor=extractor)
            for paper in manifest.papers
        ]
        evaluations.append(
            ExtractorEvaluation(
                extractor=extractor,
                per_paper=metrics,
                aggregate=_aggregate(metrics),
            )
        )
    if set(results) != set(ExtractorName):
        raise ValueError("results must include exactly PDFFigures2 and Docling")
    return EvaluationReport(
        schema_version=1,
        corpus_sha256=_manifest_sha256(manifest),
        evaluations=evaluations,
    )


def write_report(report: EvaluationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _paper_metrics(
    label: EvaluationPaperLabel,
    result: ExtractionResult,
    *,
    extractor: ExtractorName,
) -> PaperMetrics:
    if result.arxiv_id != label.arxiv_id or result.extractor != extractor:
        raise ValueError("extraction result identity does not match its label")
    if result.error_type is not None:
        return PaperMetrics(
            arxiv_id=label.arxiv_id,
            extractor=extractor,
            labeled_figures=len(label.figures),
            labeled_captions=sum(item.caption is not None for item in label.figures),
            detected_figures=0,
            matched_figures=0,
            correct_crops=0,
            correct_captions=0,
            hero_top1_correct=False,
            runtime_seconds=result.runtime_seconds,
            failed=True,
            error_type=result.error_type,
        )

    pairs: list[tuple[float, int, int]] = []
    for label_index, expected in enumerate(label.figures):
        for result_index, actual in enumerate(result.figures):
            if expected.page == actual.page and expected.kind == actual.kind:
                pairs.append(
                    (
                        expected.bbox.intersection_over_union(actual.bbox),
                        label_index,
                        result_index,
                    )
                )
    used_labels: set[int] = set()
    used_results: set[int] = set()
    matches: list[tuple[float, int, int]] = []
    for iou, label_index, result_index in sorted(
        pairs, key=lambda item: (-item[0], item[1], item[2])
    ):
        if iou < DETECTION_IOU:
            break
        if label_index in used_labels or result_index in used_results:
            continue
        used_labels.add(label_index)
        used_results.add(result_index)
        matches.append((iou, label_index, result_index))

    correct_captions = sum(
        _normalized_caption(label.figures[label_index].caption)
        == _normalized_caption(result.figures[result_index].caption)
        for _, label_index, result_index in matches
        if label.figures[label_index].caption is not None
    )
    hero_index = next(
        index
        for index, figure in enumerate(label.figures)
        if figure.label_id == label.desired_hero_label_id
    )
    top_id = result.ranked_figure_ids[0] if result.ranked_figure_ids else None
    top_index = next(
        (
            index
            for index, figure in enumerate(result.figures)
            if figure.figure_id == top_id
        ),
        None,
    )
    hero_top1 = any(
        label_index == hero_index and result_index == top_index
        for _, label_index, result_index in matches
    )
    return PaperMetrics(
        arxiv_id=label.arxiv_id,
        extractor=extractor,
        labeled_figures=len(label.figures),
        labeled_captions=sum(item.caption is not None for item in label.figures),
        detected_figures=len(result.figures),
        matched_figures=len(matches),
        correct_crops=sum(iou >= CORRECT_CROP_IOU for iou, _, _ in matches),
        correct_captions=correct_captions,
        hero_top1_correct=hero_top1,
        runtime_seconds=result.runtime_seconds,
        failed=False,
    )


def _aggregate(metrics: list[PaperMetrics]) -> AggregateMetrics:
    papers = len(metrics)
    labeled_figures = sum(item.labeled_figures for item in metrics)
    labeled_captions = sum(item.labeled_captions for item in metrics)
    return AggregateMetrics(
        papers=papers,
        labeled_figures=labeled_figures,
        labeled_captions=labeled_captions,
        detection_recall=sum(item.matched_figures for item in metrics)
        / labeled_figures,
        crop_correctness=sum(item.correct_crops for item in metrics)
        / labeled_figures,
        caption_correctness=(
            sum(item.correct_captions for item in metrics) / labeled_captions
            if labeled_captions
            else 0.0
        ),
        hero_top1_accuracy=sum(item.hero_top1_correct for item in metrics) / papers,
        mean_runtime_seconds=sum(item.runtime_seconds for item in metrics) / papers,
        failure_rate=sum(item.failed for item in metrics) / papers,
    )


def _normalized_caption(value: str | None) -> str | None:
    return " ".join(value.casefold().split()) if value is not None else None


def _manifest_sha256(manifest: EvaluationManifest) -> str:
    serialized = json.dumps(
        manifest.model_dump(mode="json"),
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(serialized).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
