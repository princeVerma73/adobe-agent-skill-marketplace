"""Homepage orientation audit rule (Area 1).

Evaluates whether a visitor or AI agent can readily understand what the website
is about and discern the organization's core purpose and value proposition.
"""

from __future__ import annotations

import re
from typing import Any, List, Optional

from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
from src.engagement.models import EngagementFinding


GENERIC_TITLES = {
    "home", "welcome", "index", "homepage", "home page", "default", "landing", "start",
}

GENERIC_H1S = {
    "welcome", "welcome to our website", "welcome to us", "home", "homepage",
    "innovative solutions", "the future is here", "transforming business",
    "making a difference", "leading the way", "hello", "main page",
}


def check_homepage_orientation(
    homepage_url: str,
    title: Optional[str],
    h1s: List[str],
    body_text: Optional[str],
    meta_description: Optional[str] = None,
) -> List[EngagementFinding]:
    """Evaluates homepage orientation and value proposition clarity."""
    findings: List[EngagementFinding] = []
    clean_title = (title or "").strip()
    clean_h1 = (h1s[0] if h1s else "").strip()
    clean_body = (body_text or "").strip()
    clean_meta = (meta_description or "").strip()

    title_lower = clean_title.lower()
    h1_lower = clean_h1.lower()

    # 1. Check for generic or missing title and H1
    is_missing_or_generic_title = (
        not clean_title
        or title_lower in GENERIC_TITLES
        or len(clean_title) < 4
    )
    is_missing_or_generic_h1 = (
        not clean_h1
        or h1_lower in GENERIC_H1S
        or len(clean_h1.split()) < 2
    )

    if is_missing_or_generic_title and is_missing_or_generic_h1:
        findings.append(
            EngagementFinding(
                id="ENG-001",
                category="engagement",
                title="Homepage orientation lacks clear purpose and value proposition",
                severity=SeverityLevel.HIGH,
                confidence=0.92,
                evidence=(
                    f"Homepage at '{homepage_url}' uses non-descriptive orientation elements: "
                    f"Title='{clean_title or '[Empty]'}' and H1='{clean_h1 or '[Empty]'}'. "
                    "Visitors and agents cannot immediately comprehend the website's purpose."
                ),
                affected_urls=[homepage_url],
                suggested_action=FindingAction(
                    summary=(
                        "Update the homepage <title> and primary <h1> to explicitly state the brand name "
                        "and its primary value proposition."
                    ),
                    priority=SeverityLevel.HIGH,
                ),
            )
        )
    elif is_missing_or_generic_title:
        findings.append(
            EngagementFinding(
                id="ENG-001-TITLE",
                category="engagement",
                title="Homepage title is generic and fails to orient visitors",
                severity=SeverityLevel.MEDIUM,
                confidence=0.88,
                evidence=(
                    f"Homepage at '{homepage_url}' has non-descriptive title '{clean_title or '[Empty]'}'. "
                    "Browser tabs and search results do not communicate the site identity."
                ),
                affected_urls=[homepage_url],
                suggested_action=FindingAction(
                    summary="Provide an informative title containing brand name and primary offering.",
                    priority=SeverityLevel.MEDIUM,
                ),
            )
        )

    # 2. Check for value proposition and substantive purpose description
    # Minimum combined orientation text
    combined_intro = f"{clean_meta} {clean_body[:600]}".strip()
    word_count = len(re.findall(r"\w+", combined_intro))

    if word_count < 10:
        findings.append(
            EngagementFinding(
                id="ENG-002",
                category="engagement",
                title="Homepage lacks identifiable product or service explanation",
                severity=SeverityLevel.HIGH,
                confidence=0.90,
                evidence=(
                    f"Homepage at '{homepage_url}' contains insufficient orientation text "
                    f"({word_count} words found in introductory content). "
                    "Neither human visitors nor AI agents can extract the core offerings."
                ),
                affected_urls=[homepage_url],
                suggested_action=FindingAction(
                    summary=(
                        "Add a concise 2-3 sentence introductory value proposition above the fold explaining "
                        "what the organization does and who it serves."
                    ),
                    priority=SeverityLevel.HIGH,
                ),
            )
        )

    return findings
