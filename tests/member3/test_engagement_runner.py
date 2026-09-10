"""Tests for Member 3 Engagement Audit runner and finding contract."""

from datetime import datetime, timezone
import pytest

from src.engagement.models import EngagementAuditResult, EngagementFinding
from src.engagement.runner import audit_engagement
from src.entity_trust.contracts.schemas import SeverityLevel, SiteSnapshot
from src.inspection.models import (
    Heading,
    Link,
    PageInspection,
    PageMetadata,
    SiteInspection,
)


@pytest.fixture
def sample_inspection() -> SiteInspection:
    """Creates a sample multi-page SiteInspection observation."""
    hp = PageInspection(
        url="https://testsite.com/",
        original_url="https://testsite.com",
        status_code=200,
        title="TestSite | AI Workflow Platform",
        body_text="TestSite automates enterprise workflow intelligence for Fortune 500 teams.",
        headings=[
            Heading(level=1, text="TestSite Platform"),
            Heading(level=2, text="Workflow Automation"),
        ],
        metadata=PageMetadata(
            title="TestSite | AI Workflow Platform",
            description="Enterprise workflow automation.",
        ),
        links=[
            Link(url="https://testsite.com/pricing", text="View Pricing", is_internal=True),
            Link(url="https://testsite.com/contact", text="Contact Us", is_internal=True),
        ],
    )
    pricing = PageInspection(
        url="https://testsite.com/pricing",
        original_url="https://testsite.com/pricing",
        status_code=200,
        title="Pricing Plans | TestSite",
        body_text="Simple transparent pricing plans.",
        headings=[Heading(level=1, text="Pricing Plans")],
        links=[Link(url="https://testsite.com/", text="Home", is_internal=True)],
    )
    return SiteInspection(
        site="testsite.com",
        root_url="https://testsite.com/",
        audited_at=datetime.now(timezone.utc),
        pages=[hp, pricing],
    )


def test_audit_engagement_with_site_inspection(sample_inspection: SiteInspection):
    """Verifies that audit_engagement ingests Member 1 SiteInspection without error."""
    result = audit_engagement(sample_inspection)
    assert isinstance(result, EngagementAuditResult)
    assert result.site == "testsite.com"
    assert result.skill == "engagement-recommendations"
    assert result.status == "success"
    assert isinstance(result.findings, list)

    # Standard finding contract verification
    for f in result.findings:
        assert isinstance(f, EngagementFinding)
        assert f.id.startswith("ENG-")
        assert f.category == "engagement"
        assert f.title
        assert f.severity in (SeverityLevel.CRITICAL, SeverityLevel.HIGH, SeverityLevel.MEDIUM, SeverityLevel.LOW, SeverityLevel.INFO)
        assert 0.0 <= f.confidence <= 1.0
        assert f.evidence
        assert isinstance(f.affected_urls, list)
        assert f.suggested_action.summary
        assert f.suggested_action.priority in SeverityLevel


def test_audit_engagement_with_site_snapshot(sample_inspection: SiteInspection):
    """Verifies that audit_engagement ingests SiteSnapshot objects."""
    snapshot = SiteSnapshot.from_site_inspection(sample_inspection)
    result = audit_engagement(snapshot)
    assert isinstance(result, EngagementAuditResult)
    assert result.site == "testsite.com"


def test_audit_engagement_with_serialized_dict(sample_inspection: SiteInspection):
    """Verifies that audit_engagement ingests serialized dictionary snapshots."""
    inspection_dict = sample_inspection.model_dump()
    result = audit_engagement(inspection_dict)
    assert isinstance(result, EngagementAuditResult)
    assert result.site == "testsite.com"


def test_audit_engagement_confidence_threshold_filter(sample_inspection: SiteInspection):
    """Verifies that confidence_threshold correctly filters low-confidence findings."""
    result_low_thresh = audit_engagement(sample_inspection, confidence_threshold=0.50)
    result_high_thresh = audit_engagement(sample_inspection, confidence_threshold=0.99)
    assert result_low_thresh.total_findings >= result_high_thresh.total_findings
    for f in result_high_thresh.findings:
        assert f.confidence >= 0.99


def test_audit_engagement_metrics_calculation(sample_inspection: SiteInspection):
    """Verifies that quantitative engagement metrics are computed accurately."""
    result = audit_engagement(sample_inspection)
    m = result.metrics
    assert m.pages_audited == 2
    assert m.internal_link_count >= 2
    assert isinstance(m.has_homepage_cta, bool)
    assert isinstance(m.has_contact_channel, bool)
