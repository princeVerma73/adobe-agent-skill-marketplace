"""Finding normalizer and evidence validator for the report composer.

Converts diverse finding structures from Member 1, Member 2, and Member 3
into the standardized ReportFinding schema and validates textual grounding.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
from src.report.models import ReportFinding


TECHNICAL_SEVERITY_MAP = {
    "error": SeverityLevel.HIGH,
    "warning": SeverityLevel.MEDIUM,
    "info": SeverityLevel.LOW,
}

TECHNICAL_ACTION_MAP = {
    "HTTP_NOT_FOUND": "Fix broken internal links or configure a 301 redirect to an active URL.",
    "HTTP_SERVER_ERROR": "Investigate backend web server logs and database connectivity to eliminate 5xx errors.",
    "HTTP_UNREACHABLE": "Verify domain DNS resolution, SSL certificates, and network firewall reachability.",
    "HTTP_CLIENT_ERROR": "Check request parameters and server access restrictions.",
    "ROBOTS_TXT_DISALLOWED": "Review robots.txt disallow directives to ensure public content is accessible to crawlers.",
    "ROBOTS_META_NOINDEX": "Remove 'noindex' meta directives from pages intended for public AI discovery.",
    "MISSING_TITLE": "Add an informative <title> tag between 15 and 60 characters containing the primary page subject.",
    "SHORT_TITLE": "Expand title tag to include brand name and specific page context.",
    "MISSING_H1": "Provide a descriptive <h1> element to establish primary topic structure.",
    "MULTIPLE_H1": "Demote secondary <h1> elements to <h2> to maintain a single primary page heading.",
    "HEADING_LEVEL_SKIPPED": "Ensure headings progress sequentially without skipping levels.",
    "LOW_BODY_TEXT": "Add substantive descriptive text to the page to improve information density.",
    "BROKEN_INTERNAL_LINK": "Update or remove broken hyperlink targets.",
    "TOO_MANY_REDIRECTS": "Reduce redirect chain length to 1 hop directly to destination URL.",
    "CANONICAL_MISMATCH": "Align canonical link tag with the page's preferred authoritative URL.",
    "CONTENT_GAP": "Implement Server-Side Rendering (SSR) so core content is available in static HTML.",
}


def normalize_technical_issue(issue: Any, page_url: str) -> ReportFinding:
    """Converts a Member 1 TechnicalIssue into a standardized ReportFinding."""
    code = getattr(issue, "code", "UNKNOWN_TECHNICAL_ISSUE")
    message = getattr(issue, "message", "Technical discoverability observation")
    raw_sev = str(getattr(issue, "severity", "warning")).lower()
    details = getattr(issue, "details", {})

    severity = TECHNICAL_SEVERITY_MAP.get(raw_sev, SeverityLevel.MEDIUM)
    if code in ("HTTP_NOT_FOUND", "HTTP_SERVER_ERROR", "HTTP_UNREACHABLE"):
        severity = SeverityLevel.HIGH

    fid = f"TECH-{code}"
    evidence = f"Page '{page_url}' reported {code}: {message}."
    if details:
        evidence += f" Context: {details}"

    action_summary = TECHNICAL_ACTION_MAP.get(
        code, f"Review and resolve technical issue '{code}' on '{page_url}'."
    )

    return ReportFinding(
        id=fid,
        category="technical",
        title=message,
        severity=severity,
        confidence=0.96,  # Technical crawler checks are directly observed
        evidence=evidence,
        affected_urls=[page_url],
        suggested_action=FindingAction(summary=action_summary, priority=severity),
    )


def normalize_member2_finding(finding: Any) -> ReportFinding:
    """Converts a Member 2 Finding into a ReportFinding."""
    category = getattr(finding, "category", "entity")
    cat_str = category.value if hasattr(category, "value") else str(category)

    sev = getattr(finding, "severity", SeverityLevel.MEDIUM)
    if isinstance(sev, str):
        try:
            sev = SeverityLevel(sev.lower())
        except ValueError:
            sev = SeverityLevel.MEDIUM

    return ReportFinding(
        id=getattr(finding, "id", "M2-UNKNOWN"),
        category=cat_str,
        title=getattr(finding, "title", "Content & Trust Finding"),
        severity=sev,
        confidence=float(getattr(finding, "confidence", 0.85)),
        evidence=getattr(finding, "evidence", ""),
        affected_urls=list(getattr(finding, "affected_urls", [])),
        suggested_action=getattr(
            finding,
            "suggested_action",
            FindingAction(summary="Review and remediate issue.", priority=sev),
        ),
    )


def normalize_engagement_finding(finding: Any) -> ReportFinding:
    """Converts a Member 3 EngagementFinding into a ReportFinding."""
    sev = getattr(finding, "severity", SeverityLevel.MEDIUM)
    if isinstance(sev, str):
        try:
            sev = SeverityLevel(sev.lower())
        except ValueError:
            sev = SeverityLevel.MEDIUM

    return ReportFinding(
        id=getattr(finding, "id", "ENG-UNKNOWN"),
        category="engagement",
        title=getattr(finding, "title", "Engagement Finding"),
        severity=sev,
        confidence=float(getattr(finding, "confidence", 0.85)),
        evidence=getattr(finding, "evidence", ""),
        affected_urls=list(getattr(finding, "affected_urls", [])),
        suggested_action=getattr(
            finding,
            "suggested_action",
            FindingAction(summary="Review and improve engagement flow.", priority=sev),
        ),
    )


def validate_evidence(
    finding: ReportFinding,
    known_urls: Set[str],
) -> bool:
    """Validates that a finding contains non-empty evidence and relates to inspected pages.

    Acts as an anti-hallucination guard to prevent speculative or ungrounded findings.
    """
    if not finding.evidence or len(finding.evidence.strip()) < 5:
        return False

    if not finding.id or not finding.title:
        return False

    # If affected URLs are specified, at least one should relate to known URLs or domain
    if finding.affected_urls and known_urls:
        norm_known = {u.rstrip("/").lower() for u in known_urls}
        has_match = any(
            u.rstrip("/").lower() in norm_known for u in finding.affected_urls
        )
        # Allow site-level findings where domain matches
        if not has_match:
            # Check domain substring
            first_known = next(iter(known_urls))
            return any(
                first_known.lower() in u.lower() or u.lower() in first_known.lower()
                for u in finding.affected_urls
            )

    return True
