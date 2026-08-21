"""PaperFlow production pipeline command entry point."""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path

from paperflow.arxiv_client import (
    ArxivClient,
    ArxivMetadataRefetcher,
    UrllibTransport,
)
from paperflow.config import load_config_bundle, load_openrouter_credentials
from paperflow.llm.openrouter import OpenRouterClient, UrllibJsonTransport
from paperflow.observability import create_run_id, structured_event
from paperflow.pipeline import PipelineDependencies, run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--manual", action="store_true")
    parser.add_argument("--paper", action="append", default=[])
    parser.add_argument("--maintenance-only", action="store_true")
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    bundle = load_config_bundle(root)
    transport = UrllibTransport()

    def llm_client():
        credentials = load_openrouter_credentials(required=True)
        assert credentials is not None
        return OpenRouterClient(
            model_config=bundle.models,
            api_key=credentials.api_key,
            transport=UrllibJsonTransport(),
            transient_retry_count=max(
                bundle.runtime.filtering.transient_retry_count,
                bundle.runtime.summaries.transient_retry_count,
            ),
            timeout_seconds=60,
            http_referer=os.environ.get("PAPERFLOW_HTTP_REFERER"),
            app_title=os.environ.get("PAPERFLOW_APP_TITLE", "PaperFlow"),
        )

    dependencies = PipelineDependencies(
        source_client=ArxivClient(transport),
        refetcher=ArxivMetadataRefetcher(
            transport,
            timeout_seconds=bundle.runtime.source.request_timeout_seconds,
        ),
        llm_client_factory=llm_client,
        now=lambda: datetime.now(UTC),
        run_id_factory=create_run_id,
    )
    try:
        run_pipeline(
            root,
            dependencies,
            manual=arguments.manual,
            manual_override_ids=arguments.paper,
            maintenance_only=arguments.maintenance_only,
        )
    except Exception as error:
        structured_event("run_failed", error_type=type(error).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
