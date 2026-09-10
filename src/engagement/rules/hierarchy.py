"""Information hierarchy audit rule (Area 3).

Evaluates heading structures, sequential heading progression, and scannability
across audited pages.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
from src.engagement.models import EngagementFinding


def check_information_hierarchy(
    pages_data: List[Dict[str, Any]],
) -> List[EngagementFinding]:
    """Analyzes heading hierarchy and scannability on all pages."""
    findings: List[EngagementFinding] = []

    for page in pages_data:
        url = page.get("url", "")
        headings: List[Dict[str, Any]] = page.get("headings", [])
        body_text = page.get("body_text", "") or ""

        if not headings:
            continue

        levels = [h.get("level", 1) for h in headings]

        # 1. Check for skipped heading levels (e.g., H1 -> H3 skipping H2)
        skipped_transitions: List[Tuple[int, int]] = []
        for i in range(len(levels) - 1):
            curr_lvl = levels[i]
            next_lvl = levels[i + 1]
            if next_lvl > curr_lvl + 1:
                skipped_transitions.append((curr_lvl, next_lvl))

        if skipped_transitions:
            trans_str = ", ".join(f"H{c}->H{n}" for c, n in skipped_transitions[:3])
            findings.append(
                EngagementFinding(
                    id="ENG-005",
                    category="engagement",
                    title="Broken heading hierarchy skips intermediate heading levels",
                    severity=SeverityLevel.MEDIUM,
                    confidence=0.88,
                    evidence=(
                        f"Page '{url}' contains illogical heading level skips: [{trans_str}]. "
                        "Skipping heading levels impairs accessibility tree construction and content parsing."
                    ),
                    affected_urls=[url],
                    suggested_action=FindingAction(
                        summary=(
                            "Restructure headings sequentially (H1 followed by H2, then H3) without skipping levels "
                            "to maintain an intuitive document outline."
                        ),
                        priority=SeverityLevel.MEDIUM,
                    ),
                )
            )

        # 2. Check for multiple H1 headings
        h1_headings = [h.get("text", "") for h in headings if h.get("level") == 1]
        if len(h1_headings) > 1:
            sample_h1s = ", ".join(f"'{t}'" for t in h1_headings[:3])
            findings.append(
                EngagementFinding(
                    id="ENG-006",
                    category="engagement",
                    title="Multiple H1 headings dilute primary page topic hierarchy",
                    severity=SeverityLevel.LOW,
                    confidence=0.85,
                    evidence=(
                        f"Page '{url}' defines {len(h1_headings)} separate <h1> elements: [{sample_h1s}]. "
                        "A single primary <h1> is recommended for clear topic disambiguation."
                    ),
                    affected_urls=[url],
                    suggested_action=FindingAction(
                        summary="Retain one primary <h1> per page and demote secondary section titles to <h2>.",
                        priority=SeverityLevel.LOW,
                    ),
                )
            )

        # 3. Check for dense text lacking subheadings
        words = len(re.findall(r"\w+", body_text))
        subheadings = [h for h in headings if h.get("level", 1) in (2, 3)]
        if words > 250 and len(subheadings) == 0:
            findings.append(
                EngagementFinding(
                    id="ENG-007",
                    category="engagement",
                    title="Dense body content lacks subheadings for scannability",
                    severity=SeverityLevel.LOW,
                    confidence=0.80,
                    evidence=(
                        f"Page '{url}' contains {words} words of body text but lacks <h2> or <h3> subheadings. "
                        "Monolithic text blocks reduce readability and structured information extraction."
                    ),
                    affected_urls=[url],
                    suggested_action=FindingAction(
                        summary="Break long content sections into subsections with descriptive <h2> and <h3> subheadings.",
                        priority=SeverityLevel.LOW,
                    ),
                )
            )

    return findings
