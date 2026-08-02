from __future__ import annotations

import hashlib

import pandas as pd


CANDIDATE_COLUMNS = [
    "candidate_id",
    "candidate_group_id",
    "exception_id",
    "payout_id",
    "processor_account",
    "source_id",
    "payment_event_id",
    "transaction_id",
    "reservation_id",
    "channel_reservation_id",
    "guest",
    "listing",
    "reservation_source",
    "transaction_date",
    "line_number",
    "allocation_type",
    "account",
    "class",
    "description",
    "signed_amount",
    "charge_gross",
    "charge_fee",
    "charge_net",
    "reservation_found",
    "candidate_status",
    "allocation_method",
    "evidence_level",
    "evidence_source",
    "evidence_reason",
    "generated_by",
]

APPROVAL_COLUMNS = [
    "candidate_group_id",
    "exception_id",
    "payout_id",
    "processor_account",
    "source_id",
    "payment_event_id",
    "guest",
    "listing",
    "reservation_source",
    "expected_payout_difference",
    "proposed_seed_effect",
    "remaining_difference_after_seed",
    "line_count",
    "reservation_found",
    "allocation_method",
    "evidence_level",
    "sign_safe",
    "exact_match",
    "approval_eligible",
    "approval_status",
    "review_notes",
]

DIAGNOSTIC_COLUMNS = [
    "candidate_group_id",
    "exception_id",
    "payout_id",
    "source_id",
    "payment_event_id",
    "guest",
    "listing",
    "reservation_source",
    "reservation_id",
    "channel_reservation_id",
    "charge_gross",
    "charge_fee",
    "charge_net",
    "reservation_revenue",
    "reservation_state_tax",
    "reservation_county_tax",
    "reservation_local_tax",
    "reservation_component_total",
    "reservation_total_paid",
    "reservation_total_refunded",
    "reservation_total_payout",
    "gross_evidence_amount",
    "gross_evidence_match",
    "allocation_method",
    "evidence_level",
    "reconstructed_revenue",
    "reconstructed_tax_2_9",
    "reconstructed_tax_2_5",
    "reconstructed_gross",
    "gross_component_difference",
    "candidate_status",
    "diagnostic_type",
    "diagnostic_detail",
    "possible_cause",
]


def _text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def _money(value: object) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def _stable_id(prefix: str, parts: list[str]) -> str:
    digest = hashlib.sha256(
        "|".join(parts).encode("utf-8")
    ).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _class_for_listing(listing: str) -> str:
    return "RV Sites" if "rv" in listing.lower() else "Hospitality"


def _revenue_account(listing: str) -> str:
    text = listing.lower()
    if "rv" in text:
        return "RV Rent - Nightly"
    if "cabin" in text:
        return "Cabin Rent - Short-Term"
    return "Motel Rent - Short Term"


def _reservation_lookup(
    reservations: pd.DataFrame,
) -> tuple[dict[str, pd.Series], dict[str, pd.Series]]:
    by_id: dict[str, pd.Series] = {}
    by_channel: dict[str, pd.Series] = {}

    if reservations.empty:
        return by_id, by_channel

    for _, row in reservations.iterrows():
        reservation_id = _text(row.get("reservation_id"))
        channel_id = _text(row.get("channel_reservation_id"))

        if reservation_id:
            by_id[reservation_id] = row
        if channel_id:
            by_channel[channel_id] = row

    return by_id, by_channel


def _find_reservation(
    *,
    charge: pd.Series,
    by_id: dict[str, pd.Series],
    by_channel: dict[str, pd.Series],
) -> pd.Series | None:
    reservation_id = _text(charge.get("reservation_id"))
    channel_id = _text(charge.get("channel_reservation_id"))

    if reservation_id and reservation_id in by_id:
        return by_id[reservation_id]
    if channel_id and channel_id in by_channel:
        return by_channel[channel_id]
    return None


