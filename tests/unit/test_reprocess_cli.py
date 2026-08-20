from paperflow.cli.reprocess import main


def test_manual_reprocess_cli_accepts_canonical_id() -> None:
    assert main(["--paper", "2608.12345", "--dry-run"]) == 0


def test_manual_reprocess_cli_rejects_versioned_or_unsafe_id() -> None:
    assert main(["--paper", "2608.12345v1", "--dry-run"]) == 1
    assert main(["--paper", "../outside", "--dry-run"]) == 1
