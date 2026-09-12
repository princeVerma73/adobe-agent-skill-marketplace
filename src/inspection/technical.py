"""Technical discoverability and SEO audit rules for website inspection.

Evaluates deterministic, evidence-based checks on HTTP status, robots.txt,
sitemaps, metadata, heading hierarchy, body content, redirect chains, canonicals,
and static-vs-rendered JavaScript discrepancies.
Populates structured TechnicalIssue observations.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from src.inspection.models import (
    Heading,
    PageInspection,
    SiteInspection,
    TechnicalIssue,
)
from src.inspection.url import (
    extract_hostname,
    is_same_domain,
    is_valid_url,
    normalize_url,
)

# Thresholds for deterministic checks
MIN_TITLE_LENGTH = 5
MIN_BODY_TEXT_CHARS = 50
MIN_BODY_TEXT_WORDS = 10
MAX_REDIRECT_HOPS = 2
CONTENT_GAP_RATIO_THRESHOLD = 2.0
CONTENT_GAP_CHAR_THRESHOLD = 150


def check_http_status(page: PageInspection) -> List[TechnicalIssue]:
    """Check HTTP accessibility, 4xx/5xx status codes, and unreachable pages."""
    issues: List[TechnicalIssue] = []

    if page.status_code is None:
        if page.allowed_by_robots:
            issues.append(
                TechnicalIssue(
                    code="HTTP_UNREACHABLE",
                    message="Page did not return a valid HTTP status code or connection failed.",
                    severity="error",
                    details={"url": page.url, "original_url": page.original_url},
                )
            )
    elif page.status_code >= 500:
        issues.append(
            TechnicalIssue(
                code="HTTP_SERVER_ERROR",
                message=f"Server returned HTTP {page.status_code} error.",
                severity="error",
                details={"status_code": page.status_code, "url": page.url},
            )
        )
    elif page.status_code == 404:
        issues.append(
            TechnicalIssue(
                code="HTTP_NOT_FOUND",
                message="Page returned HTTP 404 Not Found.",
                severity="error",
                details={"status_code": 404, "url": page.url},
            )
        )
    elif page.status_code >= 400:
        issues.append(
            TechnicalIssue(
                code="HTTP_CLIENT_ERROR",
                message=f"Client request error with HTTP {page.status_code}.",
                severity="warning",
                details={"status_code": page.status_code, "url": page.url},
            )
        )

    return issues


def check_robots_blocking(page: PageInspection) -> List[TechnicalIssue]:
    """Check if page is disallowed by robots.txt or has noindex directives."""
    issues: List[TechnicalIssue] = []

    if not page.allowed_by_robots:
        issues.append(
            TechnicalIssue(
                code="ROBOTS_TXT_DISALLOWED",
                message="Page is disallowed from crawling by robots.txt directives.",
                severity="warning",
                details={"url": page.url, "allowed_by_robots": False},
            )
        )

    robots_meta = (page.metadata.robots_meta or "").lower()
    if "noindex" in robots_meta or "none" in robots_meta:
        issues.append(
            TechnicalIssue(
                code="ROBOTS_META_NOINDEX",
                message=f"Page specifies '{page.metadata.robots_meta}' directive blocking search indexing.",
                severity="warning",
                details={"url": page.url, "robots_meta": page.metadata.robots_meta},
            )
        )

    return issues


def check_title(page: PageInspection) -> List[TechnicalIssue]:
    """Check title tag presence, whitespace, and minimum length."""
    issues: List[TechnicalIssue] = []
    title = (page.title or "").strip()

    if not title:
        issues.append(
            TechnicalIssue(
                code="MISSING_TITLE",
                message="Page is missing a title tag or has empty title content.",
                severity="error",
                details={"url": page.url, "title": page.title},
            )
        )
    elif len(title) < MIN_TITLE_LENGTH:
        issues.append(
            TechnicalIssue(
                code="SHORT_TITLE",
                message=f"Page title is very short ({len(title)} characters: '{title}').",
                severity="warning",
                details={"url": page.url, "title": title, "length": len(title)},
            )
        )

    return issues


def check_meta_description(page: PageInspection) -> List[TechnicalIssue]:
    """Check meta description presence and content."""
    issues: List[TechnicalIssue] = []
    desc = (page.metadata.description or "").strip()

    if not desc:
        issues.append(
            TechnicalIssue(
                code="MISSING_META_DESCRIPTION",
                message="Page is missing a meta description tag.",
                severity="warning",
                details={"url": page.url, "description": page.metadata.description},
            )
        )

    return issues


def check_headings_h1(page: PageInspection) -> List[TechnicalIssue]:
    """Check H1 presence, missing H1, or multiple H1 elements."""
    issues: List[TechnicalIssue] = []
    h1_headings = [h for h in page.headings if h.level == 1]

    if not h1_headings:
        issues.append(
            TechnicalIssue(
                code="MISSING_H1",
                message="Page lacks an H1 main heading tag.",
                severity="warning",
                details={"url": page.url, "total_headings": len(page.headings)},
            )
        )
    elif len(h1_headings) > 1:
        issues.append(
            TechnicalIssue(
                code="MULTIPLE_H1",
                message=f"Page defines multiple ({len(h1_headings)}) H1 headings.",
                severity="info",
                details={
                    "url": page.url,
                    "h1_count": len(h1_headings),
                    "h1_texts": [h.text for h in h1_headings],
                },
            )
        )

    return issues


def check_canonical(page: PageInspection) -> List[TechnicalIssue]:
    """Check canonical URL presence, validity, and domain matching."""
    issues: List[TechnicalIssue] = []
    canonical = (page.metadata.canonical_url or "").strip()

    if not canonical:
        issues.append(
            TechnicalIssue(
                code="MISSING_CANONICAL",
                message="Page does not declare a canonical URL tag.",
                severity="info",
                details={"url": page.url},
            )
        )
        return issues

    if not is_valid_url(canonical):
        issues.append(
            TechnicalIssue(
                code="CANONICAL_URL_INVALID",
                message=f"Canonical URL '{canonical}' is malformed or invalid.",
                severity="warning",
                details={"url": page.url, "canonical_url": canonical},
            )
        )
        return issues

    try:
        norm_canonical = normalize_url(canonical)
        # Check domain mismatch
        if not is_same_domain(page.url, norm_canonical):
            issues.append(
                TechnicalIssue(
                    code="CANONICAL_DOMAIN_MISMATCH",
                    message=f"Canonical tag points to external domain '{extract_hostname(norm_canonical)}'.",
                    severity="warning",
                    details={
                        "url": page.url,
                        "canonical_url": norm_canonical,
                        "page_host": extract_hostname(page.url),
                        "canonical_host": extract_hostname(norm_canonical),
                    },
                )
            )

        # Check protocol mismatch (e.g. page is https, canonical is http)
        if page.url.startswith("https://") and norm_canonical.startswith("http://"):
            issues.append(
                TechnicalIssue(
                    code="CANONICAL_PROTOCOL_MISMATCH",
                    message="HTTPS page specifies an insecure HTTP canonical URL.",
                    severity="warning",
                    details={"url": page.url, "canonical_url": norm_canonical},
                )
            )
    except Exception as exc:
        issues.append(
            TechnicalIssue(
                code="CANONICAL_URL_INVALID",
                message=f"Could not normalize canonical URL: {exc}",
                severity="warning",
                details={"url": page.url, "canonical_url": canonical},
            )
        )

    return issues


def check_body_text_content(page: PageInspection) -> List[TechnicalIssue]:
    """Check for empty or very low meaningful visible body text."""
    issues: List[TechnicalIssue] = []
    text = (page.body_text or "").strip()
    char_count = len(text)
    words = text.split()
    word_count = len(words)

    if char_count == 0:
        issues.append(
            TechnicalIssue(
                code="EMPTY_BODY_TEXT",
                message="Page has empty visible body text.",
                severity="error",
                details={"url": page.url, "char_count": 0, "word_count": 0},
            )
        )
    elif char_count < MIN_BODY_TEXT_CHARS or word_count < MIN_BODY_TEXT_WORDS:
        issues.append(
            TechnicalIssue(
                code="LOW_BODY_TEXT",
                message=f"Page has very sparse visible content ({char_count} chars, {word_count} words).",
                severity="warning",
                details={"url": page.url, "char_count": char_count, "word_count": word_count},
            )
        )

    return issues


def check_redirect_chain(page: PageInspection) -> List[TechnicalIssue]:
    """Check redirect hops and loop occurrences."""
    issues: List[TechnicalIssue] = []
    chain = page.redirect_chain or []

    if len(chain) > 1:
        hop_count = len(chain) - 1
        if hop_count > MAX_REDIRECT_HOPS:
            issues.append(
                TechnicalIssue(
                    code="EXCESSIVE_REDIRECT_CHAIN",
                    message=f"Page underwent {hop_count} redirect hops (threshold: {MAX_REDIRECT_HOPS}).",
                    severity="warning",
                    details={"url": page.url, "hops": hop_count, "redirect_chain": chain},
                )
            )

        # Detect loop
        if len(chain) != len(set(chain)):
            issues.append(
                TechnicalIssue(
                    code="REDIRECT_LOOP",
                    message="Redirect loop observed in URL resolution chain.",
                    severity="error",
                    details={"url": page.url, "redirect_chain": chain},
                )
            )

    return issues


def check_static_rendered_gap(page: PageInspection) -> List[TechnicalIssue]:
    """Check whether significant content or headings only exist post-rendering (JS dependency)."""
    issues: List[TechnicalIssue] = []

    if not page.is_rendered or page.rendered_text is None or page.source_text is None:
        return issues

    source_text = page.source_text.strip()
    rendered_text = page.rendered_text.strip()

    source_len = len(source_text)
    rendered_len = len(rendered_text)
    char_diff = rendered_len - source_len

    # If rendered text is substantially larger than static text
    if rendered_len > source_len and char_diff >= CONTENT_GAP_CHAR_THRESHOLD:
        ratio = rendered_len / max(source_len, 1)
        if ratio >= CONTENT_GAP_RATIO_THRESHOLD or source_len < MIN_BODY_TEXT_CHARS:
            issues.append(
                TechnicalIssue(
                    code="STATIC_RENDERED_CONTENT_GAP",
                    message=f"Substantial content discrepancy between static source ({source_len} chars) and rendered DOM ({rendered_len} chars).",
                    severity="warning",
                    details={
                        "url": page.url,
                        "source_chars": source_len,
                        "rendered_chars": rendered_len,
                        "char_difference": char_diff,
                        "expansion_ratio": round(ratio, 2),
                    },
                )
            )

    return issues


def check_sitemap_and_robots_discoverability(
    site: SiteInspection,
    page_urls: Optional[Set[str]] = None,
) -> List[TechnicalIssue]:
    """Site-level discoverability checks for robots.txt and sitemaps."""
    issues: List[TechnicalIssue] = []

    # 1. Robots.txt discoverability
    if site.robots.checked:
        if not site.robots.found:
            issues.append(
                TechnicalIssue(
                    code="ROBOTS_TXT_NOT_FOUND",
                    message=f"robots.txt not found on site '{site.site}' (HTTP {site.robots.status_code}).",
                    severity="info",
                    details={"site": site.site, "status_code": site.robots.status_code},
                )
            )
        elif site.robots.error:
            issues.append(
                TechnicalIssue(
                    code="ROBOTS_TXT_FETCH_ERROR",
                    message=f"robots.txt fetch error: {site.robots.error}",
                    severity="warning",
                    details={"site": site.site, "error": site.robots.error},
                )
            )

        if site.robots.crawl_delay is not None and site.robots.crawl_delay > 10.0:
            issues.append(
                TechnicalIssue(
                    code="HIGH_CRAWL_DELAY",
                    message=f"robots.txt specifies an unusually high crawl delay of {site.robots.crawl_delay}s.",
                    severity="warning",
                    details={"site": site.site, "crawl_delay": site.robots.crawl_delay},
                )
            )

    # 2. Sitemap discoverability
    if site.sitemap.checked:
        if not site.sitemap.found or site.sitemap.total_discovered_urls == 0:
            issues.append(
                TechnicalIssue(
                    code="SITEMAP_NOT_FOUND",
                    message=f"No accessible XML sitemaps discovered for '{site.site}'.",
                    severity="info",
                    details={"site": site.site, "discovered_count": site.sitemap.total_discovered_urls},
                )
            )
        elif site.sitemap.error:
            issues.append(
                TechnicalIssue(
                    code="SITEMAP_FETCH_ERROR",
                    message=f"Sitemap parsing error: {site.sitemap.error}",
                    severity="warning",
                    details={"site": site.site, "error": site.sitemap.error},
                )
            )

    return issues


def inspect_page_technical(
    page: PageInspection,
    site_inspection: Optional[SiteInspection] = None,
) -> List[TechnicalIssue]:
    """Run all page-level technical discoverability and SEO checks on a PageInspection."""
    issues: List[TechnicalIssue] = []

    issues.extend(check_http_status(page))
    issues.extend(check_robots_blocking(page))
    issues.extend(check_title(page))
    issues.extend(check_meta_description(page))
    issues.extend(check_headings_h1(page))
    issues.extend(check_canonical(page))
    issues.extend(check_body_text_content(page))
    issues.extend(check_redirect_chain(page))
    issues.extend(check_static_rendered_gap(page))

    # Optional sitemap inclusion check if complete sitemap was discovered
    if (
        site_inspection is not None
        and site_inspection.sitemap.found
        and site_inspection.sitemap.sample_urls
        and site_inspection.sitemap.total_discovered_urls <= len(site_inspection.sitemap.sample_urls)
    ):
        sitemap_set = {u.rstrip("/") for u in site_inspection.sitemap.sample_urls}
        page_norm = page.url.rstrip("/")
        if page_norm not in sitemap_set:
            issues.append(
                TechnicalIssue(
                    code="PAGE_NOT_IN_SITEMAP",
                    message="Page URL was not found in discovered XML sitemap URLs.",
                    severity="info",
                    details={"url": page.url, "sitemap_total_urls": len(sitemap_set)},
                )
            )

    return issues


def audit_technical_discoverability(site: SiteInspection) -> SiteInspection:
    """Run full technical discoverability audit on SiteInspection and all its inspected pages.
    
    Attaches structured TechnicalIssue findings to each PageInspection without overwriting
    existing crawl/fetch issues, and returns the enriched SiteInspection.
    """
    site_issues = check_sitemap_and_robots_discoverability(site)

    for page in site.pages:
        page_issues = inspect_page_technical(page, site_inspection=site)
        # Append without duplicating codes
        existing_codes = {issue.code for issue in page.technical_issues}
        for new_issue in page_issues:
            if new_issue.code not in existing_codes:
                page.technical_issues.append(new_issue)
                existing_codes.add(new_issue.code)

    # Record site-level issues in summary counts
    site.summary_counts["site_level_technical_issues"] = len(site_issues)
    total_page_issues = sum(len(p.technical_issues) for p in site.pages)
    site.summary_counts["total_technical_issues"] = total_page_issues + len(site_issues)

    return site