def _reservation_components(
    reservation: pd.Series | None,
) -> dict[str, float]:
    if reservation is None:
        return {
            "revenue": 0.0,
            "state_tax": 0.0,
            "county_tax": 0.0,
            "local_tax": 0.0,
            "total": 0.0,
            "total_paid": 0.0,
            "total_refunded": 0.0,
            "total_payout": 0.0,
        }

    revenue = _money(reservation.get("accommodation_revenue"))
    state_tax = _money(reservation.get("state_tax"))
    county_tax = _money(reservation.get("county_tax"))
    local_tax = _money(reservation.get("local_tax"))

    return {
        "revenue": revenue,
        "state_tax": state_tax,
        "county_tax": county_tax,
        "local_tax": local_tax,
        "total": round(
            revenue + state_tax + county_tax + local_tax,
            2,
        ),
        "total_paid": _money(reservation.get("total_paid")),
        "total_refunded": _money(
            reservation.get("total_refunded")
        ),
        "total_payout": _money(reservation.get("total_payout")),
    }


def _gross_evidence(
    *,
    components: dict[str, float],
    charge_gross: float,
) -> tuple[float, str]:
    candidates = [
        components["total_paid"],
        components["total_refunded"],
        components["total_payout"],
    ]

    for amount in candidates:
        if amount > 0 and abs(amount - charge_gross) <= 0.02:
            return amount, "Yes"

    positive = [amount for amount in candidates if amount > 0]
    return (
        positive[0] if positive else 0.0,
        "No",
    )


def _tax_reconstruction(
    gross: float,
) -> tuple[float, float, float, float] | None:
    """
    Search penny-level revenue amounts for an exact gross tie using:
      tax 1 = round(revenue * 2.9%, 2)
      tax 2 = round(revenue * 2.5%, 2)

    The narrow search avoids relying on a single algebraic division that
    can differ by pennies after line-level rounding.
    """
    approximate_revenue = gross / 1.054
    start_cents = max(
        0,
        int(round(approximate_revenue * 100)) - 10,
    )
    end_cents = int(round(approximate_revenue * 100)) + 10

    solutions: list[
        tuple[float, float, float, float]
    ] = []

    for cents in range(start_cents, end_cents + 1):
        revenue = round(cents / 100, 2)
        tax_2_9 = round(revenue * 0.029, 2)
        tax_2_5 = round(revenue * 0.025, 2)
        reconstructed = round(
            revenue + tax_2_9 + tax_2_5,
            2,
        )
        if abs(reconstructed - gross) <= 0.005:
            solutions.append(
                (
                    revenue,
                    tax_2_9,
                    tax_2_5,
                    reconstructed,
                )
            )

    if len(solutions) != 1:
        return None

    return solutions[0]


def _standard_lines(
    *,
    listing: str,
    revenue: float,
    tax_2_9: float,
    tax_2_5: float,
    charge_fee: float,
) -> list[dict[str, object]]:
    qb_class = _class_for_listing(listing)
    lines: list[dict[str, object]] = []

    if abs(revenue) > 0.005:
        lines.append(
            {
                "allocation_type": "Revenue",
                "account": _revenue_account(listing),
                "class": qb_class,
                "description": listing,
                "signed_amount": revenue,
            }
        )

    if abs(tax_2_9) > 0.005:
        lines.append(
            {
                "allocation_type": "Lodging Tax 2.9%",
                "account": "Sales & Lodging Taxes Payable",
                "class": qb_class,
                "description": "Lodging tax 2.9%",
                "signed_amount": tax_2_9,
            }
        )

    if abs(tax_2_5) > 0.005:
        lines.append(
            {
                "allocation_type": "Lodging Tax 2.5%",
                "account": "Sales & Lodging Taxes Payable",
                "class": qb_class,
                "description": "Lodging tax 2.5%",
                "signed_amount": tax_2_5,
            }
        )

    if abs(charge_fee) > 0.005:
        lines.append(
            {
                "allocation_type": "Processor Fee",
                "account": (
                    "Bank Charges & Fees:"
                    "Stripe Processing Fees"
                ),
                "class": qb_class,
                "description": "Stripe processing fees",
                "signed_amount": -abs(charge_fee),
            }
        )

    return lines


