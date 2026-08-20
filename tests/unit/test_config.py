from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from paperflow.config import (
    ModelConfig,
    RuntimeConfig,
    load_config_bundle,
    load_openrouter_credentials,
    normalized_config_hash,
)

ROOT = Path(__file__).parents[2]


def _runtime_data() -> dict[str, object]:
    return yaml.safe_load((ROOT / "configs/runtime.yaml").read_text(encoding="utf-8"))


def _model_data() -> dict[str, object]:
    return yaml.safe_load((ROOT / "configs/models.yaml").read_text(encoding="utf-8"))


def test_checked_in_configuration_loads_as_one_bundle() -> None:
    bundle = load_config_bundle(ROOT)

    assert bundle.runtime.source.categories == [
        "cs.AI",
        "cs.CV",
        "cs.LG",
        "cs.RO",
        "cs.CL",
    ]
    assert bundle.runtime.schedule.run_at_local.hour == 21
    assert str(bundle.models.model_chain("filter")[0].model_id) == (
        "deepseek/deepseek-v4-flash-0731"
    )
    assert bundle.prompts.filter.system == "filter_system.j2"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("timezone",), "Mars/Olympus_Mons"),
        (("schedule", "run_at_local"), "25:00"),
        (("source", "request_timeout_seconds"), 0),
        (("filtering", "batch_size"), 0),
        (("filtering", "concurrency"), 0),
        (("summaries", "failed_auto_retry_max_attempts"), 0),
        (("publishing", "base_url"), "http://example.com/PaperFlow/"),
        (("publishing", "base_url"), "https://example.com/PaperFlow"),
    ],
)
def test_invalid_runtime_values_are_rejected(
    path: tuple[str, ...], value: object
) -> None:
    data = deepcopy(_runtime_data())
    target = data
    for component in path[:-1]:
        target = target[component]  # type: ignore[index,assignment]
    target[path[-1]] = value

    with pytest.raises(ValidationError):
        RuntimeConfig.model_validate(data)


def test_unknown_runtime_key_and_keep_cap_are_rejected() -> None:
    data = _runtime_data()
    data["max_keep_per_day"] = 37

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RuntimeConfig.model_validate(data)


def test_unknown_model_alias_is_rejected() -> None:
    data = _model_data()
    data["tasks"]["filter"]["fallbacks"].append("missing_model")

    with pytest.raises(ValidationError, match="unknown model aliases"):
        ModelConfig.model_validate(data)


def test_duplicate_or_empty_model_configuration_is_rejected() -> None:
    duplicate = _model_data()
    duplicate["tasks"]["filter"]["fallbacks"].append("deepseek_v4_flash")
    empty = _model_data()
    empty["models"] = {}

    with pytest.raises(ValidationError, match="duplicate aliases"):
        ModelConfig.model_validate(duplicate)
    with pytest.raises(ValidationError):
        ModelConfig.model_validate(empty)


def test_config_hash_is_semantic_and_deterministic(tmp_path: Path) -> None:
    first = RuntimeConfig.model_validate(_runtime_data())
    formatted_path = tmp_path / "runtime.yaml"
    formatted_path.write_text(
        "# formatting changes do not affect the model hash\n"
        + yaml.safe_dump(_runtime_data(), sort_keys=False),
        encoding="utf-8",
    )
    second = RuntimeConfig.model_validate(yaml.safe_load(formatted_path.read_text()))
    changed_data = _runtime_data()
    changed_data["filtering"]["batch_size"] = 11
    changed = RuntimeConfig.model_validate(changed_data)

    assert normalized_config_hash(first) == normalized_config_hash(second)
    assert normalized_config_hash(first) != normalized_config_hash(changed)


def test_model_switch_is_configuration_only() -> None:
    data = _model_data()
    data["tasks"]["filter"]["primary"] = "mistral_small_4"
    data["tasks"]["filter"]["fallbacks"] = [
        "deepseek_v4_flash",
        "glm_4_7_flashx",
        "gpt_5_6_luna",
    ]
    model_config = ModelConfig.model_validate(data)

    assert model_config.model_chain("filter")[0].model_id == (
        "mistralai/mistral-small-2603"
    )


def test_secret_loader_uses_injected_environment_and_masks_representation() -> None:
    credentials = load_openrouter_credentials(
        {"OPENROUTER_API_KEY": "test-placeholder-value"}, required=True
    )

    assert credentials is not None
    assert "test-placeholder-value" not in repr(credentials)
    assert credentials.api_key.get_secret_value() == "test-placeholder-value"


def test_secret_is_optional_for_offline_commands_and_required_for_llm() -> None:
    assert load_openrouter_credentials({}, required=False) is None
    with pytest.raises(ValueError, match="required for network LLM commands"):
        load_openrouter_credentials({}, required=True)
