from __future__ import annotations

import pandas as pd

from src.posting.history import (
    POSTING_HISTORY_COLUMNS,
)
from src.posting.history_reversals import (
    build_reversal_preview,
)


def history_row(**updates):
    row = {
        column: ""
        for column in POSTING_HISTORY_COLUMNS
    }
    row.update(updates)
    return row


def original_history():
    return pd.DataFrame([
        history_row(
            posting_line_id="pl_rev",
            posting_group_id="pg_charge",
            payment_event_id="evt_charge",
            processor="Stripe",
            processor_account="Main Guesty",
            transaction_id="txn_charge",
            transaction_type="charge",
            transaction_date="2026-07-01",
            source_id="ch_1",
            payout_id="po_old",
            reservation_id="r1",
            guest="Guest",
            listing="RV 8",
            account="RV Rent - Nightly",
            **{"class": "RV Sites"},
            description="RV 8",
            signed_amount="103.50",
            posting_type="Original",
            status="Active",
        ),
        history_row(
            posting_line_id="pl_state",
            posting_group_id="pg_charge",
            payment_event_id="evt_charge",
            processor="Stripe",
            processor_account="Main Guesty",
            transaction_id="txn_charge",
            transaction_type="charge",
            transaction_date="2026-07-01",
            source_id="ch_1",
            payout_id="po_old",
            account="Sales & Lodging Taxes Payable",
            **{"class": "Hospitality"},
            description="State",
            signed_amount="3.00",
            posting_type="Original",
            status="Active",
        ),
        history_row(
            posting_line_id="pl_county",
            posting_group_id="pg_charge",
            payment_event_id="evt_charge",
            processor="Stripe",
            processor_account="Main Guesty",
            transaction_id="txn_charge",
            transaction_type="charge",
            transaction_date="2026-07-01",
            source_id="ch_1",
            payout_id="po_old",
            account="Sales & Lodging Taxes Payable",
            **{"class": "Hospitality"},
            description="County",
            signed_amount="2.59",
            posting_type="Original",
            status="Active",
        ),
        history_row(
            posting_line_id="pl_fee",
            posting_group_id="pg_charge",
            payment_event_id="evt_charge",
            processor="Stripe",
            processor_account="Main Guesty",
            transaction_id="txn_charge",
            transaction_type="charge",
            transaction_date="2026-07-01",
            source_id="ch_1",
            payout_id="po_old",
            account="Bank Charges & Fees:Stripe Processing Fees",
            **{"class": "RV Sites"},
            description="Stripe processing fees",
            signed_amount="-3.90",
            posting_type="Original",
            status="Active",
        ),
    ])


def payment_ledger():
    return pd.DataFrame([
        {
            "payment_event_id": "evt_refund",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_refund",
            "transaction_type": "refund",
            "transaction_date": "2026-07-07",
            "source_id": "ch_1",
            "payout_id": "po_target",
            "gross_amount": -54.54,
        },
        {
            "payment_event_id": "evt_adjustment",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_adjustment",
            "transaction_type": "adjustment",
            "transaction_date": "2026-07-07",
            "source_id": "ch_1",
            "payout_id": "po_target",
            "gross_amount": 0.22,
        },
    ])


def test_refund_reverses_positive_original_lines():
    reversals, review = build_reversal_preview(
        payment_ledger=payment_ledger(),
        posting_history=original_history(),
        created_at="2026-08-01T16:00:00",
    )

    refund = reversals.loc[
        reversals["payment_event_id"].eq(
            "evt_refund"
        )
    ]

    assert len(refund) == 3
    assert round(
        pd.to_numeric(
            refund["signed_amount"]
        ).sum(),
        2,
    ) == -54.54
    assert set(
        refund["reversal_of_posting_line_id"]
    ) == {
        "pl_rev",
        "pl_state",
        "pl_county",
    }
    assert review.empty


def test_adjustment_reverses_fee_line():
    reversals, review = build_reversal_preview(
        payment_ledger=payment_ledger(),
        posting_history=original_history(),
        created_at="2026-08-01T16:00:00",
    )

    adjustment = reversals.loc[
        reversals["payment_event_id"].eq(
            "evt_adjustment"
        )
    ]

    assert len(adjustment) == 1
    assert float(
        adjustment.iloc[0]["signed_amount"]
    ) == 0.22
    assert (
        adjustment.iloc[0][
            "reversal_of_posting_line_id"
        ]
        == "pl_fee"
    )
    assert review.empty


def test_missing_original_history_goes_to_review():
    reversals, review = build_reversal_preview(
        payment_ledger=payment_ledger(),
        posting_history=pd.DataFrame(
            columns=POSTING_HISTORY_COLUMNS
        ),
        created_at="2026-08-01T16:00:00",
    )

    assert reversals.empty
    assert len(review) == 2
    assert set(review["review_status"]) == {
        "Missing Original Posting History"
    }


def test_reversal_ids_are_deterministic():
    first, _ = build_reversal_preview(
        payment_ledger=payment_ledger(),
        posting_history=original_history(),
        created_at="2026-08-01T16:00:00",
    )
    second, _ = build_reversal_preview(
        payment_ledger=payment_ledger(),
        posting_history=original_history(),
        created_at="2026-08-02T16:00:00",
    )

    assert list(first["posting_line_id"]) == list(
        second["posting_line_id"]
    )
