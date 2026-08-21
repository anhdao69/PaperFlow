"""Extract or rebuild published figures for selected PaperFlow papers."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from paperflow.cli.rebuild_outputs import main as rebuild_outputs_main
from paperflow.config import load_config_bundle
from paperflow.figures.adapters.pdffigures2 import PDFFigures2Adapter
from paperflow.figures.extract import (
    FigureProductionService,
    FigureProductionSettings,
    resolve_executable_command,
)
from paperflow.models import FigureStatus
from paperflow.paper_store import load_selected_store, save_selected_store
from paperflow.taxonomy import load_taxonomy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--paper", action="append", default=[])
    parser.add_argument("--jar", type=Path)
    parser.add_argument(
        "--java", default=os.environ.get("PAPERFLOW_JAVA_COMMAND", "java")
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    jar = arguments.jar
    if jar is None:
        configured = os.environ.get("PAPERFLOW_PDFFIGURES2_JAR")
        jar = Path(configured) if configured else None
    if jar is None or not jar.is_file():
        parser.error("a valid PDFFigures2 jar is required via --jar or environment")
    bundle = load_config_bundle(root)
    taxonomy = load_taxonomy(root / "configs/topics.yaml")
    selected = load_selected_store(root / "data/papers.json", taxonomy)
    config = bundle.runtime.figures
    java_command = resolve_executable_command(
        arguments.java, working_directory=Path.cwd()
    )
    service = FigureProductionService(
        adapter=PDFFigures2Adapter(
            (java_command, "-jar", str(jar.resolve())),
            timeout_seconds=config.extraction_timeout_seconds,
        ),
        cache_root=root / "cache",
        settings=FigureProductionSettings(
            concurrency=config.concurrency,
            download_timeout_seconds=config.download_timeout_seconds,
            max_long_edge=config.max_long_edge,
            webp_quality=config.webp_quality,
        ),
    )
    papers = service.process(
        selected.papers,
        publication_root=root,
        only_ids=arguments.paper,
        force=True,
    )
    save_selected_store(root / "data/papers.json", papers, taxonomy)
    rebuild_outputs_main(["--root", str(root)])
    ready = sum(
        paper.figure_status == FigureStatus.READY for paper in papers.values()
    )
    failed = sum(
        paper.figure_status == FigureStatus.FAILED for paper in papers.values()
    )
    print(f"Figure rebuild complete: {ready} ready, {failed} failed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
