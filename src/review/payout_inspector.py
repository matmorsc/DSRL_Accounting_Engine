from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


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


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
    )


def _subset(
    frame: pd.DataFrame,
    column: str,
    value: str,
) -> pd.DataFrame:
    if frame.empty or column not in frame.columns:
        return pd.DataFrame()
    return frame.loc[
        frame[column].astype(str).str.strip().eq(value)
    ].copy()


def _sum(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame.columns:
        return 0.0
    return round(
        pd.to_numeric(
            frame[column],
            errors="coerce",
        ).fillna(0.0).sum(),
        2,
    )


def _format_frame(
    frame: pd.DataFrame,
    columns: list[str],
) -> str:
    if frame.empty:
        return "None"

    existing = [
        column
        for column in columns
        if column in frame.columns
    ]
    if not existing:
        return f"{len(frame)} row(s); requested fields unavailable."

    return frame[existing].to_string(index=False)


@dataclass
class PayoutInspection:
    payout_id: str
    summary: str
    payment_events: pd.DataFrame
    posting_history: pd.DataFrame
    reversal_lines: pd.DataFrame
    stripe_families: pd.DataFrame
    reservation_rows: pd.DataFrame


def inspect_payout(
    *,
    payout_id: str,
    processed_dir: Path,
    config_dir: Path,
) -> PayoutInspection:
    payout_ledger = _load_csv(
        processed_dir / "payout_ledger_v6.csv"
    )
    if payout_ledger.empty:
        payout_ledger = _load_csv(
            processed_dir / "payout_ledger.csv"
        )

    payment_ledger = _load_csv(
        processed_dir / "payment_ledger_v6.csv"
    )
    if payment_ledger.empty:
        payment_ledger = _load_csv(
            processed_dir / "payment_ledger.csv"
        )

    posting_summary = _load_csv(
        processed_dir / "posting_package_summary_v10.csv"
    )
    posting_lines = _load_csv(
        processed_dir / "posting_package_v10.csv"
    )
    deposit_drafts = _load_csv(
        processed_dir / "deposit_drafts_v9.csv"
    )
    deposit_lines = _load_csv(
        processed_dir / "deposit_draft_lines_v9.csv"
    )
    bank_transactions = _load_csv(
        processed_dir / "bank_transactions.csv"
    )
    reconciliation = _load_csv(
        processed_dir
        / "exception_reconciliation_summary_v11.csv"
    )
    stripe_families = _load_csv(
        processed_dir
        / "stripe_family_reconciliation_v11.csv"
    )
    reversal_preview = _load_csv(
        processed_dir
        / "posting_history_reversal_preview.csv"
    )
    persistent_history = _load_csv(
        config_dir / "posting_history.csv"
    )
    manual_seeds = _load_csv(
        config_dir / "posting_history_manual_seeds.csv"
    )
    reservations = _load_csv(
        processed_dir / "reservations.csv"
    )

    payout_row = _subset(
        payout_ledger,
        "payout_id",
        payout_id,
    )
    package_row = _subset(
        posting_summary,
        "payout_id",
        payout_id,
    )
    draft_row = _subset(
        deposit_drafts,
        "payout_id",
        payout_id,
    )
    recon_row = _subset(
        reconciliation,
        "payout_id",
        payout_id,
    )

    payment_events = _subset(
        payment_ledger,
        "payout_id",
        payout_id,
    )
    package_lines_for_payout = _subset(
        posting_lines,
        "payout_id",
        payout_id,
    )
    deposit_lines_for_payout = _subset(
        deposit_lines,
        "payout_id",
        payout_id,
    )
    reversal_lines = _subset(
        reversal_preview,
        "payout_id",
        payout_id,
    )
    family_rows = _subset(
        stripe_families,
        "payout_id",
        payout_id,
    )

    history_frames = []
    for frame, source in [
        (persistent_history, "Persistent History"),
        (manual_seeds, "Manual Seed History"),
    ]:
        subset = _subset(
            frame,
            "payout_id",
            payout_id,
        )
        if not subset.empty:
            subset["history_source"] = source
            history_frames.append(subset)

    posting_history = (
        pd.concat(
            history_frames,
            ignore_index=True,
            sort=False,
        )
        if history_frames
        else pd.DataFrame()
    )

    reservation_ids: set[str] = set()
    channel_ids: set[str] = set()

    for frame in [
        payment_events,
        posting_history,
        family_rows,
    ]:
        if "reservation_id" in frame.columns:
            reservation_ids.update(
                value
                for value in (
                    frame["reservation_id"]
                    .astype(str)
                    .str.strip()
                )
                if value
            )
        if "channel_reservation_id" in frame.columns:
            channel_ids.update(
                value
                for value in (
                    frame["channel_reservation_id"]
                    .astype(str)
                    .str.strip()
                )
                if value
            )

    reservation_matches = pd.DataFrame()
    if not reservations.empty:
        mask = pd.Series(
            False,
            index=reservations.index,
        )
        if (
            reservation_ids
            and "reservation_id"
            in reservations.columns
        ):
            mask = mask | reservations[
                "reservation_id"
            ].astype(str).str.strip().isin(
                reservation_ids
            )
        if (
            channel_ids
            and "channel_reservation_id"
            in reservations.columns
        ):
            mask = mask | reservations[
                "channel_reservation_id"
            ].astype(str).str.strip().isin(
                channel_ids
            )
        reservation_matches = reservations.loc[
            mask
        ].copy()

    bank_row = pd.DataFrame()
    if not package_row.empty:
        bank_date = _text(
            package_row.iloc[0].get(
                "bank_transaction_date"
            )
        )
        bank_amount = _money(
            package_row.iloc[0].get(
                "bank_amount"
            )
        )

        if (
            not bank_transactions.empty
            and "transaction_date"
            in bank_transactions.columns
            and "amount"
            in bank_transactions.columns
        ):
            amount_series = pd.to_numeric(
                bank_transactions["amount"],
                errors="coerce",
            ).fillna(0.0)
            date_series = (
                bank_transactions[
                    "transaction_date"
                ].astype(str).str[:10]
            )
            bank_row = bank_transactions.loc[
                date_series.eq(bank_date)
                & amount_series.sub(
                    bank_amount
                ).abs().le(0.02)
            ].copy()

    payout_amount = (
        _money(
            payout_row.iloc[0].get(
                "payout_amount"
            )
        )
        if not payout_row.empty
        else 0.0
    )
    posting_total = (
        _money(
            package_row.iloc[0].get(
                "posting_total"
            )
        )
        if not package_row.empty
        else _sum(
            deposit_lines_for_payout,
            "amount",
        )
    )
    difference = (
        _money(
            package_row.iloc[0].get(
                "bank_difference"
            )
        )
        if not package_row.empty
        else round(
            posting_total - payout_amount,
            2,
        )
    )

    processor = (
        _text(
            payout_row.iloc[0].get(
                "processor"
            )
        )
        if not payout_row.empty
        else _text(
            package_row.iloc[0].get(
                "processor"
            )
        )
        if not package_row.empty
        else ""
    )

    confidence = (
        _text(
            package_row.iloc[0].get(
                "confidence"
            )
        )
        if not package_row.empty
        else ""
    )
    recommendation = (
        _text(
            recon_row.iloc[0].get(
                "recommended_resolution"
            )
        )
        if not recon_row.empty
        else ""
    )
    sign_consistency = (
        _text(
            recon_row.iloc[0].get(
                "sign_consistency"
            )
        )
        if not recon_row.empty
        else ""
    )
    resolution_blocked = (
        _text(
            recon_row.iloc[0].get(
                "resolution_blocked"
            )
        )
        if not recon_row.empty
        else ""
    )

    summary_lines = [
        f"Payout ID:          {payout_id}",
        f"Processor:          {processor}",
        f"Payout amount:      {payout_amount:.2f}",
        f"Posting total:      {posting_total:.2f}",
        f"Difference:         {difference:.2f}",
        f"Package confidence: {confidence or 'Unavailable'}",
        f"Payment events:     {len(payment_events)}",
        f"Posting lines:      {len(package_lines_for_payout)}",
        f"History lines:      {len(posting_history)}",
        f"Reversal lines:     {len(reversal_lines)}",
        f"Stripe families:    {len(family_rows)}",
        f"Reservations found: {len(reservation_matches)}",
        f"Sign consistency:   {sign_consistency or 'Unavailable'}",
        f"Resolution blocked: {resolution_blocked or 'Unavailable'}",
        (
            "Recommendation:     "
            + (
                recommendation
                or "No reconciliation recommendation available."
            )
        ),
    ]

    if not bank_row.empty:
        description_col = (
            "description"
            if "description" in bank_row.columns
            else ""
        )
        if description_col:
            summary_lines.append(
                "Bank description:   "
                + _text(
                    bank_row.iloc[0].get(
                        description_col
                    )
                )
            )

    return PayoutInspection(
        payout_id=payout_id,
        summary="\n".join(summary_lines),
        payment_events=payment_events,
        posting_history=posting_history,
        reversal_lines=reversal_lines,
        stripe_families=family_rows,
        reservation_rows=reservation_matches,
    )


def render_inspection(
    inspection: PayoutInspection,
) -> str:
    sections = [
        "=" * 88,
        "DSRL PAYOUT INSPECTION",
        "=" * 88,
        inspection.summary,
        "",
        "PAYMENT EVENTS",
        "-" * 88,
        _format_frame(
            inspection.payment_events,
            [
                "payment_event_id",
                "transaction_type",
                "transaction_date",
                "source_id",
                "gross_amount",
                "processor_fee",
                "net_amount",
                "reservation_id",
                "channel_reservation_id",
                "guest",
                "listing",
            ],
        ),
        "",
        "ACTIVE POSTING HISTORY",
        "-" * 88,
        _format_frame(
            inspection.posting_history,
            [
                "history_source",
                "posting_line_id",
                "payment_event_id",
                "posting_type",
                "account",
                "class",
                "description",
                "signed_amount",
                "source_id",
                "guest",
                "listing",
                "classification_source",
                "notes",
            ],
        ),
        "",
        "REVERSAL PREVIEW",
        "-" * 88,
        _format_frame(
            inspection.reversal_lines,
            [
                "payment_event_id",
                "transaction_type",
                "source_id",
                "account",
                "class",
                "description",
                "signed_amount",
                "posting_type",
                "reversal_of_posting_line_id",
            ],
        ),
        "",
        "STRIPE SOURCE FAMILIES",
        "-" * 88,
        _format_frame(
            inspection.stripe_families,
            [
                "source_id",
                "family_event_total",
                "charge_total",
                "refund_total",
                "adjustment_total",
                "active_original_total",
                "reversal_preview_total",
                "ledger_effect_total",
                "family_gap",
                "family_issue",
                "candidate_resolution",
                "resolution_sign_safe",
            ],
        ),
        "",
        "RESERVATION EVIDENCE",
        "-" * 88,
        _format_frame(
            inspection.reservation_rows,
            [
                "reservation_id",
                "channel_reservation_id",
                "guest",
                "listing",
                "source",
                "confirmation_date",
                "check_in",
                "check_out",
                "accommodation_revenue",
                "state_tax",
                "county_tax",
                "local_tax",
                "total_paid",
                "total_refunded",
                "total_payout",
            ],
        ),
        "=" * 88,
    ]
    return "\n".join(sections)
