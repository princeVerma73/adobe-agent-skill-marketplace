"""Unit tests for bounded BFS crawler using mocked HTTP responses."""

import pytest
import httpx

from src.crawler.crawler import BFSCrawler, crawl_site, extract_html_links
from src.crawler.http import SafeHTTPClient
from src.inspection.models import SiteInspection


HTML_ROOT = """
<!DOCTYPE html>
<html>
<head><title>Home</title></head>
<body>
  <h1>Welcome to Store</h1>
  <a href="/products">Products</a>
  <a href="/about">About Us</a>
  <a href="https://external-partner.com/info">Partner</a>
  <a href="/disallowed-admin">Admin Panel</a>
</body>
</html>
"""

HTML_PRODUCTS = """
<!DOCTYPE html>
<html>
<head><title>Products</title></head>
<body>
  <h1>Product List</h1>
  <a href="/products/item-1">Item 1</a>
  <a href="/products/item-2">Item 2</a>
  <a href="/">Home</a>
</body>
</html>
"""

HTML_ITEM1 = """
<!DOCTYPE html>
<html>
<head><title>Item 1</title></head>
<body>
  <h1>Product Item 1</h1>
  <a href="/products/item-1/deep">Deep Page</a>
</body>
</html>
"""

HTML_DEEP = """
<!DOCTYPE html>
<html><head><title>Deep</title></head><body><h1>Deepest page</h1></body></html>
"""

ROBOTS_TXT = """
User-agent: *
Disallow: /disallowed-admin
"""


class TestLinkExtractor:
    """Test link extraction utility."""

    def test_extract_html_links(self):
        links = extract_html_links(HTML_ROOT, "https://example.com")
        urls = [url for url, _ in links]
        assert "https://example.com/products" in urls
        assert "https://example.com/about" in urls
        assert "https://external-partner.com/info" in urls
        assert "https://example.com/disallowed-admin" in urls

    def test_filter_javascript_and_anchors(self):
        html = '<a href="javascript:void(0)">JS</a><a href="#section">Hash</a><a href="/valid">Valid</a>'
        links = extract_html_links(html, "https://example.com")
        assert len(links) == 1
        assert links[0][0] == "https://example.com/valid"


