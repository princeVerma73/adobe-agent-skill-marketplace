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


def test_trailing_slash_canonicalization_redirect_integration():
    """Verifies that SafeHTTPClient follows trailing-slash canonicalization redirects without false loop."""
    import httpx
    from src.crawler.http import SafeHTTPClient

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if url_str == "https://fastapi.example.com/de":
            return httpx.Response(308, headers={"Location": "https://fastapi.example.com/de/"})
        elif url_str == "https://fastapi.example.com/de/":
            return httpx.Response(200, text="<html><body><h1>German Docs</h1></body></html>", headers={"Content-Type": "text/html"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = SafeHTTPClient(transport=transport, verify_dns=False)
    resp = client.get("https://fastapi.example.com/de")

    assert resp.success is True
    assert resp.status_code == 200
    assert "German Docs" in resp.text
    assert resp.redirect_chain == ["https://fastapi.example.com/de", "https://fastapi.example.com/de/"]


def test_sitemap_partial_sample_suppresses_false_positives():
    """Verifies that PAGE_NOT_IN_SITEMAP is not falsely emitted when only a partial sample is available."""
    from src.inspection.models import PageInspection, SiteInspection, SitemapInspection
    from src.inspection.technical import inspect_page_technical

    page = PageInspection(
        url="https://example.com/item-500",
        original_url="https://example.com/item-500",
        status_code=200,
        title="Item 500",
        body_text="Description for item 500 with sufficient length for inspection.",
    )
    site = SiteInspection(
        site="example.com",
        root_url="https://example.com",
        sitemap=SitemapInspection(
            checked=True,
            found=True,
            total_discovered_urls=1000,
            sample_urls=["https://example.com/item-1", "https://example.com/item-2"],
        ),
        pages=[page],
    )

    issues = inspect_page_technical(page, site_inspection=site)
    assert not any(i.code == "PAGE_NOT_IN_SITEMAP" for i in issues)


def test_cross_skill_heading_deduplication():
    """Verifies that duplicate heading issues across Member 1 and Member 3 are merged cleanly."""
    from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
    from src.report.deduplicator import deduplicate_findings
    from src.report.models import ReportFinding

    f1 = ReportFinding(
        id="TECH-MISSING_H1",
        category="technical",
        title="Page lacks an H1 main heading tag.",
        severity=SeverityLevel.MEDIUM,
        confidence=0.96,
        evidence="Page 'https://example.com/sub' reported MISSING_H1",
        affected_urls=["https://example.com/sub"],
        suggested_action=FindingAction(summary="Add H1", priority=SeverityLevel.MEDIUM),
    )
    f2 = ReportFinding(
        id="ENG-016",
        category="engagement",
        title="Direct landing page lacks clear orienting H1 heading",
        severity=SeverityLevel.MEDIUM,
        confidence=0.87,
        evidence="Page 'https://example.com/sub' does not have an <h1> heading",
        affected_urls=["https://example.com/sub"],
        suggested_action=FindingAction(summary="Add H1", priority=SeverityLevel.MEDIUM),
    )

    deduped = deduplicate_findings([f1, f2])
    assert len(deduped) == 1
    assert deduped[0].id == "TECH-MISSING_H1"
    assert deduped[0].confidence == 0.96

