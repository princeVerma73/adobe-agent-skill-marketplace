"""Navigation audit rule (Area 2).

Evaluates whether key pages are reachable, whether navigation paths are
understandable, and identifies vague anchor texts or navigation deadlocks.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set

from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
from src.engagement.models import EngagementFinding


VAGUE_ANCHORS = {
    "click here", "here", "read more", "more", "learn more", "link",
    "details", "this link", "view", "page", "continue", "go",
}


def check_navigation(
    homepage_url: str,
    pages_data: List[Dict[str, Any]],
) -> List[EngagementFinding]:
    """Analyzes navigation reachability and anchor text descriptiveness across pages."""
    findings: List[EngagementFinding] = []

    # 1. Check for vague or empty anchor texts
    vague_anchors_by_url: Dict[str, List[str]] = {}
    homepage_internal_links: Set[str] = set()

    for page in pages_data:
        url = page.get("url", "")
        links = page.get("links", [])
        is_homepage = (url == homepage_url or url.rstrip("/") == homepage_url.rstrip("/"))

        for link in links:
            anchor = (link.get("text") or "").strip()
            target_url = link.get("url", "")
            is_internal = link.get("is_internal", True)

            if is_homepage and is_internal and target_url:
                homepage_internal_links.add(target_url.rstrip("/"))

            # Skip fragment-only or empty links
            if target_url in ("#", "", "javascript:void(0)"):
                continue

            anchor_lower = anchor.lower()
            if anchor_lower in VAGUE_ANCHORS or (not anchor and is_internal):
                vague_anchors_by_url.setdefault(url, []).append(anchor or "[Empty Anchor]")

    # Flag pages with repetitive vague anchor texts
    for url, vague_list in vague_anchors_by_url.items():
        if len(vague_list) >= 2:
            sample_anchors = ", ".join(f"'{a}'" for a in vague_list[:4])
            findings.append(
                EngagementFinding(
                    id="ENG-003",
                    category="engagement",
                    title="Navigation links use vague, non-descriptive anchor text",
                    severity=SeverityLevel.MEDIUM,
                    confidence=0.86,
                    evidence=(
                        f"Page at '{url}' contains {len(vague_list)} vague or empty link anchor texts: "
                        f"[{sample_anchors}]. Non-descriptive anchors hinder screen readers and search agent comprehension."
                    ),
                    affected_urls=[url],
                    suggested_action=FindingAction(
                        summary=(
                            "Replace generic anchor texts like 'click here' or 'read more' with descriptive labels "
                            "indicating the destination content (e.g., 'View Enterprise Pricing Plans')."
                        ),
                        priority=SeverityLevel.MEDIUM,
                    ),
                )
            )

    # 2. Check if the homepage lacks main navigation when multiple pages exist
    all_page_urls = {p.get("url", "").rstrip("/") for p in pages_data if p.get("url")}
    other_pages = all_page_urls - {homepage_url.rstrip("/")}

    if len(other_pages) >= 2:
        reachable_from_home = homepage_internal_links.intersection(all_page_urls)
        if len(reachable_from_home) == 0:
            findings.append(
                EngagementFinding(
                    id="ENG-004",
                    category="engagement",
                    title="Homepage lacks primary navigation paths to core sections",
                    severity=SeverityLevel.HIGH,
                    confidence=0.90,
                    evidence=(
                        f"Homepage at '{homepage_url}' does not link to any of the {len(other_pages)} "
                        "other discovered internal pages. Visitors arriving on the homepage cannot discover subpages."
                    ),
                    affected_urls=[homepage_url],
                    suggested_action=FindingAction(
                        summary=(
                            "Implement a primary navigation header or menu linking to major site sections "
                            "(e.g., About, Products, Pricing, Contact)."
                        ),
                        priority=SeverityLevel.HIGH,
                    ),
                )
            )

    return findings
