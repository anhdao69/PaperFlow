"""Preview the exact deterministic prompts PaperFlow will send."""

from __future__ import annotations

import argparse
from pathlib import Path

from paperflow.config import load_config_bundle
from paperflow.llm.structured import PromptPaper, PromptRenderer
from paperflow.taxonomy import load_taxonomy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["filter", "summary", "taxonomy"])
    parser.add_argument("--root", type=Path, default=Path("."))
    return parser


def _fixture_paper() -> PromptPaper:
    return PromptPaper(
        arxiv_id="2608.12345",
        title="Geometry-Aware Navigation with Persistent Spatial Memory",
        categories=["cs.RO", "cs.CV"],
        abstract=(
            "We introduce a geometry-aware memory for instruction-guided robot "
            "navigation in previously unseen environments."
        ),
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bundle = load_config_bundle(args.root)
    taxonomy = load_taxonomy(args.root / "configs/topics.yaml")
    renderer = PromptRenderer(args.root / "configs/prompts", bundle.prompts)
    renderer.validate_templates()
    paper = _fixture_paper()

    if args.kind == "taxonomy":
        print(renderer.render_taxonomy(taxonomy), end="")
        return 0

    rendered = (
        renderer.render_filter(taxonomy, [paper])
        if args.kind == "filter"
        else renderer.render_summary(paper)
    )
    print(f"VERSION: {rendered.version}")
    print(f"SYSTEM_HASH: {rendered.system_hash}")
    print("\n--- SYSTEM ---")
    print(rendered.system, end="")
    print("\n--- USER ---")
    print(rendered.user, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
