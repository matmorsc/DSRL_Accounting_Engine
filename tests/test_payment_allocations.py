from __future__ import annotations

import pandas as pd

from src.posting.history import (
    POSTING_HISTORY_COLUMNS,
    build_proposed_posting_history,
)
from src.posting.history_review import (
    build_posting_history_review,
)
from src.posting.history_reversals import (
    build_reversal_preview,
)
from src.posting.payment_allocations import build_payment_allocations
from src.posting.deposit_drafts_v2 import build_deposit_drafts_v2


def rules():
    return {
        "amount_tolerance": 0.02,
        "classes": {
            "Cabin": "Cabins",
            "RV": "RV Sites",
            "Motel": "Hospitality",
            "tax": "Hospitality",
            "fees": "Hospitality",
        },
        "accounts": {
            "tax_payable": "Sales & Lodging Taxes Payable",
        },
        "processor_fee_accounts": {
            "Stripe": "Bank Charges & Fees:Stripe Processing Fees",
            "Airbnb": "",
        },
        "tax_descriptions": {
            "state_tax": "State",
            "county_tax": "County",
            "local_tax": "Local",
        },
        "marketplace_remitted_tax_processors": ["Airbnb"],
        "zero_basis_reconstruction": {
            "enabled_processors": ["Stripe"],
            "transaction_types": ["charge"],
            "state_rate": 0.025,
            "local_rate": 0.029,
        },
    }


def reservations():
    return pd.DataFrame([{
        "reservation_id": "r1",
        "channel_reservation_id": "A1",
        "guest": "Guest",
        "listing": "River Cabin",
        "property_class": "Cabin",
        "income_account": "Cabin Rent - Short-Term",
        "accommodation_revenue": 100.0,
        "state_tax": 5.0,
        "county_tax": 4.0,
        "local_tax": 6.0,
        "total_paid": 115.0,
        "total_refunded": 0.0,
    }])


def payments(processor="Stripe"):
    return pd.DataFrame([{
        "payment_event_id": "evt1",
        "processor": processor,
        "processor_account": "Main",
        "transaction_id": "txn1",
        "transaction_type": (
            "reservation" if processor == "Airbnb" else "charge"
        ),
        "transaction_date": "2026-06-01",
        "gross_amount": 115.0 if processor == "Stripe" else 100.0,
        "processor_fee": 3.0,
        "net_amount": 112.0 if processor == "Stripe" else 97.0,
        "reservation_id": "r1",
        "channel_reservation_id": "A1",
        "payout_id": "po1",
        "payout_assignment_status": "Assigned",
    }])


def posting(bank_amount):
    return pd.DataFrame([{
        "payout_id": "po1",
        "processor": "Stripe",
        "bank_transaction_id": "bank1",
        "bank_transaction_date": "2026-06-01",
        "bank_amount": bank_amount,
        "posting_status": "Unposted",
        "generate_entry": "Yes",
    }])


def payout(bank_amount, processor="Stripe"):
    return pd.DataFrame([{
        "payout_id": "po1",
        "processor": processor,
        "processor_account": "Main",
        "transaction_date": "2026-06-01",
        "payout_amount": bank_amount,
        "bank_transaction_id": "bank1",
        "bank_transaction_date": "2026-06-01",
        "bank_amount": bank_amount,
    }])


def test_direct_event_allocates_exact_gross():
    allocations, diagnostics = build_payment_allocations(
        payment_ledger=payments(),
        reservations=reservations(),
        rules=rules(),
    )

    non_fee = allocations.loc[
        allocations["allocation_type"].ne("Processor Fee")
    ]

    assert round(non_fee["amount"].sum(), 2) == 115.0
    assert round(allocations["amount"].sum(), 2) == 112.0
    assert diagnostics.empty


def test_marketplace_event_excludes_tax():
    allocations, diagnostics = build_payment_allocations(
        payment_ledger=payments(processor="Airbnb"),
        reservations=reservations(),
        rules=rules(),
    )

    assert set(allocations["allocation_type"]) == {
        "Revenue",
        "Processor Fee",
    }
    assert round(allocations["amount"].sum(), 2) == 97.0
    assert "Missing Fee Account" in set(
        diagnostics["diagnostic_type"]
    )


