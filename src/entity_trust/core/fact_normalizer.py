"""Fact Normalization Layer.

Normalizes extracted figures, currencies, dates, phone numbers, and locations
so that semantic equivalence can be recognized and genuine cross-page conflicts
can be isolated accurately.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set, Tuple


@dataclass(frozen=True)
class NormalizedFact:
    fact_type: str  # e.g., 'founding_year', 'price', 'headquarters', 'phone', 'metric'
    canonical_value: str
    numeric_value: Optional[float] = None
    currency: Optional[str] = None
    raw_value: str = ""

    def is_conflict(self, other: NormalizedFact) -> bool:
        """Determines if two facts of the same type represent a genuine conflict."""
        if self.fact_type != other.fact_type:
            return False

        if self.fact_type == "founding_year":
            # Founding years must match exactly if both exist
            if self.numeric_value and other.numeric_value:
                return self.numeric_value != other.numeric_value
            return self.canonical_value != other.canonical_value

        if self.fact_type == "price":
            # If currencies match or one is missing, compare numeric values
            if self.currency and other.currency and self.currency != other.currency:
                return True
            if self.numeric_value is not None and other.numeric_value is not None:
                return abs(self.numeric_value - other.numeric_value) > 0.01
            return self.canonical_value != other.canonical_value

        if self.fact_type in ("headquarters", "location"):
            # Check city/country overlap: e.g. "Delhi" and "New Delhi, India" are NOT a conflict
            tokens_a = set(re.findall(r"\w+", self.canonical_value.lower()))
            tokens_b = set(re.findall(r"\w+", other.canonical_value.lower()))
            if not tokens_a or not tokens_b:
                return False
            # If they share significant location tokens (e.g. 'delhi', 'york', 'tokyo'), compatible
            if tokens_a.intersection(tokens_b):
                return False
            return True

        if self.fact_type == "phone":
            # Stripped digits comparison
            digits_a = re.sub(r"\D", "", self.canonical_value)
            digits_b = re.sub(r"\D", "", other.canonical_value)
            if digits_a and digits_b:
                # Suffix matching for national vs international format
                return not (digits_a.endswith(digits_b) or digits_b.endswith(digits_a))
            return self.canonical_value != other.canonical_value

        return self.canonical_value.strip().lower() != other.canonical_value.strip().lower()


class FactNormalizer:
    """Normalizes raw factual strings into canonical forms."""

    CURRENCY_MAP = {
        "$": "USD",
        "usd": "USD",
        "€": "EUR",
        "eur": "EUR",
        "£": "GBP",
        "gbp": "GBP",
        "₹": "INR",
        "inr": "INR",
        "rs.": "INR",
        "rs": "INR",
        "rupees": "INR",
        "¥": "JPY",
        "jpy": "JPY",
        "cad": "CAD",
        "c$": "CAD",
        "aud": "AUD",
        "a$": "AUD",
    }

    LOCATION_SYNONYMS = {
        "sf": "san francisco",
        "nyc": "new york city",
        "ny": "new york",
        "la": "los angeles",
        "bengaluru": "bangalore",
        "delhi": "delhi",
        "new delhi": "delhi",
    }

    @classmethod
    def normalize_founding_year(cls, raw: str) -> Optional[NormalizedFact]:
        match = re.search(r"\b(19\d\d|20\d\d)\b", raw)
        if not match:
            return None
        year = int(match.group(1))
        return NormalizedFact(
            fact_type="founding_year",
            canonical_value=str(year),
            numeric_value=float(year),
            raw_value=raw.strip(),
        )

    @classmethod
    def normalize_price(cls, raw: str) -> Optional[NormalizedFact]:
        """Normalizes price strings like '$999', 'INR 999', 'Rs. 999', '99.00 USD'."""
        currency_found = None
        cleaned_raw = raw.strip()

        # Identify currency
        for sym, curr in cls.CURRENCY_MAP.items():
            pattern = re.compile(rf"(?:^|\s|\b){re.escape(sym)}(?:\s|\b|$)", re.IGNORECASE)
            if pattern.search(cleaned_raw) or sym in cleaned_raw:
                currency_found = curr
                break

        # Extract number
        num_match = re.search(r"(\d+(?:[,\.]\d+)?)", cleaned_raw.replace(",", ""))
        if not num_match:
            return None

        try:
            val = float(num_match.group(1))
        except ValueError:
            return None

        curr_code = currency_found or "USD"
        canonical = f"{val:.2f} {curr_code}"

        return NormalizedFact(
            fact_type="price",
            canonical_value=canonical,
            numeric_value=val,
            currency=curr_code,
            raw_value=cleaned_raw,
        )

    @classmethod
    def normalize_location(cls, raw: str) -> Optional[NormalizedFact]:
        cleaned = raw.strip()
        if len(cleaned) < 2:
            return None

        # Clean punctuation and normalize common city abbreviations
        tokens = re.findall(r"[A-Za-z0-9]+", cleaned.lower())
        norm_tokens = [cls.LOCATION_SYNONYMS.get(t, t) for t in tokens]
        canonical = " ".join(norm_tokens)

        return NormalizedFact(
            fact_type="headquarters",
            canonical_value=canonical,
            raw_value=cleaned,
        )

    @classmethod
    def normalize_phone(cls, raw: str) -> Optional[NormalizedFact]:
        digits = re.sub(r"\D", "", raw)
        if len(digits) < 7:
            return None
        return NormalizedFact(
            fact_type="phone",
            canonical_value=digits,
            raw_value=raw.strip(),
        )
