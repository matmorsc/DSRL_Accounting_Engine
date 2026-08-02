from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.review.payout_inspector import (
    inspect_payout,
    render_inspection,
)


def write_csv(
    directory: Path,
    name: str,
    rows: list[dict[str, object]],
) -> None:
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )
    pd.DataFrame(rows).to_csv(
        directory / name,
        index=False,
    )


def test_inspector_collects_payout_evidence(
    tmp_path: Path,
):
    processed = tmp_path / "processed"
    config = tmp_path / "config"

    write_csv(
        processed,
        "payout_ledger_v6.csv",
        [
            {
                "payout_id": "po1",
                "processor": "Stripe",
                "payout_amount": 100.00,
            }
        ],
    )
    write_csv(
        processed,
        "payment_ledger_v6.csv",
        [
            {
                "payout_id": "po1",
                "payment_event_id": "evt1",
                "transaction_type": "charge",
                "source_id": "ch1",
                "net_amount": 100.00,
                "reservation_id": "r1",
            }
        ],
    )
    write_csv(
        processed,
        "posting_package_summary_v10.csv",
        [
            {
                "payout_id": "po1",
                "processor": "Stripe",
                "posting_total": 90.00,
                "bank_difference": -10.00,
                "confidence": "Needs Review",
            }
        ],
    )
    write_csv(
        processed,
        "stripe_family_reconciliation_v11.csv",
        [
            {
                "payout_id": "po1",
                "source_id": "ch1",
                "family_gap": 10.00,
                "family_issue": "Missing original",
            }
        ],
    )
    write_csv(
        processed,
        "reservations.csv",
        [
            {
                "reservation_id": "r1",
                "guest": "Guest",
                "listing": "Room",
            }
        ],
    )
    write_csv(
        config,
        "posting_history_manual_seeds.csv",
        [
            {
                "payout_id": "po1",
                "posting_line_id": "pl1",
                "signed_amount": 90.00,
                "posting_type": "Original",
            }
        ],
    )

    inspection = inspect_payout(
        payout_id="po1",
        processed_dir=processed,
        config_dir=config,
    )

    assert len(
        inspection.payment_events
    ) == 1
    assert len(
        inspection.posting_history
    ) == 1
    assert len(
        inspection.stripe_families
    ) == 1
    assert len(
        inspection.reservation_rows
    ) == 1
    assert "Difference:         -10.00" in (
        inspection.summary
    )


def test_render_includes_expected_sections(
    tmp_path: Path,
):
    processed = tmp_path / "processed"
    config = tmp_path / "config"

    write_csv(
        processed,
        "payout_ledger_v6.csv",
        [
            {
                "payout_id": "po1",
                "processor": "Stripe",
                "payout_amount": 100.00,
            }
        ],
    )

    inspection = inspect_payout(
        payout_id="po1",
        processed_dir=processed,
        config_dir=config,
    )
    report = render_inspection(
        inspection
    )

    assert "PAYMENT EVENTS" in report
    assert "ACTIVE POSTING HISTORY" in report
    assert "REVERSAL PREVIEW" in report
    assert "STRIPE SOURCE FAMILIES" in report
    assert "RESERVATION EVIDENCE" in report
