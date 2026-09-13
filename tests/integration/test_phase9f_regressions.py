"""Phase 9F Regression Tests.

Validates the surgical fixes for:
1. URL variant normalization & link-graph attribution:
   - URL normalization collapses https://example.com, https://www.example.com, and https://example.com/
     into a single crawl target and unified link graph.
   - ENG-004 does not falsely fire when homepage redirects (e.g. python.org -> www.python.org).
2. Entity name disambiguation & contradiction checks:
   - Subpage titles (e.g., Legal / Terms of Service) do NOT produce false cross-page entity name contradictions.
   - Negative test (REQUIRED): A genuine entity-name conflict (e.g., Schema.org Organization name on homepage
     conflicting with a different Schema.org Organization name on About page) MUST still fire a contradiction (CO-*).
"""

import pytest
from src.crawler.crawler import BFSCrawler
from src.crawler.http import FetchResponse
from src.engagement.rules.navigation import check_navigation
from src.engagement.runner import audit_engagement
from src.entity_trust.contracts.schemas import PageSnapshot, SiteSnapshot
from src.entity_trust.runner import audit_content_and_entity
from src.inspection.url import canonicalize_url, is_canonical_equivalent, normalize_url


class MockRedirectCrawlerClient:
    """Mock client simulating redirect from bare domain to www domain with trailing slash."""

    def __init__(self):
        self.fetched_urls = []

    def get(self, url: str) -> FetchResponse:
        self.fetched_urls.append(url)
        if url in ("https://example.com", "https://example.com/"):
            return FetchResponse(
                url="https://www.example.com",
                original_url=url,
                status_code=200,
                redirect_chain=[url, "https://www.example.com/"],
                content_type="text/html",
                text="""
                <html>
                    <body>
                        <a href="https://www.example.com/">Home</a>
                        <a href="https://example.com">Home Alias</a>
                        <a href="/about">About Us</a>
                        <a href="/docs">Documentation</a>
                    </body>
                </html>
                """,
            )
        elif "about" in url:
            return FetchResponse(
                url="https://www.example.com/about",
                original_url=url,
                status_code=200,
                content_type="text/html",
                text="<html><body><h1>About Acme</h1><a href='/'>Home</a></body></html>",
            )
        elif "docs" in url:
            return FetchResponse(
                url="https://www.example.com/docs",
                original_url=url,
                status_code=200,
                content_type="text/html",
                text="<html><body><h1>Acme Docs</h1><a href='/'>Home</a></body></html>",
            )
        return FetchResponse(url=url, original_url=url, status_code=404, success=False)


def test_url_normalization_collapses_homepage_variants():
    """Test that URL normalization collapses scheme, default port, and trailing slashes."""
    v1 = normalize_url("https://example.com")
    v2 = normalize_url("https://example.com/")
    v3 = normalize_url("https://example.com:443/")
    assert v1 == v2 == v3 == "https://example.com"
    assert is_canonical_equivalent("https://example.com", "https://www.example.com")
    assert is_canonical_equivalent("https://example.com/", "https://www.example.com/")


def test_crawler_collapses_homepage_variants_into_single_crawl_target():
    """Crawler must not waste crawl budget fetching redundant homepage variants."""
    client = MockRedirectCrawlerClient()
    crawler = BFSCrawler(max_pages=10, max_depth=2, client=client)
    inspection = crawler.crawl("https://example.com", discover_sitemaps=False)

    crawled_urls = [p.url for p in inspection.pages]
    # Verify no duplicate homepage variants
    homepage_pages = [u for u in crawled_urls if u in ("https://example.com", "https://www.example.com", "https://www.example.com/")]
    assert len(homepage_pages) == 1, f"Expected exactly 1 homepage crawl entry, got: {homepage_pages}"

    # Verify root was redirected and subpages crawled
    assert inspection.root_url == "https://www.example.com"
    assert "https://www.example.com/about" in crawled_urls
    assert "https://www.example.com/docs" in crawled_urls


def test_redirected_homepage_does_not_fire_false_eng004():
    """When a homepage redirects (e.g. example.com -> www.example.com), ENG-004 must not fire."""
    client = MockRedirectCrawlerClient()
    crawler = BFSCrawler(max_pages=10, max_depth=2, client=client)
    inspection = crawler.crawl("https://example.com", discover_sitemaps=False)

    # Run engagement audit on the inspection result
    result = audit_engagement(inspection)
    eng004_findings = [f for f in result.findings if f.id == "ENG-004"]
    assert len(eng004_findings) == 0, f"ENG-004 fired falsely: {[f.evidence for f in eng004_findings]}"


