"""
CSV parsers for bank exports and Tithely exports.

Column mappings are saved per import source so the Treasurer only sets them up once.
"""
import csv
import io
import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedRow:
    transaction_date: datetime.date
    amount_cents: int
    payer_name: str
    memo: str
    raw_description: str
    source_reference: str
    raw: dict  # original row for debugging


class ParseError(Exception):
    def __init__(self, row_number: int, message: str):
        self.row_number = row_number
        self.message = message
        super().__init__(f"Row {row_number}: {message}")


def parse_amount(value: str) -> int:
    """Parse a dollar amount string to cents. Handles $1,234.56 and (100.00) negatives."""
    value = value.strip().replace("$", "").replace(",", "")
    negative = value.startswith("(") and value.endswith(")")
    value = value.strip("()")
    try:
        cents = int(round(float(value) * 100))
    except ValueError:
        raise ValueError(f"Cannot parse amount: '{value}'")
    return -cents if negative else cents


def parse_date(value: str, formats=None) -> datetime.date:
    if formats is None:
        formats = ["%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%d/%m/%Y", "%m/%d/%y"]
    value = value.strip()
    for fmt in formats:
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: '{value}'")


def parse_csv(
    content: bytes,
    *,
    date_column: str,
    amount_column: str,
    payer_column: str = "",
    memo_column: str = "",
    reference_column: str = "",
    description_column: str = "",
    skip_negative: bool = True,
) -> list[ParsedRow]:
    """
    Parse a CSV file into normalized ParsedRow records.

    Parameters correspond to column headers in the CSV; case-insensitive matching.
    """
    text = content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))

    # Normalize header names
    headers = {h.strip().lower(): h for h in (reader.fieldnames or [])}

    def get_col(row: dict, col_name: str, default: str = "") -> str:
        if not col_name:
            return default
        key = headers.get(col_name.strip().lower(), col_name)
        return (row.get(key) or "").strip()

    rows = []
    errors = []

    for i, row in enumerate(reader, start=2):  # row 1 is header
        try:
            date_str = get_col(row, date_column)
            amount_str = get_col(row, amount_column)

            if not date_str or not amount_str:
                continue

            txn_date = parse_date(date_str)
            amount_cents = parse_amount(amount_str)

            if skip_negative and amount_cents < 0:
                continue  # Skip bank debits / withdrawals

            if amount_cents <= 0:
                continue

            rows.append(ParsedRow(
                transaction_date=txn_date,
                amount_cents=amount_cents,
                payer_name=get_col(row, payer_column),
                memo=get_col(row, memo_column),
                raw_description=get_col(row, description_column),
                source_reference=get_col(row, reference_column),
                raw=dict(row),
            ))
        except (ValueError, KeyError) as e:
            errors.append(ParseError(i, str(e)))

    if errors:
        # Return partial results + raise first error for caller awareness
        raise errors[0]

    return rows


# Preset column mappings for common sources

TITHELY_COLUMN_MAP = {
    "date_column": "Date",
    "amount_column": "Amount",
    "payer_column": "Name",
    "memo_column": "Notes",
    "reference_column": "Transaction ID",
    "description_column": "Fund",
}

BANK_OF_AMERICA_COLUMN_MAP = {
    "date_column": "Date",
    "amount_column": "Amount",
    "payer_column": "Description",
    "memo_column": "Description",
    "reference_column": "Reference Number",
    "description_column": "Description",
}

CHASE_COLUMN_MAP = {
    "date_column": "Transaction Date",
    "amount_column": "Amount",
    "payer_column": "Description",
    "memo_column": "Memo",
    "reference_column": "Check or Slip #",
    "description_column": "Description",
}