def _authoritative_lines(
    *,
    reservation: pd.Series,
    listing: str,
    charge_gross: float,
    charge_fee: float,
) -> tuple[
    list[dict[str, object]],
    str,
    str,
    str,
]:
    components = _reservation_components(reservation)

    if abs(components["total"] - charge_gross) > 0.02:
        return (
            [],
            "",
            "",
            (
                f"Reservation components total "
                f"{components['total']:.2f}, but Stripe "
                f"charge gross is {charge_gross:.2f}."
            ),
        )

    lines = _standard_lines(
        listing=listing,
        revenue=components["revenue"],
        tax_2_9=components["state_tax"],
        tax_2_5=round(
            components["county_tax"]
            + components["local_tax"],
            2,
        ),
        charge_fee=charge_fee,
    )

    return (
        lines,
        "Original Guesty",
        "Authoritative",
        "",
    )


def _canceled_fallback(
    *,
    reservation: pd.Series,
    listing: str,
    reservation_source: str,
    charge_gross: float,
    charge_fee: float,
) -> tuple[
    list[dict[str, object]],
    str,
    str,
    str,
]:
    components = _reservation_components(reservation)
    evidence_amount, evidence_match = _gross_evidence(
        components=components,
        charge_gross=charge_gross,
    )

    if evidence_match != "Yes":
        return (
            [],
            "",
            "",
            (
                "Guesty payment/refund totals do not confirm "
                "the Stripe gross."
            ),
        )

    source = reservation_source.lower()
    listing_text = listing.lower()

    if source == "booking.com" and "lodge room" in listing_text:
        lines = _standard_lines(
            listing=listing,
            revenue=charge_gross,
            tax_2_9=0.0,
            tax_2_5=0.0,
            charge_fee=charge_fee,
        )
        return (
            lines,
            "Canceled Booking.com Gross",
            "High",
            (
                "Canceled Booking.com motel reservation; "
                "Stripe gross is confirmed by Guesty payment "
                "evidence and comparable completed Booking.com "
                "reservations show no owner-recorded tax split."
            ),
        )

    if (
        source in {"vrbo", "homeaway2"}
        and "lodge room" in listing_text
    ):
        reconstruction = _tax_reconstruction(
            charge_gross
        )
        if reconstruction is None:
            return (
                [],
                "",
                "",
                (
                    "No unique penny-level allocation was found "
                    "using the established 2.9% and 2.5% lodging "
                    "tax profile."
                ),
            )

        (
            revenue,
            tax_2_9,
            tax_2_5,
            reconstructed,
        ) = reconstruction

        lines = _standard_lines(
            listing=listing,
            revenue=revenue,
            tax_2_9=tax_2_9,
            tax_2_5=tax_2_5,
            charge_fee=charge_fee,
        )
        return (
            lines,
            "Canceled VRBO Tax Reconstruction",
            "High",
            (
                f"Canceled VRBO/HomeAway motel reservation; "
                f"Stripe gross {charge_gross:.2f} is confirmed "
                f"by Guesty payment/refund evidence and is "
                f"uniquely reconstructed as revenue "
                f"{revenue:.2f}, 2.9% tax {tax_2_9:.2f}, and "
                f"2.5% tax {tax_2_5:.2f}."
            ),
        )

    return (
        [],
        "",
        "",
        (
            "Reservation gross is confirmed, but this source/"
            "property combination is not approved for automatic "
            "allocation reconstruction."
        ),
    )


