"""Bounded breadth-first search (BFS) web crawler.

Crawls a target website up to configurable page and depth boundaries,
strictly confines crawling to same-site targets, respects robots.txt directives,
and records complete PageInspection and SiteInspection evidence.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import re
import time
from typing import Deque, List, Optional, Set, Tuple
import urllib.parse

from src.crawler.http import (
    DEFAULT_MAX_REDIRECTS,
    DEFAULT_MAX_RESPONSE_SIZE,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    SafeHTTPClient,
)
from src.crawler.sitemap import discover_and_parse_sitemaps
from src.inspection.models import (
    Link,
    PageInspection,
    RobotsTxtInspection,
    SiteInspection,
    SitemapInspection,
    TechnicalIssue,
)
from src.inspection.robots import RobotsParser, inspect_robots_txt
from src.inspection.url import (
    extract_hostname,
    is_private_or_local_target,
    is_same_site,
    is_valid_url,
    normalize_url,
)


def extract_html_links(html_text: str, base_url: str) -> List[Tuple[str, str]]:
    """Extract (normalized_target_url, anchor_text) links from HTML source.
    
    Filters out invalid, unsupported, or unsafe URLs.
    """
    if not html_text:
        return []

    discovered: List[Tuple[str, str]] = []
    # Match <a ... href="..." ...>anchor</a>
    pattern = re.compile(
        r'<a\s+(?:[^>]*?\s+)?href=(["\'])(.*?)\1[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(html_text):
        raw_href = match.group(2).strip()
        raw_text = re.sub(r"<[^>]+>", "", match.group(3)).strip()

        if not raw_href or raw_href.startswith("#"):
            continue

        # Filter out non-web schemes
        if re.match(r"^(javascript|mailto|tel|data|ftp|file):", raw_href, re.IGNORECASE):
            continue

        resolved = urllib.parse.urljoin(base_url, raw_href)
        if not is_valid_url(resolved) or is_private_or_local_target(resolved):
            continue

        try:
            norm = normalize_url(resolved)
            discovered.append((norm, raw_text))
        except Exception:
            continue

    return discovered


class BFSCrawler:
    """Bounded BFS crawler for same-site inspection."""

    def __init__(
        self,
        max_pages: int = 10,
        max_depth: int = 2,
        same_site_only: bool = True,
        respect_robots: bool = True,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT,
        max_response_size: int = DEFAULT_MAX_RESPONSE_SIZE,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        client: Optional[SafeHTTPClient] = None,
    ) -> None:
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.same_site_only = same_site_only
        self.respect_robots = respect_robots
        self.user_agent = user_agent
        self.client = client or SafeHTTPClient(
            timeout=timeout,
            max_response_size=max_response_size,
            max_redirects=max_redirects,
            user_agent=user_agent,
            verify_dns=False,
        )

    def crawl(
        self,
        root_url: str,
        discover_sitemaps: bool = True,
    ) -> SiteInspection:
        """Execute bounded BFS crawl starting from root_url."""
        start_time = time.perf_counter()
        normalized_root = normalize_url(root_url)
        hostname = extract_hostname(normalized_root) or "unknown"

        # 1. Fetch robots.txt
        robots_inspection = inspect_robots_txt(
            normalized_root,
            client=self.client,
            user_agent=self.user_agent,
        )

        robots_parser: Optional[RobotsParser] = None
        if robots_inspection.raw_text:
            robots_parser = RobotsParser(robots_inspection.raw_text)

        # 2. Discover sitemaps if enabled
        sitemap_inspection: SitemapInspection
        if discover_sitemaps:
            sitemap_inspection = discover_and_parse_sitemaps(
                normalized_root,
                robots=robots_inspection,
                client=self.client,
                same_site_only=self.same_site_only,
            )
        else:
            sitemap_inspection = SitemapInspection(checked=False, found=False)

        # 3. Initialize BFS queue: (url, depth)
        queue: Deque[Tuple[str, int]] = deque([(normalized_root, 0)])
        visited_urls: Set[str] = set()
        enqueued_urls: Set[str] = {normalized_root}
        inspected_pages: List[PageInspection] = []

        disallowed_count = 0
        error_count = 0

        while queue and len(inspected_pages) < self.max_pages:
            current_url, depth = queue.popleft()
            if current_url in visited_urls:
                continue

            visited_urls.add(current_url)

            # Check robots.txt permission
            is_allowed = True
            if self.respect_robots and robots_parser is not None:
                is_allowed = robots_parser.is_allowed(current_url, user_agent=self.user_agent)

            if not is_allowed:
                disallowed_count += 1
                page = PageInspection(
                    url=current_url,
                    original_url=current_url,
                    crawl_depth=depth,
                    allowed_by_robots=False,
                    technical_issues=[
                        TechnicalIssue(
                            code="ROBOTS_DISALLOWED",
                            message=f"Page is disallowed by robots.txt policy for agent '{self.user_agent}'.",
                            severity="warning",
                            details={"url": current_url},
                        )
                    ],
                )
                inspected_pages.append(page)
                # Disallowed pages are not fetched or followed
                continue

            # Fetch page safely
            fetch_resp = self.client.get(current_url)
            page = fetch_resp.to_page_inspection(crawl_depth=depth)
            page.allowed_by_robots = True

            if not fetch_resp.success:
                error_count += 1

            # Extract outgoing links if HTML and within depth limit
            if fetch_resp.status_code == 200 and fetch_resp.text and depth < self.max_depth:
                content_type = fetch_resp.content_type or ""
                if "text/html" in content_type or "<html" in fetch_resp.text.lower():
                    links_found = extract_html_links(fetch_resp.text, fetch_resp.url)
                    page_links: List[Link] = []

                    for link_url, anchor_text in links_found:
                        is_internal = is_same_site(normalized_root, link_url)
                        page_links.append(
                            Link(
                                url=link_url,
                                text=anchor_text,
                                is_internal=is_internal,
                            )
                        )

                        # Enqueue for crawling if same-site and not visited/queued
                        if self.same_site_only and not is_internal:
                            continue

                        if (
                            link_url not in visited_urls
                            and link_url not in enqueued_urls
                            and len(visited_urls) + len(queue) < self.max_pages * 2
                        ):
                            enqueued_urls.add(link_url)
                            queue.append((link_url, depth + 1))

                    page.links = page_links

            inspected_pages.append(page)

        total_elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return SiteInspection(
            site=hostname,
            root_url=normalized_root,
            audited_at=datetime.now(timezone.utc),
            total_duration_ms=total_elapsed_ms,
            robots=robots_inspection,
            sitemap=sitemap_inspection,
            pages=inspected_pages,
            summary_counts={
                "total_pages_inspected": len(inspected_pages),
                "disallowed_pages": disallowed_count,
                "error_pages": error_count,
            },
        )


def crawl_site(
    root_url: str,
    max_pages: int = 10,
    max_depth: int = 2,
    same_site_only: bool = True,
    respect_robots: bool = True,
    user_agent: str = DEFAULT_USER_AGENT,
    client: Optional[SafeHTTPClient] = None,
    discover_sitemaps: bool = True,
) -> SiteInspection:
    """Convenience function to run a bounded BFS crawl on a website."""
    crawler = BFSCrawler(
        max_pages=max_pages,
        max_depth=max_depth,
        same_site_only=same_site_only,
        respect_robots=respect_robots,
        user_agent=user_agent,
        client=client,
    )
    return crawler.crawl(root_url, discover_sitemaps=discover_sitemaps)
