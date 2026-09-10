"""Conversion pathway audit rule (Area 8).

Evaluates whether commercial, pricing, or product pages provide actionable
conversion next steps (signup, demo, purchase, or contact links).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
from src.engagement.models import EngagementFinding


CONVERSION_PAGE_PATTERNS = [
    r"/pricing",
    r"/plans",
    r"/products?",
    r"/services?",
    r"/solutions?",
]

CONVERSION_ACTION_PATTERNS = [
    r"\bsign\s*up\b",
    r"\bget\s+started\b",
    r"\bstart\s+(?:free\s+)?trial\b",
    r"\bselect\s+(?:a\s+)?plan\b",
    r"\bchoose\s+(?:a\s+)?plan\b",
    r"\bbuy\s+now\b",
    r"\bcheckout\b",
    r"\brequest\s+quote\b",
    r"\bcontact\s+(?:sales|us)\b",
    r"\bbook\s+demo\b",
    r"\badd\s+to\s+cart\b",
    r"\border\b",
    r"\bsubscribe\b",
]

CONVERSION_TARGET_KEYWORDS = [
    "signup", "register", "checkout", "cart", "contact", "demo", "subscribe", "buy",
]


def check_conversion_path(
    pages_data: List[Dict[str, Any]],
) -> List[EngagementFinding]:
    """Evaluates whether pricing and product pages offer actionable conversion actions."""
    findings: List[EngagementFinding] = []

    for page in pages_data:
        url = page.get("url", "")
        title = (page.get("title") or "").lower()

        # Identify if page is a conversion-critical page (pricing, plans, etc.)
        is_conversion_page = (
            any(re.search(pat, url.lower()) for pat in CONVERSION_PAGE_PATTERNS)
            or "pricing" in title
            or "plans" in title
        )

        if not is_conversion_page:
            continue

        links = page.get("links", [])
        has_conversion_action = False

        for link in links:
            anchor = (link.get("text") or "").strip().lower()
            target = (link.get("url") or "").lower()

            for pat in CONVERSION_ACTION_PATTERNS:
                if re.search(pat, anchor):
                    has_conversion_action = True
                    break

            if has_conversion_action:
                break

            if any(kw in target for kw in CONVERSION_TARGET_KEYWORDS):
                has_conversion_action = True
                break

        if not has_conversion_action:
            findings.append(
                EngagementFinding(
                    id="ENG-013",
                    category="engagement",
                    title="Conversion page lacks actionable next step or signup path",
                    severity=SeverityLevel.HIGH,
                    confidence=0.89,
                    evidence=(
                        f"Commercial conversion page '{url}' outlines offerings or pricing tiers "
                        f"but provides no actionable next step link (checked {len(links)} links; "
                        "no signup, checkout, demo, or sales inquiry links found). "
                        "Leads and automated buyers cannot convert."
                    ),
                    affected_urls=[url],
                    suggested_action=FindingAction(
                        summary=(
                            "Add prominent action links (e.g. 'Get Started', 'Choose Plan', 'Contact Sales') "
                            f"on '{url}' directly linking to checkout, registration, or sales inquiry forms."
                        ),
                        priority=SeverityLevel.HIGH,
                    ),
                )
            )

    return findings
