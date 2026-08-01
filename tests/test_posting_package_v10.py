from __future__ import annotations

import pandas as pd

from src.presentation.posting_package import build_posting_package


def drafts():
    return pd.DataFrame([{
        "payout_id":"po_target","processor":"Stripe",
        "processor_account":"Main Guesty","payout_date":"2026-07-08",
        "payout_amount":134.32,"ledger_total":134.32,"difference":0.0,
        "balanced":"Yes","draft_status":"Ready for Review","review_reason":"",
        "ledger_line_count":9,"payment_event_count":4,"source_count":3,
        "reversal_line_count":4,"seed_line_count":0,
    }])


def lines():
    return pd.DataFrame([
        {
            "payout_id":"po_target","line_number":1,"account":"Revenue",
            "class":"Hospitality","description":"Revenue","posting_type":"Original",
            "ledger_source":"Persistent History","amount":188.64,
            "posting_line_count":2,"payment_event_count":2,"source_count":2,
        },
        {
            "payout_id":"po_target","line_number":2,"account":"RV Rent",
            "class":"RV Sites","description":"Refund","posting_type":"Reversal",
            "ledger_source":"Reversal Preview","amount":-54.54,
            "posting_line_count":3,"payment_event_count":1,"source_count":1,
        },
        {
            "payout_id":"po_target","line_number":3,"account":"Stripe Fees",
            "class":"RV Sites","description":"Fee refund","posting_type":"Reversal",
            "ledger_source":"Reversal Preview","amount":0.22,
            "posting_line_count":1,"payment_event_count":1,"source_count":1,
        },
    ])


def comparison():
    return pd.DataFrame([{
        "payout_id":"po_target","legacy_draft_total":188.64,
        "legacy_difference":54.32,"comparison_status":"Improved",
    }])


def payout_ledger():
    return pd.DataFrame([{
        "payout_id":"po_target","bank_transaction_id":"bank_1",
        "bank_transaction_date":"2026-07-10","bank_amount":134.32,
    }])


def bank_transactions():
    return pd.DataFrame([{
        "transaction_id":"bank_1","transaction_date":"2026-07-10",
        "description":"STRIPE PAYOUT","amount":134.32,
    }])


def test_summary_contains_human_facing_fields():
    summary, package_lines = build_posting_package(
        deposit_drafts=drafts(), deposit_lines=lines(),
        comparison=comparison(), payout_ledger=payout_ledger(),
        bank_transactions=bank_transactions(),
    )
    assert summary.loc[0, "confidence"] == "Ready"
    assert summary.loc[0, "comparison_status"] == "Improved"
    assert "reversal" in summary.loc[0, "review_notes"].lower()
    assert summary.loc[0, "sheet_name"] == "Stripe - 2026-07-10"
    assert len(package_lines) == 3


def test_package_ids_are_deterministic():
    first_summary, first_lines = build_posting_package(
        deposit_drafts=drafts(), deposit_lines=lines(),
        comparison=comparison(), payout_ledger=payout_ledger(),
        bank_transactions=bank_transactions(),
    )
    second_summary, second_lines = build_posting_package(
        deposit_drafts=drafts(), deposit_lines=lines(),
        comparison=comparison(), payout_ledger=payout_ledger(),
        bank_transactions=bank_transactions(),
    )
    assert first_summary.loc[0, "package_id"] == second_summary.loc[0, "package_id"]
    assert set(first_lines["package_id"]) == set(second_lines["package_id"])


def test_line_notes_explain_reversals():
    _, package_lines = build_posting_package(
        deposit_drafts=drafts(), deposit_lines=lines(),
        comparison=comparison(), payout_ledger=payout_ledger(),
        bank_transactions=bank_transactions(),
    )
    notes = package_lines.loc[
        package_lines["posting_type"].eq("Reversal"), "line_note"
    ]
    assert notes.str.contains("Historical reversal", case=False).all()
    assert notes.str.contains("posting-history reversal", case=False).all()


def test_payout_ledger_supplies_bank_identity():
    summary, _ = build_posting_package(
        deposit_drafts=drafts(), deposit_lines=lines(),
        comparison=comparison(), payout_ledger=payout_ledger(),
        bank_transactions=bank_transactions(),
    )
    assert summary.loc[0, "bank_transaction_date"] == "2026-07-10"
    assert summary.loc[0, "bank_amount"] == 134.32
    assert summary.loc[0, "bank_description"] == "STRIPE PAYOUT"
    assert summary.loc[0, "bank_balanced"] == "Yes"


def test_missing_bank_match_needs_review():
    empty_payout = pd.DataFrame([{"payout_id":"po_target"}])
    summary, _ = build_posting_package(
        deposit_drafts=drafts(), deposit_lines=lines(),
        comparison=comparison(), payout_ledger=empty_payout,
        bank_transactions=bank_transactions(),
    )
    assert summary.loc[0, "bank_balanced"] == "No"
    assert summary.loc[0, "confidence"] == "Needs Review"
