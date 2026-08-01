from __future__ import annotations

from pathlib import Path

import pandas as pd


VALID_POSTING_OVERRIDES = {
    "Already Posted",
    "Partially Posted",
    "Generate Entry",
    "Do Not Post",
    "Needs Review",
}

REQUIRED_OVERRIDE_COLUMNS = {
    "payout_id",
    "bank_transaction_id",
    "posting_status",
    "quickbooks_reference",
    "notes",
}


def _read_overrides(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(
            columns=sorted(REQUIRED_OVERRIDE_COLUMNS)
        )

    frame = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
    )

    missing = sorted(
        REQUIRED_OVERRIDE_COLUMNS.difference(
            frame.columns
        )
    )
    if missing:
        raise ValueError(
            f"Posting overrides missing columns: {missing}"
        )

    invalid = sorted(
        set(
            frame.loc[
                frame["posting_status"]
                .astype(str).str.strip().ne(""),
                "posting_status",
            ]
        ).difference(VALID_POSTING_OVERRIDES)
    )

    if invalid:
        raise ValueError(
            "Invalid posting override statuses: "
            + ", ".join(invalid)
        )

    return frame


def _select_override(
    payout: pd.Series,
    overrides: pd.DataFrame,
) -> pd.Series | None:
    payout_id = str(
        payout.get("payout_id", "")
    ).strip()
    bank_id = str(
        payout.get("bank_transaction_id", "")
    ).strip()

    candidates = overrides.loc[
        (
            overrides["payout_id"]
            .astype(str).str.strip().eq(payout_id)
            & (payout_id != "")
        )
        |
        (
            overrides["bank_transaction_id"]
            .astype(str).str.strip().eq(bank_id)
            & (bank_id != "")
        )
    ]

    if candidates.empty:
        return None

    if len(candidates) > 1:
        raise ValueError(
            f"Multiple posting overrides for payout {payout_id}"
        )

    return candidates.iloc[0]


def _first_valid_date(*values: object) -> pd.Timestamp | pd.NaT:
    for value in values:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.notna(parsed):
            return parsed
    return pd.NaT


def _first_nonzero_amount(*values: object) -> float:
    for value in values:
        try:
            amount = float(value)
        except (TypeError, ValueError):
            continue
        if amount != 0:
            return amount
    return 0.0


def _quickbooks_candidates(
    payout: pd.Series,
    quickbooks_gl: pd.DataFrame,
    date_tolerance_days: int,
    amount_tolerance: float,
) -> pd.DataFrame:
    payout_date = _first_valid_date(
        payout.get("bank_transaction_date"),
        payout.get("transaction_date"),
    )

    if pd.isna(payout_date):
        return quickbooks_gl.iloc[0:0].copy()

    payout_amount = _first_nonzero_amount(
        payout.get("bank_amount"),
        payout.get("payout_amount"),
    )
    processor = str(
        payout.get("processor", "")
    ).strip()

    candidates = quickbooks_gl.loc[
        quickbooks_gl["is_bank_deposit"].eq(True)
        & quickbooks_gl["amount"].astype(float).gt(0)
    ].copy()

    if processor:
        processor_rows = candidates.loc[
            candidates["identified_processor"]
            .astype(str).str.strip().eq(processor)
        ]
        if not processor_rows.empty:
            candidates = processor_rows

    candidates["amount_difference"] = (
        candidates["amount"].astype(float)
        - payout_amount
    ).abs()

    qb_dates = pd.to_datetime(
        candidates["transaction_date"],
        errors="coerce",
    )

    candidates["date_difference_days"] = (
        qb_dates.dt.normalize()
        - payout_date.normalize()
    ).dt.days.abs()

    return candidates.loc[
        candidates["amount_difference"].le(
            amount_tolerance
        )
        & candidates["date_difference_days"].le(
            date_tolerance_days
        )
    ].sort_values(
        [
            "date_difference_days",
            "amount_difference",
            "transaction_date",
        ]
    )


