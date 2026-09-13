"""Phase 9G Regression Tests.

Validates the surgical fixes for:
1. Third-party metric attribution:
   - Named customer metrics (e.g. Hertz case study "160 countries", Supabase "150 countries")
     are not attributed to the audited entity and do NOT trigger contradictions against host metrics ("195+ countries").
   - Negative test: Audited entity's own conflicting metrics across pages (e.g. "available in 50 countries" vs
     "available in 80 countries") MUST still trigger CO-* contradictions.
2. Distinct-fee pricing classification:
   - Distinct fee types (e.g. token rates ₹0/₹0.95, MDR cap ₹200, dispute fee ₹1,000) on pricing pages
     do NOT trigger false cross-page price contradictions.
   - Negative test: Genuinely conflicting prices for the identical plan/tier (e.g. Starter $49 vs $99)
     MUST still trigger CO-* contradictions.
"""

import pytest
from src.entity_trust.core.fact_extractor import FactExtractor
from src.entity_trust.core.fact_graph import FactGraph
from src.entity_trust.core.html_parser import parse_page_html
from src.entity_trust.runner import audit_content_and_entity


def test_customer_testimonial_metric_no_contradiction_against_host():
    """Unit test: Customer metrics (Hertz/Supabase) do not conflict with host entity's global footprint."""
    payload = {
        "site": "stripe.com",
        "homepage": {
            "url": "https://stripe.com/",
            "title": "Stripe | Financial Infrastructure for the Internet",
            "text": "Stripe powers online commerce. Millions of companies in over 195+ countries use Stripe.",
            "html": "<html><head><title>Stripe</title></head><body><p>Millions of companies in over 195+ countries use Stripe.</p></body></html>",
            "images": [],
            "structured_data": [],
        },
        "pages": [
            {
                "url": "https://stripe.com/customers/hertz",
                "title": "Hertz Case Study | Stripe",
                "text": "See how Hertz unifies global car rental payments across 160 countries with Stripe.",
                "html": "<html><head><title>Hertz Case Study</title></head><body><p>See how Hertz unifies global car rental payments across 160 countries with Stripe.</p></body></html>",
            },
            {
                "url": "https://stripe.com/customers/supabase",
                "title": "Supabase Case Study | Stripe",
                "text": "Supabase delivers database services to developers in 150 countries worldwide.",
                "html": "<html><head><title>Supabase Case Study</title></head><body><p>Supabase delivers database services to developers in 150 countries worldwide.</p></body></html>",
            },
        ],
        "structured_data": [],
        "metadata": {},
        "crawl_metadata": {"pages_crawled": 3},
    }

    result = audit_content_and_entity(payload)
    metric_conflicts = [
        f for f in result.findings
        if f.category == "consistency" and "metric" in f.title.lower()
    ]
    assert len(metric_conflicts) == 0, f"Expected 0 metric contradictions, got: {[f.evidence for f in metric_conflicts]}"


def test_negative_audited_entity_conflicting_metric_triggers_co():
    """Negative test: Audited entity's own contradictory metrics across pages MUST trigger CO-*."""
    payload = {
        "site": "example.com",
        "homepage": {
            "url": "https://example.com/",
            "title": "Example Corp",
            "text": "Welcome to Example Corp. Our platform is currently available in 50 countries globally.",
            "html": "<html><head><title>Example Corp</title></head><body><p>Our platform is currently available in 50 countries globally.</p></body></html>",
            "images": [],
            "structured_data": [],
        },
        "pages": [
            {
                "url": "https://example.com/about",
                "title": "About Example Corp",
                "text": "About our global reach. We are proud to be serving customers across 80 countries worldwide.",
                "html": "<html><head><title>About Example Corp</title></head><body><p>We are proud to be serving customers across 80 countries worldwide.</p></body></html>",
            },
        ],
        "structured_data": [],
        "metadata": {},
        "crawl_metadata": {"pages_crawled": 2},
    }

    result = audit_content_and_entity(payload)
    metric_conflicts = [
        f for f in result.findings
        if f.category == "consistency" and "metric" in f.title.lower()
    ]
    assert len(metric_conflicts) == 1, f"Expected 1 metric contradiction, got: {[f.evidence for f in metric_conflicts]}"
    assert metric_conflicts[0].id.startswith("CO-")
    assert "50 countries" in metric_conflicts[0].evidence
    assert "80 countries" in metric_conflicts[0].evidence


