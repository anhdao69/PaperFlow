"""Deterministic representative-figure scoring for PaperFlow."""

from __future__ import annotations

from paperflow.figures.models import ExtractedFigure, FigureKind

HERO_KEYWORDS: dict[str, float] = {
    "overview": 5,
    "architecture": 5,
    "framework": 5,
    "pipeline": 4,
    "method": 3,
    "system": 3,
    "model": 2,
}


def hero_score(figure: ExtractedFigure) -> float:
    """Score a crop using only reproducible extractor metadata."""
    caption = (figure.caption or "").casefold()
    score = sum(
        weight for keyword, weight in HERO_KEYWORDS.items() if keyword in caption
    )
    pixels = figure.width * figure.height
    if pixels >= 500_000:
        score += 3
    elif pixels >= 200_000:
        score += 2
    elif pixels < 40_000:
        score -= 5
    aspect = figure.width / figure.height
    if 1.15 <= aspect <= 3.5:
        score += 2
    if figure.kind == FigureKind.TABLE:
        score -= 12
    if figure.page > 10:
        score -= min((figure.page - 10) * 0.25, 4)
    return score


def rank_hero_candidates(figures: list[ExtractedFigure]) -> list[ExtractedFigure]:
    """Return all crops in stable representative-first order."""
    return sorted(
        figures,
        key=lambda figure: (
            -hero_score(figure),
            figure.kind == FigureKind.TABLE,
            -(figure.width * figure.height),
            figure.page,
            figure.figure_id,
        ),
    )


def select_hero(figures: list[ExtractedFigure]) -> ExtractedFigure | None:
    ranked = rank_hero_candidates(figures)
    return ranked[0] if ranked else None
