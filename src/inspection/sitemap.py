"""Inspection module bridge for sitemap utilities."""

from src.crawler.sitemap import (
    discover_and_parse_sitemaps,
    parse_sitemap_content,
)

__all__ = [
    "discover_and_parse_sitemaps",
    "parse_sitemap_content",
]
