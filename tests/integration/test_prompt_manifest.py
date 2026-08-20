from __future__ import annotations

from pathlib import Path

from paperflow.cli.prompt_preview import main
from paperflow.config import load_config_bundle
from paperflow.llm.structured import PromptPaper, PromptRenderer
from paperflow.taxonomy import load_taxonomy


def test_all_checked_in_templates_render_with_typed_context() -> None:
    root = Path(__file__).parents[2]
    bundle = load_config_bundle(root)
    taxonomy = load_taxonomy(root / "configs/topics.yaml")
    renderer = PromptRenderer(root / "configs/prompts", bundle.prompts)
    paper = PromptPaper(
        arxiv_id="2608.12345",
        title="Fixture",
        abstract="A deterministic fixture abstract.",
        categories=["cs.AI"],
    )

    renderer.validate_templates()
    assert renderer.render_taxonomy(taxonomy)
    assert renderer.render_filter(taxonomy, [paper]).user
    assert renderer.render_summary(paper).user


def test_every_preview_command_succeeds() -> None:
    root = Path(__file__).parents[2]

    assert main(["filter", "--root", str(root)]) == 0
    assert main(["summary", "--root", str(root)]) == 0
    assert main(["taxonomy", "--root", str(root)]) == 0
