"""Turn price text from any shop into a number and a currency.

Handles US style (1,234.56), EU style (1.234,56 / 1 234,56), currency
symbols or codes on either side, and "from"/"was" noise around the price.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

SYMBOLS = {
    "€": "EUR", "$": "USD", "£": "GBP", "¥": "JPY", "₹": "INR",
    "zł": "PLN", "kr": "SEK", "CHF": "CHF", "Fr.": "CHF",
}
CODES = {"EUR", "USD", "GBP", "PLN", "SEK", "NOK", "DKK", "CHF", "JPY", "INR", "CAD", "AUD"}

_NUMBER = re.compile(r"\d[\d\s.,'  ]*")


@dataclass(frozen=True)
class Price:
    amount: float
    currency: Optional[str]


def detect_currency(text: str) -> Optional[str]:
    upper = text.upper()
    for code in CODES:
        if re.search(rf"\b{code}\b", upper):
            return code
    # Longest symbols first so "Fr." wins over nothing and "zł" over "z"
    for sym in sorted(SYMBOLS, key=len, reverse=True):
        if sym in text:
            return SYMBOLS[sym]
    return None


def _normalise(num: str) -> Optional[float]:
    s = re.sub(r"[\s'  ]", "", num).strip(".,")
    if not s:
        return None
    last_dot, last_comma = s.rfind("."), s.rfind(",")
    if last_dot != -1 and last_comma != -1:
        # The right-most separator is the decimal one
        dec = "." if last_dot > last_comma else ","
        thou = "," if dec == "." else "."
        s = s.replace(thou, "").replace(dec, ".")
    elif last_comma != -1:
        # "1,234" (thousands) vs "12,50" (decimal): 3 digits after = thousands
        tail = s[last_comma + 1:]
        s = s.replace(",", "") if len(tail) == 3 and s.count(",") >= 1 and len(s) > 4 else s.replace(",", ".")
    elif last_dot != -1:
        tail = s[last_dot + 1:]
        if len(tail) == 3 and s.count(".") > 1:
            s = s.replace(".", "")  # 1.234.567
        elif len(tail) == 3 and len(s) > 4 and s.count(".") == 1 and not s.startswith("0"):
            # "1.234" is ambiguous; shops in EU use it for thousands
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_price(text: str | None) -> Optional[Price]:
    """Return the first price found in `text`, or None."""
    if not text:
        return None
    match = _NUMBER.search(text)
    if not match:
        return None
    amount = _normalise(match.group(0))
    if amount is None:
        return None
    return Price(round(amount, 4), detect_currency(text))