def build_stripe_seed_candidates(
    *,
    reconciliation_summary: pd.DataFrame,
    stripe_families: pd.DataFrame,
    payment_ledger: pd.DataFrame,
    reservations: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if (
        reconciliation_summary.empty
        or stripe_families.empty
        or payment_ledger.empty
    ):
        return (
            pd.DataFrame(columns=CANDIDATE_COLUMNS),
            pd.DataFrame(columns=APPROVAL_COLUMNS),
            pd.DataFrame(columns=DIAGNOSTIC_COLUMNS),
        )

    eligible_exceptions = reconciliation_summary.loc[
        reconciliation_summary["processor"]
        .astype(str)
        .str.strip()
        .eq("Stripe")
        & reconciliation_summary["evidence_confidence"]
        .astype(str)
        .str.strip()
        .eq("High")
        & reconciliation_summary["resolution_blocked"]
        .astype(str)
        .str.strip()
        .eq("No")
        & reconciliation_summary["exact_match_found"]
        .astype(str)
        .str.strip()
        .eq("Yes")
        & reconciliation_summary["recommended_resolution"]
        .astype(str)
        .str.contains(
            "Create evidence-backed original charge seed",
            regex=False,
        )
    ].copy()

    if eligible_exceptions.empty:
        return (
            pd.DataFrame(columns=CANDIDATE_COLUMNS),
            pd.DataFrame(columns=APPROVAL_COLUMNS),
            pd.DataFrame(columns=DIAGNOSTIC_COLUMNS),
        )

    required_family_columns = {
        "exception_id",
        "family_issue",
        "resolution_sign_safe",
    }
    if not required_family_columns.issubset(
        stripe_families.columns
    ):
        return (
            pd.DataFrame(columns=CANDIDATE_COLUMNS),
            pd.DataFrame(columns=APPROVAL_COLUMNS),
            pd.DataFrame(columns=DIAGNOSTIC_COLUMNS),
        )

    eligible_ids = set(
        eligible_exceptions["exception_id"]
        .astype(str)
        .str.strip()
    )

    families = stripe_families.loc[
        stripe_families["exception_id"]
        .astype(str)
        .str.strip()
        .isin(eligible_ids)
        & stripe_families["family_issue"]
        .astype(str)
        .str.strip()
        .eq("Missing original charge history")
        & stripe_families["resolution_sign_safe"]
        .astype(str)
        .str.strip()
        .eq("Safe")
    ].copy()

    exception_lookup = {
        _text(row.get("exception_id")): row
        for _, row in eligible_exceptions.iterrows()
    }
    by_id, by_channel = _reservation_lookup(
        reservations
    )

    candidate_rows: list[dict[str, object]] = []
    approval_rows: list[dict[str, object]] = []
    diagnostic_rows: list[dict[str, object]] = []

    for _, family in families.iterrows():
        exception_id = _text(
            family.get("exception_id")
        )
        payout_id = _text(
            family.get("payout_id")
        )
        processor_account = _text(
            family.get("processor_account")
        )
        source_id = _text(
            family.get("source_id")
        )
        exception = exception_lookup[exception_id]

        family_events = payment_ledger.loc[
            payment_ledger["payout_id"]
            .astype(str)
            .str.strip()
            .eq(payout_id)
            & payment_ledger["source_id"]
            .astype(str)
            .str.strip()
            .eq(source_id)
            & payment_ledger["transaction_type"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("charge")
        ].copy()

        if family_events.empty:
            continue

        charge = family_events.iloc[0]

        payment_event_id = _text(
            charge.get("payment_event_id")
        )
        transaction_id = _text(
            charge.get("transaction_id")
        )
        reservation_id = _text(
            charge.get("reservation_id")
        )
        channel_id = _text(
            charge.get("channel_reservation_id")
        )
        guest = _text(charge.get("guest"))
        listing = _text(charge.get("listing"))
        transaction_date = _text(
            charge.get("transaction_date")
        )
        charge_gross = _money(
            charge.get("gross_amount")
        )
        charge_fee = _money(
            charge.get("processor_fee")
        )
        charge_net = _money(
            charge.get("net_amount")
        )

        reservation = _find_reservation(
            charge=charge,
            by_id=by_id,
            by_channel=by_channel,
        )

        candidate_group_id = _stable_id(
            "seedgrp",
            [payout_id, source_id, payment_event_id],
        )

        reservation_found = (
            "Yes" if reservation is not None else "No"
        )
        components = _reservation_components(
            reservation
        )
        reservation_source = (
            _text(reservation.get("source"))
            if reservation is not None
            else ""
        )
        evidence_amount, evidence_match = _gross_evidence(
            components=components,
            charge_gross=charge_gross,
        )

        allocation_method = ""
        evidence_level = ""
        evidence_reason = ""
        proposed_lines: list[
            dict[str, object]
        ] = []

        if reservation is None:
            error_note = (
                "No matching reservation was found."
            )
            diagnostic_type = "Missing Reservation"
        elif abs(
            components["total"] - charge_gross
        ) <= 0.02 and components["total"] > 0:
            (
                proposed_lines,
                allocation_method,
                evidence_level,
                error_note,
            ) = _authoritative_lines(
                reservation=reservation,
                listing=listing,
                charge_gross=charge_gross,
                charge_fee=charge_fee,
            )
            evidence_reason = (
                "Original normalized Guesty revenue and tax "
                "components tie to the Stripe gross."
            )
            diagnostic_type = (
                "Candidate Ready"
                if proposed_lines
                else "Reservation Gross Mismatch"
            )
        else:
            (
                proposed_lines,
                allocation_method,
                evidence_level,
                fallback_note,
            ) = _canceled_fallback(
                reservation=reservation,
                listing=listing,
                reservation_source=reservation_source,
                charge_gross=charge_gross,
                charge_fee=charge_fee,
            )
            if proposed_lines:
                error_note = ""
                evidence_reason = fallback_note
                diagnostic_type = (
                    "Canceled Reservation Reconstructed"
                )
            else:
                error_note = fallback_note
                diagnostic_type = (
                    "Canceled Allocation Not Proven"
                    if evidence_match == "Yes"
                    else "Reservation Gross Mismatch"
                )

        candidate_status = (
            "Ready for Approval"
            if proposed_lines and not error_note
            else "Review Required"
        )

        reconstructed_revenue = 0.0
        reconstructed_tax_2_9 = 0.0
        reconstructed_tax_2_5 = 0.0
        for line in proposed_lines:
            allocation_type = _text(
                line.get("allocation_type")
            )
            if allocation_type == "Revenue":
                reconstructed_revenue += _money(
                    line.get("signed_amount")
                )
            elif allocation_type == "Lodging Tax 2.9%":
                reconstructed_tax_2_9 += _money(
                    line.get("signed_amount")
                )
            elif allocation_type == "Lodging Tax 2.5%":
                reconstructed_tax_2_5 += _money(
                    line.get("signed_amount")
                )

        reconstructed_gross = round(
            reconstructed_revenue
            + reconstructed_tax_2_9
            + reconstructed_tax_2_5,
            2,
        )

        reservation_component_total = _money(
            components.get("total")
        )

        gross_component_difference = round(
            reservation_component_total - charge_gross,
             2,
        )

        diagnostic_rows.append(
            {
                "candidate_group_id": candidate_group_id,
                "exception_id": exception_id,
                "payout_id": payout_id,
                "source_id": source_id,
                "payment_event_id": payment_event_id,
                "guest": guest,
                "listing": listing,
                "reservation_source": reservation_source,
                "reservation_id": reservation_id,
                "channel_reservation_id": channel_id,
                "charge_gross": charge_gross,
                "charge_fee": charge_fee,
                "charge_net": charge_net,
                "reservation_revenue": components["revenue"],
                "reservation_state_tax": components["state_tax"],
                "reservation_county_tax": components["county_tax"],
                "reservation_local_tax": components["local_tax"],
                "reservation_component_total": reservation_component_total,
                "reservation_total_paid": components["total_paid"],
                "reservation_total_refunded": components["total_refunded"],
                "reservation_total_payout": components["total_payout"],
                "gross_component_difference": gross_component_difference,
                "gross_evidence_amount": evidence_amount,
                "gross_evidence_match": evidence_match,
                "allocation_method": allocation_method,
                "evidence_level": evidence_level,
                "reconstructed_revenue": reconstructed_revenue,
                "reconstructed_tax_2_9": reconstructed_tax_2_9,
                "reconstructed_tax_2_5": reconstructed_tax_2_5,
                "reconstructed_gross": reconstructed_gross,
                "reservation_gross_component_difference": round(
                    components["total"] - charge_gross,
                    2,
                ),
                "candidate_status": candidate_status,
                "diagnostic_type": diagnostic_type,
                "diagnostic_detail": (
                    evidence_reason
                    if proposed_lines
                    else error_note
                ),
                "possible_cause": (
                    "Current Guesty canceled-reservation rows "
                    "preserve gross payment/refund evidence but "
                    "zero out the original revenue/tax allocation."
                    if reservation is not None
                    and components["total"] == 0
                    else ""
                ),
            }
        )

        for line_number, line in enumerate(
            proposed_lines,
            start=1,
        ):
            candidate_id = _stable_id(
                "seed",
                [
                    candidate_group_id,
                    str(line_number),
                    _text(line["account"]),
                    f"{_money(line['signed_amount']):.2f}",
                ],
            )

            candidate_rows.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_group_id": candidate_group_id,
                    "exception_id": exception_id,
                    "payout_id": payout_id,
                    "processor_account": processor_account,
                    "source_id": source_id,
                    "payment_event_id": payment_event_id,
                    "transaction_id": transaction_id,
                    "reservation_id": reservation_id,
                    "channel_reservation_id": channel_id,
                    "guest": guest,
                    "listing": listing,
                    "reservation_source": reservation_source,
                    "transaction_date": transaction_date,
                    "line_number": line_number,
                    "allocation_type": _text(
                        line["allocation_type"]
                    ),
                    "account": _text(line["account"]),
                    "class": _text(line["class"]),
                    "description": _text(
                        line["description"]
                    ),
                    "signed_amount": _money(
                        line["signed_amount"]
                    ),
                    "charge_gross": charge_gross,
                    "charge_fee": charge_fee,
                    "charge_net": charge_net,
                    "reservation_found": reservation_found,
                    "candidate_status": candidate_status,
                    "allocation_method": allocation_method,
                    "evidence_level": evidence_level,
                    "evidence_source": (
                        "Stripe charge + normalized Guesty "
                        "reservation/payment evidence"
                    ),
                    "evidence_reason": evidence_reason,
                    "generated_by": (
                        "DSRL Accounting Engine V11C"
                    ),
                }
            )

        proposed_effect = round(
            sum(
                _money(line["signed_amount"])
                for line in proposed_lines
            ),
            2,
        )
        expected_difference = _money(
            exception.get("difference")
        )
        remaining = round(
            expected_difference + proposed_effect,
            2,
        )

        exact_match = (
            "Yes"
            if abs(remaining) <= 0.02
            else "No"
        )
        sign_safe = (
            "Yes"
            if (
                (
                    expected_difference < 0
                    and proposed_effect > 0
                )
                or (
                    expected_difference > 0
                    and proposed_effect < 0
                )
            )
            else "No"
        )

        approval_eligible = (
            "Yes"
            if (
                candidate_status
                == "Ready for Approval"
                and exact_match == "Yes"
                and sign_safe == "Yes"
                and evidence_level
                in {"Authoritative", "High"}
            )
            else "No"
        )

        notes: list[str] = []
        if error_note:
            notes.append(error_note)
        if exact_match == "No":
            notes.append(
                f"Proposed effect leaves "
                f"{remaining:.2f} unresolved."
            )
        if sign_safe == "No":
            notes.append(
                "Proposed seed effect is not sign-safe."
            )

        approval_rows.append(
            {
                "candidate_group_id": candidate_group_id,
                "exception_id": exception_id,
                "payout_id": payout_id,
                "processor_account": processor_account,
                "source_id": source_id,
                "payment_event_id": payment_event_id,
                "guest": guest,
                "listing": listing,
                "reservation_source": reservation_source,
                "expected_payout_difference": (
                    expected_difference
                ),
                "proposed_seed_effect": proposed_effect,
                "remaining_difference_after_seed": (
                    remaining
                ),
                "line_count": len(proposed_lines),
                "reservation_found": reservation_found,
                "allocation_method": allocation_method,
                "evidence_level": evidence_level,
                "sign_safe": sign_safe,
                "exact_match": exact_match,
                "approval_eligible": approval_eligible,
                "approval_status": (
                    "Pending"
                    if approval_eligible == "Yes"
                    else "Not Eligible"
                ),
                "review_notes": " ".join(notes),
            }
        )

    return (
        pd.DataFrame(
            candidate_rows,
            columns=CANDIDATE_COLUMNS,
        ),
        pd.DataFrame(
            approval_rows,
            columns=APPROVAL_COLUMNS,
        ),
        pd.DataFrame(
            diagnostic_rows,
            columns=DIAGNOSTIC_COLUMNS,
        ),
    )
