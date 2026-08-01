from __future__ import annotations

import pandas as pd

from src.posting.airbnb_adjustments import (
    build_airbnb_adjustment_review,
    promote_airbnb_adjustments,
)
from src.posting.history import (
    POSTING_HISTORY_COLUMNS,
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
            posting_line_id="pl_adjustment",
            posting_group_id="pg_adjustment",
            payment_event_id="Airbnb::ABC",
            processor="Airbnb",
            processor_account="Airbnb",
            transaction_id="ABC",
            transaction_type="adjustment",
            transaction_date="2026-06-29",
            source_id="AIRBNB-PAYOUT-1",
            payout_id="AIRBNB-PAYOUT-1",
            account="AirBNB Fees",
            **{"class": "Hospitality"},
            description="Airbnb processing fees",
            signed_amount="-12.03",
            posting_type="Source Event",
            status="Proposed",
        ),
        row(
            posting_line_id="pl_stripe_refund",
            posting_group_id="pg_refund",
            payment_event_id="Stripe::refund",
            processor="Stripe",
            transaction_type="refund",
            payout_id="po1",
            account="Revenue",
            **{"class": "Hospitality"},
            signed_amount="-50.00",
            posting_type="Source Event",
            status="Proposed",
        ),
    ])


def empty_history():
    return pd.DataFrame(
        columns=POSTING_HISTORY_COLUMNS
    )


def test_review_includes_only_valid_airbnb_adjustment():
    review = build_airbnb_adjustment_review(
        proposed()
    )

    assert len(review) == 1
    assert review.loc[
        0, "review_status"
    ] == "Ready for Promotion"
    assert review.loc[
        0, "adjustment_total"
    ] == -12.03


def test_approved_adjustment_promotes_as_active_adjustment():
    review = build_airbnb_adjustment_review(
        proposed()
    )
    review.loc[
        0, "approved_for_promotion"
    ] = "Yes"

    combined, diagnostics = (
        promote_airbnb_adjustments(
            proposed_history=proposed(),
            review=review,
            existing_history=empty_history(),
        )
    )

    assert len(combined) == 1
    assert combined.loc[
        0, "posting_type"
    ] == "Adjustment"
    assert combined.loc[
        0, "status"
    ] == "Active"
    assert diagnostics.empty
