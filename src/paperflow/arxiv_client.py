"""Injectable arXiv RSS client with strict complete-source semantics."""

from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from paperflow.atomic import atomic_write_text
from paperflow.models import AnnounceType, RawArxivEntry

_ANNOUNCE_TYPE = re.compile(r"Announce Type:\s*(new|cross|replace)\b", re.IGNORECASE)
_ABSTRACT_PREFIX = re.compile(r"^.*?Abstract:\s*", re.IGNORECASE | re.DOTALL)
_HTML_TAG = re.compile(r"<[^>]+>")
_ARXIV_ID_FROM_URL = re.compile(r"/abs/([^?#]+)")


class ArxivSourceError(RuntimeError):
    """A configured arXiv source could not be fetched completely and safely."""


class HttpTransport(Protocol):
    def get(self, url: str, *, timeout: float) -> bytes: ...


class UrllibTransport:
    def get(self, url: str, *, timeout: float) -> bytes:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "PaperFlow/0.1 (+https://github.com/anhdao69/PaperFlow)"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise ArxivSourceError(f"arXiv returned HTTP {response.status}")
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ArxivSourceError("arXiv request failed") from error


class ArxivClient:
    def __init__(
        self,
        transport: HttpTransport,
        *,
        endpoint_template: str = "https://rss.arxiv.org/rss/{category}",
    ) -> None:
        self._transport = transport
        self._endpoint_template = endpoint_template

    def fetch_new(
        self, categories: Sequence[str], *, timeout_seconds: float
    ) -> list[RawArxivEntry]:
        """Fetch every configured category or fail the complete source operation."""
        entries: list[RawArxivEntry] = []
        for category in categories:
            url = self._endpoint_template.format(category=quote(category, safe="."))
            try:
                payload = self._transport.get(url, timeout=timeout_seconds)
                entries.extend(parse_arxiv_rss(payload, source_category=category))
            except ArxivSourceError:
                raise
            except (ET.ParseError, ValueError) as error:
                raise ArxivSourceError(
                    f"arXiv response for {category} was invalid"
                ) from error
        return entries


def parse_arxiv_rss(payload: bytes, *, source_category: str) -> list[RawArxivEntry]:
    """Parse the minimal RSS fields required by the canonical candidate model."""
    root = ET.fromstring(payload)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("arXiv RSS response has no channel")

    entries: list[RawArxivEntry] = []
    for item in channel.findall("item"):
        title = _required_text(item, "title")
        link = _required_text(item, "link")
        description = _required_text(item, "description")
        match = _ARXIV_ID_FROM_URL.search(link)
        if match is None:
            raise ValueError("arXiv RSS item has no recognizable arXiv ID")
        source_id = match.group(1)

        announce_match = _ANNOUNCE_TYPE.search(description)
        if announce_match is None:
            raise ValueError(f"arXiv RSS item {source_id} has no announce type")
        announce_type = AnnounceType(announce_match.group(1).lower())

        plain_description = html.unescape(_HTML_TAG.sub(" ", description))
        abstract = _ABSTRACT_PREFIX.sub("", plain_description).strip()
        if not abstract:
            raise ValueError(f"arXiv RSS item {source_id} has no abstract")

        authors = _authors(item)
        categories = [
            category.text.strip()
            for category in item.findall("category")
            if category.text and category.text.strip()
        ]
        if source_category not in categories:
            categories.insert(0, source_category)

        entries.append(
            RawArxivEntry(
                source_arxiv_id=source_id,
                title=title,
                abstract=abstract,
                authors=authors,
                categories=categories,
                announce_type=announce_type,
            )
        )
    return entries


def _required_text(item: ET.Element, tag: str) -> str:
    value = item.findtext(tag)
    if value is None or not value.strip():
        raise ValueError(f"arXiv RSS item is missing {tag}")
    return value.strip()


def _authors(item: ET.Element) -> list[str]:
    names = [
        element.text.strip()
        for element in item.findall("{http://purl.org/dc/elements/1.1/}creator")
        if element.text and element.text.strip()
    ]
    if not names:
        raise ValueError("arXiv RSS item has no authors")
    return names


def save_raw_snapshot(
    cache_root: Path,
    run_id: str,
    entries: Sequence[RawArxivEntry],
) -> Path:
    """Persist source diagnostics under an explicitly supplied cache root."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+", run_id):
        raise ValueError("run_id is unsafe for a cache filename")
    path = cache_root / "raw" / f"{run_id}.json"
    payload: Mapping[str, object] = {
        "entry_count": len(entries),
        "entries": [entry.model_dump(mode="json") for entry in entries],
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    atomic_write_text(path, content)
    return path
