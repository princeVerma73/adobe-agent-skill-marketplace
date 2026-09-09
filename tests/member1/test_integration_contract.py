"""Comprehensive integration contract validation tests for Member 1 outputs and interfaces."""

import json
from pathlib import Path
import re
from unittest.mock import MagicMock
import httpx
import pytest

from src.crawler.http import SafeHTTPClient
from src.inspection import (
    Heading,
    InspectionPipeline,
    Link,
    PageInspection,
    PageMetadata,
    PipelineConfig,
    RobotsTxtInspection,
    SiteInspection,
    SitemapInspection,
    TechnicalIssue,
    inspect_site,
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SKILL_MD_PATH = ROOT_DIR / "skills" / "crawl-render-audit" / "SKILL.md"


def _build_mock_site_transport() -> httpx.MockTransport:
    """Deterministic mock transport providing multi-page crawl, robots, sitemap, and dynamic content."""
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        if url == "https://sample-site.org/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /admin\nSitemap: https://sample-site.org/sitemap.xml\nCrawl-delay: 1\n",
                headers={"Content-Type": "text/plain"},
            )
        elif url == "https://sample-site.org/sitemap.xml":
            xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://sample-site.org</loc></url>
    <url><loc>https://sample-site.org/about</loc></url>
</urlset>
"""
            return httpx.Response(200, text=xml, headers={"Content-Type": "application/xml"})
        elif url in ("https://sample-site.org", "https://sample-site.org/"):
            html = """<!DOCTYPE html>
<html>
<head>
    <title>Sample Site - Knowledge Base</title>
    <meta name="description" content="A comprehensive knowledge base for integration testing.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://sample-site.org">
    <meta property="og:title" content="Sample Knowledge Base">
    <meta name="twitter:card" content="summary">
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "WebSite", "name": "Sample Site"}
    </script>
</head>
<body>
    <h1>Knowledge Base Main Page</h1>
    <p>Welcome to our knowledge base. We provide helpful documentation and insights.</p>
    <nav>
        <a href="/about">About Us</a>
        <a href="/dynamic">Dynamic App</a>
        <a href="/admin">Admin Area</a>
        <a href="https://external.org/info" rel="nofollow">External Link</a>
    </nav>
</body>
</html>
"""
            return httpx.Response(200, text=html, headers={"Content-Type": "text/html; charset=utf-8"})
        elif url == "https://sample-site.org/about":
            html = """<!DOCTYPE html>
<html>
<head>
    <title>About Us - Sample Site</title>
    <meta name="description" content="About our mission and team.">
    <link rel="canonical" href="https://sample-site.org/about">
</head>
<body>
    <h1>About Our Team</h1>
    <p>We are a dedicated team producing high quality software.</p>
