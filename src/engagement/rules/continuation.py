"""Related content and continuation audit rule (Area 6).

Evaluates whether content/detail pages provide reasonable onward paths,
related articles, or continuation links to maintain visitor engagement.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
from src.engagement.models import EngagementFinding


def check_related_content_continuation(
    homepage_url: str,
    pages_data: List[Dict[str, Any]],
) -> List[EngagementFinding]:
    """Identifies content-heavy pages that lack onward continuation links."""
    findings: List[EngagementFinding] = []
    hp_canonical = homepage_url.rstrip("/")

    for page in pages_data:
        url = page.get("url", "")
        if url.rstrip("/") == hp_canonical:
            continue

        body_text = page.get("body_text", "") or ""
        words = len(re.findall(r"\w+", body_text))

        # Check if page is an informative/content page (>= 150 words)
        if words < 150:
            continue

        links = page.get("links", [])
        # Outgoing internal links excluding links back to homepage
        outgoing_content_links = [
            l for l in links
            if l.get("is_internal", True)
            and l.get("url", "").rstrip("/") not in (hp_canonical, url.rstrip("/"), "#", "")
        ]

        # If substantial content page has zero onward internal links
        if len(outgoing_content_links) == 0:
            findings.append(
                EngagementFinding(
                    id="ENG-011",
                    category="engagement",
                    title="Content page lacks onward continuation paths or related topic links",
                    severity=SeverityLevel.MEDIUM,
                    confidence=0.84,
                    evidence=(
                        f"Informational content page '{url}' contains {words} words but zero onward internal links "
                        f"to related content, documentation, or next steps (only {len(links)} total links found). "
                        "Visitors reaching the end of the content face an engagement drop-off."
                    ),
                    affected_urls=[url],
                    suggested_action=FindingAction(
                        summary=(
                            "Add contextual links, a 'Related Articles' section, or recommended next steps "
                            "at the conclusion of substantive content."
                        ),
                        priority=SeverityLevel.MEDIUM,
                    ),
                )
            )

    return findings
