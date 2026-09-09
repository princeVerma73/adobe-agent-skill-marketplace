"""Confidence & Ranking Engine.

Calibrates confidence scores, suppresses false positives below threshold,
deduplicates redundant findings, and ranks by severity.
"""

from __future__ import annotations

from typing import Dict, List, Tuple
from ..contracts.schemas import Finding, SeverityCounts, SeverityLevel


SEVERITY_ORDER = {
    SeverityLevel.CRITICAL: 5,
    SeverityLevel.HIGH: 4,
    SeverityLevel.MEDIUM: 3,
    SeverityLevel.LOW: 2,
    SeverityLevel.INFO: 1,
}


def filter_and_rank_findings(
    findings: List[Finding],
    confidence_threshold: float = 0.70,
) -> Tuple[List[Finding], SeverityCounts]:
    """Filters findings below confidence threshold, deduplicates, and sorts by severity."""
    # Deduplicate by (id, category, tuple(affected_urls))
    seen_keys = set()
    deduped: List[Finding] = []

    for f in findings:
        if f.confidence < confidence_threshold:
            continue
        key = (f.id, f.category, tuple(sorted(f.affected_urls)))
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(f)

    # Sort primarily by severity (highest first), then by confidence (descending)
    sorted_findings = sorted(
        deduped,
        key=lambda item: (SEVERITY_ORDER.get(item.severity, 0), item.confidence),
        reverse=True,
    )

    # Count severities
    counts = SeverityCounts()
    for f in sorted_findings:
        if f.severity == SeverityLevel.CRITICAL:
            counts.critical += 1
        elif f.severity == SeverityLevel.HIGH:
            counts.high += 1
        elif f.severity == SeverityLevel.MEDIUM:
            counts.medium += 1
        elif f.severity == SeverityLevel.LOW:
            counts.low += 1
        elif f.severity == SeverityLevel.INFO:
            counts.info += 1

    return sorted_findings, counts