def test_v2_draft_balances_from_allocations():
    allocations, _ = build_payment_allocations(
        payment_ledger=payments(),
        reservations=reservations(),
        rules=rules(),
    )

    summaries, lines = build_deposit_drafts_v2(
        posting_status=posting(112.0),
        payout_ledger=payout(112.0),
        allocations=allocations,
        rules=rules(),
    )

    assert summaries.loc[0, "balanced"] == "Yes"
    assert summaries.loc[0, "draft_status"] == "Ready for Review"
    assert round(lines["amount"].sum(), 2) == 112.0


def test_unlinked_event_is_diagnostic():
    frame = payments()
    frame.loc[0, "reservation_id"] = "missing"
    frame.loc[0, "channel_reservation_id"] = ""

    allocations, diagnostics = build_payment_allocations(
        payment_ledger=frame,
        reservations=reservations(),
        rules=rules(),
    )

    assert allocations.empty
    assert diagnostics.loc[0, "diagnostic_type"] == (
        "Unlinked Payment Event"
    )


def _zero_basis_reservation(
    *,
    reservation_id: str,
    listing: str,
    property_class: str,
    income_account: str,
):
    return pd.DataFrame([
        {
            "reservation_id": reservation_id,
            "channel_reservation_id": "",
            "guest": "Guest",
            "listing": listing,
            "property_class": property_class,
            "income_account": income_account,
            "accommodation_revenue": 0.0,
            "state_tax": 0.0,
            "county_tax": 0.0,
            "local_tax": 0.0,
            "total_paid": 0.0,
            "total_refunded": 0.0,
        }
    ])


def _stripe_charge(
    *,
    event_id: str,
    transaction_id: str,
    source_id: str,
    payout_id: str,
    reservation_id: str,
    listing: str,
    gross: float,
    fee: float,
    net: float,
):
    return {
        "payment_event_id": event_id,
        "processor": "Stripe",
        "processor_account": "Main",
        "transaction_id": transaction_id,
        "transaction_type": "charge",
        "transaction_date": "2026-06-01",
        "source_id": source_id,
        "gross_amount": gross,
        "processor_fee": fee,
        "net_amount": net,
        "reservation_id": reservation_id,
        "channel_reservation_id": "",
        "guest": "Guest",
        "listing": listing,
        "payout_id": payout_id,
        "payout_assignment_status": "Assigned",
    }


def _stripe_source_event(
    *,
    event_id: str,
    transaction_id: str,
    source_id: str,
    payout_id: str,
    reservation_id: str,
    listing: str,
    transaction_type: str,
    gross_amount: float,
):
    return {
        "payment_event_id": event_id,
        "processor": "Stripe",
        "processor_account": "Main",
        "transaction_id": transaction_id,
        "transaction_type": transaction_type,
        "transaction_date": "2026-06-02",
        "source_id": source_id,
        "gross_amount": gross_amount,
        "processor_fee": 0.0,
        "net_amount": gross_amount,
        "reservation_id": reservation_id,
        "channel_reservation_id": "",
        "guest": "Guest",
        "listing": listing,
        "payout_id": payout_id,
        "payout_assignment_status": "Assigned",
    }


def _sum_type(
    allocations: pd.DataFrame,
    allocation_type: str,
) -> float:
    return round(
        pd.to_numeric(
            allocations.loc[
                allocations["allocation_type"].eq(
                    allocation_type
                ),
                "amount",
            ],
            errors="coerce",
        )
        .fillna(0)
        .sum(),
        2,
    )


def _empty_history() -> pd.DataFrame:
    return pd.DataFrame(
        columns=POSTING_HISTORY_COLUMNS
    )


def test_zero_basis_eligible_charge_reconstructs_lines():
    payment_ledger = pd.DataFrame(
        [
            _stripe_charge(
                event_id="evt_alan",
                transaction_id="txn_alan",
                source_id="ch_alan",
                payout_id="po_alan",
                reservation_id="r_alan",
                listing="DSRL Lodge Room 4",
                gross=115.00,
                fee=4.10,
                net=110.90,
            )
        ]
    )
    reservation = _zero_basis_reservation(
        reservation_id="r_alan",
        listing="DSRL Lodge Room 4",
        property_class="Motel",
        income_account="Motel Rent - Short Term",
    )

    allocations, diagnostics = build_payment_allocations(
        payment_ledger=payment_ledger,
        reservations=reservation,
        rules=rules(),
        existing_history=_empty_history(),
    )

    assert set(allocations["allocation_type"]) == {
        "Revenue",
        "State Tax",
        "Local Tax",
        "Processor Fee",
    }
    assert _sum_type(allocations, "Revenue") == 109.11
    assert _sum_type(allocations, "State Tax") == 2.73
    assert _sum_type(allocations, "Local Tax") == 3.16
    assert _sum_type(allocations, "Processor Fee") == -4.10
    assert round(allocations["amount"].sum(), 2) == 110.90
    assert (
        "Zero-Basis Reconstruction"
        in set(diagnostics["diagnostic_type"])
    )


