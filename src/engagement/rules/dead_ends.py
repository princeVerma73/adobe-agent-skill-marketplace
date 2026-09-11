"""Dead-end page detection rule (Area 9).

Identifies pages that terminate a user journey unnecessarily by providing
zero outgoing internal links to other areas of the website.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
from src.engagement.models import EngagementFinding


TERMINAL_URL_PATTERNS = (
    "/thank-you", "/thankyou", "/thanks", "/confirmed", "/confirmation", "/success",
    "/order-complete", "/order-received", "/checkout/success", "/receipt",
    "/privacy", "/privacy-policy", "/terms", "/terms-of-service", "/terms-and-conditions",
    "/tos", "/legal", "/disclaimer", "/unsubscribe",
)
TERMINAL_TITLE_PATTERNS = (
    "thank you", "order confirmed", "order complete", "payment successful",
    "privacy policy", "terms of service", "terms and conditions", "terms of use",
    "legal notice", "unsubscribe successful",
)


def check_dead_ends(
    homepage_url: str,
    pages_data: List[Dict[str, Any]],
) -> List[EngagementFinding]:
    """Detects pages with zero outgoing internal links, excluding intentionally terminal pages."""
    findings: List[EngagementFinding] = []
    hp_canonical = homepage_url.rstrip("/")

    for page in pages_data:
        url = page.get("url", "")
        status_code = page.get("status_code", 200)

        # Only evaluate pages that rendered successfully
        if status_code and status_code >= 400:
            continue

        # Skip intentionally terminal pages (e.g. thank you, order confirmation, legal/privacy notices)
        url_lower = url.lower()
        title_lower = (page.get("title") or "").lower()
        if any(p in url_lower for p in TERMINAL_URL_PATTERNS) or any(t in title_lower for t in TERMINAL_TITLE_PATTERNS):
            continue

        links = page.get("links", [])
        # Valid outgoing internal links (exclude self-links and hashes)
        valid_outgoing = [
            l for l in links
            if l.get("is_internal", True)
            and (l.get("url") or "").rstrip("/") not in (url.rstrip("/"), "#", "")
        ]

        if len(valid_outgoing) == 0:
            findings.append(
                EngagementFinding(
                    id="ENG-014",
                    category="engagement",
                    title="Dead-end page terminates user journey without outgoing links",
                    severity=SeverityLevel.HIGH,
                    confidence=0.95,
                    evidence=(
                        f"Page '{url}' contains 0 outgoing internal links to any other page on the site. "
                        "Visitors and AI crawlers reaching this URL cannot navigate forward or return to safety."
                    ),
                    affected_urls=[url],
                    suggested_action=FindingAction(
                        summary=(
                            f"Add standard header/footer navigation or contextual next-step links on '{url}' "
                            "to ensure visitors and automated agents can continue exploring."
                        ),
                        priority=SeverityLevel.HIGH,
                    ),
                )
            )

    return findings