def build_posting_status(
    payout_ledger: pd.DataFrame,
    quickbooks_gl: pd.DataFrame,
    posting_overrides_path: Path,
    assume_posted_through: str,
    date_tolerance_days: int = 5,
    amount_tolerance: float = 0.02,
) -> pd.DataFrame:
    overrides = _read_overrides(
        posting_overrides_path
    )
    cutoff = pd.to_datetime(
        assume_posted_through,
        errors="raise",
    )

    rows: list[dict[str, object]] = []

    for _, payout in payout_ledger.iterrows():
        payout_id = str(
            payout.get("payout_id", "")
        ).strip()
        payout_date = _first_valid_date(
            payout.get("transaction_date")
        )
        payout_amount = _first_nonzero_amount(
            payout.get("payout_amount")
        )
        bank_amount = _first_nonzero_amount(
            payout.get("bank_amount")
        )
        bank_id = str(
            payout.get("bank_transaction_id", "")
        ).strip()

        override = _select_override(
            payout,
            overrides,
        )

        candidates = _quickbooks_candidates(
            payout=payout,
            quickbooks_gl=quickbooks_gl,
            date_tolerance_days=date_tolerance_days,
            amount_tolerance=amount_tolerance,
        )

        qb_match_count = len(candidates)

        if qb_match_count == 1:
            qb = candidates.iloc[0]
            qb_date = qb["transaction_date"]
            qb_amount = float(qb["amount"])
            qb_reference = (
                str(qb.get("number", "")).strip()
                or str(qb.get("memo", "")).strip()
            )
        else:
            qb_date = pd.NaT
            qb_amount = 0.0
            qb_reference = ""

        if override is not None:
            posting_status = str(
                override["posting_status"]
            ).strip()
            match_method = "Manual posting override"
            qb_reference = (
                str(
                    override.get(
                        "quickbooks_reference", ""
                    )
                ).strip()
                or qb_reference
            )
            notes = str(
                override.get("notes", "")
            ).strip()
        elif pd.isna(payout_date):
            posting_status = "Needs Review"
            match_method = "Payout date missing"
            notes = "Cannot compare payout to QuickBooks without a valid date."
        elif qb_match_count == 1:
            posting_status = "Already Posted"
            match_method = (
                "Exact QuickBooks deposit amount/date"
            )
            notes = ""
        elif qb_match_count > 1:
            posting_status = "Needs Review"
            match_method = (
                "Multiple QuickBooks deposit candidates"
            )
            notes = ""
        elif payout_date.normalize() <= cutoff.normalize():
            posting_status = "Needs Review"
            match_method = (
                "Before assumed-posted cutoff but no exact GL match"
            )
            notes = ""
        elif str(
            payout.get("bank_match_status", "")
        ).strip() != "Matched":
            posting_status = "Needs Review"
            match_method = "Payout not matched to bank"
            notes = ""
        else:
            posting_status = "Unposted"
            match_method = (
                "After cutoff with bank match and no QuickBooks match"
            )
            notes = ""

        generate_entry = (
            "Yes"
            if posting_status in {
                "Unposted",
                "Generate Entry",
            }
            else "No"
        )

        rows.append(
            {
                "payout_id": payout_id,
                "processor": payout.get(
                    "processor", ""
                ),
                "processor_account": payout.get(
                    "processor_account", ""
                ),
                "payout_date": payout_date,
                "payout_amount": payout_amount,
                "bank_transaction_id": bank_id,
                "bank_transaction_date": payout.get(
                    "bank_transaction_date"
                ),
                "bank_amount": bank_amount,
                "quickbooks_match_count": (
                    qb_match_count
                ),
                "quickbooks_transaction_date": qb_date,
                "quickbooks_amount": qb_amount,
                "quickbooks_reference": qb_reference,
                "amount_difference": round(
                    qb_amount
                    - (
                        bank_amount
                        if bank_amount
                        else payout_amount
                    ),
                    2,
                ),
                "posting_status": posting_status,
                "posting_match_method": match_method,
                "generate_entry": generate_entry,
                "review_required": (
                    "Yes"
                    if posting_status
                    in {
                        "Needs Review",
                        "Partially Posted",
                    }
                    else "No"
                ),
                "notes": notes,
            }
        )

    return pd.DataFrame(rows)
