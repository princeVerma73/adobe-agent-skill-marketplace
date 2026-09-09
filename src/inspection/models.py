"""Shared Pydantic data models for the inspection layer.

Represents raw inspection observations, evidence, and structured page/site data.
These models represent neutral observations/evidence, not final audit conclusions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class Heading(BaseModel):
    """HTML heading element observation."""
    model_config = ConfigDict(extra="ignore")

    level: int = Field(..., ge=1, le=6, description="Heading level (1 to 6)")
    text: str = Field(..., description="Cleaned heading text")


class Link(BaseModel):
    """Hyperlink observation discovered on an inspected page."""
    model_config = ConfigDict(extra="ignore")

    url: str = Field(..., description="Target URL of the link")
    text: str = Field(default="", description="Anchor text")
    is_internal: bool = Field(default=True, description="Whether link points to same site")
    rel: Optional[str] = Field(default=None, description="rel attribute value if present")


class PageMetadata(BaseModel):
    """Metadata tags extracted from HTML head and OpenGraph / Twitter cards."""
    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = Field(default=None, description="Title tag content")
    description: Optional[str] = Field(default=None, description="Meta description content")
    canonical_url: Optional[str] = Field(default=None, description="Canonical link URL")
    robots_meta: Optional[str] = Field(default=None, description="robots meta directive")
    open_graph: Dict[str, str] = Field(default_factory=dict, description="OpenGraph properties")
    twitter_card: Dict[str, str] = Field(default_factory=dict, description="Twitter card properties")
    extra: Dict[str, str] = Field(default_factory=dict, description="Additional meta name/content pairs")


class TechnicalIssue(BaseModel):
    """Technical observation or evidence item (e.g. crawl, rendering, status issue)."""
    model_config = ConfigDict(extra="ignore")

    code: str = Field(..., description="Machine-readable code, e.g. MISSING_TITLE, SLOW_RESPONSE")
    message: str = Field(..., description="Human-readable description of observation")
    severity: str = Field(default="warning", description="Severity level: info, warning, error")
    details: Dict[str, Any] = Field(default_factory=dict, description="Supporting context and key-values")


class RobotsTxtInspection(BaseModel):
    """Inspection observation for robots.txt."""
    model_config = ConfigDict(extra="ignore")

    checked: bool = Field(default=False, description="Whether robots.txt check was performed")
    found: bool = Field(default=False, description="Whether robots.txt exists and returned 200")
    status_code: Optional[int] = Field(default=None, description="HTTP status code of robots.txt request")
    allowed_for_agent: Optional[bool] = Field(
        default=True,
        description="Whether target paths are allowed for default/specified agent (None if retrieval failed/indeterminate)",
    )
    sitemap_urls: List[str] = Field(default_factory=list, description="Sitemaps declared in robots.txt")
    crawl_delay: Optional[float] = Field(default=None, description="Crawl delay specified in seconds")
    raw_text: Optional[str] = Field(default=None, description="Raw content of robots.txt")
    error: Optional[str] = Field(default=None, description="Error message if robots.txt retrieval failed")


class SitemapInspection(BaseModel):
    """Inspection observation for sitemap discovery and parsing."""
    model_config = ConfigDict(extra="ignore")

    checked: bool = Field(default=False, description="Whether sitemap discovery was attempted")
    found: bool = Field(default=False, description="Whether sitemap was successfully located")
    status_code: Optional[int] = Field(default=None, description="HTTP status code of sitemap request")
    discovered_sitemap_urls: List[str] = Field(default_factory=list, description="Discovered sitemap location URLs")
    total_discovered_urls: int = Field(default=0, description="Total number of page URLs found across sitemaps")
    sample_urls: List[str] = Field(default_factory=list, description="Sample of discovered URLs")
    raw_content: Optional[str] = Field(default=None, description="Raw sitemap XML/text snippet")


class PageInspection(BaseModel):
    """Detailed observation of a single inspected page."""
    model_config = ConfigDict(extra="ignore")

    url: str = Field(..., description="Final canonical URL after redirects")
    original_url: str = Field(..., description="Initial target URL before fetch/redirects")
    status_code: Optional[int] = Field(default=None, description="HTTP response status code")
    content_type: Optional[str] = Field(default=None, description="Content-Type response header")
    response_time_ms: Optional[float] = Field(default=None, description="Fetch response time in milliseconds")
    redirect_chain: List[str] = Field(default_factory=list, description="Sequence of URLs in redirect chain")
    crawl_depth: int = Field(default=0, description="Depth level from root page during crawl")
    allowed_by_robots: bool = Field(default=True, description="Whether page is permitted by robots.txt rules")
    is_rendered: bool = Field(default=False, description="Whether page underwent JavaScript rendering")
    raw_html_available: bool = Field(default=False, description="Whether raw source HTML was captured")
    rendered_text: Optional[str] = Field(default=None, description="Visible text extracted from rendered DOM")
    source_text: Optional[str] = Field(default=None, description="Text extracted from static source HTML")
    title: Optional[str] = Field(default=None, description="Page title")
    metadata: PageMetadata = Field(default_factory=PageMetadata, description="Extracted metadata tags")
    headings: List[Heading] = Field(default_factory=list, description="Extracted headings in order")
    body_text: Optional[str] = Field(default=None, description="Primary body text content")
    links: List[Link] = Field(default_factory=list, description="Extracted page links")
    structured_data: List[Dict[str, Any]] = Field(default_factory=list, description="Parsed JSON-LD or schema objects")
    technical_issues: List[TechnicalIssue] = Field(default_factory=list, description="Technical observations and issues")


class SiteInspection(BaseModel):
    """Aggregated inspection observation for an entire target site."""
    model_config = ConfigDict(extra="ignore")

    site: str = Field(..., description="Hostname or identifier of the inspected site")
    root_url: str = Field(..., description="Normalized starting root URL")
    audited_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when inspection completed",
    )
    total_duration_ms: Optional[float] = Field(default=None, description="Total inspection duration in ms")
    robots: RobotsTxtInspection = Field(default_factory=RobotsTxtInspection, description="Robots.txt inspection observation")
    sitemap: SitemapInspection = Field(default_factory=SitemapInspection, description="Sitemap inspection observation")
    pages: List[PageInspection] = Field(default_factory=list, description="Collection of inspected pages")
    summary_counts: Dict[str, int] = Field(default_factory=dict, description="Summary counters for pages/issues")
