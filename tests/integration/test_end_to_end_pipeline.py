"""End-to-End Multi-Agent Pipeline Integration Tests across all repository fixtures."""

import json
from pathlib import Path
import pytest

from src.report.models import FinalAuditReport
from src.report.orchestrator import run_full_audit


FIXTURES_DIR = (
    Path(__file__).parent.parent / "fixtures"
    if (Path(__file__).parent.parent / "fixtures").exists()
    else Path(__file__).parent.parent / "member2" / "fixtures"
)


def load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


def test_e2e_clear_entity_site():
    data = load_fixture("clear_entity_site.json")
    report = run_full_audit(data)

    assert isinstance(report, FinalAuditReport)
    assert report.site == "acmecloud.ai"
    assert report.status == "success"
    assert report.entity_profile is not None
    assert report.entity_profile.name == "Acme Cloud AI"
    assert report.overall_score >= 60.0
    assert len(report.recommendations) > 0

    # Ensure Markdown renders without error
    md = report.to_markdown()
    assert "# Brand AI-Readiness Audit Report: acmecloud.ai" in md


def test_e2e_ambiguous_entity_site():
    data = load_fixture("ambiguous_entity_site.json")
    report = run_full_audit(data)

    assert isinstance(report, FinalAuditReport)
    assert report.site == "apexglobal.net"
    assert report.status == "success"
    # Should catch ambiguous entity issues and engagement issues
    assert report.severity_counts.high > 0
    categories = {f.category for f in report.findings}
    assert "entity" in categories or "engagement" in categories


def test_e2e_conflicting_facts_site():
    data = load_fixture("conflicting_facts_site.json")
    report = run_full_audit(data)

    assert isinstance(report, FinalAuditReport)
    assert report.site == "quantumtech.io"
    assert report.status == "success"
    categories = {f.category for f in report.findings}
    assert "consistency" in categories
    assert any("CO-" in f.id for f in report.findings)


def test_e2e_stale_content_site():
    data = load_fixture("stale_content_site.json")
    report = run_full_audit(data)

    assert isinstance(report, FinalAuditReport)
    assert report.site == "legacysystems.org"
    assert report.status == "success"
    categories = {f.category for f in report.findings}
    assert "freshness" in categories


def test_e2e_facts_in_images_site():
    data = load_fixture("facts_in_images_site.json")
    report = run_full_audit(data)

    assert isinstance(report, FinalAuditReport)
    assert report.site == "visualdata.io"
    assert report.status == "success"
    assert any(f.id == "CC-001" for f in report.findings)


