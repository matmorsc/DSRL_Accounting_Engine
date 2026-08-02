from __future__ import annotations

import hashlib
from typing import Iterable

import pandas as pd


RECON_COLUMNS = [
    "exception_id",
    "processor",
    "payout_id",
    "bank_amount",
    "posting_total",
    "difference",
    "difference_direction",
    "authoritative_event_total",
    "active_history_total",
    "reversal_preview_total",
    "unposted_event_total",
    "reconciled_gap",
    "sign_consistency",
    "resolution_blocked",
    "recommended_resolution",
    "evidence_confidence",
    "exact_match_found",
    "review_note",
]

STRIPE_FAMILY_COLUMNS = [
    "exception_id",
    "payout_id",
    "processor_account",
    "source_id",
    "family_event_total",
    "charge_total",
    "refund_total",
    "adjustment_total",
    "other_total",
    "active_original_total",
    "active_adjustment_total",
    "reversal_preview_total",
    "ledger_effect_total",
    "family_gap",
    "has_original_charge_event",
    "has_active_original_history",
    "has_reversal_preview",
    "family_issue",
    "candidate_resolution",
    "resolution_sign_safe",
    "evidence_note",
]

AIRBNB_COMPONENT_COLUMNS = [
    "exception_id",
    "payout_id",
    "payment_event_id",
    "transaction_type",
    "transaction_date",
    "confirmation_code",
    "guest",
    "listing",
    "event_total",
    "active_history_total",
    "component_gap",
    "component_status",
    "candidate_resolution",
    "exact_difference_candidate",
    "evidence_note",
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


def _sum_money(
    frame: pd.DataFrame,
    column: str,
) -> float:
    if frame.empty or column not in frame.columns:
        return 0.0
    return round(
        pd.to_numeric(
            frame[column],
            errors="coerce",
        )
        .fillna(0.0)
        .sum(),
        2,
    )


def _exception_id(
    processor: str,
    payout_id: str,
) -> str:
    digest = hashlib.sha256(
        f"{processor}|{payout_id}".encode("utf-8")
    ).hexdigest()[:16]
    return f"exc_{digest}"


def _active_history(
    posting_history: pd.DataFrame,
    manual_seeds: pd.DataFrame,
) -> pd.DataFrame:
    frames = [
        frame
        for frame in (posting_history, manual_seeds)
        if frame is not None and not frame.empty
    ]
    if not frames:
        return pd.DataFrame()

    combined = pd.concat(
        frames,
        ignore_index=True,
        sort=False,
    )

    if "status" in combined.columns:
        combined = combined.loc[
            combined["status"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("active")
        ].copy()

    if "signed_amount" in combined.columns:
        combined["signed_amount"] = pd.to_numeric(
            combined["signed_amount"],
            errors="coerce",
        ).fillna(0.0)

    return combined


def _reversal_preview(
    reversal_preview: pd.DataFrame,
) -> pd.DataFrame:
    if (
        reversal_preview is None
        or reversal_preview.empty
    ):
        return pd.DataFrame()

    frame = reversal_preview.copy()

    if "status" in frame.columns:
        frame = frame.loc[
            frame["status"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("proposed")
        ].copy()

    if "posting_type" in frame.columns:
        frame = frame.loc[
            frame["posting_type"]
            .astype(str)
            .str.strip()
            .eq("Reversal")
        ].copy()

    if "signed_amount" in frame.columns:
        frame["signed_amount"] = pd.to_numeric(
            frame["signed_amount"],
            errors="coerce",
        ).fillna(0.0)

    return frame


def _sign_consistency(
    difference: float,
    proposed_effect: float,
) -> tuple[str, str]:
    """
    difference = posting total - bank amount.

    A safe correction must move posting total toward the bank:
    correction sign should be opposite the current difference.
    """
    if abs(difference) <= 0.02:
        return "Already balanced", "No"

    if abs(proposed_effect) <= 0.005:
        return "No proposed effect", "Yes"

    safe = (
        difference > 0 and proposed_effect < 0
    ) or (
        difference < 0 and proposed_effect > 0
    )

    return (
        "Safe" if safe else "Unsafe",
        "No" if safe else "Yes",
    )


def build_stripe_family_reconciliation(
    *,
    exception_summary: pd.DataFrame,
    payment_ledger: pd.DataFrame,
    posting_history: pd.DataFrame,
    manual_seeds: pd.DataFrame,
    reversal_preview: pd.DataFrame,
) -> pd.DataFrame:
    history = _active_history(
        posting_history,
        manual_seeds,
    )
    reversals = _reversal_preview(
        reversal_preview
    )

    rows: list[dict[str, object]] = []

    stripe_exceptions = exception_summary.loc[
        exception_summary["processor"]
        .astype(str)
        .str.strip()
        .eq("Stripe")
    ].copy()

    for _, exception in stripe_exceptions.iterrows():
        payout_id = _text(
            exception.get("payout_id")
        )
        processor_account = _text(
            exception.get("processor_account")
        )
        exception_id = _text(
            exception.get("exception_id")
        ) or _exception_id(
            "Stripe",
            payout_id,
        )
        payout_difference = _money(
            exception.get("difference")
        )

        events = payment_ledger.loc[
            payment_ledger["payout_id"]
            .astype(str)
            .str.strip()
            .eq(payout_id)
            & payment_ledger["processor"]
            .astype(str)
            .str.strip()
            .eq("Stripe")
        ].copy()

        for source_id, family in events.groupby(
            "source_id",
            dropna=False,
            sort=True,
        ):
            source_id = _text(source_id)

            types = (
                family["transaction_type"]
                .astype(str)
                .str.strip()
                .str.lower()
            )

            charges = family.loc[
                types.eq("charge")
            ]
            refunds = family.loc[
                types.isin(
                    [
                        "refund",
                        "reversal",
                        "dispute",
                    ]
                )
            ]
            adjustments = family.loc[
                types.eq("adjustment")
            ]
            others = family.loc[
                ~family.index.isin(
                    charges.index
                    .union(refunds.index)
                    .union(adjustments.index)
                )
            ]

            source_history = pd.DataFrame()
            if (
                not history.empty
                and source_id
                and "source_id" in history.columns
            ):
                source_history = history.loc[
                    history["source_id"]
                    .astype(str)
                    .str.strip()
                    .eq(source_id)
                ].copy()

            source_reversals = pd.DataFrame()
            if (
                not reversals.empty
                and source_id
                and "source_id" in reversals.columns
            ):
                source_reversals = reversals.loc[
                    reversals["source_id"]
                    .astype(str)
                    .str.strip()
                    .eq(source_id)
                ].copy()

            originals = source_history
            if (
                not source_history.empty
                and "posting_type"
                in source_history.columns
            ):
                originals = source_history.loc[
                    source_history["posting_type"]
                    .astype(str)
                    .str.strip()
                    .eq("Original")
                ].copy()

            active_adjustments = source_history
            if (
                not source_history.empty
                and "posting_type"
                in source_history.columns
            ):
                active_adjustments = source_history.loc[
                    source_history["posting_type"]
                    .astype(str)
                    .str.strip()
                    .eq("Adjustment")
                ].copy()

            family_event_total = _sum_money(
                family,
                "net_amount",
            )
            charge_total = _sum_money(
                charges,
                "net_amount",
            )
            refund_total = _sum_money(
                refunds,
                "net_amount",
            )
            adjustment_total = _sum_money(
                adjustments,
                "net_amount",
            )
            other_total = _sum_money(
                others,
                "net_amount",
            )
            active_original_total = _sum_money(
                originals,
                "signed_amount",
            )
            active_adjustment_total = _sum_money(
                active_adjustments,
                "signed_amount",
            )
            reversal_total = _sum_money(
                source_reversals,
                "signed_amount",
            )

            ledger_effect_total = round(
                active_original_total
                + active_adjustment_total
                + reversal_total,
                2,
            )

            family_gap = round(
                family_event_total
                - ledger_effect_total,
                2,
            )

            has_charge = not charges.empty
            has_original = (
                not originals.empty
            )
            has_reversal = (
                not source_reversals.empty
            )

            if (
                has_charge
                and not has_original
            ):
                family_issue = (
                    "Missing original charge history"
                )
                candidate_resolution = (
                    "Create evidence-backed original charge seed"
                )
                proposed_effect = charge_total
            elif (
                (not refunds.empty or not adjustments.empty)
                and has_original
                and not has_reversal
            ):
                family_issue = (
                    "Missing reversal effect"
                )
                candidate_resolution = (
                    "Generate or promote reversal lines"
                )
                proposed_effect = round(
                    refund_total + adjustment_total,
                    2,
                )
            elif has_reversal and abs(
                family_gap
            ) > 0.02:
                family_issue = (
                    "Reversal exists but payout remains unreconciled"
                )
                candidate_resolution = (
                    "Review payout assignment or duplicate history"
                )
                proposed_effect = family_gap
            elif abs(family_gap) <= 0.02:
                family_issue = "Family reconciled"
                candidate_resolution = "No action"
                proposed_effect = 0.0
            else:
                family_issue = (
                    "Unexplained family difference"
                )
                candidate_resolution = (
                    "Review payout membership and event classification"
                )
                proposed_effect = family_gap

            sign_status, blocked = _sign_consistency(
                payout_difference,
                proposed_effect,
            )

            note_parts = [
                (
                    f"Event total {family_event_total:.2f}; "
                    f"ledger effect {ledger_effect_total:.2f}; "
                    f"family gap {family_gap:.2f}."
                )
            ]

            if blocked == "Yes":
                note_parts.append(
                    "Proposed resolution would not move the payout toward balance."
                )

            rows.append(
                {
                    "exception_id": exception_id,
                    "payout_id": payout_id,
                    "processor_account": (
                        processor_account
                    ),
                    "source_id": source_id,
                    "family_event_total": (
                        family_event_total
                    ),
                    "charge_total": charge_total,
                    "refund_total": refund_total,
                    "adjustment_total": (
                        adjustment_total
                    ),
                    "other_total": other_total,
                    "active_original_total": (
                        active_original_total
                    ),
                    "active_adjustment_total": (
                        active_adjustment_total
                    ),
                    "reversal_preview_total": (
                        reversal_total
                    ),
                    "ledger_effect_total": (
                        ledger_effect_total
                    ),
                    "family_gap": family_gap,
                    "has_original_charge_event": (
                        "Yes" if has_charge else "No"
                    ),
                    "has_active_original_history": (
                        "Yes" if has_original else "No"
                    ),
                    "has_reversal_preview": (
                        "Yes" if has_reversal else "No"
                    ),
                    "family_issue": family_issue,
                    "candidate_resolution": (
                        candidate_resolution
                    ),
                    "resolution_sign_safe": (
                        sign_status
                    ),
                    "evidence_note": " ".join(
                        note_parts
                    ),
                }
            )

    return pd.DataFrame(
        rows,
        columns=STRIPE_FAMILY_COLUMNS,
    )


def build_airbnb_component_reconciliation(
    *,
    exception_summary: pd.DataFrame,
    payment_ledger: pd.DataFrame,
    posting_history: pd.DataFrame,
    manual_seeds: pd.DataFrame,
) -> pd.DataFrame:
    history = _active_history(
        posting_history,
        manual_seeds,
    )

    rows: list[dict[str, object]] = []

    airbnb_exceptions = exception_summary.loc[
        exception_summary["processor"]
        .astype(str)
        .str.strip()
        .eq("Airbnb")
    ].copy()

    for _, exception in airbnb_exceptions.iterrows():
        payout_id = _text(
            exception.get("payout_id")
        )
        exception_id = _text(
            exception.get("exception_id")
        ) or _exception_id(
            "Airbnb",
            payout_id,
        )
        payout_difference = _money(
            exception.get("difference")
        )

        events = payment_ledger.loc[
            payment_ledger["payout_id"]
            .astype(str)
            .str.strip()
            .eq(payout_id)
            & payment_ledger["processor"]
            .astype(str)
            .str.strip()
            .eq("Airbnb")
        ].copy()

        for _, event in events.iterrows():
            event_id = _text(
                event.get("payment_event_id")
            )

            event_history = pd.DataFrame()
            if (
                not history.empty
                and "payment_event_id"
                in history.columns
            ):
                event_history = history.loc[
                    history["payment_event_id"]
                    .astype(str)
                    .str.strip()
                    .eq(event_id)
                ].copy()

            event_total = _money(
                event.get("net_amount")
            )
            active_total = _sum_money(
                event_history,
                "signed_amount",
            )
            component_gap = round(
                event_total - active_total,
                2,
            )

            transaction_type = _text(
                event.get("transaction_type")
            ).lower()

            if abs(component_gap) <= 0.02:
                status = "Represented in history"
                resolution = "No action"
            elif transaction_type == "adjustment":
                status = (
                    "Unposted standalone adjustment"
                )
                resolution = (
                    "Review and promote standalone adjustment"
                )
            elif transaction_type in {
                "refund",
                "resolution adjustment",
            }:
                status = (
                    "Unposted refund or resolution adjustment"
                )
                resolution = (
                    "Classify adjustment against reservation or fee account"
                )
            elif transaction_type == "reservation":
                status = (
                    "Reservation allocation differs from history"
                )
                resolution = (
                    "Review revenue and Airbnb fee allocation"
                )
            else:
                status = (
                    "Unclassified component difference"
                )
                resolution = (
                    "Review authoritative Airbnb payout report"
                )

            exact_candidate = (
                "Yes"
                if abs(
                    abs(component_gap)
                    - abs(payout_difference)
                ) <= 0.02
                else "No"
            )

            rows.append(
                {
                    "exception_id": exception_id,
                    "payout_id": payout_id,
                    "payment_event_id": event_id,
                    "transaction_type": (
                        transaction_type
                    ),
                    "transaction_date": _text(
                        event.get("transaction_date")
                    ),
                    "confirmation_code": (
                        _text(
                            event.get(
                                "channel_reservation_id"
                            )
                        )
                        or _text(
                            event.get(
                                "transaction_id"
                            )
                        )
                    ),
                    "guest": _text(
                        event.get("guest")
                    ),
                    "listing": _text(
                        event.get("listing")
                    ),
                    "event_total": event_total,
                    "active_history_total": (
                        active_total
                    ),
                    "component_gap": (
                        component_gap
                    ),
                    "component_status": status,
                    "candidate_resolution": (
                        resolution
                    ),
                    "exact_difference_candidate": (
                        exact_candidate
                    ),
                    "evidence_note": (
                        f"Event {event_total:.2f}; "
                        f"active history {active_total:.2f}; "
                        f"gap {component_gap:.2f}."
                    ),
                }
            )

    return pd.DataFrame(
        rows,
        columns=AIRBNB_COMPONENT_COLUMNS,
    )


def build_exception_reconciliation_summary(
    *,
    exception_summary: pd.DataFrame,
    payment_ledger: pd.DataFrame,
    posting_history: pd.DataFrame,
    manual_seeds: pd.DataFrame,
    reversal_preview: pd.DataFrame,
    stripe_families: pd.DataFrame,
    airbnb_components: pd.DataFrame,
) -> pd.DataFrame:
    history = _active_history(
        posting_history,
        manual_seeds,
    )
    reversals = _reversal_preview(
        reversal_preview
    )

    rows: list[dict[str, object]] = []

    for _, exception in exception_summary.iterrows():
        exception_id = _text(
            exception.get("exception_id")
        )
        processor = _text(
            exception.get("processor")
        )
        payout_id = _text(
            exception.get("payout_id")
        )
        bank_amount = _money(
            exception.get("bank_amount")
        )
        posting_total = _money(
            exception.get("posting_total")
        )
        difference = _money(
            exception.get("difference")
        )

        events = payment_ledger.loc[
            payment_ledger["payout_id"]
            .astype(str)
            .str.strip()
            .eq(payout_id)
        ].copy()

        authoritative_total = _sum_money(
            events,
            "net_amount",
        )

        payout_history = pd.DataFrame()
        if (
            not history.empty
            and "payout_id" in history.columns
        ):
            payout_history = history.loc[
                history["payout_id"]
                .astype(str)
                .str.strip()
                .eq(payout_id)
            ].copy()

        payout_reversals = pd.DataFrame()
        if (
            not reversals.empty
            and "payout_id" in reversals.columns
        ):
            payout_reversals = reversals.loc[
                reversals["payout_id"]
                .astype(str)
                .str.strip()
                .eq(payout_id)
            ].copy()

        active_history_total = _sum_money(
            payout_history,
            "signed_amount",
        )
        reversal_total = _sum_money(
            payout_reversals,
            "signed_amount",
        )

        event_ids_in_history = set()
        if (
            not payout_history.empty
            and "payment_event_id"
            in payout_history.columns
        ):
            event_ids_in_history = set(
                payout_history["payment_event_id"]
                .astype(str)
                .str.strip()
            )

        unposted_events = events.loc[
            ~events["payment_event_id"]
            .astype(str)
            .str.strip()
            .isin(event_ids_in_history)
        ].copy()

        unposted_total = _sum_money(
            unposted_events,
            "net_amount",
        )

        reconciled_gap = round(
            authoritative_total
            - active_history_total
            - reversal_total,
            2,
        )

        exact_match_found = "No"
        confidence = "Low"
        blocked = "No"
        sign_status = "No proposed effect"
        recommended = (
            "Review authoritative payout evidence"
        )
        notes: list[str] = []

        if processor == "Stripe":
            families = stripe_families.loc[
                stripe_families["exception_id"]
                .astype(str)
                .eq(exception_id)
            ]

            unresolved = families.loc[
                ~families["family_issue"]
                .astype(str)
                .eq("Family reconciled")
            ]

            exact_family = unresolved.loc[
                pd.to_numeric(
                    unresolved["family_gap"],
                    errors="coerce",
                )
                .fillna(0.0)
                .abs()
                .sub(abs(difference))
                .abs()
                .le(0.02)
            ]

            blocked_rows = unresolved.loc[
                unresolved["resolution_sign_safe"]
                .astype(str)
                .eq("Unsafe")
            ]

            if not blocked_rows.empty:
                confidence = "High"
                blocked = "Yes"
                sign_status = "Unsafe"
                recommended = (
                    "Do not create missing-original seeds; investigate excess or wrong payout assignment"
                )
                if not exact_family.empty:
                    exact_match_found = "Yes"
            elif not exact_family.empty:
                exact_match_found = "Yes"
                confidence = "High"
                recommended = _text(
                    exact_family.iloc[0].get(
                        "candidate_resolution"
                    )
                )
                proposed_effect = _money(
                    exact_family.iloc[0].get(
                        "family_gap"
                    )
                )
                sign_status, blocked = (
                    _sign_consistency(
                        difference,
                        proposed_effect,
                    )
                )
            elif not unresolved.empty:
                confidence = "Medium"
                recommended = (
                    "Review unresolved Stripe source families"
                )

            notes.append(
                f"{len(families)} source family row(s); "
                f"{len(unresolved)} unresolved."
            )

        elif processor == "Airbnb":
            components = airbnb_components.loc[
                airbnb_components["exception_id"]
                .astype(str)
                .eq(exception_id)
            ]
            exact = components.loc[
                components[
                    "exact_difference_candidate"
                ]
                .astype(str)
                .eq("Yes")
            ]

            if len(exact) == 1:
                exact_match_found = "Yes"
                confidence = "High"
                recommended = _text(
                    exact.iloc[0].get(
                        "candidate_resolution"
                    )
                )
                proposed_effect = _money(
                    exact.iloc[0].get(
                        "component_gap"
                    )
                )
                sign_status, blocked = (
                    _sign_consistency(
                        difference,
                        proposed_effect,
                    )
                )
            elif len(exact) > 1:
                confidence = "Medium"
                recommended = (
                    "Review multiple Airbnb components matching the payout difference"
                )
            else:
                confidence = "Low"
                recommended = (
                    "Use authoritative Airbnb payout report to identify omitted component"
                )

            notes.append(
                f"{len(components)} Airbnb component row(s); "
                f"{len(exact)} exact candidate(s)."
            )

        if blocked == "Yes":
            notes.append(
                "Automatic resolution is blocked by sign-consistency control."
            )

        rows.append(
            {
                "exception_id": exception_id,
                "processor": processor,
                "payout_id": payout_id,
                "bank_amount": bank_amount,
                "posting_total": posting_total,
                "difference": difference,
                "difference_direction": _text(
                    exception.get(
                        "difference_direction"
                    )
                ),
                "authoritative_event_total": (
                    authoritative_total
                ),
                "active_history_total": (
                    active_history_total
                ),
                "reversal_preview_total": (
                    reversal_total
                ),
                "unposted_event_total": (
                    unposted_total
                ),
                "reconciled_gap": reconciled_gap,
                "sign_consistency": sign_status,
                "resolution_blocked": blocked,
                "recommended_resolution": (
                    recommended
                ),
                "evidence_confidence": (
                    confidence
                ),
                "exact_match_found": (
                    exact_match_found
                ),
                "review_note": " ".join(notes),
            }
        )

    return pd.DataFrame(
        rows,
        columns=RECON_COLUMNS,
    ).sort_values(
        [
            "resolution_blocked",
            "evidence_confidence",
            "processor",
            "difference",
        ],
        ascending=[False, True, True, True],
    ).reset_index(drop=True)


def build_exception_evidence_reconciliation(
    *,
    exception_summary: pd.DataFrame,
    payment_ledger: pd.DataFrame,
    posting_history: pd.DataFrame,
    manual_seeds: pd.DataFrame,
    reversal_preview: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    stripe_families = (
        build_stripe_family_reconciliation(
            exception_summary=exception_summary,
            payment_ledger=payment_ledger,
            posting_history=posting_history,
            manual_seeds=manual_seeds,
            reversal_preview=reversal_preview,
        )
    )

    airbnb_components = (
        build_airbnb_component_reconciliation(
            exception_summary=exception_summary,
            payment_ledger=payment_ledger,
            posting_history=posting_history,
            manual_seeds=manual_seeds,
        )
    )

    summary = (
        build_exception_reconciliation_summary(
            exception_summary=exception_summary,
            payment_ledger=payment_ledger,
            posting_history=posting_history,
            manual_seeds=manual_seeds,
            reversal_preview=reversal_preview,
            stripe_families=stripe_families,
            airbnb_components=airbnb_components,
        )
    )

    return (
        summary,
        stripe_families,
        airbnb_components,
    )
