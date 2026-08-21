"""The single OpenRouter structured-chat abstraction used by PaperFlow."""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, SecretStr, ValidationError

from paperflow.config import ModelConfig
from paperflow.models import LLMCallResult

OutputT = TypeVar("OutputT", bound=BaseModel)
_TRANSIENT_STATUSES = {408, 429, 500, 502, 503, 504}


class OpenRouterError(RuntimeError):
    """Base error for the only supported LLM provider abstraction."""


class OpenRouterTransportError(OpenRouterError):
    """A retryable network/availability failure after bounded attempts."""


class OpenRouterHTTPError(OpenRouterError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"OpenRouter HTTP {status}: {message}")
        self.status = status


class OpenRouterSemanticError(OpenRouterError):
    """A successful HTTP response that cannot satisfy the typed contract."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    headers: Mapping[str, str]


class JsonTransport(Protocol):
    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout: float,
    ) -> HttpResponse: ...


class UrllibJsonTransport:
    """Small injectable standard-library transport."""

    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout: float,
    ) -> HttpResponse:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers=dict(headers),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return HttpResponse(
                    status=response.status,
                    body=response.read(),
                    headers=dict(response.headers.items()),
                )
        except urllib.error.HTTPError as error:
            return HttpResponse(
                status=error.code,
                body=error.read(),
                headers=dict(error.headers.items()) if error.headers else {},
            )
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            message = "OpenRouter network request failed"
            raise OpenRouterTransportError(message) from error


def _strict_json_schema(schema: type[BaseModel]) -> dict[str, object]:
    """Return a Pydantic schema compatible with strict structured outputs."""

    def normalize(node: Any) -> Any:
        if isinstance(node, dict):
            normalized = {
                key: normalize(value)
                for key, value in node.items()
                if key != "default"
            }
            properties = normalized.get("properties")
            if isinstance(properties, dict):
                normalized["required"] = list(properties)
                normalized.setdefault("additionalProperties", False)
            return normalized
        if isinstance(node, list):
            return [normalize(item) for item in node]
        return node

    normalized = normalize(schema.model_json_schema())
    if not isinstance(normalized, dict):
        raise TypeError("Pydantic model JSON schema must be an object")
    return normalized


class OpenRouterClient:
    def __init__(
        self,
        *,
        model_config: ModelConfig,
        api_key: SecretStr,
        transport: JsonTransport,
        transient_retry_count: int,
        timeout_seconds: float = 60,
        http_referer: str | None = None,
        app_title: str = "PaperFlow",
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if transient_retry_count < 0:
            raise ValueError("transient_retry_count cannot be negative")
        self._model_config = model_config
        self._api_key = api_key
        self._transport = transport
        self._transient_retry_count = transient_retry_count
        self._timeout_seconds = timeout_seconds
        self._http_referer = http_referer
        self._app_title = app_title
        self._sleep = sleep
        self._jitter = jitter
        self._monotonic = monotonic

    def structured_chat(
        self,
        *,
        task_name: str,
        messages: list[dict[str, str]],
        schema: type[OutputT],
        model_chain: list[str],
        request_metadata: dict[str, str],
    ) -> LLMCallResult[OutputT]:
        """Send one schema-constrained request with bounded transient retries."""
        if not messages:
            raise ValueError("OpenRouter messages cannot be empty")
        model_ids = self._resolve_model_chain(model_chain)
        primary_profile = self._profile_for(model_chain[0])
        payload = self._request_payload(
            task_name=task_name,
            messages=messages,
            schema=schema,
            model_ids=model_ids,
            request_metadata=request_metadata,
            temperature=primary_profile.temperature,
            max_output_tokens=primary_profile.max_output_tokens,
        )
        headers = self._headers()
        started = self._monotonic()
        last_transient: OpenRouterError | None = None

        for attempt in range(1, self._transient_retry_count + 2):
            if attempt > 1:
                self._sleep(self._retry_delay(attempt - 1))
            try:
                response = self._transport.post_json(
                    f"{str(self._model_config.base_url).rstrip('/')}/chat/completions",
                    headers=headers,
                    payload=payload,
                    timeout=self._timeout_seconds,
                )
            except OpenRouterTransportError as error:
                last_transient = error
                if attempt <= self._transient_retry_count:
                    continue
                raise

            if response.status in _TRANSIENT_STATUSES:
                message = _safe_error_message(response.body)
                last_transient = OpenRouterHTTPError(response.status, message)
                if attempt <= self._transient_retry_count:
                    continue
                raise OpenRouterTransportError(str(last_transient)) from last_transient
            if response.status < 200 or response.status >= 300:
                raise OpenRouterHTTPError(
                    response.status, _safe_error_message(response.body)
                )

            latency_ms = max(0, round((self._monotonic() - started) * 1000))
            return self._decode_response(
                response.body,
                schema=schema,
                requested_model=model_ids[0],
                attempt=attempt,
                latency_ms=latency_ms,
            )

        message = "OpenRouter retry loop exhausted"
        raise OpenRouterTransportError(message) from last_transient

    def _resolve_model_chain(self, chain: Sequence[str]) -> list[str]:
        if not chain:
            raise ValueError("OpenRouter model_chain cannot be empty")
        resolved = [self._profile_for(alias).model_id for alias in chain]
        if len(resolved) != len(set(resolved)):
            raise ValueError("OpenRouter model_chain resolves to duplicate model IDs")
        return resolved

    def _profile_for(self, alias: str):
        try:
            return self._model_config.models[alias]
        except KeyError as error:
            raise ValueError(f"unknown configured model alias: {alias}") from error

    def _request_payload(
        self,
        *,
        task_name: str,
        messages: list[dict[str, str]],
        schema: type[OutputT],
        model_ids: list[str],
        request_metadata: dict[str, str],
        temperature: float | None,
        max_output_tokens: int,
    ) -> dict[str, object]:
        metadata = _validate_metadata(request_metadata)
        provider: dict[str, object] = {
            "allow_fallbacks": self._model_config.routing.allow_provider_fallbacks,
            "require_parameters": self._model_config.routing.require_structured_outputs,
        }
        if self._model_config.routing.provider_sort != "default":
            provider["sort"] = self._model_config.routing.provider_sort
        payload: dict[str, object] = {
            "models": model_ids,
            "messages": messages,
            "max_tokens": max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": _strict_json_schema(schema),
                },
            },
            "provider": provider,
            "usage": {"include": True},
            "metadata": {"task_name": task_name, **metadata},
            "stream": False,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        return payload

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key.get_secret_value()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Title": self._app_title,
            "X-OpenRouter-Metadata": "enabled",
        }
        if self._http_referer:
            headers["HTTP-Referer"] = self._http_referer
        return headers

    def _retry_delay(self, retry_number: int) -> float:
        base = 2 if retry_number == 1 else min(30, 5 * 2 ** (retry_number - 2))
        jitter = self._jitter()
        if not 0 <= jitter <= 1:
            raise ValueError("retry jitter must be between 0 and 1")
        return base + jitter

    @staticmethod
    def _decode_response(
        body: bytes,
        *,
        schema: type[OutputT],
        requested_model: str,
        attempt: int,
        latency_ms: int,
    ) -> LLMCallResult[OutputT]:
        try:
            envelope = json.loads(body)
            if not isinstance(envelope, dict):
                raise TypeError("response envelope is not an object")
            if "error" in envelope:
                error = envelope["error"]
                error_code = (
                    error.get("code", "unknown")
                    if isinstance(error, Mapping)
                    else "unknown"
                )
                raise OpenRouterSemanticError(
                    f"OpenRouter returned an embedded error: {error_code}"
                )
            content = envelope["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("message content is not text")
            parsed = schema.model_validate_json(content)
        except OpenRouterSemanticError:
            raise
        except (
            json.JSONDecodeError,
            KeyError,
            IndexError,
            TypeError,
            ValidationError,
        ) as error:
            raise OpenRouterSemanticError(
                "OpenRouter response did not satisfy the structured schema"
            ) from error

        usage = envelope.get("usage")
        if usage is None:
            usage = {}
        if not isinstance(usage, Mapping):
            raise OpenRouterSemanticError("OpenRouter usage metadata is malformed")
        prompt_details = usage.get("prompt_tokens_details")
        if prompt_details is None:
            prompt_details = {}
        if not isinstance(prompt_details, Mapping):
            raise OpenRouterSemanticError(
                "OpenRouter cached usage metadata is malformed"
            )
        return LLMCallResult[OutputT](
            parsed=parsed,
            requested_model=requested_model,
            actual_model=envelope.get("model"),
            provider=envelope.get("provider"),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            cached_input_tokens=prompt_details.get("cached_tokens"),
            cost_usd=usage.get("cost"),
            latency_ms=latency_ms,
            request_id=envelope.get("id"),
            attempt=attempt,
        )


def _validate_metadata(metadata: Mapping[str, str]) -> dict[str, str]:
    if len(metadata) > 15:
        raise ValueError("request_metadata supports at most 15 caller fields")
    result: dict[str, str] = {}
    for key, value in metadata.items():
        if not key or len(key) > 64 or "[" in key or "]" in key:
            raise ValueError("invalid OpenRouter metadata key")
        if len(value) > 512:
            raise ValueError("OpenRouter metadata value is too long")
        result[key] = value
    return result


def _safe_error_message(body: bytes) -> str:
    try:
        payload = json.loads(body)
        error = payload.get("error", {})
        code = error.get("metadata", {}).get("error_type") or error.get("code")
        return f"provider error {code or 'unknown'}"
    except (json.JSONDecodeError, AttributeError):
        return "unparseable provider error"


def redact_sensitive(value: Any, *, secret_values: Sequence[str] = ()) -> Any:
    """Return a recursively redacted copy suitable for narrow diagnostics."""
    if isinstance(value, Mapping):
        return {
            key: (
                "[REDACTED]"
                if key.lower() in {"authorization", "api_key", "openrouter_api_key"}
                else redact_sensitive(item, secret_values=secret_values)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item, secret_values=secret_values) for item in value]
    if isinstance(value, str):
        redacted = value
        for secret in secret_values:
            if secret:
                redacted = redacted.replace(secret, "[REDACTED]")
        return redacted
    return value
