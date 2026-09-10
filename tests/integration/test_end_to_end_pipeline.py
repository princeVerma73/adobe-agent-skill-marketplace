"""End-to-End Multi-Agent Pipeline Integration Tests across all repository fixtures."""

import json
from pathlib import Path
import pytest

from src.report.models import FinalAuditReport
from src.report.orchestrator import run_full_audit


FIXTURES_DIR = (
    Path(__file__).parent.parent / "fixtures"
    if (Path(__file__).parent.parent / "fixtures").exists()
    else Path(__file__).parent.parent / "member2" / "fixtures"
)


def load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


def test_e2e_clear_entity_site():
    data = load_fixture("clear_entity_site.json")
    report = run_full_audit(data)

    assert isinstance(report, FinalAuditReport)
    assert report.site == "acmecloud.ai"
    assert report.status == "success"
    assert report.entity_profile is not None
    assert report.entity_profile.name == "Acme Cloud AI"
    assert report.overall_score >= 60.0
    assert len(report.recommendations) > 0

    # Ensure Markdown renders without error
    md = report.to_markdown()
    assert "# Brand AI-Readiness Audit Report: acmecloud.ai" in md


def test_e2e_ambiguous_entity_site():
    data = load_fixture("ambiguous_entity_site.json")
    report = run_full_audit(data)

    assert isinstance(report, FinalAuditReport)
    assert report.site == "apexglobal.net"
    assert report.status == "success"
    # Should catch ambiguous entity issues and engagement issues
    assert report.severity_counts.high > 0
    categories = {f.category for f in report.findings}
    assert "entity" in categories or "engagement" in categories


def test_e2e_conflicting_facts_site():
    data = load_fixture("conflicting_facts_site.json")
    report = run_full_audit(data)

    assert isinstance(report, FinalAuditReport)
    assert report.site == "quantumtech.io"
    assert report.status == "success"
    categories = {f.category for f in report.findings}
    assert "consistency" in categories
    assert any("CO-" in f.id for f in report.findings)


def test_e2e_stale_content_site():
    data = load_fixture("stale_content_site.json")
    report = run_full_audit(data)

    assert isinstance(report, FinalAuditReport)
    assert report.site == "legacysystems.org"
    assert report.status == "success"
    categories = {f.category for f in report.findings}
    assert "freshness" in categories


def test_e2e_facts_in_images_site():
    data = load_fixture("facts_in_images_site.json")
    report = run_full_audit(data)

    assert isinstance(report, FinalAuditReport)
    assert report.site == "visualdata.io"
    assert report.status == "success"
    assert any(f.id == "CC-001" for f in report.findings)
