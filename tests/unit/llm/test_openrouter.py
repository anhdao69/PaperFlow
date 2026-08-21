from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel, SecretStr

from paperflow.config import load_config_bundle
from paperflow.llm.openrouter import (
    HttpResponse,
    OpenRouterClient,
    OpenRouterHTTPError,
    OpenRouterSemanticError,
    OpenRouterTransportError,
    redact_sensitive,
)
from paperflow.models import SummaryContent

ROOT = Path(__file__).parents[3]


class Answer(BaseModel):
    answer: str


class FakeTransport:
    def __init__(self, responses: list[HttpResponse | Exception]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout: float,
    ) -> HttpResponse:
        self.calls.append(
            {"url": url, "headers": headers, "payload": payload, "timeout": timeout}
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _response(path: str = "success.json", *, status: int = 200) -> HttpResponse:
    return HttpResponse(
        status=status,
        body=(ROOT / f"tests/fixtures/openrouter/{path}").read_bytes(),
        headers={},
    )


def _client(
    transport: FakeTransport,
    *,
    retries: int = 0,
    sleeps: list[float] | None = None,
    jitter: float = 0,
) -> OpenRouterClient:
    recorded_sleeps = sleeps if sleeps is not None else []
    ticks = iter([10.0, 10.125])
    return OpenRouterClient(
        model_config=load_config_bundle(ROOT).models,
        api_key=SecretStr("unit-test-placeholder"),
        transport=transport,
        transient_retry_count=retries,
        timeout_seconds=9,
        http_referer="https://example.test/PaperFlow/",
        sleep=recorded_sleeps.append,
        jitter=lambda: jitter,
        monotonic=lambda: next(ticks),
    )


def _call(client: OpenRouterClient, *, chain: list[str] | None = None):
    return client.structured_chat(
        task_name="test",
        messages=[{"role": "user", "content": "Return ok."}],
        schema=Answer,
        model_chain=chain or ["gpt_5_6_luna"],
        request_metadata={"run_id": "fixture-run"},
    )


def test_success_decodes_schema_and_usage_provenance() -> None:
    transport = FakeTransport([_response()])

    result = _call(_client(transport))

    assert result.parsed == Answer(answer="ok")
    assert result.requested_model == "openai/gpt-5.6-luna"
    assert result.actual_model == "openai/gpt-5.6-luna"
    assert result.provider == "FixtureProvider"
    assert result.input_tokens == 12
    assert result.output_tokens == 5
    assert result.cached_input_tokens == 3
    assert result.cost_usd == 0.000012
    assert result.latency_ms == 125
    assert result.request_id == "gen-fixture-1"
    assert result.attempt == 1


def test_request_uses_ordered_yaml_model_fallbacks_and_strict_schema() -> None:
    transport = FakeTransport([_response()])
    chain = ["deepseek_v4_flash", "glm_4_7_flashx", "gpt_5_6_luna"]

    _call(_client(transport), chain=chain)

    payload = transport.calls[0]["payload"]
    assert payload["models"] == [
        "deepseek/deepseek-v4-flash-0731",
        "z-ai/glm-4.7-flash",
        "openai/gpt-5.6-luna",
    ]
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["provider"]["require_parameters"] is True
    assert payload["usage"] == {"include": True}


def test_strict_schema_requires_nullable_fields_without_defaults() -> None:
    body = json.loads(_response().body)
    body["choices"][0]["message"]["content"] = json.dumps(
        {
            "tldr": "A concise summary.",
            "bullets": ["First.", "Second.", "Third."],
            "problem": None,
            "method": None,
            "contribution": None,
        }
    )
    transport = FakeTransport([HttpResponse(200, json.dumps(body).encode(), {})])

    _client(transport).structured_chat(
        task_name="summary",
        messages=[{"role": "user", "content": "Summarize."}],
        schema=SummaryContent,
        model_chain=["gpt_5_6_luna"],
        request_metadata={"run_id": "fixture-run"},
    )

    schema = transport.calls[0]["payload"]["response_format"]["json_schema"]["schema"]
    assert schema["required"] == [
        "tldr",
        "bullets",
        "problem",
        "method",
        "contribution",
    ]
    assert schema["additionalProperties"] is False
    for field in ("problem", "method", "contribution"):
        assert "default" not in schema["properties"][field]


def test_requested_and_actual_model_can_differ_after_fallback() -> None:
    body = json.loads(_response().body)
    body["model"] = "z-ai/glm-4.7-flash"
    transport = FakeTransport(
        [HttpResponse(200, json.dumps(body).encode(), headers={})]
    )

    result = _call(
        _client(transport), chain=["deepseek_v4_flash", "glm_4_7_flashx"]
    )

    assert result.requested_model == "deepseek/deepseek-v4-flash-0731"
    assert result.actual_model == "z-ai/glm-4.7-flash"


def test_unsupported_optional_temperature_is_omitted_by_configuration() -> None:
    transport = FakeTransport([_response()])

    _call(_client(transport), chain=["gpt_5_6_luna"])

    assert "temperature" not in transport.calls[0]["payload"]


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_transient_http_status_retries_then_succeeds(status: int) -> None:
    transient = HttpResponse(
        status,
        json.dumps(
            {"error": {"code": status, "metadata": {"error_type": "temporary"}}}
        ).encode(),
        {},
    )
    sleeps: list[float] = []
    transport = FakeTransport([transient, _response()])

    result = _call(_client(transport, retries=1, sleeps=sleeps, jitter=0.5))

    assert result.attempt == 2
    assert sleeps == [2.5]
    assert len(transport.calls) == 2


def test_transport_timeout_retries_then_succeeds() -> None:
    sleeps: list[float] = []
    transport = FakeTransport(
        [OpenRouterTransportError("timeout"), _response()]
    )

    result = _call(_client(transport, retries=1, sleeps=sleeps))

    assert result.attempt == 2
    assert sleeps == [2]


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 422])
def test_deterministic_http_errors_do_not_retry(status: int) -> None:
    response = HttpResponse(
        status,
        json.dumps({"error": {"code": status, "message": "sensitive detail"}}).encode(),
        {},
    )
    transport = FakeTransport([response, _response()])

    with pytest.raises(OpenRouterHTTPError) as captured:
        _call(_client(transport, retries=2))

    assert captured.value.status == status
    assert len(transport.calls) == 1
    assert "sensitive detail" not in str(captured.value)


