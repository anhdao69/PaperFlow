from __future__ import annotations

from pathlib import Path

from paperflow.figures.extract import resolve_executable_command


def test_existing_relative_java_command_becomes_absolute(tmp_path: Path) -> None:
    java = tmp_path / "tools/java"
    java.parent.mkdir()
    java.touch()

    assert resolve_executable_command(
        "tools/java", working_directory=tmp_path
    ) == str(java.resolve())


def test_path_java_command_is_left_for_environment_lookup(tmp_path: Path) -> None:
    assert resolve_executable_command(
        "java", working_directory=tmp_path
    ) == "java"
