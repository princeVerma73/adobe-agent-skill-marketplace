"""Freshness & Corroboration Audit.

Assesses temporal currency, outdated announcements presented as active,
stale product information, and expired copyright declarations.
"""

from __future__ import annotations

import datetime
import re
from typing import List, Optional, Set
from ..contracts.schemas import (
    CategoryType,
    Finding,
    FindingAction,
    SeverityLevel,
    SiteSnapshot,
)
from ..core.html_parser import ParsedPageContent


CURRENT_YEAR = 2026

# Pattern for dates in announcements/press releases/blogs: "March 15, 2020" or "2020-05-12" or "Published: 2021"
DATE_PATTERN = re.compile(
    r"\b(?:published|updated|posted|date|released)?\s*:?\s*(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+)?\b(201\d|202[0-6])\b",
    re.I,
)


def audit_freshness(
    snapshot: SiteSnapshot,
    parsed_pages: List[ParsedPageContent],
    current_year: int = CURRENT_YEAR,
) -> List[Finding]:
    findings: List[Finding] = []

    # 1. Check Copyright freshness
    all_copyright_years: Set[int] = set()
    copyright_page_map = {}

    for page in parsed_pages:
        for stmt in page.copyright_statements:
            match = re.search(r"(?:19|20)(\d{2})\b", stmt)
            # Find all 4-digit years in copyright statement
            years = [int(y) for y in re.findall(r"\b(19\d\d|20\d\d)\b", stmt)]
            for y in years:
                all_copyright_years.add(y)
                copyright_page_map[y] = page.url

    if all_copyright_years:
        max_copy_year = max(all_copyright_years)
        lag = current_year - max_copy_year
        if lag >= 2:
            severity = SeverityLevel.HIGH if lag >= 4 else SeverityLevel.MEDIUM
            findings.append(
                Finding(
                    id="FR-001",
                    category=CategoryType.FRESHNESS,
                    title=f"Outdated copyright notice indicating unmaintained site (Lag: {lag} years)",
                    severity=severity,
                    confidence=0.91,
                    evidence=(
                        f"The latest copyright year discovered on the site is {max_copy_year} "
                        f"(source: '{copyright_page_map.get(max_copy_year, snapshot.homepage.url)}'), "
                        f"which is {lag} years behind the current reference year ({current_year}). "
                        f"This signals to AI retrieval systems that site governance and information may be dormant."
                    ),
                    affected_urls=[copyright_page_map.get(max_copy_year, snapshot.homepage.url)],
                    suggested_action=FindingAction(
                        summary=f"Update footer copyright declarations to include {current_year} and verify site-wide temporal signals.",
                        priority=severity,
                    ),
                )
            )

    # 2. Check Stale Announcements / News / Products
    # Look for dated news or product pages
    page_latest_dates = {}
    for page in parsed_pages:
        years_on_page: List[int] = []

        # From meta dates (e.g. article:published_time)
        for meta_name, meta_val in page.meta_dates.items():
            year_match = re.search(r"\b(201\d|202[0-6])\b", meta_val)
            if year_match:
                years_on_page.append(int(year_match.group(1)))

        # From clean text headings / dates
        for h in page.h1s + page.h2s:
            for y_str in re.findall(r"\b(201\d|202[0-6])\b", h):
                years_on_page.append(int(y_str))

        if years_on_page:
            page_latest_dates[page.url] = max(years_on_page)

    # If the site has news, blog, or press pages where the latest year is stale
    for url, latest_year in page_latest_dates.items():
        url_lower = url.lower()
        is_news_or_updates = any(k in url_lower for k in ("news", "blog", "press", "events", "announcements", "updates"))
        if is_news_or_updates:
            diff = current_year - latest_year
            if diff >= 3:
                findings.append(
                    Finding(
                        id="FR-002",
                        category=CategoryType.FRESHNESS,
                        title=f"Stale announcements/news section inactive for {diff} years",
                        severity=SeverityLevel.MEDIUM,
                        confidence=0.85,
                        evidence=(
                            f"The news or announcement feed at '{url}' has its most recent entry dated in {latest_year}, "
                            f"over {diff} years ago, while presenting the feed as the current company timeline."
                        ),
                        affected_urls=[url],
                        suggested_action=FindingAction(
                            summary="Archive legacy press/blog releases or publish updated organizational announcements.",
                            priority=SeverityLevel.MEDIUM,
                        ),
                    )
                )

    return findings
