"""Commit only PaperFlow's generated-output allowlist in a Git worktree."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path, PurePosixPath

GENERATED_ROOTS = ("README.md", "topics", "daily", "data", "site", "figures")


def is_allowed_generated_path(path: str) -> bool:
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return False
    return candidate.parts[:1] in {
        ("README.md",),
        ("topics",),
        ("daily",),
        ("data",),
        ("site",),
        ("figures",),
    }


def commit_generated_outputs(root: Path, *, message: str) -> bool:
    targets = tuple(
        target
        for target in GENERATED_ROOTS
        if (root / target).exists()
        or bool(_git(root, "ls-files", "--", target).stdout.strip())
    )
    if targets:
        _git(root, "add", "-A", "--", *targets)
    names = _git(root, "diff", "--cached", "--name-only").stdout.splitlines()
    unexpected = [name for name in names if not is_allowed_generated_path(name)]
    if unexpected:
        raise ValueError(f"refusing unexpected generated path: {unexpected[0]}")
    if not names:
        return False
    _git(root, "commit", "-m", message)
    return True


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--message", required=True)
    arguments = parser.parse_args(argv)
    changed = commit_generated_outputs(arguments.root, message=arguments.message)
    print("Generated content committed." if changed else "No generated changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
