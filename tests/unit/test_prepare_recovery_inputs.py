from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("complete", [True, False])
def test_preparation_requires_exact_metadata_coverage(tmp_path, monkeypatch, complete):
    manifest = {
        "categories": ["cs.AI"],
        "rows_by_day": {
            "2026-10-06": [["cs.AI", "2610.01234", "new"]],
            "2026-10-07": [["cs.AI", "2502.01234", "cross"]],
        },
    }
    (tmp_path / "input_manifest.json").write_text(json.dumps(manifest))
    atom = tmp_path / "atom"
    atom.mkdir()
    ids = ["2502.01234v2", "2610.01234v1"] if complete else ["2610.01234v1"]
    entries = "".join(
        f"<entry><id>https://arxiv.org/abs/{pid}</id><title>Navigation</title>"
        "<summary>Spatial memory.</summary><author><name>A. Researcher</name>"
        "</author><category term='cs.AI'/></entry>"
        for pid in ids
    )
    (atom / "0000.xml").write_text(
        "<feed xmlns='http://www.w3.org/2005/Atom'>" + entries + "</feed>"
    )
    monkeypatch.setattr(sys, "argv", ["prepare", "--directory", str(tmp_path)])
    script = ROOT / "scripts/prepare_recovery_inputs.py"
    if not complete:
        with pytest.raises(ValueError, match="incomplete arXiv metadata batch"):
            runpy.run_path(str(script), run_name="__main__")
        assert not (tmp_path / "2026-10-06.json").exists()
        return
    runpy.run_path(str(script), run_name="__main__")
    result = json.loads((tmp_path / "2026-10-07.json").read_text())
    assert result["candidate_count"] == 1
    assert result["entries"][0]["source_arxiv_id"] == "2502.01234v2"
    assert result["entries"][0]["announce_type"] == "cross"
