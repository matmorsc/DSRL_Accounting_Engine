from __future__ import annotations

import pandas as pd

from src.posting.ledger_deposit_drafts import (
    build_ledger_deposit_drafts,
    combine_ledger_sources,
    compare_deposit_drafts,
)


def history_rows():
    columns = [
        "posting_line_id","posting_group_id","payment_event_id","processor",
        "processor_account","transaction_id","transaction_type","transaction_date",
        "source_id","payout_id","reservation_id","channel_reservation_id","guest",
        "listing","account","class","description","signed_amount","posting_type",
        "reversal_of_posting_line_id","classification_source","created_by",
        "created_at","status","notes",
    ]

    persistent = pd.DataFrame([
        {
            **{column: "" for column in columns},
            "posting_line_id": "pl_charge_1",
            "payment_event_id": "charge_1",
            "processor": "Stripe",
            "processor_account": "Main",
            "source_id": "ch_1",
            "payout_id": "po_target",
            "account": "Revenue",
            "class": "Hospitality",
            "description": "Room",
            "signed_amount": "100.00",
            "posting_type": "Original",
            "status": "Active",
        },
        {
            **{column: "" for column in columns},
            "posting_line_id": "pl_charge_2",
            "payment_event_id": "charge_2",
            "processor": "Stripe",
            "processor_account": "Main",
            "source_id": "ch_2",
            "payout_id": "po_target",
            "account": "Revenue",
            "class": "Hospitality",
            "description": "Room",
            "signed_amount": "88.64",
            "posting_type": "Original",
            "status": "Active",
        },
    ])

    seeds = pd.DataFrame([
        {
            **{column: "" for column in columns},
            "posting_line_id": "pl_seed",
            "payment_event_id": "old_charge",
            "processor": "Stripe",
            "processor_account": "Main",
            "source_id": "ch_old",
            "payout_id": "",
            "account": "Revenue",
            "class": "RV",
            "description": "RV",
            "signed_amount": "105.19",
            "posting_type": "Original",
            "status": "Active",
        }
    ])

    reversals = pd.DataFrame([
        {
            **{column: "" for column in columns},
            "posting_line_id": "rl_refund",
            "payment_event_id": "refund",
            "processor": "Stripe",
            "processor_account": "Main",
            "source_id": "ch_old",
            "payout_id": "po_target",
            "account": "Revenue",
            "class": "RV",
            "description": "Refund",
            "signed_amount": "-54.54",
            "posting_type": "Reversal",
            "status": "Proposed",
        },
        {
            **{column: "" for column in columns},
            "posting_line_id": "rl_fee",
            "payment_event_id": "adjustment",
            "processor": "Stripe",
            "processor_account": "Main",
            "source_id": "ch_old",
            "payout_id": "po_target",
            "account": "Stripe Fees",
            "class": "RV",
            "description": "Fee refund",
            "signed_amount": "0.22",
            "posting_type": "Reversal",
            "status": "Proposed",
        },
    ])

    return persistent, seeds, reversals


def payout_ledger():
    return pd.DataFrame([
        {
            "payout_id": "po_target",
            "processor": "Stripe",
            "processor_account": "Main",
            "transaction_date": "2026-07-10",
            "payout_amount": 134.32,
        }
    ])


def test_ledger_sources_combine_without_blank_seed_payout():
    persistent, seeds, reversals = history_rows()
    combined = combine_ledger_sources(
        persistent_history=persistent,
        manual_seeds=seeds,
        reversal_preview=reversals,
    )
    assert len(combined) == 4
    assert "pl_seed" not in set(combined["posting_line_id"])


def test_ledger_draft_balances_known_structure():
    persistent, seeds, reversals = history_rows()
    combined = combine_ledger_sources(
        persistent_history=persistent,
        manual_seeds=seeds,
        reversal_preview=reversals,
    )
    drafts, lines = build_ledger_deposit_drafts(
        ledger_lines=combined,
        payout_ledger=payout_ledger(),
        tolerance=0.02,
    )
    assert len(drafts) == 1
    assert drafts.loc[0, "ledger_total"] == 134.32
    assert drafts.loc[0, "difference"] == 0.0
    assert drafts.loc[0, "balanced"] == "Yes"
    # The two identical revenue postings are intentionally grouped.
    assert len(lines) == 3


def test_comparison_marks_ledger_improvement():
    ledger = pd.DataFrame([{
        "payout_id": "po_target",
        "processor": "Stripe",
        "payout_amount": 134.32,
        "ledger_total": 134.32,
        "balanced": "Yes",
    }])
    legacy = pd.DataFrame([{
        "payout_id": "po_target",
        "draft_total": 188.64,
        "balanced": "No",
    }])
    comparison = compare_deposit_drafts(
        ledger_drafts=ledger,
        legacy_drafts=legacy,
    )
    assert comparison.loc[0, "comparison_status"] == "Improved"
    assert comparison.loc[0, "ledger_difference"] == 0.0
