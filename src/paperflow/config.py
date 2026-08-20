"""Typed, strict configuration loading for PaperFlow."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from datetime import time
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

DayName = Literal[
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]
EnvironmentName = Literal["development", "test", "production"]
ModelAlias = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_]*$")]


class StrictConfigModel(BaseModel):
    """Base for configuration models that reject misspelled keys."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ScheduleConfig(StrictConfigModel):
    enabled: bool
    run_at_local: time
    run_days: list[DayName] = Field(min_length=1)
    same_day_catchup: bool

    @field_validator("run_at_local")
    @classmethod
    def require_minute_precision(cls, value: time) -> time:
        if value.second or value.microsecond or value.tzinfo is not None:
            raise ValueError("run_at_local must be a local HH:MM time")
        return value

    @field_validator("run_days")
    @classmethod
    def require_unique_days(cls, value: list[DayName]) -> list[DayName]:
        if len(value) != len(set(value)):
            raise ValueError("run_days must not contain duplicates")
        return value


class SourceConfig(StrictConfigModel):
    provider: Literal["arxiv"]
    mode: Literal["new_only"]
    categories: list[str] = Field(min_length=1)
    request_timeout_seconds: int = Field(ge=1, le=300)

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, value: list[str]) -> list[str]:
        category_pattern = re.compile(r"^[a-z-]+\.[A-Za-z-]+$")
        if any(not category_pattern.fullmatch(category) for category in value):
            raise ValueError("source categories must be valid arXiv category IDs")
        if len(value) != len(set(value)):
            raise ValueError("source categories must not contain duplicates")
        return value


class FilteringConfig(StrictConfigModel):
    batch_size: int = Field(ge=1, le=100)
    concurrency: int = Field(ge=1, le=20)
    semantic_retry_count: int = Field(ge=0, le=3)
    transient_retry_count: int = Field(ge=0, le=10)
    failed_auto_retry_max_attempts: int = Field(ge=1, le=20)
    failed_retry_cooldown_hours: float = Field(ge=0, le=24 * 30)


class SummaryConfig(StrictConfigModel):
    concurrency: int = Field(ge=1, le=20)
    semantic_retry_count: int = Field(ge=0, le=3)
    transient_retry_count: int = Field(ge=0, le=10)
    failed_auto_retry_max_attempts: int = Field(ge=1, le=20)


class PublishingConfig(StrictConfigModel):
    base_url: AnyHttpUrl
    readme_latest_limit: int = Field(ge=1, le=1000)
    generate_daily_archive: bool
    generate_feed_index: bool
    generate_daily_json_feeds: bool
    generate_topic_markdown: bool
    generate_topic_json: bool
    generate_website: bool

    @field_validator("base_url")
    @classmethod
    def validate_publication_root(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme != "https":
            raise ValueError("publishing.base_url must use HTTPS")
        if not value.path.endswith("/"):
            raise ValueError("publishing.base_url must end in /")
        if value.query is not None or value.fragment is not None:
            raise ValueError("publishing.base_url cannot contain query or fragment")
        return value


class FigureConfig(StrictConfigModel):
    enabled: bool
    iphone_placeholder: bool


class ObservabilityConfig(StrictConfigModel):
    persist_run_stats: bool
    log_llm_usage: bool
    log_model_used: bool
    log_provider_used: bool


class RuntimeConfig(StrictConfigModel):
    schema_version: Literal[1]
    environment: EnvironmentName
    timezone: str
    schedule: ScheduleConfig
    source: SourceConfig
    filtering: FilteringConfig
    summaries: SummaryConfig
    publishing: PublishingConfig
    figures: FigureConfig
    observability: ObservabilityConfig

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"unknown IANA timezone: {value}") from error
        return value


class ModelProfile(StrictConfigModel):
    model_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._:-]*$")
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int = Field(ge=1, le=100_000)


