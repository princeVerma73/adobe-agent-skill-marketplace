"""Tests for resilient error handling and graceful degradation in the orchestrator."""

from unittest.mock import patch
import pytest

from src.entity_trust.contracts.schemas import EntityProfile
from src.inspection.models import PageInspection, SiteInspection
from src.report.models import FinalAuditReport
from src.report.orchestrator import AuditOrchestrator


@pytest.fixture
def minimal_inspection() -> SiteInspection:
    return SiteInspection(
        site="broken.com",
        root_url="https://broken.com/",
        pages=[PageInspection(url="https://broken.com/", original_url="https://broken.com", status_code=200)],
    )


def test_graceful_failure_when_member2_crashes(minimal_inspection: SiteInspection):
    """Verifies that if Member 2 raises an exception, Member 1 & 3 findings are preserved."""
    with patch("src.report.orchestrator.audit_entity_trust", side_effect=RuntimeError("Member 2 simulated crash")):
        orchestrator = AuditOrchestrator()
        report = orchestrator.run_audit(minimal_inspection)

        assert isinstance(report, FinalAuditReport)
        assert report.status == "partial_failure"
        assert "error: Member 2 simulated crash" in report.skill_statuses["entity-content-freshness-trust"]
        # Member 3 still succeeded
        assert report.skill_statuses["engagement-recommendations"] == "success"


def test_graceful_failure_when_member3_crashes(minimal_inspection: SiteInspection):
    """Verifies that if Member 3 raises an exception, Member 1 & 2 findings are preserved."""
    with patch("src.report.orchestrator.audit_engagement", side_effect=ValueError("Member 3 simulated error")):
        orchestrator = AuditOrchestrator()
        report = orchestrator.run_audit(minimal_inspection)

        assert isinstance(report, FinalAuditReport)
        assert report.status == "partial_failure"
        assert "error: Member 3 simulated error" in report.skill_statuses["engagement-recommendations"]
        assert report.skill_statuses["entity-content-freshness-trust"] == "success"


def test_graceful_failure_when_inspection_fails():
    """Verifies that if Member 1 inspection throws an unhandled error, an error report is returned."""
    with patch("src.report.orchestrator.inspect_site", side_effect=ConnectionError("DNS lookup failed")):
        orchestrator = AuditOrchestrator()
        report = orchestrator.run_audit("https://unreachable-domain-xyz.test")

        assert isinstance(report, FinalAuditReport)
        assert report.status == "error"
        assert "error" in report.skill_statuses["crawl-render-audit"]
        assert "skipped" in report.skill_statuses["entity-content-freshness-trust"]
        assert "skipped" in report.skill_statuses["engagement-recommendations"]
