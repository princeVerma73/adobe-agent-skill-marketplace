"""Deterministic mocked integration tests for Member 1 inspection pipeline."""

from unittest.mock import MagicMock
import httpx
import pytest

from src.crawler.http import SafeHTTPClient
from src.inspection.models import SiteInspection
from src.inspection.pipeline import (
    InspectionPipeline,
    PipelineConfig,
    inspect_site,
)
from src.rendering.render import RenderConfig


def _create_mock_transport_for_site() -> httpx.MockTransport:
    """Create deterministic mock transport for a multi-page site with robots and sitemap."""
    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)

        if url_str == "https://example.com/robots.txt":
            content = """User-agent: *
Disallow: /admin
Disallow: /secret
Sitemap: https://example.com/sitemap.xml
"""
            return httpx.Response(200, text=content, headers={"Content-Type": "text/plain"})

        elif url_str == "https://example.com/sitemap.xml":
            xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://example.com</loc></url>
    <url><loc>https://example.com/about</loc></url>
    <url><loc>https://example.com/products</loc></url>
</urlset>
"""
            return httpx.Response(200, text=xml, headers={"Content-Type": "application/xml"})

        elif url_str == "https://example.com" or url_str == "https://example.com/":
            html = """<!DOCTYPE html>
<html>
<head>
    <title>Acme Industrial Solutions - Global Tools</title>
    <meta name="description" content="Acme supplies world-class heavy industrial equipment and tooling.">
    <link rel="canonical" href="https://example.com">
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "Organization", "name": "Acme Corp"}
    </script>
</head>
<body>
    <h1>Acme Industrial Homepage</h1>
    <p>Welcome to Acme Industrial Solutions. We manufacture high-end equipment for professionals.</p>
    <nav>
        <a href="/about">About Acme</a>
        <a href="/products">Our Products</a>
        <a href="/spa-app">Interactive App</a>
        <a href="/admin">Admin Area</a>
        <a href="https://external-partner.org">Partner Site</a>
    </nav>
</body>
</html>
"""
            return httpx.Response(200, text=html, headers={"Content-Type": "text/html; charset=utf-8"})

        elif url_str == "https://example.com/about":
            html = """<!DOCTYPE html>
<html>
<head>
    <title>About Acme Corporation</title>
    <meta name="description" content="Learn more about Acme history and team.">
    <link rel="canonical" href="https://example.com/about">
</head>
<body>
    <h1>About Our Company</h1>
    <p>Founded in 1990, Acme provides heavy engineering excellence worldwide.</p>
    <a href="/">Home</a>
</body>
</html>
"""
            return httpx.Response(200, text=html, headers={"Content-Type": "text/html; charset=utf-8"})

        elif url_str == "https://example.com/products":
            html = """<!DOCTYPE html>
<html>
<head>
    <title>Acme Products Catalog</title>
    <meta name="description" content="Browse our catalog of tools and heavy anvils.">
    <link rel="canonical" href="https://example.com/products">
</head>
<body>
    <h1>Product Catalog</h1>
    <p>Heavy duty anvils, hammers, drills, and high precision workshop equipment.</p>
    <a href="/products/drill">Deep Drill</a>
</body>
</html>
"""
            return httpx.Response(200, text=html, headers={"Content-Type": "text/html; charset=utf-8"})

        elif url_str == "https://example.com/products/drill":
            html = """<!DOCTYPE html>
<html>
<head>
    <title>Acme Deep Drill</title>
    <meta name="description" content="Heavy drill details.">
    <link rel="canonical" href="https://example.com/products/drill">
</head>
<body>
    <h1>Deep Drill Item</h1>
    <p>Deep drill specifications and performance ratings.</p>
</body>
</html>
"""
            return httpx.Response(200, text=html, headers={"Content-Type": "text/html; charset=utf-8"})

        elif url_str == "https://example.com/spa-app":
            # SPA template requiring JS rendering
            html = """<!DOCTYPE html>
<html>
<head><title>Loading Interactive App</title></head>
<body>
    <div id="root"></div>
    <script src="/static/js/main.12345.js"></script>
</body>
</html>
"""
            return httpx.Response(200, text=html, headers={"Content-Type": "text/html; charset=utf-8"})

        return httpx.Response(404, text="Not Found")

    return httpx.MockTransport(handler)


class TestPipelineIntegration:
    """Integration test suite for the complete inspection pipeline."""

    def _create_mock_playwright(self):
        """Mock Playwright hierarchy for SPA page hydration."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        rendered_html = """<!DOCTYPE html>
<html>
<head>
    <title>Interactive Dashboard - Acme App</title>
    <meta name="description" content="Real-time machinery control panel">
</head>
<body>
    <h1>Machinery Control Panel</h1>
    <p>Live status: All hydraulic systems operational and calibrated.</p>
