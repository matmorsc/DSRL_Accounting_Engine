from __future__ import annotations

import csv
from pathlib import Path

import pytest
from openpyxl import load_workbook

from src.presentation.posting_workbook import (
    PackageLine,
    PackageSummary,
    _group_package_lines,
    build_workbook,
    export_posting_package,
    load_lines,
    output_filename,
    package_month_label,
)


def summary(
    bank_date: str,
) -> PackageSummary:
    return PackageSummary(
        package_id="pkg1",
        payout_id="po1",
        processor="Stripe",
        processor_account="Main Guesty",
        processor_payout_date="2026-07-08",
        bank_transaction_id="bank1",
        bank_transaction_date=bank_date,
        bank_description="STRIPE PAYOUT",
        bank_amount=134.32,
        payout_amount=134.32,
        posting_total=134.32,
        difference=0.0,
        bank_difference=0.0,
        balanced="Yes",
        bank_balanced="Yes",
        review_status="Ready for Review",
        confidence="Ready",
        comparison_status="Improved",
        posting_line_count=3,
        payment_event_count=4,
        source_count=3,
        reversal_line_count=2,
        seed_line_count=0,
        sheet_name="Stripe - 2026-07-08",
        bank_feed_label=(
            "2026-07-08 | STRIPE PAYOUT | 134.32"
        ),
        review_notes="Includes reversal lines.",
    )


def lines() -> list[PackageLine]:
    return [
        PackageLine(
            package_id="pkg1",
            payout_id="po1",
            line_number=1,
            account="Motel Rent - Short Term",
            qb_class="Hospitality",
            description="Room revenue",
            amount=188.64,
            posting_type="Original",
            ledger_source="Persistent History",
            line_note="Persistent accounting history.",
        ),
        PackageLine(
            package_id="pkg1",
            payout_id="po1",
            line_number=2,
            account="RV Rent - Nightly",
            qb_class="RV Sites",
            description="Refund",
            amount=-54.32,
            posting_type="Reversal",
            ledger_source="Reversal Preview",
            line_note=(
                "Historical reversal. Generated from "
                "posting-history reversal."
            ),
        ),
    ]


def summary_for(
    *,
    package_id: str,
    payout_id: str,
    sheet_name: str,
    confidence: str = "Ready",
    review_status: str = "Ready for Review",
    bank_amount: float = 200.00,
    posting_total: float = 200.00,
) -> PackageSummary:
    return PackageSummary(
        package_id=package_id,
        payout_id=payout_id,
        processor="Stripe",
        processor_account="Main Guesty",
        processor_payout_date="2026-09-14",
        bank_transaction_id=f"bank-{payout_id}",
        bank_transaction_date="2026-09-14",
        bank_description="STRIPE PAYOUT",
        bank_amount=bank_amount,
        payout_amount=posting_total,
        posting_total=posting_total,
        difference=0.0,
        bank_difference=round(posting_total - bank_amount, 2),
        balanced="Yes",
        bank_balanced="Yes",
        review_status=review_status,
        confidence=confidence,
        comparison_status="Improved",
        posting_line_count=2,
        payment_event_count=2,
        source_count=2,
        reversal_line_count=0,
        seed_line_count=0,
        sheet_name=sheet_name,
        bank_feed_label=(
            f"2026-09-14 | STRIPE PAYOUT | {bank_amount:.2f}"
        ),
        review_notes="",
    )


def line_for(
    *,
    package_id: str,
    payout_id: str,
    line_number: int,
    account: str,
    qb_class: str,
    description: str,
    amount: float,
    posting_type: str = "Original",
) -> PackageLine:
    return PackageLine(
        package_id=package_id,
        payout_id=payout_id,
        line_number=line_number,
        account=account,
        qb_class=qb_class,
        description=description,
        amount=amount,
        posting_type=posting_type,
        ledger_source="Persistent History",
        line_note="Persistent accounting history.",
    )


def test_month_label_uses_latest_bank_date():
    summaries = [
        summary("2026-06-29"),
        summary("2026-07-08"),
    ]
    assert package_month_label(
        summaries
    ) == "2026-07"


def test_output_filename_is_month_specific():
    summaries = [summary("2026-07-08")]
    assert output_filename(
        summaries
    ) == (
        "QuickBooks_Posting_Package_"
        "2026-07.xlsx"
    )