def test_exhausted_transient_attempts_raise_transport_error() -> None:
    transport = FakeTransport(
        [HttpResponse(503, b'{"error":{"code":503}}', {}) for _ in range(2)]
    )

    with pytest.raises(OpenRouterTransportError):
        _call(_client(transport, retries=1))

    assert len(transport.calls) == 2


def test_missing_optional_usage_is_valid() -> None:
    body = json.loads(_response().body)
    body.pop("usage")
    result = _call(
        _client(FakeTransport([HttpResponse(200, json.dumps(body).encode(), {})]))
    )

    assert result.input_tokens is None
    assert result.output_tokens is None
    assert result.cost_usd is None


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        (ROOT / "tests/fixtures/openrouter/malformed_envelope.json").read_bytes(),
        b'{"choices":[{"message":{"content":"not json"}}]}',
        b'{"choices":[{"message":{"content":"{\\"wrong\\":1}"}}]}',
        b'{"error":null}',
        b'{"choices":[{"message":{"content":"{\\"answer\\":\\"ok\\"}"}}],"usage":[]}',
    ],
)
def test_malformed_envelope_or_schema_is_semantic_error(body: bytes) -> None:
    with pytest.raises(OpenRouterSemanticError):
        _call(_client(FakeTransport([HttpResponse(200, body, {})])))


def test_headers_and_logs_can_be_redacted() -> None:
    transport = FakeTransport([_response()])
    _call(_client(transport))
    captured = transport.calls[0]

    redacted = redact_sensitive(
        captured, secret_values=["unit-test-placeholder"]
    )
    serialized = json.dumps(redacted)
    assert "unit-test-placeholder" not in serialized
    assert "Bearer" not in serialized
    assert redacted["headers"]["Authorization"] == "[REDACTED]"


@pytest.mark.parametrize("jitter", [-0.1, 1.1])
def test_retry_jitter_must_stay_in_bounds(jitter: float) -> None:
    transport = FakeTransport([OpenRouterTransportError("timeout"), _response()])

    with pytest.raises(ValueError, match="between 0 and 1"):
        _call(_client(transport, retries=1, jitter=jitter))


def test_yaml_only_chain_change_alters_request_routing() -> None:
    transport = FakeTransport([_response()])
    _call(_client(transport), chain=["mistral_small_4", "deepseek_v4_flash"])

    assert transport.calls[0]["payload"]["models"] == [
        "mistralai/mistral-small-2603",
        "deepseek/deepseek-v4-flash-0731",
    ]