def test_distinct_pricing_fee_categories_no_contradiction():
    """Unit test: Distinct fee classifications (dispute fee, MDR cap, token rate) do not conflict."""
    payload = {
        "site": "stripe.com",
        "homepage": {
            "url": "https://stripe.com/",
            "title": "Stripe",
            "text": "Stripe financial infrastructure.",
            "html": "<html><head><title>Stripe</title></head><body><h1>Stripe</h1></body></html>",
            "images": [],
            "structured_data": [],
        },
        "pages": [
            {
                "url": "https://stripe.com/in/pricing",
                "title": "Stripe India Pricing",
                "text": "Transparent pricing for India. Card tokenization fee ₹0 per token. Step up token rate ₹0.95. Per transaction MDR cap ₹200. Dispute fee ₹1,000 per lost chargeback.",
                "html": "<html><head><title>Pricing</title></head><body><p>Card tokenization fee ₹0. Step up token rate ₹0.95. Per transaction MDR cap ₹200. Dispute fee ₹1,000 per lost chargeback.</p></body></html>",
            },
            {
                "url": "https://stripe.com/in/disputes",
                "title": "Stripe Dispute Management",
                "text": "Information on dispute processes. Standard dispute fee ₹1,000 for formal chargeback inquiries.",
                "html": "<html><head><title>Disputes</title></head><body><p>Standard dispute fee ₹1,000 for formal chargeback inquiries.</p></body></html>",
            },
        ],
        "structured_data": [],
        "metadata": {},
        "crawl_metadata": {"pages_crawled": 3},
    }

    result = audit_content_and_entity(payload)
    price_conflicts = [
        f for f in result.findings
        if f.category == "consistency" and "pricing" in f.title.lower()
    ]
    assert len(price_conflicts) == 0, f"Expected 0 price contradictions, got: {[f.evidence for f in price_conflicts]}"


def test_negative_genuinely_conflicting_plan_prices_trigger_co():
    """Negative test: Genuinely conflicting prices for identical plan MUST trigger CO-*."""
    payload = {
        "site": "saasplatform.com",
        "homepage": {
            "url": "https://saasplatform.com/",
            "title": "SaaS Platform",
            "text": "Welcome to SaaS Platform. Our Pro subscription plan starts at $49/mo.",
            "html": "<html><head><title>SaaS Platform</title></head><body><p>Our Pro subscription plan starts at $49/mo.</p></body></html>",
            "images": [],
            "structured_data": [],
        },
        "pages": [
            {
                "url": "https://saasplatform.com/pricing",
                "title": "Pricing | SaaS Platform",
                "text": "Plans and pricing details. Our Pro subscription plan starts at $99/mo with advanced features.",
                "html": "<html><head><title>Pricing</title></head><body><p>Our Pro subscription plan starts at $99/mo with advanced features.</p></body></html>",
            },
        ],
        "structured_data": [],
        "metadata": {},
        "crawl_metadata": {"pages_crawled": 2},
    }

    result = audit_content_and_entity(payload)
    price_conflicts = [
        f for f in result.findings
        if f.category == "consistency" and "pricing" in f.title.lower()
    ]
    assert len(price_conflicts) == 1, f"Expected 1 price contradiction, got: {[f.evidence for f in price_conflicts]}"
    assert price_conflicts[0].id.startswith("CO-")
    assert "49.00 USD" in price_conflicts[0].evidence
    assert "99.00 USD" in price_conflicts[0].evidence