def test_workbook_contains_dashboard_and_payout_sheet(
    tmp_path: Path,
):
    workbook = build_workbook(
        [summary("2026-07-08")],
        lines(),
    )
    path = tmp_path / "package.xlsx"
    workbook.save(path)

    reopened = load_workbook(
        path,
        data_only=False,
    )

    assert reopened.sheetnames == [
        "Dashboard",
        "Stripe - 2026-07-08",
    ]

    dashboard = reopened["Dashboard"]
    payout = reopened["Stripe - 2026-07-08"]

    assert dashboard["A1"].value.startswith(
        "Dark Sky River Lodge"
    )
    assert dashboard["A10"].value == "Open"
    assert dashboard["A10"].hyperlink is not None

    assert payout["A1"].value == (
        "Stripe Bank-Feed Split Instructions"
    )
    assert payout["B5"].value == 134.32
    assert payout["E13"].value == 188.64
    assert payout["E14"].value == -54.32


def test_same_account_and_class_consolidates_within_payout():
    grouped = _group_package_lines(
        [
            line_for(
                package_id="pkg1",
                payout_id="po1",
                line_number=1,
                account="Motel Rent - Short Term",
                qb_class="Motel",
                description="Room 4",
                amount=105.00,
            ),
            line_for(
                package_id="pkg1",
                payout_id="po1",
                line_number=2,
                account="Motel Rent - Short Term",
                qb_class="Motel",
                description="Room 8",
                amount=115.00,
            ),
        ]
    )

    assert len(grouped) == 1
    assert grouped[0].account == "Motel Rent - Short Term"
    assert grouped[0].qb_class == "Motel"
    assert grouped[0].amount == 220.00


def test_identical_lines_in_different_payouts_do_not_consolidate_across_sheets(
    tmp_path: Path,
):
    summaries = [
        summary_for(
            package_id="pkg1",
            payout_id="po1",
            sheet_name="Stripe - 2026-09-14 A",
            bank_amount=105.00,
            posting_total=105.00,
        ),
        summary_for(
            package_id="pkg2",
            payout_id="po2",
            sheet_name="Stripe - 2026-09-14 B",
            bank_amount=115.00,
            posting_total=115.00,
        ),
    ]
    detail_lines = [
        line_for(
            package_id="pkg1",
            payout_id="po1",
            line_number=1,
            account="Motel Rent - Short Term",
            qb_class="Motel",
            description="Room 4",
            amount=105.00,
        ),
        line_for(
            package_id="pkg2",
            payout_id="po2",
            line_number=1,
            account="Motel Rent - Short Term",
            qb_class="Motel",
            description="Room 8",
            amount=115.00,
        ),
    ]

    workbook = build_workbook(summaries, detail_lines)
    path = tmp_path / "cross_payout.xlsx"
    workbook.save(path)

    reopened = load_workbook(path, data_only=False)
    assert reopened["Stripe - 2026-09-14 A"]["E13"].value == 105.00
    assert reopened["Stripe - 2026-09-14 B"]["E13"].value == 115.00


def test_tax_payable_lines_group_when_entry_dimensions_match():
    grouped = _group_package_lines(
        [
            line_for(
                package_id="pkg1",
                payout_id="po1",
                line_number=1,
                account="Lodging Taxes Payable",
                qb_class="Motel",
                description="Tax line 1",
                amount=-12.34,
            ),
            line_for(
                package_id="pkg1",
                payout_id="po1",
                line_number=2,
                account="Lodging Taxes Payable",
                qb_class="Motel",
                description="Tax line 2",
                amount=-3.21,
            ),
        ]
    )

    assert len(grouped) == 1
    assert grouped[0].amount == -15.55


def test_different_accounts_do_not_group():
    grouped = _group_package_lines(
        [
            line_for(
                package_id="pkg1",
                payout_id="po1",
                line_number=1,
                account="Motel Rent - Short Term",
                qb_class="Motel",
                description="Room revenue",
                amount=105.00,
            ),
            line_for(
                package_id="pkg1",
                payout_id="po1",
                line_number=2,
                account="Cabin Rent - Short-Term",
                qb_class="Cabin",
                description="Cabin revenue",
                amount=115.00,
            ),
        ]
    )
    assert len(grouped) == 2


