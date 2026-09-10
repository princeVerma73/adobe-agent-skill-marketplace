"""Internal linking audit rule (Area 5).

Analyzes the internal link topology across audited pages and flags isolated,
poorly connected, or orphaned pages.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
from src.engagement.models import EngagementFinding


def check_internal_linking(
    homepage_url: str,
    pages_data: List[Dict[str, Any]],
) -> List[EngagementFinding]:
    """Analyzes the cross-page link graph and identifies isolated pages."""
    findings: List[EngagementFinding] = []

    if len(pages_data) < 2:
        return findings

    # Build incoming link counts and URL alias mapping for every audited page
    url_to_canonical: Dict[str, str] = {}
    incoming_links: Dict[str, Set[str]] = {}

    for p in pages_data:
        canon = p.get("url", "").rstrip("/")
        if not canon:
            continue
        incoming_links[canon] = set()
        url_to_canonical[canon] = canon
        orig = (p.get("original_url") or "").rstrip("/")
        if orig:
            url_to_canonical[orig] = canon
        for r in p.get("redirect_chain", []):
            rc = (r or "").rstrip("/")
            if rc:
                url_to_canonical[rc] = canon

    for page in pages_data:
        source_url = page.get("url", "").rstrip("/")
        for link in page.get("links", []):
            target = (link.get("url") or "").rstrip("/")
            canon_target = url_to_canonical.get(target)
            if canon_target and canon_target in incoming_links and canon_target != source_url:
                incoming_links[canon_target].add(source_url)

    hp_canonical = homepage_url.rstrip("/")

    # Identify orphan or poorly connected pages
    for page_url, sources in incoming_links.items():
        if page_url == hp_canonical:
            continue  # Homepage is the root entrypoint

        # Orphan page: 0 incoming links from audited pages
        if len(sources) == 0:
            findings.append(
                EngagementFinding(
                    id="ENG-009",
                    category="engagement",
                    title="Orphaned internal page with no incoming navigation links",
                    severity=SeverityLevel.MEDIUM,
                    confidence=0.94,
                    evidence=(
                        f"Page '{page_url}' was crawled or indexed but has 0 incoming links from any other "
                        "inspected page on the domain. Automated crawlers and human visitors cannot naturally discover it."
                    ),
                    affected_urls=[page_url],
                    suggested_action=FindingAction(
                        summary=(
                            f"Add internal links pointing to '{page_url}' from relevant parent categories, "
                            "the main navigation, or related articles."
                        ),
                        priority=SeverityLevel.MEDIUM,
                    ),
                )
            )

    return findings
