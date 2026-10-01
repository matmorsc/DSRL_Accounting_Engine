from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

import build_ledger_deposit_drafts_v9
import build_month_end_package
from build_month_end_package import STAGES
from src.artifacts import require_fresh_artifact


def set_modified(path: Path, timestamp: int) -> None:
    path.write_text("test", encoding="utf-8")
    os.utime(path, ns=(timestamp, timestamp))


def write_posting_history_review(
    path: Path,
    rows: list[dict[str, object]],
) -> None:
    pd.DataFrame(
        rows,
        columns=[
            "review_status",
            "approved_for_promotion",
        ],
    ).to_csv(path, index=False)


def test_stale_derived_artifact_is_rejected(tmp_path: Path):
    canonical = tmp_path / "payout_ledger.csv"
    versioned = tmp_path / "payout_ledger_v6.csv"
    set_modified(versioned, 1_000)
    set_modified(canonical, 2_000)

    with pytest.raises(RuntimeError, match="Stale derived artifact"):
        require_fresh_artifact(
            versioned,
            generated_by="python build_stripe_payout_reconciliation_v6.py",
            newer_than=(canonical,),
        )


def test_current_derived_artifact_is_accepted(tmp_path: Path):
    canonical = tmp_path / "posting_status.csv"
    versioned = tmp_path / "posting_status_v6.csv"
    set_modified(canonical, 1_000)
    set_modified(versioned, 2_000)

    assert require_fresh_artifact(
        versioned,
        generated_by="python build_stripe_payout_reconciliation_v6.py",
        newer_than=(canonical,),
    ) == versioned


def test_month_end_chain_rebuilds_reversals_before_v9_deposits():
    assert STAGES.index("build_stripe_payout_reconciliation_v6.py") < STAGES.index(
        "build_posting_history_review.py"
    )
    assert STAGES.index("build_posting_history_v8.py") < STAGES.index(
        "build_posting_history_review.py"
    )
    assert STAGES.index("build_posting_history_review.py") < STAGES.index(
        "build_posting_history_reversals_v8.py"
    )
    assert STAGES.index("build_posting_history_reversals_v8.py") < STAGES.index(
        "build_ledger_deposit_drafts_v9.py"
    )
    assert STAGES[-1] == "build_quickbooks_posting_package_v10.py"


@pytest.mark.parametrize(
    ("rows", "expected_returncode", "should_stop"),
    [
        ([], 0, False),
        (
            [
                {
                    "review_status": "Ready for Promotion",
                    "approved_for_promotion": "Yes",
                }
            ],
            0,
            False,
        ),
        (
            [
                {
                    "review_status": "Ready for Promotion",
                    "approved_for_promotion": "Pending",
                }
            ],
            1,
            True,
        ),
        (
            [
                {
                    "review_status": "Ready for Promotion",
                    "approved_for_promotion": "",
                }
            ],
            1,
            True,
        ),
        (
            [
                {
                    "review_status": "Ready for Promotion",
                    "approved_for_promotion": float("nan"),
                }
            ],
            1,
            True,
        ),
        (
            [
                {
                    "review_status": "Review Required",
                    "approved_for_promotion": "Pending",
                }
            ],
            0,
            False,
        ),
        (
            [
                {
                    "review_status": "Excluded - Source Event",
                    "approved_for_promotion": "Pending",
                }
            ],
            0,
            False,
        ),
    ],
    ids=[
        "no-ready-for-promotion-rows",
        "ready-for-promotion-approved-yes",
        "ready-for-promotion-pending",
        "ready-for-promotion-blank",
        "ready-for-promotion-nan",
        "review-required",
        "excluded-source-event",
    ],
)
def test_posting_history_promotion_gate_cases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    rows: list[dict[str, object]],
    expected_returncode: int,
    should_stop: bool,
):
    review_path = tmp_path / "posting_history_review.csv"
    write_posting_history_review(review_path, rows)
    monkeypatch.setattr(
        build_month_end_package,
        "REVIEW_PATH",
        review_path,
    )

    assert (
        build_month_end_package.check_posting_history_promotion_gate()
        == expected_returncode
    )

    output = capsys.readouterr().out
    if should_stop:
        assert "MONTH-END STOP: POSTING HISTORY PROMOTION REQUIRED" in output
        assert "python promote_posting_history_v8.py" in output
        assert "python build_month_end_package.py" in output
    else:
        assert "MONTH-END STOP: POSTING HISTORY PROMOTION REQUIRED" not in output


