"""Tests for Area 4 (CTA Clarity) and Area 8 (Conversion Pathways)."""

import pytest
from src.engagement.rules.cta import check_cta_clarity
from src.engagement.rules.conversion import check_conversion_path
from src.entity_trust.contracts.schemas import SeverityLevel


def test_cta_flags_missing_homepage_cta():
    """Verifies that a homepage without primary CTAs triggers ENG-008."""
    pages_data = [
        {
            "url": "https://example.com/",
            "links": [
                {"url": "https://example.com/about", "text": "About Us", "is_internal": True},
                {"url": "https://example.com/legal", "text": "Legal Notice", "is_internal": True},
            ],
        }
    ]
    findings = check_cta_clarity(homepage_url="https://example.com/", pages_data=pages_data)
    assert any(f.id == "ENG-008" for f in findings)
    f = next(f for f in findings if f.id == "ENG-008")
    assert f.severity == SeverityLevel.HIGH
    assert f.confidence >= 0.90
    assert "clear primary call-to-action" in f.title.lower()


def test_cta_passes_with_get_started_button():
    """Verifies that a prominent CTA link prevents ENG-008."""
    pages_data = [
        {
            "url": "https://example.com/",
            "links": [
                {"url": "https://example.com/signup", "text": "Get Started", "is_internal": True},
                {"url": "https://example.com/about", "text": "About Us", "is_internal": True},
            ],
        }
    ]
    findings = check_cta_clarity(homepage_url="https://example.com/", pages_data=pages_data)
    assert len(findings) == 0


def test_conversion_path_flags_pricing_page_without_action():
    """Verifies that pricing pages without signup/checkout links trigger ENG-013."""
    pages_data = [
        {
            "url": "https://example.com/pricing",
            "title": "Pricing Plans | Acme",
            "links": [
                {"url": "https://example.com/", "text": "Home", "is_internal": True},
                {"url": "https://example.com/about", "text": "About", "is_internal": True},
            ],  # No signup, checkout, demo, or sales link
        }
    ]
    findings = check_conversion_path(pages_data=pages_data)
    assert any(f.id == "ENG-013" for f in findings)
    f = next(f for f in findings if f.id == "ENG-013")
    assert f.severity == SeverityLevel.HIGH
    assert "https://example.com/pricing" in f.affected_urls


def test_conversion_path_passes_with_action_buttons():
    """Verifies that pricing page with 'Choose Plan' passes without findings."""
    pages_data = [
        {
            "url": "https://example.com/pricing",
            "title": "Pricing Plans",
            "links": [
                {"url": "https://example.com/checkout?plan=pro", "text": "Choose Plan", "is_internal": True},
            ],
        }
    ]
    findings = check_conversion_path(pages_data=pages_data)
    assert len(findings) == 0
