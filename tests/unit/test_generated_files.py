from __future__ import annotations

from pathlib import Path

from paperflow.generated_files import (
    GENERATED_FILE_MARKER,
    generated_cleanup_candidates,
    is_generated_file,
)


def test_exact_marker_at_file_start_is_recognized(tmp_path: Path) -> None:
    generated = tmp_path / "generated.md"
    generated.write_text(f"{GENERATED_FILE_MARKER}\ncontent\n", encoding="utf-8")

    assert is_generated_file(generated)


def test_marker_variants_and_manual_files_are_never_generated(tmp_path: Path) -> None:
    manual = tmp_path / "manual.md"
    manual.write_text("# Notes\n", encoding="utf-8")
    altered = tmp_path / "altered.md"
    altered.write_text(
        GENERATED_FILE_MARKER.replace("PAPERFLOW.", "PAPERFLOW") + "content\n",
        encoding="utf-8",
    )
    embedded = tmp_path / "embedded.md"
    embedded.write_text(f"preface\n{GENERATED_FILE_MARKER}", encoding="utf-8")

    assert not is_generated_file(manual)
    assert not is_generated_file(altered)
    assert not is_generated_file(embedded)
    assert generated_cleanup_candidates([manual, altered, embedded]) == ()


def test_cleanup_candidates_include_only_exact_generated_files(tmp_path: Path) -> None:
    generated = tmp_path / "z-generated.md"
    generated.write_text(GENERATED_FILE_MARKER, encoding="utf-8")
    manual = tmp_path / "a-manual.md"
    manual.write_text("manual", encoding="utf-8")

    assert generated_cleanup_candidates([manual, generated]) == (generated,)
