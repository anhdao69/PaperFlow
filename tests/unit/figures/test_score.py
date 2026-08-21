from __future__ import annotations

from paperflow.figures.models import (
    BoundingBox,
    ExtractedFigure,
    ExtractorName,
    FigureKind,
)
from paperflow.figures.score import hero_score, rank_hero_candidates, select_hero


def _figure(
    figure_id: str,
    *,
    caption: str | None = None,
    kind: FigureKind = FigureKind.FIGURE,
    page: int = 2,
    width: int = 800,
    height: int = 500,
) -> ExtractedFigure:
    return ExtractedFigure(
        figure_id=figure_id,
        figure_number=figure_id,
        kind=kind,
        page=page,
        caption=caption,
        bbox=BoundingBox(x1=20, y1=20, x2=500, y2=300),
        image_path=f"pdffigures2/paper/{figure_id}.png",
        width=width,
        height=height,
        extractor=ExtractorName.PDFFIGURES2,
    )


def test_architecture_overview_wins_over_a_larger_late_result() -> None:
    overview = _figure("1", caption="Figure 1. Architecture overview of our method.")
    result = _figure("9", caption="Figure 9. Additional result.", page=18, width=1400)

    assert hero_score(overview) > hero_score(result)
    assert select_hero([result, overview]) == overview


def test_tables_and_tiny_regions_are_penalized() -> None:
    table = _figure(
        "table", caption="System overview", kind=FigureKind.TABLE, width=1200
    )
    tiny = _figure("tiny", caption="Method", width=100, height=100)
    ordinary = _figure("ordinary", caption="Qualitative comparison")

    assert rank_hero_candidates([table, tiny, ordinary])[0] == ordinary


def test_ranking_has_a_stable_tie_break_and_empty_fallback() -> None:
    later = _figure("b", page=3)
    earlier = _figure("a", page=2)

    assert rank_hero_candidates([later, earlier]) == [earlier, later]
    assert select_hero([]) is None
