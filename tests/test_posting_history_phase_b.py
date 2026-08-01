from __future__ import annotations

import pandas as pd

from src.posting.history import (
    POSTING_HISTORY_COLUMNS,
)
from src.posting.history_review import (
    build_posting_history_review,
)
from src.posting.history_promotion import (
    promote_approved_posting_history,
)


def proposed():
    rows = []

    for line_id, amount in [
        ("pl1", 100.0),
        ("pl2", -3.0),
    ]:
        row = {
            column: ""
            for column in POSTING_HISTORY_COLUMNS
        }
        row.update(
            {
                "posting_line_id": line_id,
                "posting_group_id": "pg1",
                "payment_event_id": "evt1",
                "processor": "Stripe",
                "processor_account": "Main",
                "transaction_id": "txn1",
                "transaction_type": "charge",
                "transaction_date": (
                    "2026-07-01 00:00:00"
                ),
                "source_id": "ch1",
                "payout_id": "po1",
                "guest": "Guest",
                "listing": "Room",
                "account": (
                    "Income"
                    if amount > 0
                    else "Stripe Fees"
                ),
                "class": "Hospitality",
                "description": "Test",
                "signed_amount": f"{amount:.2f}",
                "posting_type": "Original",
                "status": "Proposed",
            }
        )
        rows.append(row)

    source_row = {
        column: ""
        for column in POSTING_HISTORY_COLUMNS
    }
    source_row.update(
        {
            "posting_line_id": "pl3",
            "posting_group_id": "pg2",
            "payment_event_id": "evt2",
            "processor": "Stripe",
            "processor_account": "Main",
            "transaction_id": "txn2",
            "transaction_type": "refund",
            "transaction_date": (
                "2026-07-02 00:00:00"
            ),
            "source_id": "ch1",
            "payout_id": "po2",
            "account": "Income",
            "class": "Hospitality",
            "description": "Refund",
            "signed_amount": "-50.00",
            "posting_type": "Source Event",
            "status": "Proposed",
        }
    )
    rows.append(source_row)

    return pd.DataFrame(rows)


def ledger():
    return pd.DataFrame(
        [
            {
                "payment_event_id": "evt1",
                "net_amount": 97.0,
            },
            {
                "payment_event_id": "evt2",
                "net_amount": -50.0,
            },
        ]
    )


def empty_history():
    return pd.DataFrame(
        columns=POSTING_HISTORY_COLUMNS
    )


def test_review_marks_original_balanced_event_ready():
    review = build_posting_history_review(
        proposed_history=proposed(),
        payment_ledger=ledger(),
    )

    original = review.loc[
        review["payment_event_id"].eq("evt1")
    ].iloc[0]

    assert original["review_status"] == (
        "Ready for Promotion"
    )
    assert original["difference"] == 0.0


def test_review_excludes_source_event():
    review = build_posting_history_review(
        proposed_history=proposed(),
        payment_ledger=ledger(),
    )

    refund = review.loc[
        review["payment_event_id"].eq("evt2")
    ].iloc[0]

    assert refund["review_status"] == (
        "Excluded - Source Event"
    )
    assert refund["approved_for_promotion"] == "No"


def test_only_explicitly_approved_originals_promote():
    review = build_posting_history_review(
        proposed_history=proposed(),
        payment_ledger=ledger(),
    )
    review.loc[
        review["payment_event_id"].eq("evt1"),
        "approved_for_promotion",
    ] = "Yes"

    combined, diagnostics = (
        promote_approved_posting_history(
            proposed_history=proposed(),
            review=review,
            existing_history=empty_history(),
        )
    )

    assert len(combined) == 2
    assert set(combined["payment_event_id"]) == {
        "evt1"
    }
    assert set(combined["status"]) == {"Active"}
    assert diagnostics.empty


def test_second_promotion_does_not_duplicate():
    review = build_posting_history_review(
        proposed_history=proposed(),
        payment_ledger=ledger(),
    )
    review.loc[
        review["payment_event_id"].eq("evt1"),
        "approved_for_promotion",
    ] = "Yes"

    first, _ = promote_approved_posting_history(
        proposed_history=proposed(),
        review=review,
        existing_history=empty_history(),
    )

    second, diagnostics = (
        promote_approved_posting_history(
            proposed_history=proposed(),
            review=review,
            existing_history=first,
        )
    )

    assert len(second) == 2
    assert len(diagnostics) == 2
    assert set(
        diagnostics["diagnostic_type"]
    ) == {"Already In Posting History"}
