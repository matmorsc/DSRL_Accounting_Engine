from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.review.overrides import (
    apply_manual_payment_matches,
    read_manual_payment_matches,
    read_payout_adjustments,
)
from src.posting.deposit_drafts_v2 import (
    build_deposit_drafts_v2,
)


def test_manual_payment_match_is_applied(tmp_path: Path):
    path = tmp_path / "matches.csv"
    path.write_text(
        "payment_event_id,reservation_id,channel_reservation_id,status,notes\n"
        "evt1,r1,,Accepted,Confirmed\n",
        encoding="utf-8",
    )

    ledger = pd.DataFrame([{
        "payment_event_id": "evt1",
        "reservation_id": "",
        "channel_reservation_id": "",
    }])

    result = apply_manual_payment_matches(
        ledger,
        read_manual_payment_matches(path),
    )

    assert result.loc[0, "reservation_id"] == "r1"
    assert result.loc[0, "manual_match_applied"] == "Yes"


def test_inactive_adjustment_is_excluded(tmp_path: Path):
    path = tmp_path / "adjustments.csv"
    path.write_text(
        "payout_id,adjustment_type,amount,account,class,description,status,notes\n"
        "po1,Adjustment,50,Other Income,Hospitality,Test,Inactive,No\n",
        encoding="utf-8",
    )

    result = read_payout_adjustments(path)
    assert result.empty


def test_adjustment_can_balance_draft():
    posting = pd.DataFrame([{
        "payout_id": "po1",
        "processor": "Airbnb",
        "bank_transaction_id": "bank1",
        "bank_transaction_date": "2026-06-01",
        "bank_amount": 100.0,
        "posting_status": "Unposted",
        "generate_entry": "Yes",
    }])

    payout = pd.DataFrame([{
        "payout_id": "po1",
        "processor": "Airbnb",
        "processor_account": "Airbnb",
        "transaction_date": "2026-06-01",
        "payout_amount": 100.0,
        "bank_transaction_id": "bank1",
        "bank_transaction_date": "2026-06-01",
        "bank_amount": 100.0,
    }])

    allocations = pd.DataFrame([{
        "payment_event_id": "evt1",
        "payout_id": "po1",
        "processor": "Airbnb",
        "reservation_id": "r1",
        "channel_reservation_id": "A1",
        "guest": "Guest",
        "listing": "Cabin",
        "allocation_type": "Revenue",
        "account": "Cabin Rent - Short-Term",
        "description": "Cabin",
        "amount": 120.0,
        "class": "Cabins",
    }])

    adjustments = pd.DataFrame([{
        "payout_id": "po1",
        "adjustment_type": "Processor Adjustment",
        "amount": -20.0,
        "account": "OTA Commissions:AirBNB Fees",
        "class": "Hospitality",
        "description": "Correction",
        "status": "Active",
        "notes": "Confirmed",
    }])

    summaries, lines = build_deposit_drafts_v2(
        posting_status=posting,
        payout_ledger=payout,
        allocations=allocations,
        rules={"amount_tolerance": 0.02},
        payout_adjustments=adjustments,
    )

    assert summaries.loc[0, "balanced"] == "Yes"
    assert summaries.loc[0, "manual_adjustment_total"] == -20.0
    assert "Manual Adjustment" in " ".join(lines["line_type"])