def test_different_classes_do_not_group():
    grouped = _group_package_lines(
        [
            line_for(
                package_id="pkg1",
                payout_id="po1",
                line_number=1,
                account="Motel Rent - Short Term",
                qb_class="Motel",
                description="Room 4",
                amount=105.00,
            ),
            line_for(
                package_id="pkg1",
                payout_id="po1",
                line_number=2,
                account="Motel Rent - Short Term",
                qb_class="Cabin",
                description="Room 8",
                amount=115.00,
            ),
        ]
    )
    assert len(grouped) == 2


def test_distinct_posting_types_do_not_net_even_when_account_and_class_match():
    grouped = _group_package_lines(
        [
            line_for(
                package_id="pkg1",
                payout_id="po1",
                line_number=1,
                account="Motel Rent - Short Term",
                qb_class="Motel",
                description="Original revenue",
                amount=120.00,
                posting_type="Original",
            ),
            line_for(
                package_id="pkg1",
                payout_id="po1",
                line_number=2,
                account="Motel Rent - Short Term",
                qb_class="Motel",
                description="Revenue reversal",
                amount=-20.00,
                posting_type="Reversal",
            ),
        ]
    )
    assert len(grouped) == 2
    assert round(sum(line.amount for line in grouped), 2) == 100.00


def test_grouped_total_equals_original_total_to_cent():
    original = [
        line_for(
            package_id="pkg1",
            payout_id="po1",
            line_number=1,
            account="Motel Rent - Short Term",
            qb_class="Motel",
            description="Room 4",
            amount=105.00,
        ),
        line_for(
            package_id="pkg1",
            payout_id="po1",
            line_number=2,
            account="Motel Rent - Short Term",
            qb_class="Motel",
            description="Room 8",
            amount=115.00,
        ),
        line_for(
            package_id="pkg1",
            payout_id="po1",
            line_number=3,
            account="Stripe Fees",
            qb_class="Motel",
            description="Fee",
            amount=-6.38,
            posting_type="Reversal",
        ),
    ]
    grouped = _group_package_lines(original)
    assert round(sum(line.amount for line in original), 2) == round(
        sum(line.amount for line in grouped),
        2,
    )


def test_ready_and_needs_review_status_counts_are_unchanged_in_dashboard(
    tmp_path: Path,
):
    workbook = build_workbook(
        [
            summary_for(
                package_id="pkg1",
                payout_id="po1",
                sheet_name="Stripe Ready",
                confidence="Ready",
                review_status="Ready for Review",
                bank_amount=100.00,
                posting_total=100.00,
            ),
            summary_for(
                package_id="pkg2",
                payout_id="po2",
                sheet_name="Stripe Review",
                confidence="Needs Review",
                review_status="Review Required",
                bank_amount=120.00,
                posting_total=110.00,
            ),
        ],
        [
            line_for(
                package_id="pkg1",
                payout_id="po1",
                line_number=1,
                account="Motel Rent - Short Term",
                qb_class="Motel",
                description="Room",
                amount=100.00,
            ),
            line_for(
                package_id="pkg2",
                payout_id="po2",
                line_number=1,
                account="Motel Rent - Short Term",
                qb_class="Motel",
                description="Room",
                amount=110.00,
            ),
        ],
    )
    path = tmp_path / "status_counts.xlsx"
    workbook.save(path)

    reopened = load_workbook(path, data_only=False)
    dashboard = reopened["Dashboard"]
    assert dashboard["B5"].value == 1
    assert dashboard["B6"].value == 1


