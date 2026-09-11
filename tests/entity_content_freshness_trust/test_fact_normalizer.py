"""Tests for fact normalization logic."""

from src.entity_trust.core.fact_normalizer import FactNormalizer, NormalizedFact


def test_price_normalization_and_equivalence():
    p1 = FactNormalizer.normalize_price("₹999")
    p2 = FactNormalizer.normalize_price("INR 999")
    p3 = FactNormalizer.normalize_price("Rs. 999")
    p4 = FactNormalizer.normalize_price("$999")
    p5 = FactNormalizer.normalize_price("INR 1499")

    assert p1 is not None and p2 is not None and p3 is not None and p4 is not None and p5 is not None
    assert p1.currency == "INR"
    assert p2.currency == "INR"
    assert p3.currency == "INR"
    assert p1.numeric_value == 999.0
    assert p2.numeric_value == 999.0

    # p1, p2, p3 are the exact same normalized fact -> NOT a conflict
    assert not p1.is_conflict(p2)
    assert not p1.is_conflict(p3)

    # p1 (INR) and p4 (USD) -> conflict
    assert p1.is_conflict(p4)

    # p1 (999 INR) and p5 (1499 INR) -> conflict
    assert p1.is_conflict(p5)


def test_founding_year_normalization():
    y1 = FactNormalizer.normalize_founding_year("founded back in 2015")
    y2 = FactNormalizer.normalize_founding_year("Est. 2015")
    y3 = FactNormalizer.normalize_founding_year("founded in 2018")

    assert y1 is not None and y2 is not None and y3 is not None
    assert y1.numeric_value == 2015.0
    assert y2.numeric_value == 2015.0
    assert not y1.is_conflict(y2)
    assert y1.is_conflict(y3)


def test_location_normalization_equivalence():
    loc1 = FactNormalizer.normalize_location("New Delhi")
    loc2 = FactNormalizer.normalize_location("Delhi, India")
    loc3 = FactNormalizer.normalize_location("London, UK")

    assert loc1 is not None and loc2 is not None and loc3 is not None
    # Delhi and New Delhi share city token -> compatible
    assert not loc1.is_conflict(loc2)
    # Delhi vs London -> genuine conflict
    assert loc1.is_conflict(loc3)
