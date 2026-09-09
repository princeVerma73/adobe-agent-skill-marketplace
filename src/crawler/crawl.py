"""Crawler module bridge."""

from src.crawler.crawler import (
    BFSCrawler,
    crawl_site,
    extract_html_links,
)

__all__ = [
    "BFSCrawler",
    "crawl_site",
    "extract_html_links",
]
