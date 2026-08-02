from __future__ import annotations

import pandas as pd

from src.review.stripe_seed_candidates import (
    build_stripe_seed_candidates,
)


def base_reconciliation(
    difference: float,
) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "exception_id": "exc1",
            "processor": "Stripe",
            "payout_id": "po1",
            "difference": difference,
            "evidence_confidence": "High",
            "resolution_blocked": "No",
            "exact_match_found": "Yes",
            "recommended_resolution": (
                "Create evidence-backed original charge seed"
            ),
        }
    ])


def base_family() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "exception_id": "exc1",
            "payout_id": "po1",
            "processor_account": "Main Guesty",
            "source_id": "ch1",
            "family_issue": (
                "Missing original charge history"
            ),
            "resolution_sign_safe": "Safe",
        }
    ])


def test_booking_com_canceled_motel_uses_gross_as_revenue():
    payments = pd.DataFrame([
        {
            "payout_id": "po1",
            "source_id": "ch1",
            "transaction_type": "charge",
            "payment_event_id": "evt1",
            "transaction_id": "txn1",
            "reservation_id": "r1",
            "channel_reservation_id": "597",
            "guest": "Paul",
            "listing": "DSRL Lodge Room 4",
            "transaction_date": "2026-06-16",
            "gross_amount": 95.00,
            "processor_fee": 3.44,
            "net_amount": 91.56,
        }
    ])

    reservations = pd.DataFrame([
        {
            "reservation_id": "r1",
            "channel_reservation_id": "597",
            "source": "Booking.com",
            "accommodation_revenue": 0.0,
            "state_tax": 0.0,
            "county_tax": 0.0,
            "local_tax": 0.0,
            "total_paid": 95.00,
            "total_refunded": 0.0,
            "total_payout": 0.0,
        }
    ])

    candidates, approvals, diagnostics = (
        build_stripe_seed_candidates(
            reconciliation_summary=base_reconciliation(
                -91.56
            ),
            stripe_families=base_family(),
            payment_ledger=payments,
            reservations=reservations,
        )
    )

    assert round(
        candidates["signed_amount"].sum(),
        2,
    ) == 91.56
    assert approvals.iloc[0][
        "approval_eligible"
    ] == "Yes"
    assert approvals.iloc[0][
        "allocation_method"
    ] == "Canceled Booking.com Gross"
    assert diagnostics.iloc[0][
        "evidence_level"
    ] == "High"


def test_vrbo_canceled_motel_reconstructs_5_4_percent_tax():
    payments = pd.DataFrame([
        {
            "payout_id": "po1",
            "source_id": "ch1",
            "transaction_type": "charge",
            "payment_event_id": "evt1",
            "transaction_id": "txn1",
            "reservation_id": "r1",
            "channel_reservation_id": "HA-1",
            "guest": "Randal",
            "listing": "DSRL Lodge Room 8",
            "transaction_date": "2026-06-19",
            "gross_amount": 177.07,
            "processor_fee": 6.15,
            "net_amount": 170.92,
        }
    ])

    reservations = pd.DataFrame([
        {
            "reservation_id": "r1",
            "channel_reservation_id": "HA-1",
            "source": "VRBO",
            "accommodation_revenue": 0.0,
            "state_tax": 0.0,
            "county_tax": 0.0,
            "local_tax": 0.0,
            "total_paid": 0.0,
            "total_refunded": 177.07,
            "total_payout": 0.0,
        }
    ])

    candidates, approvals, diagnostics = (
        build_stripe_seed_candidates(
            reconciliation_summary=base_reconciliation(
                -170.92
            ),
            stripe_families=base_family(),
            payment_ledger=payments,
            reservations=reservations,
        )
    )

    amounts = {
        row["allocation_type"]: row["signed_amount"]
        for _, row in candidates.iterrows()
    }

    assert amounts["Revenue"] == 168.00
    assert amounts["Lodging Tax 2.9%"] == 4.87
    assert amounts["Lodging Tax 2.5%"] == 4.20
    assert amounts["Processor Fee"] == -6.15
    assert approvals.iloc[0][
        "approval_eligible"
    ] == "Yes"
    assert diagnostics.iloc[0][
        "diagnostic_type"
    ] == "Canceled Reservation Reconstructed"


def test_website_rv_canceled_reservation_stays_blocked():
    payments = pd.DataFrame([
        {
            "payout_id": "po1",
            "source_id": "ch1",
            "transaction_type": "charge",
            "payment_event_id": "evt1",
            "transaction_id": "txn1",
            "reservation_id": "r1",
            "channel_reservation_id": "",
            "guest": "Johnathon",
            "listing": "DSRL RV 2",
            "transaction_date": "2026-06-14",
            "gross_amount": 115.91,
            "processor_fee": 4.12,
            "net_amount": 111.79,
        }
    ])

    reservations = pd.DataFrame([
        {
            "reservation_id": "r1",
            "channel_reservation_id": "",
            "source": "website",
            "accommodation_revenue": 0.0,
            "state_tax": 0.0,
            "county_tax": 0.0,
            "local_tax": 0.0,
            "total_paid": 115.91,
            "total_refunded": 0.0,
            "total_payout": 57.96,
        }
    ])

    candidates, approvals, diagnostics = (
        build_stripe_seed_candidates(
            reconciliation_summary=base_reconciliation(
                -111.79
            ),
            stripe_families=base_family(),
            payment_ledger=payments,
            reservations=reservations,
        )
    )

    assert candidates.empty
    assert approvals.iloc[0][
        "approval_eligible"
    ] == "No"
    assert diagnostics.iloc[0][
        "diagnostic_type"
    ] == "Canceled Allocation Not Proven"