def test_subpage_titles_do_not_produce_false_entity_name_contradiction():
    """Subpage titles like 'Legal', 'Terms of Service' must NOT produce entity name contradictions."""
    snapshot = SiteSnapshot(
        site="stripe.com",
        homepage=PageSnapshot(
            url="https://stripe.com/in",
            html="""
            <html>
                <head>
                    <title>Financial Infrastructure for the Internet | Stripe | India</title>
                    <script type="application/ld+json">
                    {
                        "@context": "https://schema.org",
                        "@type": "Organization",
                        "name": "Stripe",
                        "url": "https://stripe.com"
                    }
                    </script>
                </head>
                <body>
                    <h1>Financial Infrastructure</h1>
                    <p>Stripe is a financial infrastructure platform for businesses.</p>
                </body>
            </html>
            """,
            text="Financial infrastructure for the internet. Stripe is a financial infrastructure platform.",
        ),
        pages=[
            PageSnapshot(
                url="https://stripe.com/in/legal/ssa",
                html="<html><head><title>Stripe Services Agreement - India</title></head><body><h1>Stripe Services Agreement</h1></body></html>",
                text="Stripe Services Agreement for India customers.",
            ),
            PageSnapshot(
                url="https://stripe.com/in/legal/privacy",
                html="<html><head><title>Legal - Privacy Center</title></head><body><h1>Privacy Center</h1></body></html>",
                text="Privacy policies and compliance overview.",
            ),
            PageSnapshot(
                url="https://stripe.com/in/pricing",
                html="<html><head><title>Pricing & Fees | Stripe India</title></head><body><h1>Transparent pricing</h1></body></html>",
                text="Pricing details for Indian businesses.",
            ),
        ],
    )

    result = audit_content_and_entity(snapshot)
    entity_name_conflicts = [
        f for f in result.findings
        if f.id.startswith("CO-") and ("Entity Name" in f.title or "Organization Name" in f.title)
    ]
    assert len(entity_name_conflicts) == 0, f"False entity name contradiction detected: {[f.evidence for f in entity_name_conflicts]}"


def test_negative_genuine_organization_name_conflict_fires_co_finding():
    """NEGATIVE TEST: Genuinely conflicting Schema.org Organization names across pages MUST trigger CO-*."""
    snapshot = SiteSnapshot(
        site="acme.com",
        homepage=PageSnapshot(
            url="https://acme.com",
            html="""
            <html>
                <head>
                    <title>Acme Corporation</title>
                    <script type="application/ld+json">
                    {
                        "@context": "https://schema.org",
                        "@type": "Organization",
                        "name": "Acme Global Industries",
                        "url": "https://acme.com"
                    }
                    </script>
                </head>
                <body>
                    <h1>Welcome to Acme</h1>
                    <p>Acme is a global manufacturing leader.</p>
                </body>
            </html>
            """,
            text="Welcome to Acme. Acme is a global manufacturing leader.",
        ),
        pages=[
            PageSnapshot(
                url="https://acme.com/about",
                html="""
                <html>
                    <head>
                        <title>About Us</title>
                        <script type="application/ld+json">
                        {
                            "@context": "https://schema.org",
                            "@type": "Organization",
                            "name": "Zenith Apex Holdings",
                            "url": "https://acme.com/about"
                        }
                        </script>
                    </head>
                    <body>
                        <h1>About Zenith Apex</h1>
                        <p>Zenith Apex Holdings is an investment conglomerate.</p>
                    </body>
                </html>
                """,
                text="About Zenith Apex Holdings investment conglomerate.",
            ),
        ],
    )

    result = audit_content_and_entity(snapshot)
    org_conflicts = [
        f for f in result.findings
        if f.id.startswith("CO-") and ("Organization Name" in f.title or "Entity Name" in f.title)
    ]
    assert len(org_conflicts) == 1, f"Expected 1 organization name CO-* finding, got {len(org_conflicts)}: {[f.evidence for f in org_conflicts]}"
    assert "Acme Global Industries" in org_conflicts[0].evidence
    assert "Zenith Apex Holdings" in org_conflicts[0].evidence
