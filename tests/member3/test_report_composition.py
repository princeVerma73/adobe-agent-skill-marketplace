"""Tests for Report Composition, Normalization, and Scoring."""

import pytest
from src.entity_trust.contracts.schemas import (
    EntityProfile,
    Finding,
    FindingAction,
    SeverityCounts,
    SeverityLevel,
)
from src.engagement.models import EngagementFinding
from src.inspection.models import TechnicalIssue
from src.report.builder import ReportBuilder, calculate_readiness_score
from src.report.models import FinalAuditReport
from src.report.normalizer import (
    normalize_engagement_finding,
    normalize_member2_finding,
    normalize_technical_issue,
    validate_evidence,
)


def test_normalize_technical_issue():
    """Verifies that Member 1 TechnicalIssue is correctly converted into a ReportFinding."""
    tech_issue = TechnicalIssue(
        code="HTTP_NOT_FOUND",
        message="Page returned HTTP 404 Not Found.",
        severity="error",
        details={"status_code": 404},
    )
    rf = normalize_technical_issue(tech_issue, "https://example.com/broken-link")
    assert rf.id == "TECH-HTTP_NOT_FOUND"
    assert rf.category == "technical"
    assert rf.severity == SeverityLevel.HIGH
    assert rf.confidence >= 0.95
    assert "https://example.com/broken-link" in rf.affected_urls
    assert "HTTP 404" in rf.evidence


def test_evidence_validation_anti_hallucination():
    """Verifies that validate_evidence drops ungrounded or empty findings."""
    known_urls = {"https://example.com/", "https://example.com/about"}

    # Valid grounded finding
    valid_finding = normalize_engagement_finding(
        EngagementFinding(
            id="ENG-001",
            category="engagement",
            title="Title issue",
            severity=SeverityLevel.HIGH,
            confidence=0.90,
            evidence="Homepage Title='Home' is non-descriptive.",
            affected_urls=["https://example.com/"],
            suggested_action=FindingAction(summary="Fix title", priority=SeverityLevel.HIGH),
        )
    )
    assert validate_evidence(valid_finding, known_urls) is True

    # Ungrounded finding with empty evidence
    empty_evidence_finding = normalize_engagement_finding(
        EngagementFinding(
            id="ENG-002",
            category="engagement",
            title="Empty evidence",
            severity=SeverityLevel.LOW,
            confidence=0.80,
            evidence="",
            affected_urls=["https://example.com/"],
            suggested_action=FindingAction(summary="Fix", priority=SeverityLevel.LOW),
        )
    )
    assert validate_evidence(empty_evidence_finding, known_urls) is False


def test_calculate_readiness_score():
    """Verifies Brand AI Readiness score calculations and grade assignments."""
    # Perfect score: zero findings
    zero_counts = SeverityCounts()
    score, grade = calculate_readiness_score(zero_counts)
    assert score == 100.0
    assert grade == "A"

    # Critical penalty: 1 critical = -25 points -> 75 (Grade C)
    crit_counts = SeverityCounts(critical=1)
    score, grade = calculate_readiness_score(crit_counts)
    assert score == 75.0
    assert grade == "C"

    # Heavy issues floor at 0.0 (Grade F)
    heavy_counts = SeverityCounts(critical=5)
    score, grade = calculate_readiness_score(heavy_counts)
    assert score == 0.0
    assert grade == "F"


def test_report_builder_multi_skill_composition():
    """Verifies end-to-end report building, JSON serialization, and Markdown generation."""
    builder = ReportBuilder(
        site="novastack.io",
        root_url="https://novastack.io/",
        entity_profile=EntityProfile(name="NovaStack Inc", industry="software"),
    )
    builder.add_known_urls(["https://novastack.io/", "https://novastack.io/pricing"])

    # Add Technical Issue
    builder.add_technical_issues([
        (
            TechnicalIssue(code="ROBOTS_TXT_DISALLOWED", message="Robots disallowed.", severity="warning"),
            "https://novastack.io/pricing",
        )
    ])

    # Add Member 2 Finding
    builder.add_member2_findings([
        Finding(
            id="FR-001",
            category="freshness",
            title="Copyright lag",
            severity=SeverityLevel.MEDIUM,
            confidence=0.88,
            evidence="Footer copyright year is 2021.",
            affected_urls=["https://novastack.io/"],
            suggested_action=FindingAction(summary="Update copyright", priority=SeverityLevel.MEDIUM),
        )
    ])

    # Add Member 3 Engagement Finding
    builder.add_engagement_findings([
        EngagementFinding(
            id="ENG-008",
            category="engagement",
            title="Missing CTA",
            severity=SeverityLevel.HIGH,
            confidence=0.91,
            evidence="No CTA button found on homepage.",
            affected_urls=["https://novastack.io/"],
            suggested_action=FindingAction(summary="Add CTA button", priority=SeverityLevel.HIGH),
        )
    ])

    report = builder.build()
    assert isinstance(report, FinalAuditReport)
    assert report.site == "novastack.io"
    assert report.status == "success"
    assert len(report.findings) == 3
    assert len(report.recommendations) == 3
    assert report.entity_profile.name == "NovaStack Inc"

    # Test JSON and Markdown exports
    json_str = report.to_json()
    assert "novastack.io" in json_str
    assert "ENG-008" in json_str

    md_str = report.to_markdown()
    assert "# Brand AI-Readiness Audit Report: novastack.io" in md_str
    assert "NovaStack Inc" in md_str
    assert "Actionable Remediation Roadmap" in md_str
