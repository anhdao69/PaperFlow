from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel

from paperflow.config import load_config_bundle, load_openrouter_credentials
from paperflow.llm.openrouter import OpenRouterClient, UrllibJsonTransport


class SmokeOutput(BaseModel):
    ok: Literal[True]


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("PAPERFLOW_LIVE_OPENROUTER") != "1",
    reason="set PAPERFLOW_LIVE_OPENROUTER=1 for the explicit paid smoke test",
)
@pytest.mark.parametrize(
    "model_alias",
    [
        "deepseek_v4_flash",
        "glm_4_7_flashx",
        "gpt_5_6_luna",
        "mistral_small_4",
    ],
)
def test_configured_model_structured_output_reachability(model_alias: str) -> None:
    root = Path(__file__).parents[2]
    bundle = load_config_bundle(root)
    credentials = load_openrouter_credentials(required=True)
    assert credentials is not None
    client = OpenRouterClient(
        model_config=bundle.models,
        api_key=credentials.api_key,
        transport=UrllibJsonTransport(),
        transient_retry_count=0,
        timeout_seconds=90,
        http_referer=os.environ.get("PAPERFLOW_HTTP_REFERER"),
        app_title=os.environ.get("PAPERFLOW_APP_TITLE", "PaperFlow"),
    )

    result = client.structured_chat(
        task_name="live_smoke",
        messages=[
            {
                "role": "user",
                "content": "Return a JSON object with ok set to true.",
            }
        ],
        schema=SmokeOutput,
        model_chain=[model_alias],
        request_metadata={"purpose": "paperflow-live-smoke"},
    )

    assert result.parsed.ok is True
    assert result.actual_model
