"""Contact and support pathway audit rule (Area 7).

Evaluates whether visitors and AI agents can locate an obvious contact, support,
or communication pathway.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
from src.engagement.models import EngagementFinding


CONTACT_PATTERNS = [
    r"/contact(?:-us)?",
    r"/support",
    r"/help(?:-center)?",
    r"/get-in-touch",
    r"mailto:[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    r"tel:[+0-9() -]+",
]

CONTACT_ANCHORS = {
    "contact", "contact us", "support", "help", "help center",
    "get in touch", "talk to us", "customer service",
}


def check_contact_path(
    site_domain: str,
    homepage_url: str,
    pages_data: List[Dict[str, Any]],
) -> List[EngagementFinding]:
    """Identifies sites lacking any clear contact or customer support channels."""
    findings: List[EngagementFinding] = []
    has_contact = False
    evidence_channel = ""

    for page in pages_data:
        url = page.get("url", "").lower()
        # 1. URL itself is contact or support
        if any(re.search(pat, url) for pat in CONTACT_PATTERNS[:4]):
            has_contact = True
            break

        # 2. Links to contact/support/mailto/tel
        for link in page.get("links", []):
            target = (link.get("url") or "").lower()
            anchor = (link.get("text") or "").strip().lower()

            if any(re.search(pat, target) for pat in CONTACT_PATTERNS):
                has_contact = True
                break
            if anchor in CONTACT_ANCHORS or any(kw in anchor for kw in ("contact", "support", "help desk", "help center", "get in touch", "customer service", "feedback")):
                has_contact = True
                break

        if has_contact:
            break

        # 3. Check body text for email addresses or phone numbers
        body_text = page.get("body_text", "") or ""
        if re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", body_text):
            has_contact = True
            break
        if re.search(r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b", body_text):
            has_contact = True
            break

    if not has_contact and pages_data:
        findings.append(
            EngagementFinding(
                id="ENG-012",
                category="engagement",
                title="Missing identifiable contact or customer support pathway",
                severity=SeverityLevel.HIGH,
                confidence=0.91,
                evidence=(
                    f"Inspected {len(pages_data)} pages on '{site_domain}' but found 0 contact pages, "
                    "support links, email addresses, or phone channels. "
                    "Users and agents cannot find a path for inquiries, technical support, or assistance."
                ),
                affected_urls=[homepage_url],
                suggested_action=FindingAction(
                    summary=(
                        "Provide a dedicated /contact or /support page with a verifiable email address, "
                        "contact form, or customer service channel in header and footer navigation."
                    ),
                    priority=SeverityLevel.HIGH,
                ),
            )
        )

    return findings
