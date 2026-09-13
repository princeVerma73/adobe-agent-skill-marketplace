"""Navigation audit rule (Area 2).

Evaluates whether key pages are reachable, whether navigation paths are
understandable, and identifies vague anchor texts or navigation deadlocks.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set

from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
from src.engagement.models import EngagementFinding
from src.inspection.url import is_canonical_equivalent, is_same_site, normalize_url


VAGUE_ANCHORS = {
    "click here", "here", "read more", "more", "learn more", "link",
    "details", "this link", "view", "page", "continue", "go",
}


def check_navigation(
    homepage_url: str,
    pages_data: List[Dict[str, Any]],
    homepage_aliases: Optional[Set[str]] = None,
) -> List[EngagementFinding]:
    """Analyzes navigation reachability and anchor text descriptiveness across pages."""
    findings: List[EngagementFinding] = []

    # 1. Resolve homepage aliases
    aliases: Set[str] = {homepage_url.rstrip("/")}
    if homepage_aliases:
        aliases.update(a.rstrip("/") for a in homepage_aliases if a)
    try:
        norm_hp = normalize_url(homepage_url)
        aliases.add(norm_hp)
    except Exception:
        pass

    # Check if pages contain explicit canonical equivalents or redirect chains for the homepage
    for p in pages_data:
        p_u = p.get("url", "")
        p_orig = p.get("original_url", "")
        if (
            is_canonical_equivalent(p_u, homepage_url)
            or (p_orig and is_canonical_equivalent(p_orig, homepage_url))
        ):
            if p_u:
                aliases.add(p_u.rstrip("/"))
            if p_orig:
                aliases.add(p_orig.rstrip("/"))
            for r in p.get("redirect_chain", []):
                if r:
                    aliases.add(r.rstrip("/"))

    # 1. Check for vague or empty anchor texts and extract homepage internal links
    vague_anchors_by_url: Dict[str, List[str]] = {}
    homepage_internal_links: Set[str] = set()

    for page in pages_data:
        url = page.get("url", "")
        orig_url = page.get("original_url", "")
        links = page.get("links", [])

        is_homepage = (
            url.rstrip("/") in aliases
            or orig_url.rstrip("/") in aliases
            or any(is_canonical_equivalent(url, a) for a in aliases)
            or any(is_canonical_equivalent(orig_url, a) for a in aliases if orig_url)
        )


        for link in links:
            anchor = (link.get("text") or "").strip()
            target_url = link.get("url", "")
            is_internal = link.get("is_internal", True)

            if is_homepage and is_internal and target_url:
                try:
                    norm_target = normalize_url(target_url)
                except Exception:
                    norm_target = target_url.rstrip("/")
                homepage_internal_links.add(norm_target)

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
    all_page_urls: Set[str] = set()
    for p in pages_data:
        u = p.get("url", "")
        if u:
            try:
                all_page_urls.add(normalize_url(u))
            except Exception:
                all_page_urls.add(u.rstrip("/"))

    other_pages = {
        u for u in all_page_urls
        if not any(is_canonical_equivalent(u, a) for a in aliases)
    }

    if len(other_pages) >= 2:
        reachable_from_home = {
            u for u in homepage_internal_links
            if any(is_canonical_equivalent(u, p_url) for p_url in all_page_urls)
        }
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

