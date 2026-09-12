"""Phase 9C Regression Tests — Locale & Regional Variant Handling.

Deterministic local tests verifying:
1. Multi-locale regional address/location facts do NOT produce false CO-001.
2. Entity profile selection prefers audited locale (/in/) over regional siblings (/au/).
3. Regional sibling roots do NOT trigger false ENG-009 (orphan) or ENG-015 (missing home link).
4. NEGATIVE CONTRADICTION TEST: Conflicting same-locale facts (e.g. founding years) MUST still produce CO-001.
5. Crawl queue prioritizes same-locale content over regional siblings under page budgets.
6. Non-locale root audits (e.g. https://example.com/) preserve existing crawler behavior.
7. Unit tests for locale URL utilities.
"""

import pytest
from typing import List

from src.crawler.crawler import BFSCrawler
from src.engagement.rules.context_retention import check_context_retention
from src.engagement.rules.linking import check_internal_linking
from src.entity_trust.audits.consistency_audit import audit_consistency
from src.entity_trust.audits.entity_audit import audit_entity
from src.entity_trust.contracts.schemas import PageSnapshot, SiteSnapshot
from src.entity_trust.core.fact_extractor import FactExtractor
from src.entity_trust.core.fact_graph import FactGraph
from src.entity_trust.core.html_parser import ParsedPageContent
from src.inspection.models import SiteInspection, SitemapInspection
from src.inspection.url import (
    extract_locale_prefix,
    is_locale_root,
    is_regional_sibling,
    is_same_locale,
)


class DummyHTTPClient:
    """Mock HTTP client for deterministic local testing."""

    def __init__(self, responses: dict):
        self.responses = responses

    def get(self, url: str):
        class MockResponse:
            def __init__(self, url: str, status_code: int, text: str, headers: dict = None):
                self.url = url
                self.status_code = status_code
                self.text = text
                self.success = status_code == 200
                self.content_type = "text/html"
                self.headers = headers or {"content-type": "text/html"}

            def to_page_inspection(self, crawl_depth: int = 0):
                from src.inspection.models import PageInspection
                return PageInspection(
                    url=self.url,
                    original_url=self.url,
                    status_code=self.status_code,
                    crawl_depth=crawl_depth,
                    allowed_by_robots=True,
                )

        normalized = url.rstrip("/")
        resp_data = self.responses.get(url) or self.responses.get(normalized) or self.responses.get(f"{normalized}/")
        if resp_data:
            return MockResponse(url, resp_data.get("status", 200), resp_data.get("html", ""))
        return MockResponse(url, 404, "Not Found")


# =========================================================================
# Test 1: Multi-Locale Entity & Address (No False CO-001)
# =========================================================================
def test_multi_locale_regional_addresses_no_false_co001():
    """Verify regional Schema.org addresses across /us/, /uk/, /in/ do not trigger false CO-001."""
    pages = [
        ParsedPageContent(
            url="https://example.com/us/",
            title="Acme US Homepage",
            json_ld_objects=[
                {
                    "@type": "Organization",
                    "name": "Acme Global",
                    "address": {
                        "addressLocality": "San Jose",
                        "addressRegion": "CA",
                        "addressCountry": "US",
                    },
                    "telephone": "+1-800-555-0100",
                }
            ],
        ),
        ParsedPageContent(
            url="https://example.com/uk/",
            title="Acme UK Homepage",
            json_ld_objects=[
                {
                    "@type": "Organization",
                    "name": "Acme Global",
                    "address": {
                        "addressLocality": "London",
                        "addressRegion": "England",
                        "addressCountry": "UK",
                    },
                    "telephone": "+44-20-7946-0919",
                }
            ],
        ),
        ParsedPageContent(
            url="https://example.com/in/",
            title="Acme India Homepage",
            json_ld_objects=[
                {
                    "@type": "Organization",
                    "name": "Acme Global",
                    "address": {
                        "addressLocality": "Bangalore",
                        "addressRegion": "Karnataka",
                        "addressCountry": "India",
                    },
                    "telephone": "+91-80-1234-5678",
                }
            ],
        ),
    ]

    snapshot = SiteSnapshot(
        site="example.com",
        homepage=PageSnapshot(url="https://example.com/in/", title="Acme India Homepage"),
        pages=[PageSnapshot(url=p.url, title=p.title) for p in pages],
    )

    fact_graph = FactGraph(site="example.com")
    findings = audit_consistency(snapshot, pages, fact_graph)

    # Address and phone differences across distinct regional roots are valid regional variants
    co_findings = [f for f in findings if f.id.startswith("CO-")]
    assert len(co_findings) == 0, f"Expected 0 CO-001 findings, got: {[f.evidence for f in co_findings]}"


