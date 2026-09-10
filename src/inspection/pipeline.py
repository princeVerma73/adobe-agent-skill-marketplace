"""End-to-end Member 1 inspection pipeline.

Orchestrates URL normalization and SSRF validation, safe HTTP client fetching,
robots.txt checking, sitemap discovery, bounded BFS crawling, static HTML extraction,
selective Playwright rendering, and technical discoverability audit rules.
Returns a unified, fully-populated SiteInspection model.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import time
from typing import TYPE_CHECKING, Any, Deque, List, Optional, Set, Tuple
import urllib.parse

if TYPE_CHECKING:
    from src.crawler.http import SafeHTTPClient
    from src.extraction.extract import (
        extract_static_html,
        is_rendering_needed,
        populate_page_inspection,
    )
from src.inspection.models import (
    Link,
    PageInspection,
    RobotsTxtInspection,
    SiteInspection,
    SitemapInspection,
    TechnicalIssue,
)
from src.inspection.robots import RobotsParser, inspect_robots_txt
from src.inspection.technical import audit_technical_discoverability
from src.inspection.url import (
    InvalidURLError,
    PrivateTargetError,
    extract_hostname,
    is_private_or_local_target,
    is_same_site,
    is_valid_url,
    normalize_url,
)
from src.rendering.render import (
    RenderConfig,
    render_and_inspect_page,
)

if TYPE_CHECKING:
    from src.crawler.http import SafeHTTPClient

logger = logging.getLogger(__name__)

# Constants
DEFAULT_PIPELINE_USER_AGENT = "Adobe-BrandAuditBot/1.0 (+https://adobe.com/agent-marketplace-audit)"
DEFAULT_PIPELINE_TIMEOUT = 10.0
DEFAULT_PIPELINE_MAX_RESPONSE_SIZE = 2 * 1024 * 1024
DEFAULT_PIPELINE_MAX_REDIRECTS = 5


@dataclass
class PipelineConfig:
    """Configuration settings for Member 1 inspection pipeline."""
    max_pages: int = 10
    max_depth: int = 2
    timeout: float = DEFAULT_PIPELINE_TIMEOUT
    max_response_size: int = DEFAULT_PIPELINE_MAX_RESPONSE_SIZE
    max_redirects: int = DEFAULT_PIPELINE_MAX_REDIRECTS
    same_site_only: bool = True
    respect_robots: bool = True
    discover_sitemaps: bool = True
    enable_rendering: bool = True
    user_agent: str = DEFAULT_PIPELINE_USER_AGENT
    render_config: Optional[RenderConfig] = None


class InspectionPipeline:
    """Unified inspection pipeline connecting crawl, extraction, rendering, and technical auditing."""

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        client: Optional[Any] = None,
        playwright_instance: Optional[Any] = None,
    ) -> None:
        self.config = config or PipelineConfig()
        if client is not None:
            self.client = client
        else:
            from src.crawler.http import SafeHTTPClient
            self.client = SafeHTTPClient(
                timeout=self.config.timeout,
                max_response_size=self.config.max_response_size,
                max_redirects=self.config.max_redirects,
                user_agent=self.config.user_agent,
                verify_dns=False,
            )
        self.playwright_instance = playwright_instance

    def run(self, url: str) -> SiteInspection:
        """Run full inspection pipeline on target website URL."""
        start_time = time.perf_counter()

        # 1. URL Normalization and SSRF Boundary Check
        try:
            normalized_root = normalize_url(url)
        except (InvalidURLError, PrivateTargetError) as exc:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            raw_host = extract_hostname(url) or "invalid"
            return SiteInspection(
                site=raw_host,
                root_url=url,
                audited_at=datetime.now(timezone.utc),
                total_duration_ms=elapsed_ms,
                pages=[
                    PageInspection(
                        url=url,
                        original_url=url,
                        technical_issues=[
                            TechnicalIssue(
                                code="INVALID_ROOT_URL",
                                message=f"Root URL validation failed: {exc}",
                                severity="error",
                                details={"url": url, "error": str(exc)},
                            )
                        ],
                    )
                ],
                summary_counts={"total_pages_inspected": 0, "error_pages": 1},
            )

        hostname = extract_hostname(normalized_root) or "unknown"

        # 2. Inspect robots.txt
        robots_inspection: RobotsTxtInspection
        robots_parser: Optional[RobotsParser] = None
        if self.config.respect_robots:
            robots_inspection = inspect_robots_txt(
                normalized_root,
                client=self.client,
                user_agent=self.config.user_agent,
            )
            if robots_inspection.raw_text:
                robots_parser = RobotsParser(robots_inspection.raw_text)
        else:
            robots_inspection = RobotsTxtInspection(checked=False, found=False)

        # 3. Discover Sitemaps
        sitemap_inspection: SitemapInspection
        if self.config.discover_sitemaps:
            from src.crawler.sitemap import discover_and_parse_sitemaps
            sitemap_inspection = discover_and_parse_sitemaps(
                normalized_root,
                robots=robots_inspection,
                client=self.client,
                same_site_only=self.config.same_site_only,
            )
        else:
            sitemap_inspection = SitemapInspection(checked=False, found=False)

        # 4. Bounded BFS Crawl + Extraction + Selective Rendering
        queue: Deque[Tuple[str, int]] = deque([(normalized_root, 0)])
        visited_urls: Set[str] = set()
        enqueued_urls: Set[str] = {normalized_root}
        inspected_pages: List[PageInspection] = []

        disallowed_count = 0
        error_count = 0

        while queue and len(inspected_pages) < self.config.max_pages:
            current_url, depth = queue.popleft()
            if current_url in visited_urls:
                continue
            visited_urls.add(current_url)

            # Robots.txt check
            is_allowed = True
            if self.config.respect_robots and robots_parser is not None:
                is_allowed = robots_parser.is_allowed(current_url, user_agent=self.config.user_agent)

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
                            message=f"Page is disallowed by robots.txt policy for agent '{self.config.user_agent}'.",
                            severity="warning",
                            details={"url": current_url},
                        )
                    ],
                )
                inspected_pages.append(page)
                continue

            # Fetch page safely
            fetch_resp = self.client.get(current_url)
            page = fetch_resp.to_page_inspection(crawl_depth=depth)
            page.allowed_by_robots = True

            if not fetch_resp.success or (fetch_resp.status_code is not None and fetch_resp.status_code >= 400):
                error_count += 1

            # If HTML response was received
            if fetch_resp.status_code == 200 and fetch_resp.text:
                content_type = (fetch_resp.content_type or "").lower()
                if "text/html" in content_type or "<html" in fetch_resp.text.lower():
                    from src.extraction.extract import (
                        extract_static_html,
                        is_rendering_needed,
                        populate_page_inspection,
                    )
                    # Base static extraction
                    static_extracted = extract_static_html(fetch_resp.text, base_url=page.url)
                    populate_page_inspection(page, html=fetch_resp.text, base_url=page.url)

                    # Check if rendering is required
                    if self.config.enable_rendering:
                        needs_render, reason = is_rendering_needed(
                            html=fetch_resp.text,
                            extracted=static_extracted,
                            base_url=page.url,
                        )
                        if needs_render:
                            render_and_inspect_page(
                                url=page.url,
                                static_html=fetch_resp.text,
                                page_inspection=page,
                                config=self.config.render_config,
                                force_render=True,
                                playwright_instance=self.playwright_instance,
                            )

                    # Discover and enqueue outgoing links
                    if depth < self.config.max_depth:
                        for link in page.links:
                            link_url = link.url
                            is_internal = is_same_site(normalized_root, link_url)

                            if self.config.same_site_only and not is_internal:
                                continue

                            if (
                                link_url not in visited_urls
                                and link_url not in enqueued_urls
                                and len(visited_urls) + len(queue) < self.config.max_pages * 2
                            ):
                                enqueued_urls.add(link_url)
                                queue.append((link_url, depth + 1))

            inspected_pages.append(page)

        total_elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 5. Build SiteInspection
        site_inspection = SiteInspection(
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

        # 6. Run Member 1 Technical Discoverability Audit
        audit_technical_discoverability(site_inspection)

        return site_inspection


def inspect_site(
    url: str,
    max_pages: int = 10,
    max_depth: int = 2,
    timeout: float = DEFAULT_PIPELINE_TIMEOUT,
    same_site_only: bool = True,
    respect_robots: bool = True,
    discover_sitemaps: bool = True,
    enable_rendering: bool = True,
    user_agent: str = DEFAULT_PIPELINE_USER_AGENT,
    render_config: Optional[RenderConfig] = None,
    client: Optional[Any] = None,
    playwright_instance: Optional[Any] = None,
) -> SiteInspection:
    """Convenience function to run Member 1 site inspection pipeline."""
    config = PipelineConfig(
        max_pages=max_pages,
        max_depth=max_depth,
        timeout=timeout,
        same_site_only=same_site_only,
        respect_robots=respect_robots,
        discover_sitemaps=discover_sitemaps,
        enable_rendering=enable_rendering,
        user_agent=user_agent,
        render_config=render_config,
    )
    pipeline = InspectionPipeline(
        config=config,
        client=client,
        playwright_instance=playwright_instance,
    )
    return pipeline.run(url)
