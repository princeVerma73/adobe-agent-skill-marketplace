"""Tests for Actionable Recommendation Engine."""

import pytest
from src.engagement.models import EngagementFinding
from src.entity_trust.contracts.schemas import Finding, FindingAction, SeverityLevel
from src.recommendations.engine import RecommendationEngine
from src.recommendations.models import ActionableRecommendation


def test_recommendation_generation_for_engagement_finding():
    """Verifies that an EngagementFinding produces an ActionableRecommendation with all required fields."""
    finding = EngagementFinding(
        id="ENG-008",
        category="engagement",
        title="Homepage lacks a clear primary call-to-action (CTA)",
        severity=SeverityLevel.HIGH,
        confidence=0.91,
        evidence="Homepage has 0 action links.",
        affected_urls=["https://example.com/"],
        suggested_action=FindingAction(
            summary="Add a clearly identifiable primary CTA button near the hero value proposition.",
            priority=SeverityLevel.HIGH,
        ),
    )
    rec = RecommendationEngine.generate_recommendation(finding)

    assert isinstance(rec, ActionableRecommendation)
    assert rec.finding_id == "ENG-008"
    assert rec.category == "engagement"
    assert rec.priority == SeverityLevel.HIGH
    assert rec.where_it_occurs == ["https://example.com/"]

    # Verify actionable recommendation structure
    assert rec.what_is_wrong
    assert rec.what_should_be_changed
    assert rec.why_it_matters
    assert rec.verification_steps
    assert "Re-run the engagement audit" in rec.verification_steps


def test_recommendation_generation_for_member2_finding():
    """Verifies that Member 2 findings produce actionable recommendations."""
    finding = Finding(
        id="EC-003",
        category="entity",
        title="Missing Schema.org structured data",
        severity=SeverityLevel.HIGH,
        confidence=0.92,
        evidence="No Schema.org Organization tag found.",
        affected_urls=["https://example.com/"],
        suggested_action=FindingAction(
            summary="Add Schema.org Organization markup in JSON-LD.",
            priority=SeverityLevel.HIGH,
        ),
    )
    rec = RecommendationEngine.generate_recommendation(finding)

    assert rec.finding_id == "EC-003"
    assert rec.category == "entity"
    assert "JSON-LD" in rec.what_should_be_changed
    assert "re-run the entity audit" in rec.verification_steps.lower() or "rich results" in rec.verification_steps.lower()


def test_recommendations_batch_sorting_and_deduplication():
    """Verifies that batch recommendation generation deduplicates by finding ID and sorts by priority."""
    f1 = EngagementFinding(
        id="ENG-007",
        category="engagement",
        title="Dense body content lacks subheadings",
        severity=SeverityLevel.LOW,
        confidence=0.80,
        evidence="Text block.",
        affected_urls=["https://example.com/terms"],
        suggested_action=FindingAction(summary="Add H2 headings.", priority=SeverityLevel.LOW),
    )
    f2 = EngagementFinding(
        id="ENG-001",
        category="engagement",
        title="Homepage orientation lacks clear purpose",
        severity=SeverityLevel.HIGH,
        confidence=0.92,
        evidence="Generic title.",
        affected_urls=["https://example.com/"],
        suggested_action=FindingAction(summary="Fix title.", priority=SeverityLevel.HIGH),
    )
    # Duplicate f2
    f2_dup = EngagementFinding(
        id="ENG-001",
        category="engagement",
        title="Homepage orientation lacks clear purpose",
        severity=SeverityLevel.HIGH,
        confidence=0.92,
        evidence="Generic title on mirror.",
        affected_urls=["https://example.com/home"],
        suggested_action=FindingAction(summary="Fix title.", priority=SeverityLevel.HIGH),
    )

    recs = RecommendationEngine.generate_recommendations([f1, f2, f2_dup])
    assert len(recs) == 2  # Deduplicated from 3 to 2
    # Highest priority (HIGH) comes first
    assert recs[0].finding_id == "ENG-001"
    assert recs[1].finding_id == "ENG-007"
