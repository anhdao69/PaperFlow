"""Pure arXiv identity normalization and stable candidate deduplication."""

from __future__ import annotations

import re
from collections.abc import Iterable

from paperflow.models import AnnounceType, CandidatePaper, RawArxivEntry

_MODERN_SOURCE_ID = re.compile(r"^(\d{4}\.\d{4,5})(?:v\d+)?$")
_LEGACY_SOURCE_ID = re.compile(
    r"^([a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?$"
)


def normalize_arxiv_id(source_arxiv_id: str) -> str:
    """Return the canonical versionless identity for modern or legacy IDs."""
    candidate = source_arxiv_id.removeprefix("arXiv:").strip()
    for pattern in (_MODERN_SOURCE_ID, _LEGACY_SOURCE_ID):
        match = pattern.fullmatch(candidate)
        if match is not None:
            return match.group(1)
    raise ValueError(f"invalid arXiv ID: {source_arxiv_id!r}")


def normalize_scientific_text(value: str) -> str:
    """Normalize presentation whitespace without rewriting scientific content."""
    return " ".join(value.split())


def normalize_and_deduplicate(
    entries: Iterable[RawArxivEntry],
) -> list[CandidatePaper]:
    """Exclude replacements and merge cross-list duplicates in source order."""
    candidates: list[CandidatePaper] = []
    index_by_id: dict[str, int] = {}
    for entry in entries:
        if entry.announce_type == AnnounceType.REPLACE:
            continue
        arxiv_id = normalize_arxiv_id(entry.source_arxiv_id)
        existing_index = index_by_id.get(arxiv_id)
        if existing_index is None:
            candidate = CandidatePaper(
                arxiv_id=arxiv_id,
                source_arxiv_id=entry.source_arxiv_id,
                title=normalize_scientific_text(entry.title),
                abstract=normalize_scientific_text(entry.abstract),
                authors=_stable_unique(entry.authors),
                categories=_stable_unique(entry.categories),
                arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
            )
            index_by_id[arxiv_id] = len(candidates)
            candidates.append(candidate)
            continue

        existing = candidates[existing_index]
        merged_categories = _stable_unique([*existing.categories, *entry.categories])
        merged_authors = _stable_unique([*existing.authors, *entry.authors])
        candidates[existing_index] = existing.model_copy(
            update={"categories": merged_categories, "authors": merged_authors}
        )
    return candidates


def _stable_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = normalize_scientific_text(value)
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
