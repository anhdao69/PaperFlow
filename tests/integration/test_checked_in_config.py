from __future__ import annotations

from pathlib import Path

from paperflow.config import load_config_bundle


def test_checked_in_values_are_obtained_from_configuration() -> None:
    root = Path(__file__).parents[2]
    bundle = load_config_bundle(root)

    assert bundle.runtime.timezone == "America/New_York"
    assert bundle.runtime.source.provider == "arxiv"
    assert bundle.runtime.publishing.readme_latest_limit == 80
    assert bundle.models.tasks["summary"].primary == "gpt_5_6_luna"
    assert bundle.models.models["gpt_5_6_luna"].model_id == "openai/gpt-5.6-luna"
    assert bundle.prompts.summary.user == "summary_user.j2"