</body>
</html>
"""
            return httpx.Response(200, text=html, headers={"Content-Type": "text/html; charset=utf-8"})
        elif url == "https://sample-site.org/dynamic":
            return httpx.Response(
                200,
                text="""<!DOCTYPE html><html><head><title>Loading...</title></head><body><div id="root"></div><script src="/app.js"></script></body></html>""",
                headers={"Content-Type": "text/html; charset=utf-8"},
            )

        return httpx.Response(404, text="Not Found")

    return httpx.MockTransport(handler)


class TestMember1IntegrationContract:
    """Verify Member 1 contracts and data consumers (Member 2/3 compatibility)."""

    def _mock_playwright_instance(self):
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_page.content.return_value = """<!DOCTYPE html>
<html><head><title>Hydrated Dynamic App</title><meta name="description" content="Rendered app content"></head>
<body><h1>Hydrated Dashboard</h1><p>Rendered live dashboard widgets and data.</p></body></html>"""
        mock_page.inner_text.return_value = "Hydrated Dashboard Rendered live dashboard widgets and data."
        return mock_pw

    def test_inspect_site_returns_valid_site_inspection_with_all_subcomponents(self):
        """1. inspect_site(url) returns valid SiteInspection with robots, sitemap, pages, and technical evidence."""
        transport = _build_mock_site_transport()
        client = SafeHTTPClient(transport=transport, verify_dns=False)
        mock_pw = self._mock_playwright_instance()

        site = inspect_site(
            url="sample-site.org",
            max_pages=5,
            max_depth=2,
            client=client,
            playwright_instance=mock_pw,
            discover_sitemaps=True,
            enable_rendering=True,
        )

        # 1 & 2: SiteInspection structure
        assert isinstance(site, SiteInspection)
        assert site.site == "sample-site.org"
        assert site.root_url == "https://sample-site.org"
        assert isinstance(site.robots, RobotsTxtInspection)
        assert site.robots.checked is True
        assert site.robots.found is True
        assert isinstance(site.sitemap, SitemapInspection)
        assert site.sitemap.checked is True
        assert site.sitemap.found is True
        assert site.sitemap.total_discovered_urls >= 2
        assert isinstance(site.pages, list)
        assert len(site.pages) >= 3

        # 3: PageInspection extracted/rendered observations and technical issues
        root_page = next((p for p in site.pages if p.url == "https://sample-site.org"), None)
        assert root_page is not None
        assert root_page.title == "Sample Site - Knowledge Base"
        assert root_page.metadata.description == "A comprehensive knowledge base for integration testing."
        assert root_page.metadata.robots_meta == "index, follow"
        assert root_page.metadata.canonical_url == "https://sample-site.org"
        assert root_page.metadata.open_graph.get("og:title") == "Sample Knowledge Base"
        assert root_page.metadata.twitter_card.get("twitter:card") == "summary"
        assert len(root_page.headings) == 1
        assert root_page.headings[0].level == 1
        assert root_page.headings[0].text == "Knowledge Base Main Page"
        assert "Welcome to our knowledge base" in (root_page.body_text or "")
        assert len(root_page.links) >= 3
        assert len(root_page.structured_data) == 1
        assert root_page.structured_data[0]["@type"] == "WebSite"
        assert isinstance(root_page.technical_issues, list)

        # Disallowed page observation
        admin_page = next((p for p in site.pages if p.url == "https://sample-site.org/admin"), None)
        assert admin_page is not None
        assert admin_page.allowed_by_robots is False

        # Rendered page observation
        dyn_page = next((p for p in site.pages if p.url == "https://sample-site.org/dynamic"), None)
        assert dyn_page is not None
        assert dyn_page.is_rendered is True
        assert dyn_page.rendered_text is not None
        assert "Hydrated Dashboard" in dyn_page.rendered_text

    def test_json_serialization_and_deserialization_round_trip(self):
        """4. JSON serialization / deserialization round trip compatibility."""
        transport = _build_mock_site_transport()
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        site = inspect_site(
            url="https://sample-site.org",
            max_pages=2,
            client=client,
            discover_sitemaps=False,
            enable_rendering=False,
        )

        json_str = site.model_dump_json()
        assert isinstance(json_str, str)
        assert "sample-site.org" in json_str

        # Verify exact round-trip reconstruction
        reconstructed = SiteInspection.model_validate_json(json_str)
        assert reconstructed.site == site.site
        assert reconstructed.root_url == site.root_url
        assert len(reconstructed.pages) == len(site.pages)
        assert reconstructed.pages[0].title == site.pages[0].title
        assert reconstructed.pages[0].headings[0].text == site.pages[0].headings[0].text

        # Also verify dict serialization
        dict_data = site.model_dump()
        reconstructed_from_dict = SiteInspection.model_validate(dict_data)
        assert reconstructed_from_dict.site == site.site

    def test_neutral_evidence_without_member2_member3_assumptions(self):
        """5. Verify that Member 1 outputs represent neutral raw evidence without final scoring/downstream logic."""
        page = PageInspection(
            url="https://example.com",
            original_url="https://example.com",
            status_code=200,
            title="Clean Page",
            technical_issues=[
                TechnicalIssue(code="MISSING_H1", message="Page lacks H1", severity="warning")
            ],
        )

        site = SiteInspection(
            site="example.com",
            root_url="https://example.com",
            pages=[page],
        )

        data = site.model_dump()
        # Verify no hardcoded final scoring / brand audit conclusions are injected
        assert "final_score" not in data
        assert "overall_grade" not in data
        assert "recommendation_actions" not in data
        assert "brand_trust_score" not in data
        # Verify neutral structure
        assert "pages" in data
        assert "robots" in data
        assert "sitemap" in data
        assert "summary_counts" in data

    def test_pipeline_configuration_controllability(self):
        """6. Pipeline configuration options are respected."""
        transport = _build_mock_site_transport()
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        # 1. Depth=0, max_pages=1
        site_bounded = inspect_site(
            url="https://sample-site.org",
            max_pages=1,
            max_depth=0,
            client=client,
            discover_sitemaps=False,
            enable_rendering=False,
        )
        assert len(site_bounded.pages) == 1

        # 2. respect_robots=False
        site_no_robots = inspect_site(
            url="https://sample-site.org",
            max_pages=3,
            respect_robots=False,
            client=client,
            discover_sitemaps=False,
            enable_rendering=False,
        )
        assert site_no_robots.robots.checked is False

    def test_failures_remain_structured_and_do_not_crash(self):
        """7. Failures remain structured and do not crash the pipeline."""
        # 1. Invalid / SSRF target
        ssrf_site = inspect_site(url="http://127.0.0.1:9000/private")
        assert isinstance(ssrf_site, SiteInspection)
        assert ssrf_site.summary_counts["error_pages"] == 1
        assert any(i.code == "INVALID_ROOT_URL" for i in ssrf_site.pages[0].technical_issues)

        # 2. Network / server error handler
        def broken_handler(request: httpx.Request) -> httpx.Response:
            if str(request.url).endswith("robots.txt"):
                return httpx.Response(500, text="Server Error")
            return httpx.Response(503, text="Service Unavailable")

        broken_client = SafeHTTPClient(transport=httpx.MockTransport(broken_handler), verify_dns=False)
        error_site = inspect_site(
            url="https://failing-site.com",
            client=broken_client,
            discover_sitemaps=False,
            enable_rendering=False,
        )
        assert isinstance(error_site, SiteInspection)
        assert error_site.summary_counts["error_pages"] >= 1

    def test_skill_documentation_matches_pipeline_interface(self):
        """8. Skill documentation in SKILL.md matches actual inspect_site pipeline signature."""
        assert SKILL_MD_PATH.exists()
        skill_doc = SKILL_MD_PATH.read_text(encoding="utf-8")

        # Check documented parameters exist in inspect_site signature
        import inspect
        from src.inspection import inspect_site as actual_fn

        sig = inspect.signature(actual_fn)
        param_names = list(sig.parameters.keys())

        expected_params = [
            "url",
            "max_pages",
            "max_depth",
            "timeout",
            "same_site_only",
            "respect_robots",
            "discover_sitemaps",
            "enable_rendering",
        ]

        for p in expected_params:
            assert p in param_names, f"Parameter '{p}' missing from inspect_site signature"
            assert f"`{p}`" in skill_doc, f"Parameter '{p}' not documented in SKILL.md"
