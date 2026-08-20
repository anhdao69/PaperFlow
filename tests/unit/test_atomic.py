from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from paperflow.atomic import atomic_write_text, install_staged_files


def test_atomic_write_validation_failure_preserves_prior_bytes(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    target.write_bytes(b"original")

    def reject(_: Path) -> None:
        raise ValueError("invalid staged content")

    with pytest.raises(ValueError, match="invalid staged content"):
        atomic_write_text(target, "replacement", validator=reject)

    assert target.read_bytes() == b"original"
    assert not list(tmp_path.glob("*.tmp"))


def test_batch_failure_before_install_preserves_every_original(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    live = tmp_path / "live"
    staging.mkdir()
    live.mkdir()
    (staging / "one.txt").write_text("new one", encoding="utf-8")
    (staging / "two.txt").write_text("new two", encoding="utf-8")
    (live / "one.txt").write_text("old one", encoding="utf-8")
    (live / "two.txt").write_text("old two", encoding="utf-8")

    def fail() -> None:
        raise RuntimeError("injected before install")

    with pytest.raises(RuntimeError, match="injected"):
        install_staged_files(
            staging,
            live,
            [PurePosixPath("one.txt"), PurePosixPath("two.txt")],
            validate_staging=lambda _: None,
            before_install=fail,
        )

    assert (live / "one.txt").read_text(encoding="utf-8") == "old one"
    assert (live / "two.txt").read_text(encoding="utf-8") == "old two"


def test_batch_install_rejects_unsafe_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsafe"):
        install_staged_files(
            tmp_path,
            tmp_path,
            [PurePosixPath("../outside")],
            validate_staging=lambda _: None,
        )
