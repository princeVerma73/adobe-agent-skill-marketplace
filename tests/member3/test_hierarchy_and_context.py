"""Tests for Area 3 (Information Hierarchy) and Area 10 (Context Retention)."""

import pytest
from src.engagement.rules.hierarchy import check_information_hierarchy
from src.engagement.rules.context_retention import check_context_retention
from src.entity_trust.contracts.schemas import SeverityLevel


def test_hierarchy_flags_skipped_heading_levels():
    """Verifies that skipping from H1 directly to H3 triggers ENG-005."""
    pages_data = [
        {
            "url": "https://example.com/docs",
            "headings": [
                {"level": 1, "text": "Documentation"},
                {"level": 3, "text": "Nested Section Without H2"},  # Skips H2
            ],
            "body_text": "Content here.",
        }
    ]
    findings = check_information_hierarchy(pages_data=pages_data)
    assert any(f.id == "ENG-005" for f in findings)
    f = next(f for f in findings if f.id == "ENG-005")
    assert f.severity == SeverityLevel.MEDIUM
    assert "H1->H3" in f.evidence


def test_hierarchy_flags_multiple_h1_elements():
    """Verifies that multiple H1s trigger ENG-006."""
    pages_data = [
        {
            "url": "https://example.com/",
            "headings": [
                {"level": 1, "text": "First Main Title"},
                {"level": 1, "text": "Second Main Title"},
            ],
            "body_text": "Content.",
        }
    ]
    findings = check_information_hierarchy(pages_data=pages_data)
    assert any(f.id == "ENG-006" for f in findings)
    f = next(f for f in findings if f.id == "ENG-006")
    assert f.severity == SeverityLevel.LOW


def test_hierarchy_flags_dense_unscannable_text():
    """Verifies that long text without H2/H3 subheadings triggers ENG-007."""
    pages_data = [
        {
            "url": "https://example.com/terms",
            "headings": [{"level": 1, "text": "Terms of Service"}],
            "body_text": "Legal terms text word " * 70,  # ~280 words with zero H2/H3
        }
    ]
    findings = check_information_hierarchy(pages_data=pages_data)
    assert any(f.id == "ENG-007" for f in findings)
    f = next(f for f in findings if f.id == "ENG-007")
    assert "Dense body content" in f.title


def test_context_retention_flags_deep_page_missing_home_link():
    """Verifies that a deep page lacking a link back to homepage triggers ENG-015."""
    pages_data = [
        {
            "url": "https://example.com/category/product-details",
            "crawl_depth": 2,
            "title": "Product Details - Acme",
            "headings": [{"level": 1, "text": "Product Details"}],
            "links": [{"url": "https://example.com/category/other", "text": "Other", "is_internal": True}],
        }
    ]
    findings = check_context_retention(
        site_domain="example.com",
        homepage_url="https://example.com/",
        pages_data=pages_data,
    )
    assert any(f.id == "ENG-015" for f in findings)
    f = next(f for f in findings if f.id == "ENG-015")
    assert f.severity == SeverityLevel.MEDIUM
    assert "https://example.com/category/product-details" in f.affected_urls


def test_context_retention_flags_missing_h1_on_direct_landing():
    """Verifies that a direct landing page without an H1 triggers ENG-016."""
    pages_data = [
        {
            "url": "https://example.com/solutions/enterprise",
            "crawl_depth": 1,
            "title": "Enterprise Solutions",
            "headings": [{"level": 2, "text": "Features"}],  # No H1
            "links": [{"url": "https://example.com/", "text": "Home", "is_internal": True}],
        }
    ]
    findings = check_context_retention(
        site_domain="example.com",
        homepage_url="https://example.com/",
        pages_data=pages_data,
    )
    assert any(f.id == "ENG-016" for f in findings)
    f = next(f for f in findings if f.id == "ENG-016")
    assert "Direct landing page lacks clear orienting H1" in f.title
