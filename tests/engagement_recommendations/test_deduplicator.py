"""Tests for Finding Deduplication and Evidence Preservation."""

import pytest
from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
from src.report.deduplicator import deduplicate_findings
from src.report.models import ReportFinding


def test_deduplicator_combines_affected_urls_and_evidence():
    """Verifies that findings with matching (id, category) merge URLs and preserve distinct evidence."""
    f1 = ReportFinding(
        id="ENG-014",
        category="engagement",
        title="Dead-end page terminates user journey",
        severity=SeverityLevel.HIGH,
        confidence=0.90,
        evidence="Page 'https://site.com/sub1' has 0 outgoing links.",
        affected_urls=["https://site.com/sub1"],
        suggested_action=FindingAction(summary="Add links", priority=SeverityLevel.HIGH),
    )
    f2 = ReportFinding(
        id="ENG-014",
        category="engagement",
        title="Dead-end page terminates user journey",
        severity=SeverityLevel.CRITICAL,  # Higher severity
        confidence=0.95,  # Higher confidence
        evidence="Page 'https://site.com/sub2' has 0 outgoing links.",
        affected_urls=["https://site.com/sub2"],
        suggested_action=FindingAction(summary="Add links", priority=SeverityLevel.CRITICAL),
    )

    deduped = deduplicate_findings([f1, f2])
    assert len(deduped) == 1
    merged = deduped[0]

    # Preserves highest severity and confidence
    assert merged.severity == SeverityLevel.CRITICAL
    assert merged.confidence == 0.95

    # Combines all affected URLs without loss
    assert set(merged.affected_urls) == {"https://site.com/sub1", "https://site.com/sub2"}

    # Preserves both evidence excerpts
    assert "https://site.com/sub1" in merged.evidence
    assert "https://site.com/sub2" in merged.evidence


def test_deduplicator_keeps_distinct_finding_ids():
    """Verifies that findings with different IDs remain distinct."""
    f1 = ReportFinding(
        id="ENG-001",
        category="engagement",
        title="Orientation issue",
        severity=SeverityLevel.HIGH,
        confidence=0.90,
        evidence="Title issue",
        affected_urls=["https://site.com/"],
        suggested_action=FindingAction(summary="Fix title", priority=SeverityLevel.HIGH),
    )
    f2 = ReportFinding(
        id="ENG-008",
        category="engagement",
        title="CTA issue",
        severity=SeverityLevel.HIGH,
        confidence=0.90,
        evidence="CTA issue",
        affected_urls=["https://site.com/"],
        suggested_action=FindingAction(summary="Fix CTA", priority=SeverityLevel.HIGH),
    )

    deduped = deduplicate_findings([f1, f2])
    assert len(deduped) == 2
