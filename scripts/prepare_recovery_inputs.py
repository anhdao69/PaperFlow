"""One-off metadata reconstruction for reviewed October 2026 arXiv ID lists."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from paperflow.arxiv_client import parse_arxiv_atom_candidate
from paperflow.models import RawArxivEntry
from paperflow.normalize import normalize_and_deduplicate, normalize_arxiv_id
from paperflow.recovery import load_recovery_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    root = args.directory
    manifest = json.loads((root / "input_manifest.json").read_text())
    categories = manifest["categories"]
    namespace = "{http://www.w3.org/2005/Atom}"
    metadata = {}
    ids = sorted(
        {
            row[1]
            for day, rows in manifest["rows_by_day"].items()
            if day != "2026-10-08"
            for row in rows
        }
    )
    evidence = root / "atom"
    evidence.mkdir(exist_ok=True)
    for offset in range(0, len(ids), 100):
        batch = ids[offset : offset + 100]
        path = evidence / f"{offset:04d}.xml"
        if not path.exists():
            url = (
                "https://export.arxiv.org/api/query?id_list="
                + ",".join(batch)
                + "&max_results=100"
            )
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "PaperFlow/0.1 (+https://github.com/anhdao69/PaperFlow)"
                },
            )
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(request, timeout=90) as response:
                        payload = response.read()
                    ET.fromstring(payload)
                    path.write_bytes(payload)
                    break
                except urllib.error.HTTPError as error:
                    print(
                        f"arXiv HTTP {error.code}; batch {offset}; "
                        f"attempt {attempt + 1}",
                        flush=True,
                    )
                    if attempt == 2 or error.code not in {429, 500, 502, 503, 504}:
                        raise
                    retry = error.headers.get("Retry-After", "30")
                    time.sleep(max(30, int(retry)) if retry.isdigit() else 60)
                except (TimeoutError, urllib.error.URLError):
                    print(f"arXiv network failure; batch {offset}", flush=True)
                    if attempt == 2:
                        raise
                    time.sleep(30)
            time.sleep(3.1)
        feed = ET.fromstring(path.read_bytes())
        found = set()
        for entry in feed.findall(namespace + "entry"):
            source_id = entry.findtext(namespace + "id").rsplit("/", 1)[-1]
            canonical = normalize_arxiv_id(source_id)
            if canonical not in batch or canonical in found:
                raise ValueError("unexpected or duplicate metadata ID")
            wrapper = ET.Element(namespace + "feed")
            wrapper.append(entry)
            candidate = parse_arxiv_atom_candidate(
                ET.tostring(wrapper), expected_id=canonical
            )
            if candidate is None:
                raise ValueError("missing metadata")
            metadata[canonical] = candidate
            found.add(canonical)
        if found != set(batch):
            raise ValueError("incomplete arXiv metadata batch")
        print(f"Metadata verified: {len(metadata)}/{len(ids)}", flush=True)
    for day, rows in manifest["rows_by_day"].items():
        if day == "2026-10-08":
            continue
        entries = []
        for category, paper_id, announce_type in rows:
            paper = metadata[paper_id]
            entries.append(
                RawArxivEntry(
                    source_arxiv_id=paper.source_arxiv_id,
                    title=paper.title,
                    abstract=paper.abstract,
                    authors=paper.authors,
                    categories=list(dict.fromkeys([category, *paper.categories])),
                    announce_type=announce_type,
                )
            )
        snapshot = {
            "schema_version": 1,
            "publication_date": day,
            "announcement_date": (
                date.fromisoformat(day) + timedelta(days=1)
            ).isoformat(),
            "categories": categories,
            "captured_at": datetime.now(UTC).isoformat(),
            "provenance": (
                "dated arXiv recent lists; current Atom metadata fetched during "
                "recovery, not original failed-run bytes"
            ),
            "candidate_count": len(normalize_and_deduplicate(entries)),
            "entries": [entry.model_dump(mode="json") for entry in entries],
        }
        target = root / f"{day}.json"
        target.write_text(
            json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
        load_recovery_snapshot(
            target, publication_date=date.fromisoformat(day), categories=categories
        )
        print(f"Verified {day}: {snapshot['candidate_count']} candidates", flush=True)


if __name__ == "__main__":
    main()