class TestBFSCrawler:
    """Test suite for BFSCrawler execution and limits."""

    def test_bounded_bfs_crawl_success(self):
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/robots.txt":
                return httpx.Response(200, text=ROBOTS_TXT)
            elif path == "/sitemap.xml":
                return httpx.Response(404)
            elif path in ("", "/"):
                return httpx.Response(200, text=HTML_ROOT, headers={"Content-Type": "text/html"})
            elif path == "/products":
                return httpx.Response(200, text=HTML_PRODUCTS, headers={"Content-Type": "text/html"})
            elif path == "/about":
                return httpx.Response(200, text="<h1>About</h1>", headers={"Content-Type": "text/html"})
            elif path == "/products/item-1":
                return httpx.Response(200, text=HTML_ITEM1, headers={"Content-Type": "text/html"})
            elif path == "/products/item-2":
                return httpx.Response(200, text="<h1>Item 2</h1>", headers={"Content-Type": "text/html"})
            elif path == "/products/item-1/deep":
                return httpx.Response(200, text=HTML_DEEP, headers={"Content-Type": "text/html"})
            elif path == "/disallowed-admin":
                return httpx.Response(200, text="<h1>Secret Admin</h1>", headers={"Content-Type": "text/html"})
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        crawler = BFSCrawler(
            max_pages=5,
            max_depth=2,
            same_site_only=True,
            respect_robots=True,
            client=client,
        )

        site_result = crawler.crawl("https://example.com", discover_sitemaps=True)

        assert isinstance(site_result, SiteInspection)
        assert site_result.site == "example.com"
        assert site_result.root_url == "https://example.com"
        assert len(site_result.pages) <= 5

        # Check pages visited
        crawled_urls = [p.url for p in site_result.pages]
        assert "https://example.com" in crawled_urls

        # Verify robots.txt disallowed page was recorded but not fetched
        admin_page = next((p for p in site_result.pages if "/disallowed-admin" in p.url), None)
        if admin_page:
            assert admin_page.allowed_by_robots is False
            assert any(issue.code == "ROBOTS_DISALLOWED" for issue in admin_page.technical_issues)

        # External URLs must NEVER be crawled
        assert not any("external-partner.com" in p.url for p in site_result.pages)

    def test_max_depth_enforced(self):
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/robots.txt" or path == "/sitemap.xml":
                return httpx.Response(404)
            elif path in ("", "/"):
                return httpx.Response(200, text=HTML_ROOT, headers={"Content-Type": "text/html"})
            elif path == "/products":
                return httpx.Response(200, text=HTML_PRODUCTS, headers={"Content-Type": "text/html"})
            elif path == "/about":
                return httpx.Response(200, text="<h1>About</h1>", headers={"Content-Type": "text/html"})
            elif path == "/products/item-1":
                return httpx.Response(200, text=HTML_ITEM1, headers={"Content-Type": "text/html"})
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        # Depth 1: should only crawl root (depth 0) and its direct children (depth 1)
        crawler = BFSCrawler(max_pages=10, max_depth=1, client=client)
        result = crawler.crawl("https://example.com", discover_sitemaps=False)

        for page in result.pages:
            assert page.crawl_depth <= 1

    def test_page_errors_handled_gracefully(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(404)
            elif request.url.path in ("", "/"):
                return httpx.Response(
                    200,
                    text='<a href="/broken">Broken</a><a href="/error">Error</a>',
                    headers={"Content-Type": "text/html"},
                )
            elif request.url.path == "/broken":
                return httpx.Response(404, text="Not Found")
            elif request.url.path == "/error":
                return httpx.Response(500, text="Server Crash")
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        result = crawl_site("https://example.com", max_pages=5, client=client, discover_sitemaps=False)

        assert len(result.pages) == 3
        broken_page = next((p for p in result.pages if "/broken" in p.url), None)
        assert broken_page is not None
        assert broken_page.status_code == 404
        assert any("HTTP_404" in issue.code for issue in broken_page.technical_issues)

    def test_deduplication_prevents_infinite_loops(self):
        # A links to B, B links to A
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(404)
            elif request.url.path in ("", "/"):
                return httpx.Response(200, text='<a href="/page-b">B</a>', headers={"Content-Type": "text/html"})
            elif request.url.path == "/page-b":
                return httpx.Response(200, text='<a href="/">A</a>', headers={"Content-Type": "text/html"})
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        result = crawl_site("https://example.com", max_pages=10, max_depth=5, client=client, discover_sitemaps=False)

        # Should only visit root and /page-b exactly once each
        assert len(result.pages) == 2
        visited = [p.url for p in result.pages]
        assert visited == ["https://example.com", "https://example.com/page-b"]

    def test_sitemap_discovered_urls_audited_within_page_budget(self):
        """Verifies that URLs discovered exclusively via XML sitemaps are seeded and crawled."""
        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/sitemap-exclusive-1</loc></url>
          <url><loc>https://example.com/sitemap-exclusive-2</loc></url>
        </urlset>
        """

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nSitemap: https://example.com/sitemap.xml\n")
            elif path == "/sitemap.xml":
                return httpx.Response(200, text=sitemap_xml, headers={"Content-Type": "application/xml"})
            elif path in ("", "/"):
                # Homepage has no outgoing links
                return httpx.Response(200, text="<html><body><h1>Bare Homepage</h1></body></html>", headers={"Content-Type": "text/html"})
            elif path == "/sitemap-exclusive-1":
                return httpx.Response(200, text="<html><body><h1>Exclusive Page 1</h1></body></html>", headers={"Content-Type": "text/html"})
            elif path == "/sitemap-exclusive-2":
                return httpx.Response(200, text="<html><body><h1>Exclusive Page 2</h1></body></html>", headers={"Content-Type": "text/html"})
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        crawler = BFSCrawler(max_pages=5, max_depth=2, client=client)
        result = crawler.crawl("https://example.com", discover_sitemaps=True)

        urls_crawled = [p.url for p in result.pages]
        assert "https://example.com" in urls_crawled
        assert "https://example.com/sitemap-exclusive-1" in urls_crawled
        assert "https://example.com/sitemap-exclusive-2" in urls_crawled
        assert len(result.pages) == 3
