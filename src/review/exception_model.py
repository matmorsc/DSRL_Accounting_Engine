from __future__ import annotations

import hashlib
from typing import Iterable

import pandas as pd


SUMMARY_COLUMNS = [
    "exception_id",
    "processor",
    "processor_account",
    "payout_id",
    "bank_transaction_date",
    "bank_description",
    "bank_amount",
    "posting_total",
    "difference",
    "difference_direction",
    "absolute_difference",
    "exception_category",
    "likely_resolution_type",
    "evidence_confidence",
    "source_event_count",
    "unposted_event_count",
    "missing_original_source_count",
    "unlinked_event_count",
    "adjustment_event_count",
    "refund_event_count",
    "charge_event_count",
    "review_status",
    "resolution_status",
    "review_notes",
]

EVENT_COLUMNS = [
    "exception_id",
    "processor",
    "processor_account",
    "payout_id",
    "payment_event_id",
    "transaction_id",
    "transaction_type",
    "transaction_date",
    "source_id",
    "reservation_id",
    "channel_reservation_id",
    "guest",
    "listing",
    "gross_amount",
    "processor_fee",
    "net_amount",
    "event_posted_in_history",
    "original_source_in_history",
    "reversal_review_status",
    "event_role",
    "evidence_note",
]

AIRBNB_COLUMNS = [
    "exception_id",
    "payout_id",
    "payment_event_id",
    "transaction_type",
    "transaction_date",
    "confirmation_code",
    "guest",
    "listing",
    "gross_amount",
    "processor_fee",
    "net_amount",
    "history_status",
    "likely_missing_component",
    "proposed_account",
    "proposed_class",
    "proposed_resolution",
    "evidence_note",
]