class TaskModelChain(StrictConfigModel):
    primary: ModelAlias
    fallbacks: list[ModelAlias] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_chain(self) -> TaskModelChain:
        chain = [self.primary, *self.fallbacks]
        if len(chain) != len(set(chain)):
            raise ValueError("task model chain must not contain duplicate aliases")
        return self


class RoutingConfig(StrictConfigModel):
    allow_provider_fallbacks: bool
    provider_sort: Literal["default", "price", "throughput", "latency"]
    require_structured_outputs: bool


class ModelConfig(StrictConfigModel):
    schema_version: Literal[1]
    provider: Literal["openrouter"]
    base_url: AnyHttpUrl
    models: dict[ModelAlias, ModelProfile] = Field(min_length=1)
    tasks: dict[str, TaskModelChain] = Field(min_length=1)
    routing: RoutingConfig

    @field_validator("base_url")
    @classmethod
    def require_https(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme != "https":
            raise ValueError("model base_url must use HTTPS")
        return value

    @model_validator(mode="after")
    def validate_task_aliases(self) -> ModelConfig:
        aliases = set(self.models)
        for task_name, task in self.tasks.items():
            unknown = set([task.primary, *task.fallbacks]) - aliases
            if unknown:
                rendered = ", ".join(sorted(unknown))
                message = f"task {task_name!r} uses unknown model aliases: {rendered}"
                raise ValueError(message)
        return self

    def model_chain(self, task_name: str) -> tuple[ModelProfile, ...]:
        """Resolve a configured task into its ordered model profiles."""
        try:
            task = self.tasks[task_name]
        except KeyError as error:
            raise KeyError(f"unknown model task: {task_name}") from error
        return tuple(self.models[alias] for alias in [task.primary, *task.fallbacks])


class PromptDefinition(StrictConfigModel):
    version: str = Field(min_length=1)
    system: str
    user: str

    @field_validator("system", "user")
    @classmethod
    def validate_template_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or path.suffix != ".j2":
            raise ValueError("prompt template must be a safe relative .j2 path")
        return value


class PromptManifest(StrictConfigModel):
    filter: PromptDefinition
    summary: PromptDefinition


class ConfigBundle(StrictConfigModel):
    runtime: RuntimeConfig
    models: ModelConfig
    prompts: PromptManifest

    @property
    def runtime_hash(self) -> str:
        return normalized_config_hash(self.runtime)

    @property
    def model_hash(self) -> str:
        return normalized_config_hash(self.models)


class OpenRouterCredentials(BaseModel):
    """Non-serializable credential holder loaded only from environment."""

    model_config = ConfigDict(extra="forbid")
    api_key: SecretStr


def normalized_config_hash(config: BaseModel) -> str:
    """Hash semantic model content independently of YAML formatting."""
    normalized = json.dumps(
        config.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(normalized).hexdigest()


def load_yaml(path: Path) -> object:
    """Load one YAML document with actionable path context."""
    try:
        with path.open(encoding="utf-8") as stream:
            return yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"unable to load YAML configuration {path}") from error


def load_config_bundle(root: Path = Path(".")) -> ConfigBundle:
    """Load the checked-in runtime, model, and prompt configurations."""
    config_root = root / "configs"
    return ConfigBundle(
        runtime=RuntimeConfig.model_validate(load_yaml(config_root / "runtime.yaml")),
        models=ModelConfig.model_validate(load_yaml(config_root / "models.yaml")),
        prompts=PromptManifest.model_validate(
            load_yaml(config_root / "prompts" / "manifest.yaml")
        ),
    )


def load_openrouter_credentials(
    environment: Mapping[str, str] | None = None,
    *,
    required: bool,
) -> OpenRouterCredentials | None:
    """Load the OpenRouter key from an injected environment mapping only."""
    source = os.environ if environment is None else environment
    api_key = source.get("OPENROUTER_API_KEY", "")
    if not api_key:
        if required:
            raise ValueError("OPENROUTER_API_KEY is required for network LLM commands")
        return None
    return OpenRouterCredentials(api_key=SecretStr(api_key))
