from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from paperflow.config import PromptManifest, load_config_bundle
from paperflow.llm.structured import PromptPaper, PromptRenderer
from paperflow.taxonomy import TaxonomyConfig, load_taxonomy

ROOT = Path(__file__).parents[2]


def _renderer(manifest: PromptManifest | None = None) -> PromptRenderer:
    configured = manifest or load_config_bundle(ROOT).prompts
    return PromptRenderer(ROOT / "configs/prompts", configured)


def _paper() -> PromptPaper:
    return PromptPaper(
        arxiv_id="2608.12345",
        title="A Test Paper",
        abstract="We present a spatial world model for robotic navigation.",
        categories=["cs.RO", "cs.AI"],
    )


def test_identical_inputs_render_byte_identically() -> None:
    renderer = _renderer()
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")

    first = renderer.render_filter(taxonomy, [_paper()])
    second = renderer.render_filter(taxonomy, [_paper()])

    assert first == second
    assert first.system_hash == second.system_hash


def test_taxonomy_render_preserves_yaml_order() -> None:
    rendered = _renderer().render_taxonomy(
        load_taxonomy(ROOT / "configs/topics.yaml")
    )

    assert rendered.index("LARGE TOPIC: Embodied AI") < rendered.index(
        "LARGE TOPIC: World Models"
    )
    assert rendered.index("SUBTOPIC: Latent Action Models") < rendered.index(
        "SUBTOPIC: Video World Models"
    )


def test_taxonomy_change_updates_filter_hash_but_not_summary_hash() -> None:
    renderer = _renderer()
    original = load_taxonomy(ROOT / "configs/topics.yaml")
    changed_data = deepcopy(original.model_dump(mode="python"))
    changed_data["topics"][0]["description"] += " Expanded scope."
    changed = TaxonomyConfig.model_validate(changed_data)
    paper = _paper()

    assert renderer.render_filter(original, [paper]).system_hash != (
        renderer.render_filter(changed, [paper]).system_hash
    )
    assert renderer.render_summary(paper).system_hash == (
        renderer.render_summary(paper).system_hash
    )


def test_filter_prompt_contains_locked_decision_constraints() -> None:
    rendered = _renderer().render_filter(
        load_taxonomy(ROOT / "configs/topics.yaml"), [_paper()]
    )

    assert "Use ONLY title, abstract, and arXiv categories" in rendered.system
    assert "at least one valid large-topic assignment" in rendered.system
    assert "set assignments=[]" in rendered.system
    assert "Do not summarize" in rendered.system


def test_filter_user_prompt_exposes_only_approved_paper_fields() -> None:
    rendered = _renderer().render_filter(
        load_taxonomy(ROOT / "configs/topics.yaml"), [_paper()]
    )

    assert rendered.user.splitlines() == [
        "ARXIV_ID: 2608.12345",
        "TITLE: A Test Paper",
        "CATEGORIES: cs.RO, cs.AI",
        "ABSTRACT: We present a spatial world model for robotic navigation.",
    ]
    for excluded in ("AUTHOR", "INSTITUTION", "CITATION", "PRESTIGE"):
        assert excluded not in rendered.user.upper()


def test_summary_prompt_uses_only_title_and_abstract() -> None:
    rendered = _renderer().render_summary(_paper())

    assert "3-5 concise bullets" in rendered.system
    assert rendered.user.splitlines() == [
        "TITLE: A Test Paper",
        "ABSTRACT: We present a spatial world model for robotic navigation.",
    ]
    assert "CATEGORIES" not in rendered.user
    assert "2608.12345" not in rendered.user


def test_filter_requires_nonempty_batch() -> None:
    with pytest.raises(ValueError, match="at least one paper"):
        _renderer().render_filter(load_taxonomy(ROOT / "configs/topics.yaml"), [])


def test_missing_configured_template_is_rejected_before_render() -> None:
    data = load_config_bundle(ROOT).prompts.model_dump(mode="python")
    data["filter"]["system"] = "missing.j2"
    renderer = _renderer(PromptManifest.model_validate(data))

    with pytest.raises(ValueError, match="does not exist"):
        renderer.validate_templates()
