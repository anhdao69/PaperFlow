"""Deterministic prompt rendering and prompt provenance."""

from __future__ import annotations

import hashlib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound
from pydantic import ConfigDict, Field

from paperflow.config import PromptDefinition, PromptManifest
from paperflow.models import DomainModel, NonEmptyText
from paperflow.taxonomy import TaxonomyConfig


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
