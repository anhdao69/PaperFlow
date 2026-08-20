from __future__ import annotations

from pathlib import Path

from paperflow.cli.validate_taxonomy import main
from paperflow.taxonomy import load_taxonomy, validate_assignments


def test_checked_in_taxonomy_validates_empty_selected_store() -> None:
    root = Path(__file__).parents[2]
    taxonomy = load_taxonomy(root / "configs/topics.yaml")

    validate_assignments(taxonomy, [])
    assert main([str(root / "configs/topics.yaml")]) == 0


def test_cli_rejects_every_invalid_fixture() -> None:
    root = Path(__file__).parents[2]
    fixtures = root / "tests/fixtures/taxonomy"

    for fixture in fixtures.glob("invalid_*.yaml"):
        assert main([str(fixture)]) == 1