def test_month_end_gate_stops_before_reversals_for_unapproved_ready_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    review_path = tmp_path / "posting_history_review.csv"
    called_stages: list[str] = []

    class SuccessfulStage:
        returncode = 0

    def fake_run(args, **kwargs):
        stage = Path(args[1]).name
        called_stages.append(stage)
        if stage == "build_posting_history_review.py":
            write_posting_history_review(
                review_path,
                [
                    {
                        "review_status": "Ready for Promotion",
                        "approved_for_promotion": "Pending",
                    }
                ],
            )
        return SuccessfulStage()

    monkeypatch.setattr(
        build_month_end_package,
        "REVIEW_PATH",
        review_path,
    )
    monkeypatch.setattr(
        build_month_end_package.subprocess,
        "run",
        fake_run,
    )

    assert build_month_end_package.main() == 1

    output = capsys.readouterr().out
    assert "Payment events requiring promotion approval: 1" in output
    assert "build_posting_history_reversals_v8.py" not in called_stages
    assert "build_ledger_deposit_drafts_v9.py" not in called_stages


def test_month_end_gate_fails_clearly_when_review_file_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    review_path = tmp_path / "posting_history_review.csv"
    called_stages: list[str] = []

    class SuccessfulStage:
        returncode = 0

    def fake_run(args, **kwargs):
        stage = Path(args[1]).name
        called_stages.append(stage)
        return SuccessfulStage()

    monkeypatch.setattr(
        build_month_end_package,
        "REVIEW_PATH",
        review_path,
    )
    monkeypatch.setattr(
        build_month_end_package.subprocess,
        "run",
        fake_run,
    )

    assert build_month_end_package.main() == 1

    output = capsys.readouterr().out
    assert "completed without creating" in output
    assert str(review_path) in output
    assert "build_posting_history_reversals_v8.py" not in called_stages
    assert "build_ledger_deposit_drafts_v9.py" not in called_stages


def test_v9_builder_rejects_stale_v6_payout_instead_of_selecting_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    processed = tmp_path / "processed"
    processed.mkdir()
    settings = tmp_path / "settings.yaml"
    settings.write_text("matching:\n  amount_tolerance: 0.02\n", encoding="utf-8")

    canonical_payout = processed / "payout_ledger.csv"
    canonical_status = processed / "posting_status.csv"
    stale_payout = processed / "payout_ledger_v6.csv"
    current_status = processed / "posting_status_v6.csv"
    current_legacy = processed / "deposit_drafts_v6.csv"

    set_modified(stale_payout, 1_000)
    set_modified(canonical_payout, 2_000)
    set_modified(canonical_status, 2_000)
    set_modified(current_status, 3_000)
    set_modified(current_legacy, 3_000)

    monkeypatch.setattr(build_ledger_deposit_drafts_v9, "PROCESSED", processed)
    monkeypatch.setattr(build_ledger_deposit_drafts_v9, "SETTINGS", settings)

    assert build_ledger_deposit_drafts_v9.main() == 1
    output = capsys.readouterr().out
    assert "Stale derived artifact" in output
    assert "build_stripe_payout_reconciliation_v6.py" in output


def test_successful_month_end_warns_that_posting_state_is_external(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    review_path = tmp_path / "posting_history_review.csv"

    class SuccessfulStage:
        returncode = 0

    def fake_run(args, **kwargs):
        stage = Path(args[1]).name
        if stage == "build_posting_history_review.py":
            write_posting_history_review(review_path, [])
        return SuccessfulStage()

    monkeypatch.setattr(
        build_month_end_package,
        "REVIEW_PATH",
        review_path,
    )

    monkeypatch.setattr(
        build_month_end_package.subprocess,
        "run",
        fake_run,
    )

    assert build_month_end_package.main() == 0
    output = capsys.readouterr().out
    assert "does not mark its payouts as posted" in output
    assert "refresh the QuickBooks exports" in output
    assert "Already Posted" in output
    assert "may be proposed again" in output
