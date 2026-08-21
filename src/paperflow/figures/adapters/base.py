"""Shared adapter interface and injectable subprocess boundary."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from paperflow.figures.models import ExtractionResult


class CommandRunner(Protocol):
    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]: ...


class SubprocessCommandRunner:
    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=cwd,
            timeout=timeout,
            check=False,
            capture_output=True,
            text=True,
        )


class FigureExtractorAdapter(Protocol):
    def extract(
        self,
        pdf_path: Path,
        *,
        arxiv_id: str,
        work_dir: Path,
    ) -> ExtractionResult: ...
