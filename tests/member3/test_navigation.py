"""Tests for Area 2: Navigation Analysis."""

import pytest
from src.engagement.rules.navigation import check_navigation
from src.entity_trust.contracts.schemas import SeverityLevel


def test_navigation_flags_vague_anchor_texts():
    """Verifies that non-descriptive links ('click here', 'read more') trigger ENG-003."""
    pages_data = [
        {
            "url": "https://example.com/",
            "links": [
                {"url": "https://example.com/features", "text": "click here", "is_internal": True},
                {"url": "https://example.com/pricing", "text": "read more", "is_internal": True},
                {"url": "https://example.com/about", "text": "learn more", "is_internal": True},
            ],
        }
    ]
    findings = check_navigation(homepage_url="https://example.com/", pages_data=pages_data)
    assert any(f.id == "ENG-003" for f in findings)
    f = next(f for f in findings if f.id == "ENG-003")
    assert f.severity == SeverityLevel.MEDIUM
    assert f.confidence >= 0.85
    assert "https://example.com/" in f.affected_urls
    assert "click here" in f.evidence


def test_navigation_flags_homepage_missing_primary_navigation():
    """Verifies that a homepage lacking links to discovered subpages triggers ENG-004."""
    pages_data = [
        {"url": "https://example.com/", "links": []},  # Homepage has 0 links
        {"url": "https://example.com/about", "links": []},
        {"url": "https://example.com/pricing", "links": []},
    ]
    findings = check_navigation(homepage_url="https://example.com/", pages_data=pages_data)
    assert any(f.id == "ENG-004" for f in findings)
    f = next(f for f in findings if f.id == "ENG-004")
    assert f.severity == SeverityLevel.HIGH
    assert "primary navigation" in f.title.lower()


def test_navigation_passes_for_descriptive_links():
    """Verifies that descriptive navigation produces zero navigation findings."""
    pages_data = [
        {
            "url": "https://example.com/",
            "links": [
                {"url": "https://example.com/about", "text": "About Acme", "is_internal": True},
                {"url": "https://example.com/pricing", "text": "Enterprise Pricing", "is_internal": True},
            ],
        },
        {
            "url": "https://example.com/about",
            "links": [
                {"url": "https://example.com/", "text": "Home", "is_internal": True},
            ],
        },
    ]
    findings = check_navigation(homepage_url="https://example.com/", pages_data=pages_data)
    assert len(findings) == 0
