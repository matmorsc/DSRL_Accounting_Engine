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


def row(**updates):
    base = {
        column: ""
        for column in POSTING_HISTORY_COLUMNS
    }
    base.update(updates)
    return base


def proposed():
    return pd.DataFrame([
        row(
            posting_line_id="pl_rev",
            posting_group_id="pg_reservation",
            payment_event_id="Airbnb::ABC",
            processor="Airbnb",
            processor_account="Airbnb",
            transaction_id="ABC",
            transaction_type="reservation",
            transaction_date="2026-06-26 00:00:00",
            source_id="payout_a",
            payout_id="payout_a",
            account="Motel Rent - Short Term",
            **{"class": "Hospitality"},
            description="Room",
            signed_amount="349.60",
            posting_type="Original",
            status="Proposed",
        ),
        row(
            posting_line_id="pl_fee",
            posting_group_id="pg_reservation",
            payment_event_id="Airbnb::ABC",
            processor="Airbnb",
            processor_account="Airbnb",
            transaction_id="ABC",
            transaction_type="reservation",
            transaction_date="2026-06-26 00:00:00",
            source_id="payout_a",
            payout_id="payout_a",
            account="AirBNB Fees",
            **{"class": "Hospitality"},
            description="Airbnb processing fees",
            signed_amount="-54.19",
            posting_type="Original",
            status="Proposed",
        ),
        row(
            posting_line_id="pl_adjustment",
            posting_group_id="pg_adjustment",
            payment_event_id="Airbnb::ABC",
            processor="Airbnb",
            processor_account="Airbnb",
            transaction_id="ABC",
            transaction_type="adjustment",
            transaction_date="2026-06-29 00:00:00",
            source_id="payout_b",
            payout_id="payout_b",
            account="AirBNB Fees",
            **{"class": "Hospitality"},
            description="Airbnb processing fees",
            signed_amount="-12.03",
            posting_type="Source Event",
            status="Proposed",
        ),
    ])


def ledger():
    return pd.DataFrame([
        {
            "payment_event_id": "Airbnb::ABC",
            "transaction_id": "ABC",
            "transaction_type": "reservation",
            "transaction_date": "2026-06-26 00:00:00",
            "payout_id": "payout_a",
            "net_amount": 295.41,
        },
        {
            "payment_event_id": "Airbnb::ABC",
            "transaction_id": "ABC",
            "transaction_type": "adjustment",
            "transaction_date": "2026-06-29 00:00:00",
            "payout_id": "payout_b",
            "net_amount": 0.0,
        },
    ])


def empty_history():
    return pd.DataFrame(
        columns=POSTING_HISTORY_COLUMNS
    )


def test_duplicate_payment_event_ids_review_separately():
    review = build_posting_history_review(
        proposed_history=proposed(),
        payment_ledger=ledger(),
    )

    assert len(review) == 2

    reservation = review.loc[
        review["posting_group_id"].eq(
            "pg_reservation"
        )
    ].iloc[0]
    adjustment = review.loc[
        review["posting_group_id"].eq(
            "pg_adjustment"
        )
    ].iloc[0]

    assert reservation["review_status"] == (
        "Ready for Promotion"
    )
    assert reservation["difference"] == 0.0
    assert adjustment["review_status"] == (
        "Excluded - Source Event"
    )


def test_promotion_is_keyed_by_posting_group():
    review = build_posting_history_review(
        proposed_history=proposed(),
        payment_ledger=ledger(),
    )
    review.loc[
        review["posting_group_id"].eq(
            "pg_reservation"
        ),
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
    assert set(combined["posting_group_id"]) == {
        "pg_reservation"
    }
    assert set(combined["posting_type"]) == {
        "Original"
    }
    assert diagnostics.empty