def test_export_does_not_modify_source_csv_artifacts(
    tmp_path: Path,
):
    summary_path = tmp_path / "summary.csv"
    lines_path = tmp_path / "lines.csv"
    output_path = tmp_path / "package.xlsx"

    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "package_id",
                "payout_id",
                "processor",
                "processor_account",
                "processor_payout_date",
                "bank_transaction_id",
                "bank_transaction_date",
                "bank_description",
                "bank_amount",
                "payout_amount",
                "posting_total",
                "difference",
                "bank_difference",
                "balanced",
                "bank_balanced",
                "review_status",
                "confidence",
                "comparison_status",
                "posting_line_count",
                "payment_event_count",
                "source_count",
                "reversal_line_count",
                "seed_line_count",
                "sheet_name",
                "bank_feed_label",
                "review_notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "package_id": "pkg1",
                "payout_id": "po1",
                "processor": "Stripe",
                "processor_account": "Main Guesty",
                "processor_payout_date": "2026-09-14",
                "bank_transaction_id": "bank1",
                "bank_transaction_date": "2026-09-14",
                "bank_description": "STRIPE PAYOUT",
                "bank_amount": "220.00",
                "payout_amount": "220.00",
                "posting_total": "220.00",
                "difference": "0.00",
                "bank_difference": "0.00",
                "balanced": "Yes",
                "bank_balanced": "Yes",
                "review_status": "Ready for Review",
                "confidence": "Ready",
                "comparison_status": "Improved",
                "posting_line_count": "2",
                "payment_event_count": "2",
                "source_count": "2",
                "reversal_line_count": "0",
                "seed_line_count": "0",
                "sheet_name": "Stripe - 2026-09-14",
                "bank_feed_label": "2026-09-14 | STRIPE PAYOUT | 220.00",
                "review_notes": "",
            }
        )

    with lines_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "package_id",
                "payout_id",
                "line_number",
                "account",
                "class",
                "description",
                "amount",
                "posting_type",
                "ledger_source",
                "line_note",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "package_id": "pkg1",
                "payout_id": "po1",
                "line_number": "1",
                "account": "Motel Rent - Short Term",
                "class": "Motel",
                "description": "Room 4",
                "amount": "105.00",
                "posting_type": "Original",
                "ledger_source": "Persistent History",
                "line_note": "Persistent accounting history.",
            }
        )
        writer.writerow(
            {
                "package_id": "pkg1",
                "payout_id": "po1",
                "line_number": "2",
                "account": "Motel Rent - Short Term",
                "class": "Motel",
                "description": "Room 8",
                "amount": "115.00",
                "posting_type": "Original",
                "ledger_source": "Persistent History",
                "line_note": "Persistent accounting history.",
            }
        )

    before = lines_path.read_text(encoding="utf-8")
    export_posting_package(
        summary_path=summary_path,
        lines_path=lines_path,
        output_path=output_path,
    )
    after = lines_path.read_text(encoding="utf-8")

    assert before == after


def test_workbook_header_metadata_remains_present_after_grouping(
    tmp_path: Path,
):
    workbook = build_workbook(
        [summary_for(
            package_id="pkg1",
            payout_id="po1",
            sheet_name="Stripe - 2026-09-14",
            bank_amount=220.00,
            posting_total=220.00,
        )],
        [
            line_for(
                package_id="pkg1",
                payout_id="po1",
                line_number=1,
                account="Motel Rent - Short Term",
                qb_class="Motel",
                description="Room 4",
                amount=105.00,
            ),
            line_for(
                package_id="pkg1",
                payout_id="po1",
                line_number=2,
                account="Motel Rent - Short Term",
                qb_class="Motel",
                description="Room 8",
                amount=115.00,
            ),
        ],
    )
    path = tmp_path / "metadata.xlsx"
    workbook.save(path)

    reopened = load_workbook(path, data_only=False)
    payout = reopened["Stripe - 2026-09-14"]

    assert payout["A1"].value == "Stripe Bank-Feed Split Instructions"
    assert payout["A3"].value == "Bank date"
    assert payout["D3"].value == "Processor"
    assert payout["B10"].value == "po1"


def test_real_posting_package_grouping_preserves_per_payout_totals_if_fixture_exists():
    lines_path = Path("data/processed/posting_package_v10.csv")
    if not lines_path.exists():
        pytest.skip("Current posting package fixture is not available in data/processed.")

    lines = load_lines(lines_path)
    lines_by_package: dict[str, list[PackageLine]] = {}
    for line in lines:
        lines_by_package.setdefault(line.package_id, []).append(line)

    violations: list[str] = []
    for package_id, package_lines in lines_by_package.items():
        original_total = round(sum(item.amount for item in package_lines), 2)
        grouped_total = round(
            sum(item.amount for item in _group_package_lines(package_lines)),
            2,
        )
        if grouped_total != original_total:
            payout_id = package_lines[0].payout_id if package_lines else ""
            violations.append(
                f"package_id={package_id} payout_id={payout_id} "
                f"original={original_total:.2f} grouped={grouped_total:.2f}"
            )

    assert not violations, "\n".join(violations)