# =========================================================================
# Test 2: Entity Profile Locale Prioritization (/in/ audit)
# =========================================================================
def test_entity_profile_prefers_audited_locale():
    """For an /in/ audit, entity selection must prefer /in/ and not allow /au/ to override."""
    pages = [
        ParsedPageContent(
            url="https://example.com/in/",
            title="Acme India - Cloud Services",
            json_ld_objects=[
                {
                    "@type": "Organization",
                    "name": "Acme India",
                }
            ],
        ),
        ParsedPageContent(
            url="https://example.com/au/",
            title="Acme Australia - Cloud Services",
            json_ld_objects=[
                {
                    "@type": "Organization",
                    "name": "Acme Australia",
                }
            ],
        ),
    ]

    snapshot = SiteSnapshot(
        site="example.com",
        homepage=PageSnapshot(url="https://example.com/in/", title="Acme India"),
        pages=[PageSnapshot(url=p.url, title=p.title) for p in pages],
    )

    findings, entity_profile = audit_entity(snapshot, pages)
    assert entity_profile.name == "Acme India"


# =========================================================================
# Test 3: Locale Sibling Orphan & Homepage Link Findings (ENG-009 / ENG-015)
# =========================================================================
def test_regional_sibling_roots_do_not_fire_eng009_or_eng015():
    """Regional sibling roots reached via sitemaps/selectors must not fire ENG-009 or ENG-015."""
    homepage_url = "https://example.com/in/"
    pages_data = [
        {
            "url": "https://example.com/in/",
            "crawl_depth": 0,
            "title": "Acme India",
            "links": [
                {"url": "https://example.com/in/products", "text": "Products"},
                {"url": "https://example.com/in/pricing", "text": "Pricing"},
            ],
        },
        {
            "url": "https://example.com/in/products",
            "crawl_depth": 1,
            "title": "Products | Acme India",
            "headings": [{"level": 1, "text": "Products"}],
            "links": [{"url": "https://example.com/in/", "text": "Home"}],
        },
        {
            "url": "https://example.com/au/",
            "crawl_depth": 1,
            "title": "Acme Australia",
            "headings": [{"level": 1, "text": "Acme Australia"}],
            "links": [{"url": "https://example.com/au/pricing", "text": "Pricing"}],
        },
        {
            "url": "https://example.com/ae_ar/",
            "crawl_depth": 1,
            "title": "Acme Middle East",
            "headings": [{"level": 1, "text": "Acme Arabic"}],
            "links": [{"url": "https://example.com/ae_ar/about", "text": "About"}],
        },
    ]

    # 1. Check linking rule (ENG-009)
    linking_findings = check_internal_linking(homepage_url, pages_data)
    eng009_urls = [u for f in linking_findings if f.id == "ENG-009" for u in f.affected_urls]
    assert "https://example.com/au/" not in eng009_urls
    assert "https://example.com/ae_ar/" not in eng009_urls

    # 2. Check context retention rule (ENG-015)
    context_findings = check_context_retention("example.com", homepage_url, pages_data)
    eng015_urls = [u for f in context_findings if f.id == "ENG-015" for u in f.affected_urls]
    assert "https://example.com/au/" not in eng015_urls
    assert "https://example.com/ae_ar/" not in eng015_urls


# =========================================================================
# Test 4: NEGATIVE CONTRADICTION TEST — REQUIRED
# =========================================================================
def test_same_locale_contradiction_must_fire_co001():
    """Within the same locale, conflicting founding years MUST trigger CO-001."""
    pages = [
        ParsedPageContent(
            url="https://example.com/us/about/",
            title="About Us",
            clean_text="Acme Corp was founded in 1982 by engineers in California.",
        ),
        ParsedPageContent(
            url="https://example.com/us/company/",
            title="Company Overview",
            clean_text="Acme Corp was founded in 1995 as an innovative startup.",
        ),
    ]

    snapshot = SiteSnapshot(
        site="example.com",
        homepage=PageSnapshot(url="https://example.com/us/", title="Acme US"),
        pages=[PageSnapshot(url=p.url, title=p.title) for p in pages],
    )

    fact_graph = FactGraph(site="example.com")
    findings = audit_consistency(snapshot, pages, fact_graph)

    co_findings = [f for f in findings if f.id.startswith("CO-")]
    assert len(co_findings) >= 1, "Expected CO-001 to fire for same-locale founding year conflict!"
    assert any("Founding Year" in f.title or "1982" in f.evidence for f in co_findings)


