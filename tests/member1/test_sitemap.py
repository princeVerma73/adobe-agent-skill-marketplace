"""Unit tests for sitemap discovery and XML parsing."""

import pytest
import httpx

from src.crawler.http import SafeHTTPClient
from src.crawler.sitemap import (
    discover_and_parse_sitemaps,
    parse_sitemap_content,
)
from src.inspection.models import RobotsTxtInspection, SitemapInspection


SAMPLE_URLSET_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/</loc>
    <lastmod>2026-01-01</lastmod>
  </url>
  <url>
    <loc>https://example.com/products</loc>
  </url>
  <url>
    <loc>https://example.com/about</loc>
  </url>
  <url>
    <loc>javascript:alert(1)</loc>
  </url>
  <url>
    <loc>http://127.0.0.1/private</loc>
  </url>
  <url>
    <loc>https://example.com/products</loc>
  </url>
</urlset>
"""

SAMPLE_INDEX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://example.com/sitemap-main.xml</loc>
  </sitemap>
  <sitemap>
    <loc>https://example.com/sitemap-blog.xml</loc>
  </sitemap>
</sitemapindex>
"""

SAMPLE_BLOG_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/blog/post-1</loc>
  </url>
  <url>
    <loc>https://example.com/blog/post-2</loc>
  </url>
</urlset>
"""


class TestSitemapParser:
    """Test unit behavior of parse_sitemap_content."""

    def test_parse_standard_urlset(self):
        pages, sub_sitemaps = parse_sitemap_content(SAMPLE_URLSET_XML)
        assert len(pages) == 3
        assert "https://example.com" in pages
        assert "https://example.com/products" in pages
        assert "https://example.com/about" in pages
        # Unsafe and invalid URLs filtered
        assert not any("127.0.0.1" in p for p in pages)
        assert not any("javascript" in p for p in pages)
        assert sub_sitemaps == []

    def test_parse_sitemap_index(self):
        pages, sub_sitemaps = parse_sitemap_content(SAMPLE_INDEX_XML)
        assert pages == []
        assert len(sub_sitemaps) == 2
        assert "https://example.com/sitemap-main.xml" in sub_sitemaps
        assert "https://example.com/sitemap-blog.xml" in sub_sitemaps

    def test_plain_text_sitemap_fallback(self):
        plain_text = """
        https://example.com/page1
        https://example.com/page2
        not-a-url
        http://192.168.1.1/secret
        """
        pages, sub_sitemaps = parse_sitemap_content(plain_text)
        assert len(pages) == 2
        assert "https://example.com/page1" in pages
        assert "https://example.com/page2" in pages

    def test_empty_content_returns_empty(self):
        pages, sub = parse_sitemap_content("")
        assert pages == []
        assert sub == []


class TestDiscoverAndParseSitemaps:
    """Test sitemap discovery through mocked HTTP interactions."""

    def test_discover_from_robots_sitemap_declaration(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/custom-sitemap.xml":
                return httpx.Response(200, text=SAMPLE_URLSET_XML)
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        robots = RobotsTxtInspection(
            checked=True,
            found=True,
            sitemap_urls=["https://example.com/custom-sitemap.xml"],
        )

        result = discover_and_parse_sitemaps("https://example.com", robots=robots, client=client)
        assert isinstance(result, SitemapInspection)
        assert result.checked is True
        assert result.found is True
        assert result.total_discovered_urls == 3
        assert "https://example.com/products" in result.sample_urls
        assert "https://example.com/custom-sitemap.xml" in result.discovered_sitemap_urls

    def test_discover_fallback_to_default_sitemap_xml(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/sitemap.xml":
                return httpx.Response(200, text=SAMPLE_URLSET_XML)
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        # No robots sitemap declared
        robots = RobotsTxtInspection(checked=True, found=True, sitemap_urls=[])

        result = discover_and_parse_sitemaps("https://example.com", robots=robots, client=client)
        assert result.found is True
        assert result.total_discovered_urls == 3
        assert "https://example.com/sitemap.xml" in result.discovered_sitemap_urls

    def test_nested_sitemap_index_resolution(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/sitemap.xml":
                return httpx.Response(200, text=SAMPLE_INDEX_XML)
            elif request.url.path == "/sitemap-main.xml":
                return httpx.Response(200, text=SAMPLE_URLSET_XML)
            elif request.url.path == "/sitemap-blog.xml":
                return httpx.Response(200, text=SAMPLE_BLOG_XML)
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        result = discover_and_parse_sitemaps("https://example.com", client=client)
        assert result.found is True
        # 3 pages from main + 2 pages from blog = 5 unique pages
        assert result.total_discovered_urls == 5
        assert "https://example.com/blog/post-1" in result.sample_urls
        assert len(result.discovered_sitemap_urls) == 3

    def test_sitemap_not_found_404(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="Not Found")

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        result = discover_and_parse_sitemaps("https://example.com", client=client)
        assert result.checked is True
        assert result.found is False
        assert result.total_discovered_urls == 0
        assert result.error is not None