def test_zero_basis_ineligible_fails_closed():
    payment_ledger = pd.DataFrame(
        [
            _stripe_charge(
                event_id="evt_bad",
                transaction_id="txn_bad",
                source_id="ch_bad",
                payout_id="po_bad",
                reservation_id="r_bad",
                listing="DSRL River Cabin",
                gross=200.00,
                fee=6.00,
                net=194.00,
            )
        ]
    )
    reservation = _zero_basis_reservation(
        reservation_id="r_bad",
        listing="DSRL River Cabin",
        property_class="Cabin",
        income_account="Cabin Rent - Short-Term",
    )
    unsafe_rules = rules()
    unsafe_rules["zero_basis_reconstruction"] = {
        "enabled_processors": ["Stripe"],
        "transaction_types": ["charge"],
        "state_rate": 0.025,
    }

    allocations, diagnostics = build_payment_allocations(
        payment_ledger=payment_ledger,
        reservations=reservation,
        rules=unsafe_rules,
        existing_history=_empty_history(),
    )

    assert set(allocations["allocation_type"]) == {
        "Processor Fee"
    }
    assert round(allocations["amount"].sum(), 2) == -6.00
    skipped = diagnostics.loc[
        diagnostics["diagnostic_type"].eq(
            "Zero-Basis Reconstruction Skipped"
        )
    ]
    assert len(skipped) == 1
    assert (
        "Missing or invalid zero-basis local tax rate configuration."
        in str(skipped.iloc[0]["detail"])
    )


def test_zero_basis_skip_when_active_original_exists():
    payment_ledger = pd.DataFrame(
        [
            _stripe_charge(
                event_id="evt_history",
                transaction_id="txn_history",
                source_id="ch_history",
                payout_id="po_history",
                reservation_id="r_history",
                listing="DSRL RV 9",
                gross=140.72,
                fee=4.94,
                net=135.78,
            )
        ]
    )
    reservation = _zero_basis_reservation(
        reservation_id="r_history",
        listing="DSRL RV 9",
        property_class="RV",
        income_account="RV Rent - Nightly",
    )
    existing = pd.DataFrame(
        [
            {
                "posting_line_id": "pl1",
                "posting_group_id": "pg1",
                "payment_event_id": "evt_history",
                "posting_type": "Original",
                "status": "Active",
            }
        ]
    )

    allocations, diagnostics = build_payment_allocations(
        payment_ledger=payment_ledger,
        reservations=reservation,
        rules=rules(),
        existing_history=existing,
    )

    assert set(allocations["allocation_type"]) == {
        "Processor Fee"
    }
    skipped = diagnostics.loc[
        diagnostics["diagnostic_type"].eq(
            "Zero-Basis Reconstruction Skipped"
        )
    ]
    assert len(skipped) == 1
    assert (
        "Event already has active Original posting history."
        in str(skipped.iloc[0]["detail"])
    )


def _run_family_flow(
    *,
    charge_event: dict,
    refund_event: dict,
    adjustment_event: dict,
    reservation: pd.DataFrame,
):
    ledger = pd.DataFrame(
        [charge_event, adjustment_event, refund_event]
    )
    allocations, diagnostics = build_payment_allocations(
        payment_ledger=ledger,
        reservations=reservation,
        rules=rules(),
        existing_history=_empty_history(),
    )

    proposed, history_diags = build_proposed_posting_history(
        allocations=allocations,
        payment_ledger=ledger,
        existing_history=_empty_history(),
        created_at="2026-10-01T12:00:00",
    )
    review = build_posting_history_review(
        proposed_history=proposed,
        payment_ledger=ledger,
        tolerance=0.02,
    )

    promoted = proposed.copy()
    promoted["status"] = "Active"

    reversals, reversal_review = build_reversal_preview(
        payment_ledger=ledger,
        posting_history=promoted,
        created_at="2026-10-01T12:10:00",
    )

    return (
        allocations,
        diagnostics,
        history_diags,
        review,
        reversals,
        reversal_review,
    )


