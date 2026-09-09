"""Sitemap discovery and XML/index parser.

Discovers sitemaps from robots.txt declarations and standard /sitemap.xml fallback,
recursively resolves sitemap indices, extracts and validates page URLs, and deduplicates.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List, Optional, Set, Tuple
import urllib.parse
import xml.etree.ElementTree as ET

from src.inspection.models import RobotsTxtInspection, SitemapInspection
from src.inspection.url import (
    extract_hostname,
    is_private_or_local_target,
    is_same_site,
    is_valid_url,
    normalize_url,
)

if TYPE_CHECKING:
    from src.crawler.http import SafeHTTPClient


def _extract_text_locs(content: str) -> List[str]:
    """Fallback extractor using regex when strict XML parsing encounters malformed data."""
    # Matches <loc>URL</loc> tags regardless of XML namespaces or surrounding tags
    matches = re.findall(r"<loc[^>]*>\s*([^<\s]+)\s*</loc>", content, re.IGNORECASE)
    if matches:
        return matches

    # Plain text sitemap fallback (one URL per line)
    urls = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("http://") or line.startswith("https://"):
            urls.append(line)
    return urls


def parse_sitemap_content(content: str) -> Tuple[List[str], List[str]]:
    """Parse sitemap content and return (deduplicated_page_urls, deduplicated_sub_sitemaps).
    
    Supports:
    - Standard XML sitemaps (<urlset>)
    - Sitemap Index files (<sitemapindex>)
    - Fallback regex / plain text parsing
    """
    if not content or not content.strip():
        return [], []

    page_urls: List[str] = []
    sub_sitemaps: List[str] = []
    seen_pages: Set[str] = set()
    seen_subs: Set[str] = set()

    # Clean XML content
    cleaned = content.strip()

    try:
        root = ET.fromstring(cleaned)
        tag_name = root.tag.split("}")[-1].lower() if "}" in root.tag else root.tag.lower()

        if tag_name == "sitemapindex":
            # Sitemap index containing pointers to other sitemaps
            for elem in root.iter():
                elem_tag = elem.tag.split("}")[-1].lower() if "}" in elem.tag else elem.tag.lower()
                if elem_tag == "loc" and elem.text and elem.text.strip():
                    url_str = elem.text.strip()
                    if is_valid_url(url_str) and not is_private_or_local_target(url_str):
                        try:
                            norm = normalize_url(url_str)
                            if norm not in seen_subs:
                                seen_subs.add(norm)
                                sub_sitemaps.append(norm)
                        except Exception:
                            pass
            return page_urls, sub_sitemaps

        elif tag_name == "urlset":
            # Standard urlset sitemap
            for elem in root.iter():
                elem_tag = elem.tag.split("}")[-1].lower() if "}" in elem.tag else elem.tag.lower()
                if elem_tag == "loc" and elem.text and elem.text.strip():
                    url_str = elem.text.strip()
                    if is_valid_url(url_str) and not is_private_or_local_target(url_str):
                        try:
                            norm = normalize_url(url_str)
                            if norm not in seen_pages:
                                seen_pages.add(norm)
                                page_urls.append(norm)
                        except Exception:
                            pass
            return page_urls, sub_sitemaps
    except ET.ParseError:
        # Fallback to regex text extraction if XML has minor syntax flaws
        pass
    except Exception:
        pass

    # Fallback extraction
    raw_locs = _extract_text_locs(cleaned)
    for loc in raw_locs:
        if is_valid_url(loc) and not is_private_or_local_target(loc):
            try:
                norm = normalize_url(loc)
                if norm.endswith(".xml") or "sitemap" in norm.lower():
                    if norm not in seen_subs:
                        seen_subs.add(norm)
                        sub_sitemaps.append(norm)
                else:
                    if norm not in seen_pages:
                        seen_pages.add(norm)
                        page_urls.append(norm)
            except Exception:
                pass

    return page_urls, sub_sitemaps


def discover_and_parse_sitemaps(
    site_url: str,
    robots: Optional[RobotsTxtInspection] = None,
    client: Optional[SafeHTTPClient] = None,
    max_sitemaps: int = 5,
    same_site_only: bool = True,
) -> SitemapInspection:
    """Discover, fetch, and parse XML sitemaps and sitemap indices for a website.
    
    Args:
        site_url: Base site URL or root domain.
        robots: Optional pre-fetched RobotsTxtInspection for initial sitemap discovery.
        client: SafeHTTPClient instance.
        max_sitemaps: Maximum number of sitemap files to fetch and parse.
        same_site_only: If True, only retains discovered URLs matching target site.
        
    Returns:
        Populated SitemapInspection data model.
    """
    try:
        norm_site = normalize_url(site_url)
    except Exception as exc:
        return SitemapInspection(
            checked=False,
            found=False,
            error=f"Invalid site URL: {exc}",
        )

    parsed = urllib.parse.urlparse(norm_site)
    scheme = parsed.scheme if parsed.scheme in ("http", "https") else "https"
    hostname = parsed.hostname or extract_hostname(site_url)

    if not hostname:
        return SitemapInspection(
            checked=False,
            found=False,
            error="Missing or invalid hostname.",
        )

    port_part = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
    default_sitemap_url = f"{scheme}://{hostname}{port_part}/sitemap.xml"

    # Gather initial candidate sitemap URLs
    sitemap_queue: List[str] = []
    if robots and robots.sitemap_urls:
        for sm in robots.sitemap_urls:
            if sm not in sitemap_queue:
                sitemap_queue.append(sm)

    if default_sitemap_url not in sitemap_queue:
        sitemap_queue.append(default_sitemap_url)

    visited_sitemaps: Set[str] = set()
    discovered_sitemap_files: List[str] = []
    all_discovered_page_urls: List[str] = []
    seen_page_urls: Set[str] = set()
    primary_status_code: Optional[int] = None
    captured_raw_snippet: Optional[str] = None

    if client is None:
        from src.crawler.http import SafeHTTPClient
        client = SafeHTTPClient(verify_dns=False)

    while sitemap_queue and len(visited_sitemaps) < max_sitemaps:
        sitemap_url = sitemap_queue.pop(0)
        if sitemap_url in visited_sitemaps:
            continue

        visited_sitemaps.add(sitemap_url)

        # Ensure sitemap target is same site / safe
        if same_site_only and not is_same_site(norm_site, sitemap_url):
            continue

        resp = client.get(sitemap_url)
        if primary_status_code is None and resp.status_code is not None:
            primary_status_code = resp.status_code

        if resp.status_code == 200 and resp.text:
            discovered_sitemap_files.append(sitemap_url)
            if captured_raw_snippet is None:
                captured_raw_snippet = resp.text[:2000]

            pages, sub_sitemaps = parse_sitemap_content(resp.text)

            # Add discovered page URLs
            for page in pages:
                if same_site_only and not is_same_site(norm_site, page):
                    continue
                if page not in seen_page_urls:
                    seen_page_urls.add(page)
                    all_discovered_page_urls.append(page)

            # Enqueue discovered sub-sitemaps
            for sub_sm in sub_sitemaps:
                if sub_sm not in visited_sitemaps and sub_sm not in sitemap_queue:
                    sitemap_queue.append(sub_sm)

    found = len(discovered_sitemap_files) > 0

    return SitemapInspection(
        checked=True,
        found=found,
        status_code=primary_status_code if primary_status_code is not None else (200 if found else 404),
        discovered_sitemap_urls=discovered_sitemap_files,
        total_discovered_urls=len(all_discovered_page_urls),
        sample_urls=all_discovered_page_urls[:50],
        raw_content=captured_raw_snippet,
        error=None if found else "No valid sitemap files found.",
    )
