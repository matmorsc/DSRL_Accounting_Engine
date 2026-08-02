from __future__ import annotations

import pandas as pd

from src.review.stripe_linked_disputes import (
    apply_linked_dispute_promotion,
    build_linked_dispute_approvals,
    preview_linked_dispute_promotion,
)


def payment_ledger() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "payment_event_id": "evt_dispute",
            "processor": "Stripe",
            "transaction_type": "adjustment",
            "source_id": "du_1",
            "payout_id": "po1",
            "gross_amount": -95.00,
            "processor_fee": 15.00,
            "net_amount": -110.00,
        }
    ])


def history() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "posting_line_id": "pl_revenue",
            "posting_group_id": "pg_original",
            "payment_event_id": "evt_original",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_original",
            "transaction_type": "charge",
            "transaction_date": "2026-06-16",
            "source_id": "ch_original",
            "payout_id": "po_original",
            "reservation_id": "r_paul",
            "channel_reservation_id": "597",
            "guest": "Paul Weissmann",
            "listing": "DSRL Lodge Room 4",
            "account": "Motel Rent - Short Term",
            "class": "Hospitality",
            "description": "DSRL Lodge Room 4",
            "signed_amount": 95.00,
            "posting_type": "Original",
            "reversal_of_posting_line_id": "",
            "classification_source": "Canceled Booking.com Gross",
            "created_by": "V11D",
            "created_at": "",
            "status": "Active",
            "notes": "",
        },
        {
            "posting_line_id": "pl_fee",
            "posting_group_id": "pg_original",
            "payment_event_id": "evt_original",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_original",
            "transaction_type": "charge",
            "transaction_date": "2026-06-16",
            "source_id": "ch_original",
            "payout_id": "po_original",
            "reservation_id": "r_paul",
            "channel_reservation_id": "597",
            "guest": "Paul Weissmann",
            "listing": "DSRL Lodge Room 4",
            "account": (
                "Bank Charges & Fees:"
                "Stripe Processing Fees"
            ),
            "class": "Hospitality",
            "description": "Stripe fee",
            "signed_amount": -3.44,
            "posting_type": "Original",
            "reversal_of_posting_line_id": "",
            "classification_source": "Canceled Booking.com Gross",
            "created_by": "V11D",
            "created_at": "",
            "status": "Active",
            "notes": "",
        },
    ])


def approved() -> pd.DataFrame:
    approvals = build_linked_dispute_approvals(
        payment_ledger()
    )
    approvals.loc[
        0, "linked_reservation_id"
    ] = "r_paul"
    approvals.loc[
        0, "linked_guest"
    ] = "Paul Weissmann"
    approvals.loc[
        0, "approval_status"
    ] = "Approved"
    return approvals


def test_linked_dispute_reverses_revenue_not_old_fee():
    preview, proposed = (
        preview_linked_dispute_promotion(
            approvals=approved(),
            existing_history=history(),
        )
    )

    assert preview.iloc[0][
        "validation_status"
    ] == "Ready to Promote"
    assert len(proposed) == 2
    assert set(proposed["posting_type"]) == {
        "Reversal",
        "Source Event",
    }
    assert round(
        proposed["signed_amount"].sum(),
        2,
    ) == -110.00

    reversal = proposed.loc[
        proposed["posting_type"] == "Reversal"
    ].iloc[0]
    assert reversal["signed_amount"] == -95.00
    assert reversal[
        "reversal_of_posting_line_id"
    ] == "pl_revenue"

    fee = proposed.loc[
        proposed["posting_type"] == "Source Event"
    ].iloc[0]
    assert fee["signed_amount"] == -15.00


def test_linked_guest_mismatch_blocks():
    approvals = approved()
    approvals.loc[
        0, "linked_guest"
    ] = "Wrong Guest"

    preview, proposed = (
        preview_linked_dispute_promotion(
            approvals=approvals,
            existing_history=history(),
        )
    )

    assert preview.iloc[0][
        "validation_status"
    ] == "Blocked"
    assert proposed.empty


def test_apply_is_idempotent():
    preview, first_history, updated = (
        apply_linked_dispute_promotion(
            approvals=approved(),
            existing_history=history(),
        )
    )

    approvals_again = approved()
    second_preview, second_history, _ = (
        apply_linked_dispute_promotion(
            approvals=approvals_again,
            existing_history=first_history,
        )
    )

    assert len(first_history) == 4
    assert len(second_history) == 4
    assert second_preview.iloc[0][
        "validation_status"
    ] == "Already Promoted"
