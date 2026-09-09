"""Crawler and HTTP fetching utilities."""

from src.crawler.crawler import (
    BFSCrawler,
    crawl_site,
    extract_html_links,
)
from src.crawler.http import (
    DEFAULT_MAX_REDIRECTS,
    DEFAULT_MAX_RESPONSE_SIZE,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    FetchResponse,
    SafeHTTPClient,
    fetch_url,
)
from src.crawler.sitemap import (
    discover_and_parse_sitemaps,
    parse_sitemap_content,
)

__all__ = [
    "BFSCrawler",
    "crawl_site",
    "extract_html_links",
    "DEFAULT_MAX_REDIRECTS",
    "DEFAULT_MAX_RESPONSE_SIZE",
    "DEFAULT_TIMEOUT",
    "DEFAULT_USER_AGENT",
    "FetchResponse",
    "SafeHTTPClient",
    "fetch_url",
    "discover_and_parse_sitemaps",
    "parse_sitemap_content",
]