# =========================================================================
# Test 5: Crawl Priority Under Budget Constraints
# =========================================================================
def test_crawler_prioritizes_same_locale_content():
    """Given same-locale links and sibling regional roots, crawler must prioritize same-locale."""
    responses = {
        "https://example.com/in/": {
            "html": """
            <html>
                <body>
                    <a href="/in/pricing">Pricing</a>
                    <a href="/in/products">Products</a>
                    <a href="/in/about">About</a>
                    <a href="/au/">Australia</a>
                    <a href="/uk/">UK</a>
                    <a href="/de/">Germany</a>
                </body>
            </html>
            """
        },
        "https://example.com/in/pricing": {"html": "<html><body><h1>Pricing</h1></body></html>"},
        "https://example.com/in/products": {"html": "<html><body><h1>Products</h1></body></html>"},
        "https://example.com/in/about": {"html": "<html><body><h1>About</h1></body></html>"},
        "https://example.com/au/": {"html": "<html><body><h1>Australia</h1></body></html>"},
        "https://example.com/uk/": {"html": "<html><body><h1>UK</h1></body></html>"},
        "https://example.com/de/": {"html": "<html><body><h1>Germany</h1></body></html>"},
    }

    client = DummyHTTPClient(responses)
    crawler = BFSCrawler(max_pages=4, max_depth=2, client=client)
    inspection = crawler.crawl("https://example.com/in/", discover_sitemaps=False)

    crawled_urls = [p.url for p in inspection.pages]
    # Under max_pages=4, the 4 crawled pages should be /in/, /in/pricing, /in/products, /in/about
    assert "https://example.com/in" in crawled_urls or "https://example.com/in/" in crawled_urls
    same_locale_count = sum(1 for u in crawled_urls if "/in/" in u or u.endswith("/in"))
    assert same_locale_count >= 3, f"Expected same-locale pages to dominate crawl budget, got: {crawled_urls}"


# =========================================================================
# Test 6: No-Locale Root Audit Preserves Existing Behavior
# =========================================================================
def test_no_locale_root_preserves_standard_crawler_behavior():
    """A standard non-locale root (https://example.com/) must preserve existing crawl behavior."""
    responses = {
        "https://example.com/": {
            "html": """
            <html>
                <body>
                    <a href="/features">Features</a>
                    <a href="/pricing">Pricing</a>
                    <a href="/docs/intro">Docs</a>
                </body>
            </html>
            """
        },
        "https://example.com/features": {"html": "<html><body>Features</body></html>"},
        "https://example.com/pricing": {"html": "<html><body>Pricing</body></html>"},
        "https://example.com/docs/intro": {"html": "<html><body>Docs</body></html>"},
    }

    client = DummyHTTPClient(responses)
    crawler = BFSCrawler(max_pages=4, max_depth=2, client=client)
    inspection = crawler.crawl("https://example.com/", discover_sitemaps=False)

    crawled_urls = [p.url for p in inspection.pages]
    assert len(crawled_urls) == 4
    assert any("features" in u for u in crawled_urls)
    assert any("pricing" in u for u in crawled_urls)


# =========================================================================
# Test 7: URL Locale Helper Utilities
# =========================================================================
def test_url_locale_helpers():
    """Unit tests for extract_locale_prefix, is_locale_root, is_same_locale, and is_regional_sibling."""
    assert extract_locale_prefix("https://www.adobe.com/in/") == "in"
    assert extract_locale_prefix("https://www.adobe.com/in/products") == "in"
    assert extract_locale_prefix("https://www.adobe.com/ae_ar/about") == "ae_ar"
    assert extract_locale_prefix("https://www.adobe.com/en-us/pricing") == "en-us"
    assert extract_locale_prefix("https://www.adobe.com/africa/") == "africa"
    assert extract_locale_prefix("https://docs.python.org/3") is None
    assert extract_locale_prefix("https://fastapi.tiangolo.com/") is None
    assert extract_locale_prefix("https://example.com/api/v1") is None
    assert extract_locale_prefix("https://example.com/docs/intro") is None

    assert is_locale_root("https://www.adobe.com/in/") is True
    assert is_locale_root("https://www.adobe.com/in") is True
    assert is_locale_root("https://www.adobe.com/ae_ar/") is True
    assert is_locale_root("https://www.adobe.com/africa") is True
    assert is_locale_root("https://www.adobe.com/in/products") is False
    assert is_locale_root("https://example.com/") is False

    assert is_same_locale("https://www.adobe.com/in/", "https://www.adobe.com/in/products") is True
    assert is_same_locale("https://www.adobe.com/in/", "https://www.adobe.com/au/") is False
    assert is_same_locale("https://example.com/a", "https://example.com/b") is True

    assert is_regional_sibling("https://www.adobe.com/in/", "https://www.adobe.com/au/") is True
    assert is_regional_sibling("https://www.adobe.com/in/", "https://www.adobe.com/in/pricing") is False
    assert is_regional_sibling("https://example.com/", "https://example.com/au/") is False
