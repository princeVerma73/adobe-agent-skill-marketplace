"""Internal linking audit rule (Area 5).

Analyzes the internal link topology across audited pages and flags isolated,
poorly connected, or orphaned pages.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
from src.engagement.models import EngagementFinding
from src.inspection.url import (
    is_canonical_equivalent,
    is_locale_root,
    is_regional_sibling,
    normalize_url,
)


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
        raw_u = p.get("url", "")
        if not raw_u:
            continue
        try:
            canon = normalize_url(raw_u)
        except Exception:
            canon = raw_u.rstrip("/")

        incoming_links[canon] = set()
        url_to_canonical[canon] = canon
        url_to_canonical[raw_u.rstrip("/")] = canon

        orig = (p.get("original_url") or "").rstrip("/")
        if orig:
            url_to_canonical[orig] = canon
            try:
                url_to_canonical[normalize_url(orig)] = canon
            except Exception:
                pass
        for r in p.get("redirect_chain", []):
            rc = (r or "").rstrip("/")
            if rc:
                url_to_canonical[rc] = canon
                try:
                    url_to_canonical[normalize_url(rc)] = canon
                except Exception:
                    pass

    for page in pages_data:
        raw_source = page.get("url", "")
        source_url = url_to_canonical.get(raw_source, raw_source.rstrip("/"))
        for link in page.get("links", []):
            target = (link.get("url") or "").rstrip("/")
            canon_target = url_to_canonical.get(target)
            if not canon_target:
                try:
                    canon_target = url_to_canonical.get(normalize_url(target))
                except Exception:
                    pass
            if canon_target and canon_target in incoming_links and canon_target != source_url:
                incoming_links[canon_target].add(source_url)

    hp_canonical = url_to_canonical.get(homepage_url.rstrip("/"), homepage_url.rstrip("/"))
    try:
        hp_norm = normalize_url(homepage_url)
        hp_canonical = url_to_canonical.get(hp_norm, hp_canonical)
    except Exception:
        pass

    # Identify orphan or poorly connected pages
    for page_url, sources in incoming_links.items():
        if page_url == hp_canonical or is_canonical_equivalent(page_url, hp_canonical):
            continue  # Homepage is the root entrypoint

        # Regional sibling roots (e.g. /au/, /at/ during an /in/ audit) reached via sitemaps/selectors
        # should not be penalized as orphaned internal pages of the audited locale.
        if is_regional_sibling(homepage_url, page_url) and is_locale_root(page_url):
            continue

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

