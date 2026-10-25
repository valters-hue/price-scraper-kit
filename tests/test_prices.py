import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prices import parse_price  # noqa: E402


@pytest.mark.parametrize(
    "text, amount, currency",
    [
        ("£51.77", 51.77, "GBP"),
        ("$1,234.56", 1234.56, "USD"),
        ("1.234,56 €", 1234.56, "EUR"),
        ("1 234,56 EUR", 1234.56, "EUR"),
        ("12,50 €", 12.5, "EUR"),
        ("From $19.99", 19.99, "USD"),
        ("Was 2.499 kr", 2499.0, "SEK"),
        ("99 zł", 99.0, "PLN"),
        ("CHF 1'250.00", 1250.0, "CHF"),
        ("1,000", 1000.0, None),
        ("0.999", 0.999, None),
    ],
)
def test_parse_price(text, amount, currency):
    p = parse_price(text)
    assert p is not None
    assert p.amount == pytest.approx(amount)
    assert p.currency == currency


@pytest.mark.parametrize("text", [None, "", "Out of stock", "—"])
def test_no_price(text):
    assert parse_price(text) is None