def test_ian_family_reconstructs_and_reverses_to_expected_net():
    charge = _stripe_charge(
        event_id="Main Guesty::txn_3U8k5rJtejknM7350yDDXzcY",
        transaction_id="txn_3U8k5rJtejknM7350yDDXzcY",
        source_id="ch_3U8k5rJtejknM7350OsSPBIS",
        payout_id="po_1UAIv3JtejknM735G43m57RN",
        reservation_id="6a8f1667c06d20172ddccb26",
        listing="DSRL River Cabin",
        gross=347.52,
        fee=11.77,
        net=335.75,
    )
    adjustment = _stripe_source_event(
        event_id="Main Guesty::txn_1U9Aa0JtejknM735EOo6zqz5",
        transaction_id="txn_1U9Aa0JtejknM735EOo6zqz5",
        source_id="ch_3U8k5rJtejknM7350OsSPBIS",
        payout_id="po_1UAIv3JtejknM735G43m57RN",
        reservation_id="6a8f1667c06d20172ddccb26",
        listing="DSRL River Cabin",
        transaction_type="adjustment",
        gross_amount=1.39,
    )
    refund = _stripe_source_event(
        event_id="Main Guesty::txn_3U8k5rJtejknM7350I7XiCzh",
        transaction_id="txn_3U8k5rJtejknM7350I7XiCzh",
        source_id="ch_3U8k5rJtejknM7350OsSPBIS",
        payout_id="po_1UAIv3JtejknM735G43m57RN",
        reservation_id="6a8f1667c06d20172ddccb26",
        listing="DSRL River Cabin",
        transaction_type="refund",
        gross_amount=-347.52,
    )

    reservation = _zero_basis_reservation(
        reservation_id="6a8f1667c06d20172ddccb26",
        listing="DSRL River Cabin",
        property_class="Cabin",
        income_account="Cabin Rent - Short-Term",
    )

    (
        allocations,
        diagnostics,
        history_diags,
        review,
        reversals,
        reversal_review,
    ) = _run_family_flow(
        charge_event=charge,
        adjustment_event=adjustment,
        refund_event=refund,
        reservation=reservation,
    )

    assert history_diags.empty
    assert reversal_review.empty
    assert (
        "Zero-Basis Reconstruction"
        in set(diagnostics["diagnostic_type"])
    )
    assert _sum_type(allocations, "Revenue") == 329.72
    assert _sum_type(allocations, "State Tax") == 8.24
    assert _sum_type(allocations, "Local Tax") == 9.56
    assert _sum_type(allocations, "Processor Fee") == -11.77
    assert round(allocations["amount"].sum(), 2) == 335.75

    review_row = review.iloc[0]
    assert review_row["review_status"] == "Ready for Promotion"
    assert round(float(review_row["difference"]), 2) == 0.0

    refund_sum = round(
        pd.to_numeric(
            reversals.loc[
                reversals["payment_event_id"].eq(
                    refund["payment_event_id"]
                ),
                "signed_amount",
            ],
            errors="coerce",
        ).sum(),
        2,
    )
    adjustment_sum = round(
        pd.to_numeric(
            reversals.loc[
                reversals["payment_event_id"].eq(
                    adjustment["payment_event_id"]
                ),
                "signed_amount",
            ],
            errors="coerce",
        ).sum(),
        2,
    )
    assert refund_sum == -347.52
    assert adjustment_sum == 1.39
    assert round(335.75 + refund_sum + adjustment_sum, 2) == -10.38


