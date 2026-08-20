"""Deterministic prompt rendering and prompt provenance."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, TypeVar

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from paperflow.atomic import atomic_write_text
from paperflow.config import PromptDefinition, PromptManifest
from paperflow.models import (
    DomainModel,
    LLMCallResult,
    NonEmptyText,
    Sha256,
    validate_canonical_arxiv_id,
)
from paperflow.taxonomy import TaxonomyConfig

OutputT = TypeVar("OutputT", bound=BaseModel)


class PromptPaper(DomainModel):
    """The complete and exclusive paper input allowed in filtering prompts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    arxiv_id: NonEmptyText
    title: NonEmptyText
    abstract: NonEmptyText
    categories: list[NonEmptyText] = Field(min_length=1)


class RenderedPrompt(DomainModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    system: str
    user: str
    system_hash: str


class LLMCacheKey(DomainModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task: Literal["filter", "summary"]
    arxiv_id: str
    abstract_hash: Sha256
    prompt_hash: Sha256
    model_id: NonEmptyText
    taxonomy_hash: Sha256 | None = None

    _validate_arxiv_id = field_validator("arxiv_id")(validate_canonical_arxiv_id)

    @model_validator(mode="after")
    def validate_task_components(self) -> LLMCacheKey:
        if self.task == "filter" and self.taxonomy_hash is None:
            raise ValueError("filter cache keys require taxonomy_hash")
        if self.task == "summary" and self.taxonomy_hash is not None:
            raise ValueError("summary cache keys must not include taxonomy_hash")
        return self

    def fingerprint(self) -> str:
        normalized = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(normalized).hexdigest()


class _LLMCacheRecord(DomainModel):
    schema_version: Literal[1] = 1
    key: LLMCacheKey
    result: dict[str, Any]


class LLMCache:
    """Optional validated disk cache; corrupt or stale records are misses."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def load(
        self, key: LLMCacheKey, schema: type[OutputT]
    ) -> LLMCallResult[OutputT] | None:
        path = self._path(key)
        try:
            record = _LLMCacheRecord.model_validate_json(
                path.read_text(encoding="utf-8")
            )
            if record.key != key:
                return None
            return LLMCallResult[schema].model_validate(record.result)
        except (OSError, ValidationError, ValueError):
            return None

    def store(
        self, key: LLMCacheKey, result: LLMCallResult[OutputT]
    ) -> Path:
        record = _LLMCacheRecord(
            key=key,
            result=result.model_dump(mode="json"),
        )
        path = self._path(key)
        encoded = json.dumps(
            record.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"
        atomic_write_text(
            path,
            encoded,
            validator=lambda staged: _LLMCacheRecord.model_validate_json(
                staged.read_text(encoding="utf-8")
            ),
        )
        return path

    def _path(self, key: LLMCacheKey) -> Path:
        safe_id = key.arxiv_id.replace("/", "_")
        return self.root / f"llm_{key.task}" / f"{safe_id}__{key.fingerprint()}.json"


def summary_cache_key(
    paper: PromptPaper, prompt: RenderedPrompt, model_id: str
) -> LLMCacheKey:
    return LLMCacheKey(
        task="summary",
        arxiv_id=paper.arxiv_id,
        abstract_hash=hashlib.sha256(paper.abstract.encode()).hexdigest(),
        prompt_hash=prompt.system_hash,
        model_id=model_id,
    )


def prompt_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


class PromptRenderer:
    """Render all configured prompts through one strict Jinja environment."""

    def __init__(self, template_root: Path, manifest: PromptManifest) -> None:
        self._template_root = template_root
        self._manifest = manifest
        self._environment = Environment(
            loader=FileSystemLoader(template_root),
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
            newline_sequence="\n",
        )

    def validate_templates(self) -> None:
        """Prove every configured template exists before any LLM request."""
        template_names = [
            "taxonomy_block.j2",
            self._manifest.filter.system,
            self._manifest.filter.user,
            self._manifest.summary.system,
            self._manifest.summary.user,
        ]
        for template_name in template_names:
            try:
                self._environment.get_template(template_name)
            except TemplateNotFound as error:
                raise ValueError(
                    f"configured prompt template does not exist: {template_name}"
                ) from error

    def render_taxonomy(self, taxonomy: TaxonomyConfig) -> str:
        template = self._environment.get_template("taxonomy_block.j2")
        return self._normalize(template.render(topics=taxonomy.topics))

    def render_filter(
        self, taxonomy: TaxonomyConfig, papers: list[PromptPaper]
    ) -> RenderedPrompt:
        if not papers:
            raise ValueError("filter prompt requires at least one paper")
        definition = self._manifest.filter
        taxonomy_block = self.render_taxonomy(taxonomy)
        system = self._render(definition.system, taxonomy_block=taxonomy_block)
        user = self._render(definition.user, papers=papers)
        return self._result(definition, system, user)

    def render_summary(self, paper: PromptPaper) -> RenderedPrompt:
        definition = self._manifest.summary
        system = self._render(definition.system)
        user = self._render(definition.user, paper=paper)
        return self._result(definition, system, user)

    def _render(self, template_name: str, **context: object) -> str:
        rendered = self._environment.get_template(template_name).render(**context)
        return self._normalize(rendered)

    @staticmethod
    def _normalize(rendered: str) -> str:
        return f"{rendered.rstrip()}\n"

    @staticmethod
    def _result(
        definition: PromptDefinition, system: str, user: str
    ) -> RenderedPrompt:
        return RenderedPrompt(
            version=definition.version,
            system=system,
            user=user,
            system_hash=prompt_hash(system),
        )