def test_trailing_slash_canonicalization_redirect_integration():
    """Verifies that SafeHTTPClient follows trailing-slash canonicalization redirects without false loop."""
    import httpx
    from src.crawler.http import SafeHTTPClient

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if url_str == "https://fastapi.example.com/de":
            return httpx.Response(308, headers={"Location": "https://fastapi.example.com/de/"})
        elif url_str == "https://fastapi.example.com/de/":
            return httpx.Response(200, text="<html><body><h1>German Docs</h1></body></html>", headers={"Content-Type": "text/html"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = SafeHTTPClient(transport=transport, verify_dns=False)
    resp = client.get("https://fastapi.example.com/de")

    assert resp.success is True
    assert resp.status_code == 200
    assert "German Docs" in resp.text
    assert resp.redirect_chain == ["https://fastapi.example.com/de", "https://fastapi.example.com/de/"]


def test_sitemap_partial_sample_suppresses_false_positives():
    """Verifies that PAGE_NOT_IN_SITEMAP is not falsely emitted when only a partial sample is available."""
    from src.inspection.models import PageInspection, SiteInspection, SitemapInspection
    from src.inspection.technical import inspect_page_technical

    page = PageInspection(
        url="https://example.com/item-500",
        original_url="https://example.com/item-500",
        status_code=200,
        title="Item 500",
        body_text="Description for item 500 with sufficient length for inspection.",
    )
    site = SiteInspection(
        site="example.com",
        root_url="https://example.com",
        sitemap=SitemapInspection(
            checked=True,
            found=True,
            total_discovered_urls=1000,
            sample_urls=["https://example.com/item-1", "https://example.com/item-2"],
        ),
        pages=[page],
    )

    issues = inspect_page_technical(page, site_inspection=site)
    assert not any(i.code == "PAGE_NOT_IN_SITEMAP" for i in issues)


def test_cross_skill_heading_deduplication():
    """Verifies that duplicate heading issues across Member 1 and Member 3 are merged cleanly."""
    from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
    from src.report.deduplicator import deduplicate_findings
    from src.report.models import ReportFinding

    f1 = ReportFinding(
        id="TECH-MISSING_H1",
        category="technical",
        title="Page lacks an H1 main heading tag.",
        severity=SeverityLevel.MEDIUM,
        confidence=0.96,
        evidence="Page 'https://example.com/sub' reported MISSING_H1",
        affected_urls=["https://example.com/sub"],
        suggested_action=FindingAction(summary="Add H1", priority=SeverityLevel.MEDIUM),
    )
    f2 = ReportFinding(
        id="ENG-016",
        category="engagement",
        title="Direct landing page lacks clear orienting H1 heading",
        severity=SeverityLevel.MEDIUM,
        confidence=0.87,
        evidence="Page 'https://example.com/sub' does not have an <h1> heading",
        affected_urls=["https://example.com/sub"],
        suggested_action=FindingAction(summary="Add H1", priority=SeverityLevel.MEDIUM),
    )

    deduped = deduplicate_findings([f1, f2])
    assert len(deduped) == 1
    assert deduped[0].id == "TECH-MISSING_H1"
    assert deduped[0].confidence == 0.96


def test_e2e_clean_strong_website_high_score():
    """Verifies that a well-structured website with Schema.org, CTAs, and clear identity receives a high grade."""
    homepage_html = """<!DOCTYPE html>
    <html>
    <head>
      <title>CloudFlow - Enterprise Workflow Automation Platform</title>
      <meta name="description" content="CloudFlow develops scalable enterprise cloud workflow and AI orchestration software for global engineering teams.">
      <meta property="og:site_name" content="CloudFlow">
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "CloudFlow",
        "url": "https://cloudflow.io/",
        "email": "support@cloudflow.io",
        "telephone": "(415) 555-0100",
        "address": {"@type": "PostalAddress", "addressLocality": "San Francisco", "addressRegion": "CA"}
      }
      </script>
    </head>
    <body>
      <h1>Enterprise Cloud Workflow Automation</h1>
      <h2>Core Capabilities</h2>
      <p>CloudFlow is a modern cloud software company that specializes in automated workflow orchestration. We provide enterprise-grade data synchronization and multi-cloud scheduling for over 50,000 active developers worldwide. Headquartered in San Francisco, CA. Contact us at support@cloudflow.io or call (415) 555-0100.</p>
      <a href="/signup">Get Started Free</a>
      <a href="/pricing">View Pricing</a>
      <a href="/about">About Us</a>
      <a href="/contact">Contact Support</a>
      <footer><p>© 2026 CloudFlow Inc. All rights reserved.</p></footer>
    </body>
    </html>
    """

    about_html = """<!DOCTYPE html>
    <html>
    <head>
      <title>About CloudFlow - Company and Mission</title>
      <meta name="description" content="Learn about CloudFlow mission and leadership.">
    </head>
    <body>
      <h1>About CloudFlow</h1>
      <h2>Our Mission</h2>
      <p>CloudFlow is an American software company founded in 2020 by leading distributed systems engineers to build intelligent workflow pipelines in San Francisco, California.</p>
      <a href="/">Home</a>
      <a href="/contact">Contact Us</a>
      <footer><p>© 2026 CloudFlow Inc.</p></footer>
    </body>
    </html>
    """

    clean_site_payload = {
        "site": "cloudflow.io",
        "root_url": "https://cloudflow.io/",
        "homepage": {
            "url": "https://cloudflow.io/",
            "title": "CloudFlow - Enterprise Workflow Automation Platform",
            "html": homepage_html,
            "text": "CloudFlow is a modern cloud software company that specializes in automated workflow orchestration. We provide enterprise-grade data synchronization and multi-cloud scheduling for over 50,000 active developers worldwide. Headquartered in San Francisco, CA. Contact support@cloudflow.io.",
            "links": [
                "https://cloudflow.io/pricing",
                "https://cloudflow.io/about",
                "https://cloudflow.io/signup",
                "https://cloudflow.io/contact",
            ],
            "images": []
        },
        "pages": [
            {
                "url": "https://cloudflow.io/about",
                "title": "About CloudFlow - Company and Mission",
                "html": about_html,
                "text": "CloudFlow is an American software company founded in 2020 by leading distributed systems engineers in San Francisco, California.",
                "links": [
                    "https://cloudflow.io/",
                    "https://cloudflow.io/contact"
                ],
                "images": []
            }
        ]
    }

    report = run_full_audit(clean_site_payload)
    assert report.status == "success"
    assert report.overall_score >= 80.0
    assert report.readiness_grade in ("A", "B")
    assert report.severity_counts.critical == 0
    assert report.severity_counts.high == 0


def test_informational_article_without_commercial_cta_passes():
    """Verifies that non-homepage educational articles are not falsely penalized for missing commercial CTAs."""
    from src.engagement.rules.cta import check_cta_clarity

    article_page = {
        "url": "https://example.com/blog/understanding-dns",
        "title": "Understanding Domain Name System (DNS) Resolution",
        "body_text": "DNS translates human friendly domain names to machine IP addresses in distributed networking.",
        "links": [
            {"url": "https://example.com/", "text": "Home", "is_internal": True},
            {"url": "https://example.com/blog/tcp-handshake", "text": "Next: TCP Handshake", "is_internal": True},
        ]
    }
    # check_cta_clarity only evaluates the root homepage
    findings = check_cta_clarity(
        homepage_url="https://example.com/",
        pages_data=[article_page]
    )
    # Since article is not homepage, no ENG-008 is emitted
    assert not any(f.id == "ENG-008" for f in findings)


def test_ambiguous_entity_produces_ec002_finding():
    """Asserts that an ambiguous entity with generic name and no structured data produces EC-002."""
    ambiguous_payload = {
        "site": "nexusportal.net",
        "root_url": "https://nexusportal.net/",
        "homepage": {
            "url": "https://nexusportal.net/",
            "title": "Welcome - Home",
            "html": "<!DOCTYPE html><html><head><title>Welcome - Home</title></head><body><h1>Welcome to our Portal</h1><p>We are doing innovative things and creating next generation solutions.</p><a href='/about'>About</a></body></html>",
            "text": "Welcome to our Portal. We are doing innovative things and creating next generation solutions.",
            "links": ["https://nexusportal.net/about"],
            "images": []
        },
        "pages": [
            {
                "url": "https://nexusportal.net/about",
                "title": "About Us",
                "html": "<!DOCTYPE html><html><head><title>About Us</title></head><body><h1>About Us</h1><p>Our team provides solutions.</p><a href='/'>Home</a></body></html>",
                "text": "Our team provides solutions.",
                "links": ["https://nexusportal.net/"],
                "images": []
            }
        ]
    }
    report = run_full_audit(ambiguous_payload)
    assert report.status == "success"
    assert any(f.id == "EC-002" for f in report.findings), "Expected EC-002 finding for ambiguous entity"
    ec002 = next(f for f in report.findings if f.id == "EC-002")
    assert ec002.category == "entity"


def test_stale_news_feed_produces_fr002_while_evergreen_page_does_not():
    """Asserts that a stale news/blog feed triggers FR-002, while an evergreen page with the same past date does not."""
    site_payload = {
        "site": "techinnovations.org",
        "root_url": "https://techinnovations.org/",
        "homepage": {
            "url": "https://techinnovations.org/",
            "title": "Tech Innovations Organization",
            "html": "<!DOCTYPE html><html><head><title>Tech Innovations Organization</title></head><body><h1>Tech Innovations</h1><a href='/news/latest'>News</a><a href='/about'>About</a></body></html>",
            "text": "Tech Innovations is an open research foundation.",
            "links": ["https://techinnovations.org/news/latest", "https://techinnovations.org/about"],
            "images": []
        },
        "pages": [
            {
                # News page with 2019 announcement presented as active feed
                "url": "https://techinnovations.org/news/latest",
                "title": "News and Announcements",
                "html": "<!DOCTYPE html><html><head><title>News and Announcements</title><meta name='article:published_time' content='2019-06-15'></head><body><h1>Latest Press Release</h1><h2>2019 Annual Conference Highlights</h2><p>Published in 2019.</p><a href='/'>Home</a></body></html>",
                "text": "Latest Press Release. 2019 Annual Conference Highlights. Published in 2019.",
                "links": ["https://techinnovations.org/"],
                "images": []
            },
            {
                # Evergreen page with same historical date (2019 founding milestone)
                "url": "https://techinnovations.org/about",
                "title": "About Tech Innovations",
                "html": "<!DOCTYPE html><html><head><title>About Tech Innovations</title></head><body><h1>About Us</h1><p>Our foundation was established in 2019 to advance open computing standards.</p><a href='/'>Home</a></body></html>",
                "text": "About Us. Our foundation was established in 2019 to advance open computing standards.",
                "links": ["https://techinnovations.org/"],
                "images": []
            }
        ]
    }
    report = run_full_audit(site_payload)
    assert report.status == "success"
    # FR-002 should be emitted for /news/latest but NOT for /about
    assert any(f.id == "FR-002" for f in report.findings), "Expected FR-002 finding for stale news page"
    fr002 = next(f for f in report.findings if f.id == "FR-002")
    assert "https://techinnovations.org/news/latest" in fr002.affected_urls
    assert "https://techinnovations.org/about" not in fr002.affected_urls


