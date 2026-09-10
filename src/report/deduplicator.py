"""Deduplication and consolidation engine for the report composer.

Merges redundant findings across specialist skills and multiple pages
while preserving evidence excerpts and combining affected URLs.
"""

from __future__ import annotations

from typing import Dict, List, Tuple
from src.entity_trust.contracts.schemas import SeverityLevel
from src.report.models import ReportFinding

SEVERITY_ORDER = {
    SeverityLevel.CRITICAL: 5,
    SeverityLevel.HIGH: 4,
    SeverityLevel.MEDIUM: 3,
    SeverityLevel.LOW: 2,
    SeverityLevel.INFO: 1,
}


CROSS_SKILL_EQUIVALENCE: Dict[str, Tuple[str, str]] = {
    "ENG-006": ("TECH-MULTIPLE_H1", "technical"),
    "ENG-016": ("TECH-MISSING_H1", "technical"),
}


def deduplicate_findings(findings: List[ReportFinding]) -> List[ReportFinding]:
    """Deduplicates findings by (id, category) or equivalent issue footprint.

    Consolidates affected URLs, preserves unique evidence strings, and retains
    the highest severity and confidence score.
    """
    merged: Dict[Tuple[str, str], ReportFinding] = {}

    for f in findings:
        canon_id, canon_cat = CROSS_SKILL_EQUIVALENCE.get(f.id, (f.id, f.category))
        key = (canon_id, canon_cat)

        if key not in merged:
            # Clone finding
            merged[key] = ReportFinding(
                id=f.id,
                category=f.category,
                title=f.title,
                severity=f.severity,
                confidence=f.confidence,
                evidence=f.evidence,
                affected_urls=list(dict.fromkeys(f.affected_urls)),
                suggested_action=f.suggested_action,
            )
        else:
            existing = merged[key]

            # Combine affected URLs without duplicates
            combined_urls = list(dict.fromkeys(existing.affected_urls + f.affected_urls))
            existing.affected_urls = combined_urls

            # Preserve highest severity
            if SEVERITY_ORDER.get(f.severity, 0) > SEVERITY_ORDER.get(existing.severity, 0):
                existing.severity = f.severity
                existing.suggested_action.priority = f.severity

            # Preserve highest confidence
            if f.confidence > existing.confidence:
                existing.confidence = f.confidence

            # Append new unique evidence if not already present
            if f.evidence and f.evidence not in existing.evidence:
                existing.evidence = f"{existing.evidence} | {f.evidence}"

    # Sort final deduplicated list by severity descending, then confidence descending
    return sorted(
        merged.values(),
        key=lambda item: (SEVERITY_ORDER.get(item.severity, 0), item.confidence),
        reverse=True,
    )
