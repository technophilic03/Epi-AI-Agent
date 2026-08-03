from __future__ import annotations

from pathlib import Path


def test_study_neutral_plan_smoke_declares_real_browser_contract() -> None:
    source = Path(
        "scripts/e2e_fastapi_typescript_study_neutral_plan_real.py"
    ).read_text()

    assert "300" in source
    assert "retrieval_summary" in source
    assert "dataset_plan_review" in source
    assert "selected_column_keys" in source
    assert "PLAN_ROLE_COLLECTION_INVALID" not in source
    assert "PLAN_OUTPUT_NAME_CONFLICT" not in source


def test_study_neutral_plan_smoke_has_bounded_cli_defaults() -> None:
    from scripts.e2e_fastapi_typescript_study_neutral_plan_real import parse_args

    args = parse_args([])

    assert args.timeout_seconds == 300
