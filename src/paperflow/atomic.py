"""Validated atomic filesystem operations used by canonical writers."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath

PathValidator = Callable[[Path], None]


def atomic_write_bytes(
    path: Path, content: bytes, *, validator: PathValidator | None = None
) -> None:
    """Validate and atomically replace one file while preserving the prior file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if validator is not None:
            validator(temporary_path)
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def atomic_write_text(
    path: Path,
    content: str,
    *,
    validator: PathValidator | None = None,
) -> None:
    """UTF-8 variant of :func:`atomic_write_bytes`."""
    atomic_write_bytes(path, content.encode(), validator=validator)


def _validate_relative_path(path: PurePosixPath) -> None:
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"unsafe staged install path: {path}")


def install_staged_files(
    staging_root: Path,
    destination_root: Path,
    relative_paths: Iterable[PurePosixPath],
    *,
    validate_staging: Callable[[Path], None],
    before_install: Callable[[], None] | None = None,
) -> None:
    """Validate a staged batch, then install it with best-effort rollback.

    Each replacement is atomic. If a later replacement fails, prior destination
    bytes are restored so callers never intentionally retain a partial batch.
    """
    paths = tuple(sorted(set(relative_paths), key=str))
    for relative_path in paths:
        _validate_relative_path(relative_path)
        if not (staging_root / relative_path).is_file():
            raise ValueError(f"staged file is missing: {relative_path}")

    validate_staging(staging_root)
    if before_install is not None:
        before_install()

    originals: dict[PurePosixPath, bytes | None] = {}
    installed: list[PurePosixPath] = []
    try:
        for relative_path in paths:
            source = staging_root / relative_path
            destination = destination_root / relative_path
            originals[relative_path] = (
                destination.read_bytes() if destination.is_file() else None
            )
            atomic_write_bytes(destination, source.read_bytes())
            installed.append(relative_path)
    except BaseException:
        for relative_path in reversed(installed):
            destination = destination_root / relative_path
            original = originals[relative_path]
            if original is None:
                destination.unlink(missing_ok=True)
            else:
                atomic_write_bytes(destination, original)
        raise