STRIPE_COLUMNS = [
    "exception_id",
    "payout_id",
    "processor_account",
    "source_id",
    "original_charge_event_id",
    "original_charge_gross",
    "original_charge_fee",
    "original_charge_net",
    "original_reservation_id",
    "original_channel_reservation_id",
    "original_guest",
    "original_listing",
    "refund_total",
    "adjustment_total",
    "other_event_total",
    "event_count",
    "original_posting_history_lines",
    "reversal_preview_lines",
    "missing_original_posting_history",
    "family_difference",
    "likely_resolution",
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


def _date_text(value: object) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d")


def _exception_id(processor: str, payout_id: str) -> str:
    digest = hashlib.sha256(
        f"{processor}|{payout_id}".encode("utf-8")
    ).hexdigest()[:16]
    return f"exc_{digest}"


def _find_column(
    frame: pd.DataFrame,
    candidates: Iterable[str],
) -> str:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    return ""


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

    return combined


def build_exception_event_evidence(
    *,
    exceptions: pd.DataFrame,
    payment_ledger: pd.DataFrame,
    posting_history: pd.DataFrame,
    manual_seeds: pd.DataFrame,
    reversal_review: pd.DataFrame,
) -> pd.DataFrame:
    history = _active_history(
        posting_history,
        manual_seeds,
    )

    history_event_ids = set()
    history_source_ids = set()

    if not history.empty:
        if "payment_event_id" in history.columns:
            history_event_ids = set(
                history["payment_event_id"]
                .astype(str)
                .str.strip()
            )
        if "source_id" in history.columns:
            originals = history
            if "posting_type" in history.columns:
                originals = history.loc[
                    history["posting_type"]
                    .astype(str)
                    .str.strip()
                    .isin(["Original", "Adjustment"])
                ]
            history_source_ids = set(
                originals["source_id"]
                .astype(str)
                .str.strip()
            )

    reversal_lookup: dict[str, str] = {}
    if reversal_review is not None and not reversal_review.empty:
        event_col = _find_column(
            reversal_review,
            ["payment_event_id"],
        )
        status_col = _find_column(
            reversal_review,
            ["review_status", "diagnostic_type"],
        )
        if event_col and status_col:
            reversal_lookup = {
                _text(row.get(event_col)): _text(row.get(status_col))
                for _, row in reversal_review.iterrows()
                if _text(row.get(event_col))
            }

    rows: list[dict[str, object]] = []

    for _, exception in exceptions.iterrows():
        payout_id = _text(exception.get("payout_id"))
        processor = _text(exception.get("processor"))
        processor_account = _text(
            exception.get("processor_account")
        )
        exception_id = _exception_id(
            processor,
            payout_id,
        )

        payout_events = payment_ledger.loc[
            payment_ledger["payout_id"]
            .astype(str)
            .str.strip()
            .eq(payout_id)
        ].copy()

        for _, event in payout_events.iterrows():
            event_id = _text(
                event.get("payment_event_id")
            )
            source_id = _text(
                event.get("source_id")
            )
            transaction_type = _text(
                event.get("transaction_type")
            ).lower()

            event_posted = event_id in history_event_ids
            source_exists = (
                bool(source_id)
                and source_id in history_source_ids
            )
            reversal_status = reversal_lookup.get(
                event_id,
                "",
            )

            if event_posted:
                event_role = "Posted"
            elif transaction_type in {
                "refund",
                "reversal",
                "dispute",
                "adjustment",
            }:
                event_role = (
                    "Unposted Reversal/Adjustment"
                    if source_exists
                    else "Missing Original Posting History"
                )
            elif transaction_type in {
                "charge",
                "reservation",
                "payment",
            }:
                event_role = "Unposted Original Event"
            else:
                event_role = "Unclassified Event"

            note_parts = [
                (
                    "Event exists in active posting history."
                    if event_posted
                    else "Event is not in active posting history."
                )
            ]
            if source_id:
                note_parts.append(
                    (
                        "Original source exists in active history."
                        if source_exists
                        else "No active original history found for source."
                    )
                )
            if reversal_status:
                note_parts.append(
                    f"Reversal review: {reversal_status}."
                )

            rows.append(
                {
                    "exception_id": exception_id,
                    "processor": processor,
                    "processor_account": processor_account,
                    "payout_id": payout_id,
                    "payment_event_id": event_id,
                    "transaction_id": _text(
                        event.get("transaction_id")
                    ),
                    "transaction_type": transaction_type,
                    "transaction_date": _date_text(
                        event.get("transaction_date")
                    ),
                    "source_id": source_id,
                    "reservation_id": _text(
                        event.get("reservation_id")
                    ),
                    "channel_reservation_id": _text(
                        event.get("channel_reservation_id")
                    ),
                    "guest": _text(
                        event.get("guest")
                    ),
                    "listing": _text(
                        event.get("listing")
                    ),
                    "gross_amount": _money(
                        event.get("gross_amount")
                    ),
                    "processor_fee": _money(
                        event.get("processor_fee")
                    ),
                    "net_amount": _money(
                        event.get("net_amount")
                    ),
                    "event_posted_in_history": (
                        "Yes" if event_posted else "No"
                    ),
                    "original_source_in_history": (
                        "Yes" if source_exists else "No"
                    ),
                    "reversal_review_status": reversal_status,
                    "event_role": event_role,
                    "evidence_note": " ".join(note_parts),
                }
            )

    return pd.DataFrame(
        rows,
        columns=EVENT_COLUMNS,
    )


def build_airbnb_exception_detail(
    event_evidence: pd.DataFrame,
) -> pd.DataFrame:
    if event_evidence.empty:
        return pd.DataFrame(columns=AIRBNB_COLUMNS)

    candidates = event_evidence.loc[
        event_evidence["processor"]
        .astype(str)
        .str.strip()
        .eq("Airbnb")
    ].copy()

    rows: list[dict[str, object]] = []

    for _, event in candidates.iterrows():
        transaction_type = _text(
            event.get("transaction_type")
        )
        history_status = _text(
            event.get("event_role")
        )

        proposed_account = ""
        proposed_class = ""
        likely_missing_component = ""
        proposed_resolution = ""

        if history_status == "Posted":
            likely_missing_component = "None identified"
            proposed_resolution = "No action"
        elif transaction_type == "adjustment":
            likely_missing_component = (
                "Standalone Airbnb payout adjustment"
            )
            proposed_account = "AirBNB Fees"
            proposed_class = "Hospitality"
            proposed_resolution = (
                "Review and promote standalone adjustment"
            )
        elif transaction_type in {
            "refund",
            "resolution adjustment",
        }:
            likely_missing_component = (
                "Airbnb refund or resolution adjustment"
            )
            proposed_resolution = (
                "Classify against reservation or fee account"
            )
        elif transaction_type == "reservation":
            likely_missing_component = (
                "Original reservation earnings or service fee"
            )
            proposed_resolution = (
                "Review missing original reservation allocation"
            )
        else:
            likely_missing_component = (
                "Unclassified Airbnb payout component"
            )
            proposed_resolution = (
                "Review Airbnb payout report evidence"
            )

        rows.append(
            {
                "exception_id": _text(
                    event.get("exception_id")
                ),
                "payout_id": _text(
                    event.get("payout_id")
                ),
                "payment_event_id": _text(
                    event.get("payment_event_id")
                ),
                "transaction_type": transaction_type,
                "transaction_date": _text(
                    event.get("transaction_date")
                ),
                "confirmation_code": (
                    _text(
                        event.get("channel_reservation_id")
                    )
                    or _text(
                        event.get("transaction_id")
                    )
                ),
                "guest": _text(
                    event.get("guest")
                ),
                "listing": _text(
                    event.get("listing")
                ),
                "gross_amount": _money(
                    event.get("gross_amount")
                ),
                "processor_fee": _money(
                    event.get("processor_fee")
                ),
                "net_amount": _money(
                    event.get("net_amount")
                ),
                "history_status": history_status,
                "likely_missing_component": (
                    likely_missing_component
                ),
                "proposed_account": proposed_account,
                "proposed_class": proposed_class,
                "proposed_resolution": proposed_resolution,
                "evidence_note": _text(
                    event.get("evidence_note")
                ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=AIRBNB_COLUMNS,
    )


def build_stripe_exception_detail(
    *,
    event_evidence: pd.DataFrame,
    posting_history: pd.DataFrame,
    manual_seeds: pd.DataFrame,
    reversal_preview: pd.DataFrame,
) -> pd.DataFrame:
    if event_evidence.empty:
        return pd.DataFrame(columns=STRIPE_COLUMNS)

    stripe_events = event_evidence.loc[
        event_evidence["processor"]
        .astype(str)
        .str.strip()
        .eq("Stripe")
    ].copy()

    history = _active_history(
        posting_history,
        manual_seeds,
    )

    rows: list[dict[str, object]] = []

    group_columns = [
        "exception_id",
        "payout_id",
        "processor_account",
        "source_id",
    ]

    for keys, family in stripe_events.groupby(
        group_columns,
        dropna=False,
        sort=True,
    ):
        (
            exception_id,
            payout_id,
            processor_account,
            source_id,
        ) = keys
        source_id = _text(source_id)

        transaction_types = (
            family["transaction_type"]
            .astype(str)
            .str.lower()
        )

        charge_rows = family.loc[
            transaction_types.eq("charge")
        ]
        refund_rows = family.loc[
            transaction_types.isin(
                ["refund", "reversal", "dispute"]
            )
        ]
        adjustment_rows = family.loc[
            transaction_types.eq("adjustment")
        ]
        other_rows = family.loc[
            ~family.index.isin(
                charge_rows.index
                .union(refund_rows.index)
                .union(adjustment_rows.index)
            )
        ]

        charge = (
            charge_rows.iloc[0]
            if not charge_rows.empty
            else None
        )

        source_history = pd.DataFrame()
        if (
            not history.empty
            and "source_id" in history.columns
            and source_id
        ):
            source_history = history.loc[
                history["source_id"]
                .astype(str)
                .str.strip()
                .eq(source_id)
            ].copy()

        original_history_lines = 0
        if not source_history.empty:
            if "posting_type" in source_history.columns:
                original_history_lines = int(
                    source_history["posting_type"]
                    .astype(str)
                    .str.strip()
                    .eq("Original")
                    .sum()
                )
            else:
                original_history_lines = len(
                    source_history
                )

        reversal_lines = 0
        if (
            reversal_preview is not None
            and not reversal_preview.empty
            and "source_id" in reversal_preview.columns
            and source_id
        ):
            reversal_lines = int(
                reversal_preview["source_id"]
                .astype(str)
                .str.strip()
                .eq(source_id)
                .sum()
            )

        refund_total = round(
            pd.to_numeric(
                refund_rows["gross_amount"],
                errors="coerce",
            )
            .fillna(0.0)
            .sum(),
            2,
        )
        adjustment_total = round(
            pd.to_numeric(
                adjustment_rows["gross_amount"],
                errors="coerce",
            )
            .fillna(0.0)
            .sum(),
            2,
        )
        other_total = round(
            pd.to_numeric(
                other_rows["net_amount"],
                errors="coerce",
            )
            .fillna(0.0)
            .sum(),
            2,
        )

        missing_original = original_history_lines == 0

        if missing_original and charge is not None:
            likely_resolution = (
                "Create evidence-backed original charge seed"
            )
        elif missing_original:
            likely_resolution = (
                "Locate original charge and create posting-history seed"
            )
        elif (
            refund_total != 0.0
            or adjustment_total != 0.0
        ) and reversal_lines == 0:
            likely_resolution = (
                "Generate or promote reversal lines"
            )
        elif reversal_lines:
            likely_resolution = (
                "Rebuild ledger-backed draft with reversal lines"
            )
        else:
            likely_resolution = (
                "Review payout membership and posting assignment"
            )

        family_difference = round(
            pd.to_numeric(
                family["net_amount"],
                errors="coerce",
            )
            .fillna(0.0)
            .sum(),
            2,
        )

        notes = []
        if source_id:
            notes.append(
                f"Stripe source {source_id}."
            )
        if missing_original:
            notes.append(
                "No Original posting-history lines found."
            )
        else:
            notes.append(
                f"{original_history_lines} Original line(s) found."
            )
        if reversal_lines:
            notes.append(
                f"{reversal_lines} reversal preview line(s) found."
            )

        rows.append(
            {
                "exception_id": _text(exception_id),
                "payout_id": _text(payout_id),
                "processor_account": _text(
                    processor_account
                ),
                "source_id": source_id,
                "original_charge_event_id": (
                    _text(
                        charge.get("payment_event_id")
                    )
                    if charge is not None
                    else ""
                ),
                "original_charge_gross": (
                    _money(
                        charge.get("gross_amount")
                    )
                    if charge is not None
                    else 0.0
                ),
                "original_charge_fee": (
                    _money(
                        charge.get("processor_fee")
                    )
                    if charge is not None
                    else 0.0
                ),
                "original_charge_net": (
                    _money(
                        charge.get("net_amount")
                    )
                    if charge is not None
                    else 0.0
                ),
                "original_reservation_id": (
                    _text(
                        charge.get("reservation_id")
                    )
                    if charge is not None
                    else ""
                ),
                "original_channel_reservation_id": (
                    _text(
                        charge.get(
                            "channel_reservation_id"
                        )
                    )
                    if charge is not None
                    else ""
                ),
                "original_guest": (
                    _text(charge.get("guest"))
                    if charge is not None
                    else ""
                ),
                "original_listing": (
                    _text(charge.get("listing"))
                    if charge is not None
                    else ""
                ),
                "refund_total": refund_total,
                "adjustment_total": adjustment_total,
                "other_event_total": other_total,
                "event_count": len(family),
                "original_posting_history_lines": (
                    original_history_lines
                ),
                "reversal_preview_lines": reversal_lines,
                "missing_original_posting_history": (
                    "Yes" if missing_original else "No"
                ),
                "family_difference": family_difference,
                "likely_resolution": likely_resolution,
                "evidence_note": " ".join(notes),
            }
        )

    return pd.DataFrame(
        rows,
        columns=STRIPE_COLUMNS,
    )


def build_exception_summary(
    *,
    exceptions: pd.DataFrame,
    event_evidence: pd.DataFrame,
    stripe_detail: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for _, exception in exceptions.iterrows():
        processor = _text(
            exception.get("processor")
        )
        processor_account = _text(
            exception.get("processor_account")
        )
        payout_id = _text(
            exception.get("payout_id")
        )
        exception_id = _exception_id(
            processor,
            payout_id,
        )
        difference = _money(
            exception.get("bank_difference")
        )

        events = event_evidence.loc[
            event_evidence["exception_id"]
            .astype(str)
            .eq(exception_id)
        ]
        unposted = events.loc[
            events["event_posted_in_history"]
            .astype(str)
            .eq("No")
        ]
        missing_original = events.loc[
            events["event_role"]
            .astype(str)
            .eq("Missing Original Posting History")
        ]
        unlinked = events.loc[
            events["event_role"]
            .astype(str)
            .eq("Unclassified Event")
        ]

        transaction_types = (
            events["transaction_type"]
            .astype(str)
            .str.lower()
        )

        if processor == "Airbnb":
            if (
                transaction_types.eq("adjustment").any()
                and not unposted.empty
            ):
                category = "Missing Airbnb Adjustment"
                resolution = (
                    "Review and promote standalone Airbnb adjustment"
                )
                confidence = "High"
            elif not unposted.empty:
                category = (
                    "Missing Airbnb Payout Component"
                )
                resolution = (
                    "Review Airbnb payout rows and classify missing component"
                )
                confidence = "Medium"
            else:
                category = (
                    "Airbnb Payout Total Mismatch"
                )
                resolution = (
                    "Review Airbnb sequence and payout grouping"
                )
                confidence = "Low"
        elif processor == "Stripe":
            stripe_rows = stripe_detail.loc[
                stripe_detail["exception_id"]
                .astype(str)
                .eq(exception_id)
            ]

            missing_sources = int(
                stripe_rows[
                    "missing_original_posting_history"
                ]
                .astype(str)
                .eq("Yes")
                .sum()
            )
            reversal_sources = int(
                pd.to_numeric(
                    stripe_rows["reversal_preview_lines"],
                    errors="coerce",
                )
                .fillna(0)
                .gt(0)
                .sum()
            )

            if missing_sources:
                category = (
                    "Missing Stripe Original Charge History"
                )
                resolution = (
                    "Create evidence-backed original charge seed(s)"
                )
                confidence = "High"
            elif reversal_sources:
                category = (
                    "Stripe Reversal Not Reflected in Draft"
                )
                resolution = (
                    "Rebuild ledger-backed draft with reversal history"
                )
                confidence = "High"
            elif not unposted.empty:
                category = (
                    "Unposted Stripe Payout Events"
                )
                resolution = (
                    "Classify unposted charge-family events"
                )
                confidence = "Medium"
            else:
                category = (
                    "Stripe Payout Membership Mismatch"
                )
                resolution = (
                    "Review payout membership export and assignments"
                )
                confidence = "Low"
        else:
            category = (
                "Unclassified Processor Exception"
            )
            resolution = (
                "Review processor evidence manually"
            )
            confidence = "Low"

        if difference > 0:
            direction = "Posting total too high"
        elif difference < 0:
            direction = "Posting total too low"
        else:
            direction = "No difference"

        source_ids = (
            missing_original["source_id"]
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
        )

        rows.append(
            {
                "exception_id": exception_id,
                "processor": processor,
                "processor_account": processor_account,
                "payout_id": payout_id,
                "bank_transaction_date": _date_text(
                    exception.get(
                        "bank_transaction_date"
                    )
                ),
                "bank_description": _text(
                    exception.get("bank_description")
                ),
                "bank_amount": _money(
                    exception.get("bank_amount")
                ),
                "posting_total": _money(
                    exception.get("posting_total")
                ),
                "difference": difference,
                "difference_direction": direction,
                "absolute_difference": abs(difference),
                "exception_category": category,
                "likely_resolution_type": resolution,
                "evidence_confidence": confidence,
                "source_event_count": len(events),
                "unposted_event_count": len(unposted),
                "missing_original_source_count": (
                    source_ids.nunique()
                ),
                "unlinked_event_count": len(unlinked),
                "adjustment_event_count": int(
                    transaction_types.eq(
                        "adjustment"
                    ).sum()
                ),
                "refund_event_count": int(
                    transaction_types.isin(
                        [
                            "refund",
                            "reversal",
                            "dispute",
                        ]
                    ).sum()
                ),
                "charge_event_count": int(
                    transaction_types.isin(
                        [
                            "charge",
                            "reservation",
                            "payment",
                        ]
                    ).sum()
                ),
                "review_status": (
                    "Ready for Exception Review"
                ),
                "resolution_status": "Unresolved",
                "review_notes": (
                    f"{len(events)} event(s); "
                    f"{len(unposted)} unposted; "
                    f"{len(missing_original)} missing-original."
                ),
            }
        )

    result = pd.DataFrame(
        rows,
        columns=SUMMARY_COLUMNS,
    )
    if result.empty:
        return result

    return result.sort_values(
        [
            "processor",
            "absolute_difference",
            "bank_transaction_date",
        ],
        ascending=[True, True, True],
    ).reset_index(drop=True)


def build_exception_review_model(
    *,
    posting_package_summary: pd.DataFrame,
    payment_ledger: pd.DataFrame,
    posting_history: pd.DataFrame,
    manual_seeds: pd.DataFrame,
    reversal_review: pd.DataFrame,
    reversal_preview: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    exceptions = posting_package_summary.loc[
        posting_package_summary["confidence"]
        .astype(str)
        .str.strip()
        .eq("Needs Review")
    ].copy()

    event_evidence = build_exception_event_evidence(
        exceptions=exceptions,
        payment_ledger=payment_ledger,
        posting_history=posting_history,
        manual_seeds=manual_seeds,
        reversal_review=reversal_review,
    )
    airbnb_detail = build_airbnb_exception_detail(
        event_evidence
    )
    stripe_detail = build_stripe_exception_detail(
        event_evidence=event_evidence,
        posting_history=posting_history,
        manual_seeds=manual_seeds,
        reversal_preview=reversal_preview,
    )
    summary = build_exception_summary(
        exceptions=exceptions,
        event_evidence=event_evidence,
        stripe_detail=stripe_detail,
    )

    return (
        summary,
        event_evidence,
        airbnb_detail,
        stripe_detail,
    )
