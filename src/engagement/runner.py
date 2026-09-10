"""Master runner and entrypoint for Member 3 Engagement Audit.

Exposes `audit_engagement` which evaluates website inspection observations
for visitor orientation, navigation scannability, CTA paths, and continuation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from bs4 import BeautifulSoup

from src.entity_trust.contracts.schemas import (
    FindingAction,
    SeverityCounts,
    SeverityLevel,
    SiteSnapshot,
)
from src.engagement.models import (
    EngagementAuditResult,
    EngagementFinding,
    EngagementMetrics,
)
from src.engagement.rules import (
    check_contact_path,
    check_context_retention,
    check_conversion_path,
    check_cta_clarity,
    check_dead_ends,
    check_homepage_orientation,
    check_information_hierarchy,
    check_internal_linking,
    check_navigation,
    check_related_content_continuation,
)

SEVERITY_ORDER = {
    SeverityLevel.CRITICAL: 5,
    SeverityLevel.HIGH: 4,
    SeverityLevel.MEDIUM: 3,
    SeverityLevel.LOW: 2,
    SeverityLevel.INFO: 1,
}


def _extract_page_dict(p: Any, site_domain: str) -> Dict[str, Any]:
    """Normalizes various page representations (PageInspection, PageSnapshot, dict) into a uniform dict."""
    if isinstance(p, dict):
        url = p.get("url", "")
        title = p.get("title") or ""
        body_text = (
            p.get("body_text")
            or p.get("rendered_text")
            or p.get("source_text")
            or p.get("text")
            or ""
        )
        html = p.get("html") or ""
        status_code = p.get("status_code", 200)
        crawl_depth = p.get("crawl_depth", 0)

        # Headings
        raw_headings = p.get("headings", [])
        headings: List[Dict[str, Any]] = []
        for h in raw_headings:
            if isinstance(h, dict):
                headings.append({"level": h.get("level", 1), "text": h.get("text", "")})
            else:
                headings.append({
                    "level": getattr(h, "level", 1),
                    "text": getattr(h, "text", ""),
                })

        # Links
        raw_links = p.get("links", [])
        links: List[Dict[str, Any]] = []
        for l in raw_links:
            if isinstance(l, dict):
                links.append({
                    "url": l.get("url", ""),
                    "text": l.get("text", ""),
                    "is_internal": l.get("is_internal", True),
                })
            elif isinstance(l, str):
                is_internal = site_domain.lower() in l.lower() or l.startswith(("/", "#"))
                links.append({"url": l, "text": "", "is_internal": is_internal})
            else:
                links.append({
                    "url": getattr(l, "url", ""),
                    "text": getattr(l, "text", ""),
                    "is_internal": getattr(l, "is_internal", True),
                })

        meta_dict = p.get("metadata") or {}
        if hasattr(meta_dict, "model_dump"):
            meta_dict = meta_dict.model_dump()
        meta_desc = meta_dict.get("description") or ""

    else:
        # Pydantic model (PageInspection or PageSnapshot)
        url = getattr(p, "url", "")
        title = getattr(p, "title", "") or ""
        body_text = (
            getattr(p, "body_text", None)
            or getattr(p, "rendered_text", None)
            or getattr(p, "source_text", None)
            or getattr(p, "text", "")
            or ""
        )
        html = getattr(p, "html", "") or getattr(p, "source_text", "") or ""
        status_code = getattr(p, "status_code", 200)
        crawl_depth = getattr(p, "crawl_depth", 0)

        raw_headings = getattr(p, "headings", [])
        headings = []
        for h in raw_headings:
            headings.append({
                "level": getattr(h, "level", 1),
                "text": getattr(h, "text", ""),
            })

        raw_links = getattr(p, "links", [])
        links = []
        for l in raw_links:
            if isinstance(l, str):
                is_internal = site_domain.lower() in l.lower() or l.startswith(("/", "#"))
                links.append({"url": l, "text": "", "is_internal": is_internal})
            else:
                links.append({
                    "url": getattr(l, "url", ""),
                    "text": getattr(l, "text", ""),
                    "is_internal": getattr(l, "is_internal", True),
                })

        meta_obj = getattr(p, "metadata", None)
        meta_dict = (
            meta_obj.model_dump()
            if hasattr(meta_obj, "model_dump")
            else (meta_obj if isinstance(meta_obj, dict) else {})
        )
        meta_desc = meta_dict.get("description") or ""

    # Fallback HTML extraction if headings or links were empty but html is available
    if html and not headings:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for h_tag in soup.find_all(re.compile(r"^h[1-6]$")):
                lvl = int(h_tag.name[1])
                headings.append({"level": lvl, "text": h_tag.get_text(strip=True)})
        except Exception:
            pass

    if html and not links:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                anchor_text = a_tag.get_text(strip=True)
                is_internal = site_domain.lower() in href.lower() or href.startswith(("/", "#"))
                links.append({"url": href, "text": anchor_text, "is_internal": is_internal})
        except Exception:
            pass

    return {
        "url": url,
        "title": title,
        "body_text": body_text,
        "html": html,
        "status_code": status_code,
        "crawl_depth": crawl_depth,
        "headings": headings,
        "links": links,
        "meta_description": meta_desc,
    }


def audit_engagement(
    snapshot: Union[SiteSnapshot, Dict[str, Any], Any],
    confidence_threshold: float = 0.70,
) -> EngagementAuditResult:
    """Audits website inspection data for visitor engagement, orientation, and pathway quality.

    Parameters:
        snapshot: A Member 1 SiteInspection model, a SiteSnapshot, or a conforming dict.
        confidence_threshold: Minimum confidence score (0.0 to 1.0) to report a finding.

    Returns:
        EngagementAuditResult containing standardized findings and engagement metrics.
    """
    # 1. Resolve site domain and root URL
    if isinstance(snapshot, dict):
        site_domain = snapshot.get("site", "unknown")
        root_url = snapshot.get("root_url") or (
            snapshot.get("homepage", {}).get("url") if isinstance(snapshot.get("homepage"), dict) else ""
        ) or f"https://{site_domain}/"
        raw_pages = snapshot.get("pages", [])
        if "homepage" in snapshot and isinstance(snapshot["homepage"], dict):
            raw_pages = [snapshot["homepage"]] + [p for p in raw_pages if p.get("url") != snapshot["homepage"].get("url")]
    else:
        site_domain = getattr(snapshot, "site", "unknown")
        root_url = getattr(snapshot, "root_url", "")
        if hasattr(snapshot, "all_pages"):
            raw_pages = snapshot.all_pages()
        else:
            raw_pages = getattr(snapshot, "pages", [])
        if not root_url and hasattr(snapshot, "homepage"):
            root_url = getattr(snapshot.homepage, "url", f"https://{site_domain}/")
        elif not root_url:
            root_url = f"https://{site_domain}/"

    # 2. Normalize pages into standard dictionaries
    pages_data: List[Dict[str, Any]] = [
        _extract_page_dict(p, site_domain) for p in raw_pages
    ]

    if not pages_data and root_url:
        pages_data.append({
            "url": root_url,
            "title": "",
            "body_text": "",
            "html": "",
            "status_code": 200,
            "crawl_depth": 0,
            "headings": [],
            "links": [],
            "meta_description": "",
        })

    # Identify homepage page data
    homepage_data = None
    for p in pages_data:
        u = p.get("url", "").rstrip("/")
        if u == root_url.rstrip("/"):
            homepage_data = p
            break
    if not homepage_data and pages_data:
        homepage_data = pages_data[0]

    all_findings: List[EngagementFinding] = []

    # 3. Rule 1: Homepage Orientation
    if homepage_data:
        hp_h1s = [
            h.get("text", "")
            for h in homepage_data.get("headings", [])
            if h.get("level") == 1
        ]
        all_findings.extend(
            check_homepage_orientation(
                homepage_url=homepage_data.get("url", root_url),
                title=homepage_data.get("title"),
                h1s=hp_h1s,
                body_text=homepage_data.get("body_text"),
                meta_description=homepage_data.get("meta_description"),
            )
        )

    # 4. Rule 2: Navigation Analysis
    all_findings.extend(
        check_navigation(homepage_url=root_url, pages_data=pages_data)
    )

    # 5. Rule 3: Information Hierarchy
    all_findings.extend(
        check_information_hierarchy(pages_data=pages_data)
    )

    # 6. Rule 4: CTA Clarity
    all_findings.extend(
        check_cta_clarity(homepage_url=root_url, pages_data=pages_data)
    )

    # 7. Rule 5: Internal Linking
    all_findings.extend(
        check_internal_linking(homepage_url=root_url, pages_data=pages_data)
    )

    # 8. Rule 6: Related Content & Continuation
    all_findings.extend(
        check_related_content_continuation(homepage_url=root_url, pages_data=pages_data)
    )

    # 9. Rule 7: Contact Path
    all_findings.extend(
        check_contact_path(
            site_domain=site_domain,
            homepage_url=root_url,
            pages_data=pages_data,
        )
    )

    # 10. Rule 8: Conversion Path
    all_findings.extend(
        check_conversion_path(pages_data=pages_data)
    )

    # 11. Rule 9: Dead Ends
    all_findings.extend(
        check_dead_ends(homepage_url=root_url, pages_data=pages_data)
    )

    # 12. Rule 10: Context Retention
    all_findings.extend(
        check_context_retention(
            site_domain=site_domain,
            homepage_url=root_url,
            pages_data=pages_data,
        )
    )

    # 13. Filter by confidence and deduplicate
    seen_keys: Set[Tuple[str, str, Tuple[str, ...]]] = set()
    deduped_findings: List[EngagementFinding] = []

    for f in all_findings:
        if f.confidence < confidence_threshold:
            continue
        key = (f.id, f.category, tuple(sorted(f.affected_urls)))
        if key not in seen_keys:
            seen_keys.add(key)
            deduped_findings.append(f)

    # Rank by severity (highest first), then by confidence
    sorted_findings = sorted(
        deduped_findings,
        key=lambda item: (SEVERITY_ORDER.get(item.severity, 0), item.confidence),
        reverse=True,
    )

    # Calculate severity counts
    severity_counts = SeverityCounts()
    for f in sorted_findings:
        if f.severity == SeverityLevel.CRITICAL:
            severity_counts.critical += 1
        elif f.severity == SeverityLevel.HIGH:
            severity_counts.high += 1
        elif f.severity == SeverityLevel.MEDIUM:
            severity_counts.medium += 1
        elif f.severity == SeverityLevel.LOW:
            severity_counts.low += 1
        elif f.severity == SeverityLevel.INFO:
            severity_counts.info += 1

    # Compute metrics
    total_internal_links = sum(
        len([l for l in p.get("links", []) if l.get("is_internal", True)])
        for p in pages_data
    )
    total_external_links = sum(
        len([l for l in p.get("links", []) if not l.get("is_internal", True)])
        for p in pages_data
    )
    total_headings = sum(len(p.get("headings", [])) for p in pages_data)
    avg_headings = (total_headings / len(pages_data)) if pages_data else 0.0

    dead_end_findings = [f for f in sorted_findings if f.id == "ENG-014"]
    orphan_findings = [f for f in sorted_findings if f.id == "ENG-009"]
    missing_cta_findings = [f for f in sorted_findings if f.id == "ENG-008"]
    missing_contact_findings = [f for f in sorted_findings if f.id == "ENG-012"]

    metrics = EngagementMetrics(
        pages_audited=len(pages_data),
        internal_link_count=total_internal_links,
        external_link_count=total_external_links,
        orphan_page_count=len(orphan_findings),
        dead_end_count=len(dead_end_findings),
        has_homepage_cta=(len(missing_cta_findings) == 0),
        has_contact_channel=(len(missing_contact_findings) == 0),
        avg_headings_per_page=round(avg_headings, 1),
    )

    return EngagementAuditResult(
        skill="engagement-recommendations",
        status="success",
        site=site_domain,
        total_findings=len(sorted_findings),
        severity_counts=severity_counts,
        findings=sorted_findings,
        metrics=metrics,
        metadata={
            "pages_analyzed": len(pages_data),
            "confidence_threshold_applied": confidence_threshold,
            "root_url": root_url,
        },
    )
