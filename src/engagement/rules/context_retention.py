"""Context retention audit rule (Area 10).

Evaluates whether deeper pages provide sufficient orienting context, brand identity,
and parent navigation for visitors or AI agents arriving directly on that page.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Dict, List

from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
from src.engagement.models import EngagementFinding


def check_context_retention(
    site_domain: str,
    homepage_url: str,
    pages_data: List[Dict[str, Any]],
) -> List[EngagementFinding]:
    """Audits deeper pages for direct-landing context retention and breadcrumbs."""
    findings: List[EngagementFinding] = []
    hp_canonical = homepage_url.rstrip("/")

    for page in pages_data:
        url = page.get("url", "")
        if url.rstrip("/") == hp_canonical:
            continue  # Homepage is the root

        crawl_depth = page.get("crawl_depth", 0)
        parsed_path = urllib.parse.urlparse(url).path.strip("/")
        path_segments = [s for s in parsed_path.split("/") if s]

        # Consider deep if crawl_depth >= 1 or has path segments
        if not path_segments and crawl_depth == 0:
            continue

        title = (page.get("title") or "").strip()
        headings = page.get("headings", [])
        links = page.get("links", [])

        # 1. Check if the page links back to homepage/root
        has_home_link = False
        for link in links:
            t = (link.get("url") or "").rstrip("/")
            anchor = (link.get("text") or "").strip().lower()
            if t == hp_canonical or t == f"{hp_canonical}/":
                has_home_link = True
                break
            if anchor in ("home", "homepage", "index", "main"):
                has_home_link = True
                break

        if not has_home_link:
            findings.append(
                EngagementFinding(
                    id="ENG-015",
                    category="engagement",
                    title="Deep landing page lacks navigation link back to homepage",
                    severity=SeverityLevel.MEDIUM,
                    confidence=0.90,
                    evidence=(
                        f"Direct landing page '{url}' has no link back to the root homepage '{homepage_url}'. "
                        "Visitors arriving from external search engines or AI direct references cannot navigate "
                        "back to the main brand portal."
                    ),
                    affected_urls=[url],
                    suggested_action=FindingAction(
                        summary=(
                            f"Include a logo/home link or breadcrumb navigation on '{url}' that connects back "
                            f"to the homepage ('{homepage_url}')."
                        ),
                        priority=SeverityLevel.MEDIUM,
                    ),
                )
            )

        # 2. Check if deep page lacks any H1 heading
        has_h1 = any(h.get("level") == 1 and (h.get("text") or "").strip() for h in headings)
        if not has_h1:
            findings.append(
                EngagementFinding(
                    id="ENG-016",
                    category="engagement",
                    title="Direct landing page lacks clear orienting H1 heading",
                    severity=SeverityLevel.MEDIUM,
                    confidence=0.87,
                    evidence=(
                        f"Page '{url}' does not have an <h1> heading defining the page topic. "
                        "Users landing directly on this page receive no prominent topical orientation."
                    ),
                    affected_urls=[url],
                    suggested_action=FindingAction(
                        summary=f"Add a descriptive primary <h1> heading to '{url}' clarifying the section subject.",
                        priority=SeverityLevel.MEDIUM,
                    ),
                )
            )

    return findings
