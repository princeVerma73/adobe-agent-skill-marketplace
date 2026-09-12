"""Deterministic regression tests for Phase 9B calibration fixes."""

#import pytest
from src.entity_trust.contracts.schemas import SiteSnapshot, PageSnapshot, SeverityLevel
from src.entity_trust.runner import audit_content_and_entity
from src.engagement.rules.context_retention import check_context_retention


def test_same_page_multi_value_pricing_no_conflict_wikimedia_donation():
    """FIX 1: Selectable donation tiers on the same page must not be flagged as contradictions."""
    payload = {
        "site": "wikimedia.org",
        "homepage": {
            "url": "https://www.wikimedia.org/",
            "title": "Wikimedia",
            "text": "Wikimedia Foundation empowers free knowledge globally. Please support our mission.",
            "html": "<html><head><title>Wikimedia</title></head><body><h1>Wikimedia</h1><p>Wikimedia Foundation empowers free knowledge globally.</p></body></html>",
            "images": [],
            "structured_data": [],
        },
        "pages": [
            {
                "url": "https://donate.wikimedia.org/w/index.php?title=Special:LandingPage",
                "title": "Donate to Wikimedia",
                "text": "Please join readers who donate. Any amount helps: ₹ 25, ₹ 100, ₹ 500, or whatever feels right. Donation amount (INR) ₹ 25 ₹ 100 ₹ 500 ₹ 1000 ₹ 1500 ₹ 3000 ₹ 5000.",
                "html": "<html><head><title>Donate</title></head><body><p>Donation amount (INR) ₹ 25 ₹ 100 ₹ 500 ₹ 1000 ₹ 1500 ₹ 3000 ₹ 5000</p></body></html>",
            }
        ],
        "structured_data": [],
        "metadata": {},
        "crawl_metadata": {"pages_crawled": 2},
    }

    result = audit_content_and_entity(payload)
    price_conflicts = [f for f in result.findings if f.category == "consistency" and "pricing" in f.title.lower()]
    assert len(price_conflicts) == 0, f"Expected 0 price contradictions, got: {[f.evidence for f in price_conflicts]}"


def test_multi_plan_billing_frequency_no_conflict_mozilla_vpn():
    """FIX 1: Monthly vs Annual billing options on a pricing page must not be flagged as contradictions."""
    payload = {
        "site": "mozilla.org",
        "homepage": {
            "url": "https://www.mozilla.org/en-US/",
            "title": "Internet for people, not profit — Mozilla",
            "text": "Mozilla is the non-profit behind Firefox. We build products for a better internet.",
            "html": "<html><head><title>Internet for people, not profit — Mozilla</title></head><body><h1>Mozilla</h1></body></html>",
            "images": [],
            "structured_data": [],
        },
        "pages": [
            {
                "url": "https://www.mozilla.org/en-US/products/vpn/",
                "title": "Mozilla VPN - Fast and Private",
                "text": "One subscription for all your devices. Recommended Annual ₹416.58 /month ₹4,999.00 total. Monthly ₹839.00 /month.",
                "html": "<html><head><title>Mozilla VPN</title></head><body><p>Recommended Annual ₹416.58 /month ₹4,999.00 total. Monthly ₹839.00 /month.</p></body></html>",
            }
        ],
        "structured_data": [],
        "metadata": {},
        "crawl_metadata": {"pages_crawled": 2},
    }

    result = audit_content_and_entity(payload)
    price_conflicts = [f for f in result.findings if f.category == "consistency" and "pricing" in f.title.lower()]
    assert len(price_conflicts) == 0, f"Expected 0 price contradictions for monthly vs annual plans, got: {[f.evidence for f in price_conflicts]}"


