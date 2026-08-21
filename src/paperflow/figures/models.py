"""Typed contracts shared by figure extractor adapters and evaluation."""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from paperflow.models import validate_canonical_arxiv_id

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class FigureModel(BaseModel):
    """Strict base model for persisted figure evaluation data."""

    model_config = ConfigDict(extra="forbid")


class ExtractorName(StrEnum):
    PDFFIGURES2 = "pdffigures2"
    DOCLING = "docling"


class FigureKind(StrEnum):
    FIGURE = "figure"
    TABLE = "table"


class LayoutClass(StrEnum):
    SINGLE_COLUMN = "single-column"
    TWO_COLUMN = "two-column"
    MULTI_PANEL = "multi-panel"
    VECTOR_DIAGRAM = "vector-diagram"
    RASTER = "raster"
    FULL_WIDTH = "full-width"
    TABLE_NEAR_FIGURE = "table-near-figure"
    LONG_CAPTION = "long-caption"


class BoundingBox(FigureModel):
    """A top-left-origin box in 72-DPI PDF page coordinates."""

    x1: float = Field(ge=0)
    y1: float = Field(ge=0)
    x2: float = Field(gt=0)
    y2: float = Field(gt=0)

    @model_validator(mode="after")
    def require_positive_area(self) -> BoundingBox:
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("bounding box must have positive area")
        return self

    @property
    def area(self) -> float:
        return (self.x2 - self.x1) * (self.y2 - self.y1)

    def intersection_over_union(self, other: BoundingBox) -> float:
        width = max(0.0, min(self.x2, other.x2) - max(self.x1, other.x1))
        height = max(0.0, min(self.y2, other.y2) - max(self.y1, other.y1))
        intersection = width * height
        union = self.area + other.area - intersection
        return intersection / union if union else 0.0


class ExtractedFigure(FigureModel):
    """Extractor-neutral figure metadata used by scoring and evaluation."""

    figure_id: NonEmptyText
    figure_number: str | None = None
    kind: FigureKind
    page: int = Field(ge=1)
    caption: str | None = None
    bbox: BoundingBox
    image_path: NonEmptyText
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    extractor: ExtractorName
    extractor_version: str | None = None

    @field_validator("image_path")
    @classmethod
    def require_safe_relative_image_path(cls, value: str) -> str:
        candidate = PurePosixPath(value)
        if (
            candidate.is_absolute()
            or ".." in candidate.parts
            or "\\" in value
            or not candidate.parts
        ):
            raise ValueError("image_path must be a safe relative path")
        return value


class ExtractionResult(FigureModel):
    arxiv_id: str
    extractor: ExtractorName
    extractor_version: str | None = None
    runtime_seconds: float = Field(ge=0)
    figures: list[ExtractedFigure] = Field(default_factory=list)
    ranked_figure_ids: list[NonEmptyText] = Field(default_factory=list)
    error_type: str | None = None
    error_message: str | None = None

    _validate_arxiv_id = field_validator("arxiv_id")(validate_canonical_arxiv_id)

    @model_validator(mode="after")
    def validate_result(self) -> ExtractionResult:
        ids = [figure.figure_id for figure in self.figures]
        if len(ids) != len(set(ids)):
            raise ValueError("figure IDs must be unique")
        if len(self.ranked_figure_ids) != len(set(self.ranked_figure_ids)):
            raise ValueError("ranked figure IDs must be unique")
        if set(self.ranked_figure_ids) != set(ids):
            raise ValueError("ranking must contain every extracted figure exactly once")
        if any(figure.extractor != self.extractor for figure in self.figures):
            raise ValueError("figure extractor must match result extractor")
        if (self.error_type is None) != (self.error_message is None):
            raise ValueError("error type and message must be present together")
        if self.error_type is not None and self.figures:
            raise ValueError("failed extraction cannot contain partial figures")
        return self


class LabeledFigure(FigureModel):
    label_id: NonEmptyText
    figure_number: str | None = None
    kind: FigureKind
    page: int = Field(ge=1)
    caption: str | None = None
    bbox: BoundingBox


class EvaluationPaperLabel(FigureModel):
    arxiv_id: str
    pdf_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    layout_classes: list[LayoutClass] = Field(min_length=1)
    figures: list[LabeledFigure] = Field(min_length=1)
    desired_hero_label_id: NonEmptyText
    reviewed_by: NonEmptyText

    _validate_arxiv_id = field_validator("arxiv_id")(validate_canonical_arxiv_id)

    @model_validator(mode="after")
    def validate_paper_label(self) -> EvaluationPaperLabel:
        layouts = list(dict.fromkeys(self.layout_classes))
        if len(layouts) != len(self.layout_classes):
            raise ValueError("layout classes must be unique")
        ids = [figure.label_id for figure in self.figures]
        if len(ids) != len(set(ids)):
            raise ValueError("figure label IDs must be unique")
        if self.desired_hero_label_id not in ids:
            raise ValueError("desired hero must reference a labeled figure")
        return self


class EvaluationManifest(FigureModel):
    schema_version: int = Field(ge=1)
    human_reviewed: bool
    papers: list[EvaluationPaperLabel]

    @model_validator(mode="after")
    def require_unique_papers(self) -> EvaluationManifest:
        ids = [paper.arxiv_id for paper in self.papers]
        if len(ids) != len(set(ids)):
            raise ValueError("evaluation paper IDs must be unique")
        return self


class PaperMetrics(FigureModel):
    arxiv_id: str
    extractor: ExtractorName
    labeled_figures: int = Field(ge=1)
    labeled_captions: int = Field(ge=0)
    detected_figures: int = Field(ge=0)
    matched_figures: int = Field(ge=0)
    correct_crops: int = Field(ge=0)
    correct_captions: int = Field(ge=0)
    hero_top1_correct: bool
    runtime_seconds: float = Field(ge=0)
    failed: bool
    error_type: str | None = None

    _validate_arxiv_id = field_validator("arxiv_id")(validate_canonical_arxiv_id)


class AggregateMetrics(FigureModel):
    papers: int = Field(ge=1)
    labeled_figures: int = Field(ge=1)
    labeled_captions: int = Field(ge=0)
    detection_recall: float = Field(ge=0, le=1)
    crop_correctness: float = Field(ge=0, le=1)
    caption_correctness: float = Field(ge=0, le=1)
    hero_top1_accuracy: float = Field(ge=0, le=1)
    mean_runtime_seconds: float = Field(ge=0)
    failure_rate: float = Field(ge=0, le=1)


class ExtractorEvaluation(FigureModel):
    extractor: ExtractorName
    per_paper: list[PaperMetrics] = Field(min_length=1)
    aggregate: AggregateMetrics


class EvaluationReport(FigureModel):
    schema_version: int = Field(ge=1)
    corpus_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    evaluations: list[ExtractorEvaluation] = Field(min_length=2)

    @model_validator(mode="after")
    def require_unique_extractors(self) -> EvaluationReport:
        names = [evaluation.extractor for evaluation in self.evaluations]
        if len(names) != len(set(names)):
            raise ValueError("evaluation extractors must be unique")
        return self
