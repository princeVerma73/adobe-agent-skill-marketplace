"""Tests for Area 5 (Internal Linking), Area 6 (Continuation), Area 7 (Contact Path), and Area 9 (Dead Ends)."""

import pytest
from src.engagement.rules.contact import check_contact_path
from src.engagement.rules.continuation import check_related_content_continuation
from src.engagement.rules.dead_ends import check_dead_ends
from src.engagement.rules.linking import check_internal_linking
from src.entity_trust.contracts.schemas import SeverityLevel


def test_internal_linking_flags_orphan_pages():
    """Verifies that pages with 0 incoming internal links trigger ENG-009."""
    pages_data = [
        {
            "url": "https://example.com/",
            "links": [{"url": "https://example.com/about", "is_internal": True}],
        },
        {
            "url": "https://example.com/about",
            "links": [{"url": "https://example.com/", "is_internal": True}],
        },
        {
            "url": "https://example.com/hidden-promo",  # No page links to this
            "links": [{"url": "https://example.com/", "is_internal": True}],
        },
    ]
    findings = check_internal_linking(homepage_url="https://example.com/", pages_data=pages_data)
    assert any(f.id == "ENG-009" for f in findings)
    f = next(f for f in findings if f.id == "ENG-009")
    assert "https://example.com/hidden-promo" in f.affected_urls
    assert f.severity == SeverityLevel.MEDIUM


def test_dead_ends_flags_unintentional_dead_end_pages():
    """Verifies that non-terminal content pages with 0 outgoing internal links trigger ENG-014."""
    pages_data = [
        {
            "url": "https://example.com/products/item-catalog-392",
            "status_code": 200,
            "links": [],  # 0 outgoing links on a product content page
        }
    ]
    findings = check_dead_ends(homepage_url="https://example.com/", pages_data=pages_data)
    assert any(f.id == "ENG-014" for f in findings)
    f = next(f for f in findings if f.id == "ENG-014")
    assert f.severity == SeverityLevel.HIGH
    assert "Dead-end page" in f.title


def test_dead_ends_ignores_intentionally_terminal_pages():
    """Verifies that intentionally terminal pages (thank-you, privacy, terms) do NOT trigger ENG-014."""
    pages_data = [
        {
            "url": "https://example.com/thank-you",
            "title": "Thank You for Your Order",
            "status_code": 200,
            "links": [],
        },
        {
            "url": "https://example.com/privacy-policy",
            "title": "Privacy Policy",
            "status_code": 200,
            "links": [],
        },
        {
            "url": "https://example.com/terms-of-service",
            "title": "Terms of Service",
            "status_code": 200,
            "links": [],
        },
    ]
    findings = check_dead_ends(homepage_url="https://example.com/", pages_data=pages_data)
    assert len(findings) == 0


def test_continuation_flags_content_pages_without_next_steps():
    """Verifies that substantive articles with no onward links trigger ENG-011."""
    pages_data = [
        {
            "url": "https://example.com/blog/ai-trends",
            "body_text": "This is a detailed article exploring machine learning and artificial intelligence trends. " * 20,
            "links": [{"url": "https://example.com/", "is_internal": True}],  # Only home link
        }
    ]
    findings = check_related_content_continuation(
        homepage_url="https://example.com/", pages_data=pages_data
    )
    assert any(f.id == "ENG-011" for f in findings)
    f = next(f for f in findings if f.id == "ENG-011")
    assert f.severity == SeverityLevel.MEDIUM


def test_contact_path_flags_site_lacking_all_contact_channels():
    """Verifies that a site with no contact/support links triggers ENG-012."""
    pages_data = [
        {
            "url": "https://example.com/",
            "body_text": "Welcome to our product showcase.",
            "links": [{"url": "https://example.com/products", "text": "Products", "is_internal": True}],
        },
        {
            "url": "https://example.com/products",
            "body_text": "Product specifications.",
            "links": [{"url": "https://example.com/", "text": "Home", "is_internal": True}],
        },
    ]
    findings = check_contact_path(
        site_domain="example.com",
        homepage_url="https://example.com/",
        pages_data=pages_data,
    )
    assert any(f.id == "ENG-012" for f in findings)
    f = next(f for f in findings if f.id == "ENG-012")
    assert f.severity == SeverityLevel.HIGH


def test_contact_path_passes_when_contact_link_present():
    """Verifies that having a /contact link satisfies contact requirements."""
    pages_data = [
        {
            "url": "https://example.com/",
            "links": [{"url": "https://example.com/contact-us", "text": "Contact Us", "is_internal": True}],
        }
    ]
    findings = check_contact_path(
        site_domain="example.com",
        homepage_url="https://example.com/",
        pages_data=pages_data,
    )
    assert len(findings) == 0