def test_third_party_editorial_pricing_no_conflict_theverge_news():
    """FIX 2: Third-party product prices quoted in news/editorial articles must not be flagged as publisher contradictions."""
    payload = {
        "site": "theverge.com",
        "homepage": {
            "url": "https://www.theverge.com/",
            "title": "The Verge",
            "text": "The Verge is a technology news publication covering the future.",
            "html": "<html><head><title>The Verge</title></head><body><h1>The Verge</h1></body></html>",
            "images": [],
            "structured_data": [],
        },
        "pages": [
            {
                "url": "https://www.theverge.com/tech/986400/anthropic-max-plan-pricing",
                "title": "Anthropic introduces new Max subscription",
                "text": "Subscribers of Anthropic’s Max plan ($100-$200 per month) say they didn’t get what they thought.",
                "html": "<html><head><title>Anthropic Max</title></head><body><p>Subscribers of Anthropic’s Max plan ($100-$200 per month)...</p></body></html>",
            },
            {
                "url": "https://www.theverge.com/news/991130/tmobile-iphone-handoff-price",
                "title": "T-Mobile Handoff Feature",
                "text": "Using iPhone Handoff will cost $5 per month on T-Mobile.",
                "html": "<html><head><title>T-Mobile Handoff</title></head><body><p>Using iPhone Handoff will cost $5 per month on T-Mobile.</p></body></html>",
            },
        ],
        "structured_data": [],
        "metadata": {},
        "crawl_metadata": {"pages_crawled": 3},
    }

    result = audit_content_and_entity(payload)
    price_conflicts = [f for f in result.findings if f.category == "consistency" and "pricing" in f.title.lower()]
    assert len(price_conflicts) == 0, f"Expected 0 price contradictions on news articles quoting 3rd parties, got: {[f.evidence for f in price_conflicts]}"


def test_multi_department_emails_no_conflict_wikimedia():
    """FIX 3: Multiple departmental email addresses across pages must not be flagged as contradictions."""
    payload = {
        "site": "wikimedia.org",
        "homepage": {
            "url": "https://www.wikimedia.org/",
            "title": "Wikimedia",
            "text": "Welcome to Wikimedia Foundation. Contact us at info@wikimedia.org.",
            "html": "<html><head><title>Wikimedia</title></head><body><h1>Wikimedia</h1></body></html>",
            "images": [],
            "structured_data": [],
        },
        "pages": [
            {
                "url": "https://donate.wikimedia.org/w/landing",
                "title": "Donate to Wikimedia",
                "text": "For questions about tax deductions, please contact donate@wikimedia.org.",
                "html": "<html><body><p>contact donate@wikimedia.org</p></body></html>",
            },
            {
                "url": "https://foundation.wikimedia.org/wiki/Privacy_policy",
                "title": "Privacy Policy",
                "text": "For questions regarding your personal data, please email privacy@wikimedia.org or contact our representative at EUrepresentative.Wikimedia@twobirds.com.",
                "html": "<html><body><p>email privacy@wikimedia.org or EUrepresentative.Wikimedia@twobirds.com</p></body></html>",
            },
        ],
        "structured_data": [],
        "metadata": {},
        "crawl_metadata": {"pages_crawled": 3},
    }

    result = audit_content_and_entity(payload)
    email_conflicts = [f for f in result.findings if f.category == "consistency" and "email" in f.title.lower()]
    assert len(email_conflicts) == 0, f"Expected 0 email contradictions, got: {[f.evidence for f in email_conflicts]}"


