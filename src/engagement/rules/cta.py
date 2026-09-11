"""CTA (Call-to-Action) clarity audit rule (Area 4).

Evaluates whether key landing pages provide prominent, actionable next steps
and meaningful calls-to-action for visitors and automated journey agents.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set

from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
from src.engagement.models import EngagementFinding


CTA_PATTERNS = [
    r"\bget\s+started\b",
    r"\bsign\s+up\b",
    r"\bregister\b",
    r"\btry\s+(?:for\s+)?free\b",
    r"\bstart\s+(?:your\s+)?free\s+trial\b",
    r"\brequest\s+a?\s*demo\b",
    r"\bbook\s+a?\s*demo\b",
    r"\bschedule\s+a?\s*demo\b",
    r"\bcontact\s+(?:us|sales)\b",
    r"\btalk\s+to\s+(?:us|sales)\b",
    r"\bbuy\s+now\b",
    r"\bpurchase\b",
    r"\bdownload\b",
    r"\bjoin\s+now\b",
    r"\bview\s+pricing\b",
    r"\bexplore\s+plans\b",
]

CTA_URL_KEYWORDS = [
    "signup", "register", "start", "demo", "pricing", "trial", "contact", "join",
]


def check_cta_clarity(
    homepage_url: str,
    pages_data: List[Dict[str, Any]],
) -> List[EngagementFinding]:
    """Identifies missing or obscure calls-to-action on key landing surfaces."""
    findings: List[EngagementFinding] = []

    # Locate homepage
    homepage_page = None
    for p in pages_data:
        u = p.get("url", "")
        if u == homepage_url or u.rstrip("/") == homepage_url.rstrip("/"):
            homepage_page = p
            break

    if not homepage_page:
        return findings

    if homepage_page:
        hp_url = homepage_page.get("url", "")
        links = homepage_page.get("links", [])
        
        has_action_cta = False
        discovered_ctas: List[str] = []

        for link in links:
            anchor = (link.get("text") or "").strip()
            target_url = link.get("url", "").lower()

            # Check anchor text against CTA regex patterns
            for pat in CTA_PATTERNS:
                if re.search(pat, anchor, re.I):
                    has_action_cta = True
                    discovered_ctas.append(anchor)
                    break

            if has_action_cta:
                break

            # Check target URL for CTA destinations
            if any(kw in target_url for kw in CTA_URL_KEYWORDS):
                has_action_cta = True
                discovered_ctas.append(anchor or target_url)
                break

        if not has_action_cta:
            findings.append(
                EngagementFinding(
                    id="ENG-008",
                    category="engagement",
                    title="Homepage lacks a clear primary call-to-action (CTA)",
                    severity=SeverityLevel.HIGH,
                    confidence=0.91,
                    evidence=(
                        f"Homepage at '{hp_url}' has {len(links)} links but none present a clear primary call-to-action "
                        "(e.g., 'Get Started', 'Request Demo', 'Sign Up', or 'Contact Us'). "
                        "Visitors arriving on the homepage have no distinct conversion or next-action path."
                    ),
                    affected_urls=[hp_url],
                    suggested_action=FindingAction(
                        summary=(
                            "Add a clearly identifiable primary CTA button near the hero value proposition "
                            "connecting to an onboarding, demo, or signup flow."
                        ),
                        priority=SeverityLevel.HIGH,
                    ),
                )
            )

    return findings
