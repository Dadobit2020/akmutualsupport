"""
Money helpers. All monetary values are stored as integers in the smallest currency unit
(cents for USD). Never use floats for money.
"""
from decimal import Decimal


def cents_to_dollars(cents: int) -> Decimal:
    return Decimal(cents) / 100


def dollars_to_cents(dollars: Decimal | float | str) -> int:
    return int(Decimal(str(dollars)) * 100)


def format_money(cents: int, currency: str = "USD") -> str:
    return f"${cents_to_dollars(cents):,.2f}"