def test_title_fallback_cleaning_python_docs_and_mozilla():
    """FIX 4a: Version numbers and marketing taglines in <title> should be cleaned to extract proper brand name."""
    # 1. Python docs title fallback
    py_payload = {
        "site": "docs.python.org",
        "homepage": {
            "url": "https://docs.python.org/3/",
            "title": "3.14.7 Documentation",
            "text": "Welcome to Python documentation. Browse library reference and tutorials.",
            "html": "<html><head><title>3.14.7 Documentation</title></head><body><h1>Python 3.14 Documentation</h1></body></html>",
            "images": [],
            "structured_data": [],
        },
        "pages": [],
        "structured_data": [],
        "metadata": {},
        "crawl_metadata": {"pages_crawled": 1},
    }
    py_result = audit_content_and_entity(py_payload)
    assert py_result.entity_profile.name == "Python", f"Expected 'Python', got '{py_result.entity_profile.name}'"
    ec002_py = [f for f in py_result.findings if f.id == "EC-002"]
    if ec002_py:
        assert ec002_py[0].severity == "medium", "EC-002 from title fallback alone should be medium severity"

    # 2. Mozilla title with slogan
    moz_payload = {
        "site": "mozilla.org",
        "homepage": {
            "url": "https://www.mozilla.org/",
            "title": "Internet for people, not profit — Mozilla",
            "text": "Mozilla is dedicated to keeping the internet open and accessible to all.",
            "html": "<html><head><title>Internet for people, not profit — Mozilla</title></head><body><h1>Mozilla</h1></body></html>",
            "images": [],
            "structured_data": [],
        },
        "pages": [],
        "structured_data": [],
        "metadata": {},
        "crawl_metadata": {"pages_crawled": 1},
    }
    moz_result = audit_content_and_entity(moz_payload)
    assert moz_result.entity_profile.name == "Mozilla", f"Expected 'Mozilla', got '{moz_result.entity_profile.name}'"


def test_genuinely_ambiguous_entity_still_fires_ec002():
    """FIX 4b: Genuinely ambiguous entity with vague descriptions must still produce EC-002."""
    payload = {
        "site": "apexglobal.net",
        "homepage": {
            "url": "https://apexglobal.net/",
            "title": "Home",
            "text": "Welcome to us. We empower businesses to succeed with world-class solutions. Innovative solutions for tomorrow.",
            "html": "<!DOCTYPE html><html><head><title>Home</title><meta name=\"description\" content=\"Welcome to our homepage.\"></head><body><h1>Welcome</h1><p>We empower businesses to succeed with world-class solutions.</p><footer><p>© 2026 Apex Global</p></footer></body></html>",
            "images": [],
            "structured_data": [],
        },
        "pages": [],
        "structured_data": [],
        "metadata": {},
        "crawl_metadata": {"pages_crawled": 1},
    }
    result = audit_content_and_entity(payload)
    ec002_findings = [f for f in result.findings if f.id == "EC-002"]
    assert len(ec002_findings) == 1, "Genuinely ambiguous entity must still produce EC-002"
    assert ec002_findings[0].severity == "high"


def test_localized_homepage_recognition_mozilla_en_us():
    """FIX 5: Deep pages linking to localized root paths (e.g. /en-US/) must satisfy ENG-015 home link check."""
    pages_data = [
        {
            "url": "https://www.mozilla.org/en-US/products/vpn/",
            "crawl_depth": 2,
            "title": "Mozilla VPN",
            "headings": [{"level": 1, "text": "Mozilla VPN"}],
            "links": [
                {"url": "https://www.mozilla.org/en-US/", "text": "Mozilla", "rel": ""},
                {"url": "/en-US/about/", "text": "About Us", "rel": ""},
            ],
        },
        {
            "url": "https://www.mozilla.org/en-US/products/monitor/",
            "crawl_depth": 2,
            "title": "Mozilla Monitor",
            "headings": [{"level": 1, "text": "Mozilla Monitor"}],
            "links": [
                {"url": "/en-US/", "text": "Home", "rel": ""},
            ],
        }
    ]

    findings = check_context_retention(
        site_domain="mozilla.org",
        homepage_url="https://www.mozilla.org",
        pages_data=pages_data,
    )

    eng015_findings = [f for f in findings if f.id == "ENG-015"]
    assert len(eng015_findings) == 0, f"Expected 0 ENG-015 findings for localized /en-US/ links, got: {[f.evidence for f in eng015_findings]}"
