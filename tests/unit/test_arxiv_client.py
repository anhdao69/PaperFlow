from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperflow.arxiv_client import (
    ArxivClient,
    ArxivSourceError,
    parse_arxiv_atom_candidate,
    parse_arxiv_rss,
    save_raw_snapshot,
)
from paperflow.models import AnnounceType


class FakeTransport:
    def __init__(self, responses: dict[str, bytes | Exception]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, float]] = []

    def get(self, url: str, *, timeout: float) -> bytes:
        self.calls.append((url, timeout))
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response


def _rss(items: str = "") -> bytes:
    return f"""<?xml version="1.0"?>
<rss xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0">
  <channel><title>arXiv fixture</title>{items}</channel>
</rss>
""".encode()


def _item(*, announce_type: str = "new", source_id: str = "2608.12345v1") -> str:
    return f"""
<item>
  <title>Geometry-Aware   Navigation</title>
  <link>https://arxiv.org/abs/{source_id}</link>
  <description><![CDATA[Announce Type: {announce_type}<br/>
  Abstract: We preserve $x^2$.]]></description>
  <dc:creator>A. Researcher</dc:creator>
  <category>cs.RO</category>
</item>
"""


def test_rss_parser_maps_new_cross_and_replacement() -> None:
    entries = parse_arxiv_rss(
        _rss(
            _item(announce_type="new", source_id="2608.12345v1")
            + _item(announce_type="cross", source_id="2608.12346v1")
            + _item(announce_type="replace", source_id="2608.12347v2")
        ),
        source_category="cs.AI",
    )

    assert [entry.announce_type for entry in entries] == [
        AnnounceType.NEW,
        AnnounceType.CROSS,
        AnnounceType.REPLACE,
    ]
    assert entries[0].categories == ["cs.AI", "cs.RO"]
    assert entries[0].abstract == "We preserve $x^2$."


def test_client_fetches_all_categories_with_injected_transport() -> None:
    responses = {
        "https://fixture/cs.AI": _rss(_item()),
        "https://fixture/cs.RO": _rss(),
    }
    transport = FakeTransport(responses)
    client = ArxivClient(transport, endpoint_template="https://fixture/{category}")

    entries = client.fetch_new(["cs.AI", "cs.RO"], timeout_seconds=12)

    assert len(entries) == 1
    assert transport.calls == [
        ("https://fixture/cs.AI", 12),
        ("https://fixture/cs.RO", 12),
    ]


def test_complete_fetch_failure_is_not_a_valid_empty_result() -> None:
    transport = FakeTransport(
        {
            "https://fixture/cs.AI": _rss(),
            "https://fixture/cs.RO": ArxivSourceError("offline"),
        }
    )
    client = ArxivClient(transport, endpoint_template="https://fixture/{category}")

    with pytest.raises(ArxivSourceError, match="offline"):
        client.fetch_new(["cs.AI", "cs.RO"], timeout_seconds=10)


def test_parse_failure_is_mapped_to_source_failure() -> None:
    transport = FakeTransport({"https://fixture/cs.AI": b"not xml"})
    client = ArxivClient(transport, endpoint_template="https://fixture/{category}")

    with pytest.raises(ArxivSourceError, match=r"response for cs\.AI was invalid"):
        client.fetch_new(["cs.AI"], timeout_seconds=10)


def test_successful_empty_feed_returns_empty_list() -> None:
    transport = FakeTransport({"https://fixture/cs.AI": _rss()})
    client = ArxivClient(transport, endpoint_template="https://fixture/{category}")

    assert client.fetch_new(["cs.AI"], timeout_seconds=10) == []


def test_raw_snapshot_is_written_only_below_supplied_cache(tmp_path: Path) -> None:
    entries = parse_arxiv_rss(_rss(_item()), source_category="cs.AI")

    path = save_raw_snapshot(tmp_path / "cache", "run-1", entries)

    assert path == tmp_path / "cache/raw/run-1.json"
    assert json.loads(path.read_text(encoding="utf-8"))["entry_count"] == 1
    with pytest.raises(ValueError, match="unsafe"):
        save_raw_snapshot(tmp_path / "cache", "../outside", entries)


def test_atom_metadata_refetch_parses_one_canonical_candidate() -> None:
    payload = b"""<?xml version='1.0' encoding='UTF-8'?>
    <feed xmlns='http://www.w3.org/2005/Atom'>
      <entry>
        <id>http://arxiv.org/abs/2608.12345v2</id>
        <title>  Spatial   model  </title>
        <summary>A useful\nabstract.</summary>
        <author><name>Author One</name></author>
        <category term='cs.AI'/><category term='cs.CV'/>
      </entry>
    </feed>"""

    paper = parse_arxiv_atom_candidate(payload, expected_id="2608.12345")

    assert paper is not None
    assert paper.arxiv_id == "2608.12345"
    assert paper.source_arxiv_id == "2608.12345v2"
    assert paper.title == "Spatial model"
    assert paper.abstract == "A useful abstract."
    assert paper.categories == ["cs.AI", "cs.CV"]