def test_patrick_family_reconstructs_and_reverses_to_expected_net():
    charge = _stripe_charge(
        event_id="Main Guesty::txn_3UEIzgJtejknM7351jPlr6kT",
        transaction_id="txn_3UEIzgJtejknM7351jPlr6kT",
        source_id="ch_3UEIzgJtejknM7351yhAnctc",
        payout_id="po_1UFjpVJtejknM735TNhwB2OO",
        reservation_id="6aa3550472d8966c441295df",
        listing="DSRL RV  9",
        gross=140.72,
        fee=4.94,
        net=135.78,
    )
    adjustment = _stripe_source_event(
        event_id="Main Guesty::txn_1UEcAqJtejknM735Mm7Ip4zG",
        transaction_id="txn_1UEcAqJtejknM735Mm7Ip4zG",
        source_id="ch_3UEIzgJtejknM7351yhAnctc",
        payout_id="po_1UFjpVJtejknM735TNhwB2OO",
        reservation_id="6aa3550472d8966c441295df",
        listing="DSRL RV  9",
        transaction_type="adjustment",
        gross_amount=0.56,
    )
    refund = _stripe_source_event(
        event_id="Main Guesty::txn_3UEIzgJtejknM73517aIWtuv",
        transaction_id="txn_3UEIzgJtejknM73517aIWtuv",
        source_id="ch_3UEIzgJtejknM7351yhAnctc",
        payout_id="po_1UFjpVJtejknM735TNhwB2OO",
        reservation_id="6aa3550472d8966c441295df",
        listing="DSRL RV  9",
        transaction_type="refund",
        gross_amount=-140.72,
    )

    reservation = _zero_basis_reservation(
        reservation_id="6aa3550472d8966c441295df",
        listing="DSRL RV  9",
        property_class="RV",
        income_account="RV Rent - Nightly",
    )

    (
        allocations,
        diagnostics,
        _,
        review,
        reversals,
        reversal_review,
    ) = _run_family_flow(
        charge_event=charge,
        adjustment_event=adjustment,
        refund_event=refund,
        reservation=reservation,
    )

    assert reversal_review.empty
    assert (
        "Zero-Basis Reconstruction"
        in set(diagnostics["diagnostic_type"])
    )
    assert _sum_type(allocations, "Revenue") == 133.51
    assert _sum_type(allocations, "State Tax") == 3.34
    assert _sum_type(allocations, "Local Tax") == 3.87
    assert _sum_type(allocations, "Processor Fee") == -4.94
    assert round(allocations["amount"].sum(), 2) == 135.78

    review_row = review.iloc[0]
    assert review_row["review_status"] == "Ready for Promotion"
    assert round(float(review_row["difference"]), 2) == 0.0

    refund_sum = round(
        pd.to_numeric(
            reversals.loc[
                reversals["payment_event_id"].eq(
                    refund["payment_event_id"]
                ),
                "signed_amount",
            ],
            errors="coerce",
        ).sum(),
        2,
    )
    adjustment_sum = round(
        pd.to_numeric(
            reversals.loc[
                reversals["payment_event_id"].eq(
                    adjustment["payment_event_id"]
                ),
                "signed_amount",
            ],
            errors="coerce",
        ).sum(),
        2,
    )
    assert refund_sum == -140.72
    assert adjustment_sum == 0.56
    assert round(135.78 + refund_sum + adjustment_sum, 2) == -4.38


def test_dale_zero_basis_reconstructs_expected_charge_total():
    payment_ledger = pd.DataFrame(
        [
            _stripe_charge(
                event_id="Main Guesty::txn_3U1vijJtejknM73504a3Hder",
                transaction_id="txn_3U1vijJtejknM73504a3Hder",
                source_id="ch_3U1vijJtejknM7350ZLX6IuN",
                payout_id="po_1U3m4eJtejknM735TxqeEXdH",
                reservation_id="6a76531d6c3929266261d3ab",
                listing="DSRL Lodge Room 7",
                gross=625.19,
                fee=20.93,
                net=604.26,
            )
        ]
    )
    reservation = _zero_basis_reservation(
        reservation_id="6a76531d6c3929266261d3ab",
        listing="DSRL Lodge Room 7",
        property_class="Motel",
        income_account="Motel Rent - Short Term",
    )

    allocations, diagnostics = build_payment_allocations(
        payment_ledger=payment_ledger,
        reservations=reservation,
        rules=rules(),
        existing_history=_empty_history(),
    )

    assert _sum_type(allocations, "Revenue") == 593.16
    assert _sum_type(allocations, "State Tax") == 14.83
    assert _sum_type(allocations, "Local Tax") == 17.20
    assert _sum_type(allocations, "Processor Fee") == -20.93
    assert round(allocations["amount"].sum(), 2) == 604.26
    assert (
        "Zero-Basis Reconstruction"
        in set(diagnostics["diagnostic_type"])
    )