</body>
</html>
"""
        mock_page.content.return_value = rendered_html
        mock_page.inner_text.return_value = "Machinery Control Panel Live status: All hydraulic systems operational and calibrated."
        return mock_pw

    def test_full_pipeline_crawl_extraction_rendering_and_technical_audit(self):
        transport = _create_mock_transport_for_site()
        client = SafeHTTPClient(transport=transport, verify_dns=False)
        mock_pw = self._create_mock_playwright()

        site_inspection = inspect_site(
            url="example.com",  # Bare domain should normalize to https://example.com
            max_pages=6,
            max_depth=2,
            client=client,
            playwright_instance=mock_pw,
            discover_sitemaps=True,
            enable_rendering=True,
        )

        assert isinstance(site_inspection, SiteInspection)
        assert site_inspection.site == "example.com"
        assert site_inspection.root_url == "https://example.com"
        assert site_inspection.total_duration_ms is not None

        # 1. Robots.txt verified
        assert site_inspection.robots.checked is True
        assert site_inspection.robots.found is True
        assert len(site_inspection.robots.sitemap_urls) == 1

        # 2. Sitemap verified
        assert site_inspection.sitemap.checked is True
        assert site_inspection.sitemap.found is True
        assert site_inspection.sitemap.total_discovered_urls == 3

        # 3. Pages crawled and extracted
        page_urls = [p.url for p in site_inspection.pages]
        assert "https://example.com" in page_urls
        assert "https://example.com/about" in page_urls
        assert "https://example.com/products" in page_urls

        # 4. Robots disallowed page encountered
        assert "https://example.com/admin" in page_urls
        admin_page = next(p for p in site_inspection.pages if p.url == "https://example.com/admin")
        assert admin_page.allowed_by_robots is False
        assert any(issue.code == "ROBOTS_DISALLOWED" for issue in admin_page.technical_issues)

        # 5. SPA selective rendering verified
        assert "https://example.com/spa-app" in page_urls
        spa_page = next(p for p in site_inspection.pages if p.url == "https://example.com/spa-app")
        assert spa_page.is_rendered is True
        assert spa_page.title == "Interactive Dashboard - Acme App"
        assert "Machinery Control Panel" in (spa_page.rendered_text or "")

        # 6. Technical discoverability audit evidence verified
        assert site_inspection.summary_counts["total_pages_inspected"] >= 4
        assert "total_technical_issues" in site_inspection.summary_counts

    def test_ssrf_and_private_target_rejected(self):
        site_inspection = inspect_site(url="http://127.0.0.1:8000/app")

        assert site_inspection.summary_counts["total_pages_inspected"] == 0
        assert site_inspection.summary_counts["error_pages"] == 1
        assert len(site_inspection.pages) == 1
        assert any(i.code == "INVALID_ROOT_URL" for i in site_inspection.pages[0].technical_issues)

    def test_pipeline_with_rendering_disabled(self):
        transport = _create_mock_transport_for_site()
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        config = PipelineConfig(
            max_pages=3,
            enable_rendering=False,
            discover_sitemaps=False,
        )
        pipeline = InspectionPipeline(config=config, client=client)
        site_inspection = pipeline.run("https://example.com")

        assert site_inspection.sitemap.checked is False
        assert all(not p.is_rendered for p in site_inspection.pages)

    def test_pipeline_with_respect_robots_disabled(self):
        transport = _create_mock_transport_for_site()
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        config = PipelineConfig(
            max_pages=5,
            respect_robots=False,
            discover_sitemaps=False,
            enable_rendering=False,
        )
        pipeline = InspectionPipeline(config=config, client=client)
        site_inspection = pipeline.run("https://example.com")

        assert site_inspection.robots.checked is False

    def test_depth_and_page_limits_respected(self):
        transport = _create_mock_transport_for_site()
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        # Depth = 0 (only root page)
        site_0 = inspect_site(
            url="https://example.com",
            max_pages=10,
            max_depth=0,
            client=client,
            discover_sitemaps=False,
            enable_rendering=False,
        )
        assert len(site_0.pages) == 1

        # Max pages = 2
        site_2 = inspect_site(
            url="https://example.com",
            max_pages=2,
            max_depth=2,
            client=client,
            discover_sitemaps=False,
            enable_rendering=False,
        )
        assert len(site_2.pages) == 2

    def test_pipeline_gracefully_handles_page_failures(self):
        def failing_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if url_str == "https://example.com/robots.txt":
                return httpx.Response(404)
            if url_str == "https://example.com":
                return httpx.Response(
                    200,
                    text="""<html><head><title>Home</title></head><body><h1>Home</h1><a href="/error-500">Error</a></body></html>""",
                    headers={"Content-Type": "text/html"},
                )
            if url_str == "https://example.com/error-500":
                return httpx.Response(500, text="Internal Server Error")
            return httpx.Response(404)

        transport = httpx.MockTransport(failing_handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        site_inspection = inspect_site(
            url="https://example.com",
            max_pages=5,
            client=client,
            discover_sitemaps=False,
            enable_rendering=False,
        )

        assert site_inspection.summary_counts["error_pages"] >= 1
        err_page = next((p for p in site_inspection.pages if p.url == "https://example.com/error-500"), None)
        assert err_page is not None
        assert err_page.status_code == 500
        assert any(i.code == "HTTP_SERVER_ERROR" for i in err_page.technical_issues)
