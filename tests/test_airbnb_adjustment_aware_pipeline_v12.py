from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.importers.normalize import normalize_airbnb
from src.posting.airbnb_adjustments import (
    build_airbnb_adjustment_review,
    promote_airbnb_adjustments,
)
from src.posting.history import (
    POSTING_HISTORY_COLUMNS,
    build_proposed_posting_history,
)
from src.posting.payment_allocations import (
    _signed_event_amount,
)


def _airbnb_export_row(**updates):
    row = {
        "Date": "2026-06-08",
        "Type": "resolution adjustment",
        "Confirmation code": "HMFQ5QX22M",
        "Guest": "Guest",
        "Listing": "DSRL Lodge Room 4",
        "Details": "Resolution adjustment",
        "Reference code": "",
        "Amount": -50.02,
        "Paid out": 0.0,
        "Service fee": 0.0,
        "Fast pay fee": 0.0,
        "Gross earnings": -50.02,
        "Airbnb remitted tax": 0.0,
        "Arriving by date": "2026-06-09",
    }
    row.update(updates)
    return row


def _history_row(**updates):
    row = {column: "" for column in POSTING_HISTORY_COLUMNS}
    row.update(updates)
    return row


def test_normalize_non_reservation_airbnb_event_uses_amount(tmp_path: Path):
    path = tmp_path / "airbnb.csv"
    pd.DataFrame([_airbnb_export_row()]).to_csv(path, index=False)

    normalized = normalize_airbnb(path)

    assert normalized.loc[0, "gross_amount"] == -50.02
    assert normalized.loc[0, "net_amount"] == -50.02


def test_normalize_payout_still_uses_paid_out(tmp_path: Path):
    path = tmp_path / "airbnb.csv"
    pd.DataFrame([
        _airbnb_export_row(
            Type="payout",
            **{
                "Confirmation code": "",
                "Reference code": "G-ONE",
                "Amount": 0.0,
                "Paid out": 50.53,
                "Gross earnings": 0.0,
            },
        )
    ]).to_csv(path, index=False)

    normalized = normalize_airbnb(path)

    assert normalized.loc[0, "gross_amount"] == 50.53
    assert normalized.loc[0, "net_amount"] == 50.53


@pytest.mark.parametrize(
    "event_type,amount",
    [
        ("adjustment", -65.57),
        ("resolution adjustment", -209.50),
        ("cancellation fee", -50.00),
    ],
)
def test_adjustment_event_types_preserve_exported_sign(event_type, amount):
    assert _signed_event_amount(event_type, amount) == amount


def test_history_marks_resolution_adjustment_as_source_event():
    allocations = pd.DataFrame([
        {
            "payment_event_id": "Airbnb::H1",
            "payout_id": "G-ONE",
            "processor": "Airbnb",
            "processor_account": "Airbnb",
            "transaction_id": "H1",
            "transaction_type": "resolution adjustment",
            "transaction_date": "2026-06-08",
            "reservation_id": "r1",
            "channel_reservation_id": "H1",
            "guest": "Guest",
            "listing": "DSRL Lodge Room 4",
            "allocation_type": "Revenue",
            "account": "Motel Rent - Short Term",
            "description": "DSRL Lodge Room 4",
            "amount": -50.02,
            "class": "Hospitality",
        }
    ])
    ledger = pd.DataFrame([
        {
            "payment_event_id": "Airbnb::H1",
            "source_id": "G-ONE",
        }
    ])
    empty = pd.DataFrame(columns=POSTING_HISTORY_COLUMNS)

    proposed, _ = build_proposed_posting_history(
        allocations=allocations,
        payment_ledger=ledger,
        existing_history=empty,
        created_at="2026-08-03T00:00:00Z",
    )

    assert proposed.loc[0, "posting_type"] == "Source Event"


def test_review_and_promotion_include_resolution_adjustment():
    proposed = pd.DataFrame([
        _history_row(
            posting_line_id="pl_resolution",
            posting_group_id="pg_resolution",
            payment_event_id="Airbnb::H1",
            processor="Airbnb",
            processor_account="Airbnb",
            transaction_id="H1",
            transaction_type="resolution adjustment",
            transaction_date="2026-06-08",
            source_id="G-ONE",
            payout_id="G-ONE",
            account="Refunds",
            **{"class": "Hospitality"},
            description="Airbnb resolution adjustment",
            signed_amount="-50.02",
            posting_type="Source Event",
            status="Proposed",
        )
    ])

    review = build_airbnb_adjustment_review(proposed)
    assert len(review) == 1
    assert review.loc[0, "transaction_type"] == "resolution adjustment"
    review.loc[0, "approved_for_promotion"] = "Yes"

    combined, diagnostics = promote_airbnb_adjustments(
        proposed_history=proposed,
        review=review,
        existing_history=pd.DataFrame(columns=POSTING_HISTORY_COLUMNS),
    )

    assert len(combined) == 1
    assert combined.loc[0, "posting_type"] == "Adjustment"
    assert combined.loc[0, "signed_amount"] == "-50.02"
    assert diagnostics.empty
