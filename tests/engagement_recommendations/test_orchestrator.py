"""Tests for Master Audit Orchestrator execution and skill merging."""

from datetime import datetime, timezone
import pytest

from src.entity_trust.contracts.schemas import SeverityLevel
from src.inspection.models import (
    Heading,
    Link,
    PageInspection,
    PageMetadata,
    SiteInspection,
    TechnicalIssue,
)
from src.report.models import FinalAuditReport
from src.report.orchestrator import AuditOrchestrator, run_full_audit


@pytest.fixture
def mock_inspection_fixture() -> SiteInspection:
    """Fixture creating a realistic multi-page inspection with issues across all 3 member areas."""
    hp = PageInspection(
        url="https://acmeai.io/",
        original_url="https://acmeai.io",
        status_code=200,
        title="Acme AI - Document Processing",
        body_text="Acme AI provides automated document intelligence solutions. Established in 2021 in Seattle, WA. Contact us at support@acmeai.io.",
        headings=[
            Heading(level=1, text="Acme AI Document Platform"),
            Heading(level=3, text="Architecture Overview"),  # Skips H2 (ENG-005)
        ],
        metadata=PageMetadata(
            title="Acme AI - Document Processing",
            description="Document processing AI for banking.",
        ),
        links=[
            Link(url="https://acmeai.io/pricing", text="Pricing", is_internal=True),
        ],  # Lacks primary CTA button (ENG-008)
        structured_data=[
            {
                "@type": "Organization",
                "name": "Acme AI Inc",
                "url": "https://acmeai.io",
                "foundingDate": "2021",
            }
        ],
    )

    pricing = PageInspection(
        url="https://acmeai.io/pricing",
        original_url="https://acmeai.io/pricing",
        status_code=404,  # Technical 404 (Member 1)
        title="Pricing | Acme AI",
        technical_issues=[
            TechnicalIssue(
                code="HTTP_NOT_FOUND",
                message="Page returned HTTP 404 Not Found.",
                severity="error",
            )
        ],
    )

    return SiteInspection(
        site="acmeai.io",
        root_url="https://acmeai.io/",
        audited_at=datetime.now(timezone.utc),
        pages=[hp, pricing],
    )


def test_orchestrator_runs_and_merges_all_skills(mock_inspection_fixture: SiteInspection):
    """Verifies that the orchestrator merges M1 technical, M2 trust, and M3 engagement findings."""
    orchestrator = AuditOrchestrator(confidence_threshold=0.70)
    report = orchestrator.run_audit(mock_inspection_fixture)

    assert isinstance(report, FinalAuditReport)
    assert report.site == "acmeai.io"
    assert report.status == "success"

    # Verify all skills participated
    assert report.skill_statuses["crawl-render-audit"] == "success"
    assert report.skill_statuses["entity-content-freshness-trust"] == "success"
    assert report.skill_statuses["engagement-recommendations"] == "success"

    # Verify presence of findings across multiple categories
    categories = {f.category for f in report.findings}
    assert "technical" in categories
    assert "engagement" in categories

    # Entity Profile extracted
    assert report.entity_profile is not None
    assert report.entity_profile.name == "Acme AI Inc"

    # Actionable recommendations attached
    assert len(report.recommendations) > 0
    for rec in report.recommendations:
        assert rec.what_is_wrong
        assert rec.what_should_be_changed
        assert rec.verification_steps


def test_orchestrator_functional_entrypoint(mock_inspection_fixture: SiteInspection):
    """Verifies the run_full_audit convenience function."""
    report = run_full_audit(mock_inspection_fixture, confidence_threshold=0.75)
    assert isinstance(report, FinalAuditReport)
    assert report.site == "acmeai.io"
    assert report.overall_score <= 100.0
