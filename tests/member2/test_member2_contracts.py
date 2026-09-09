"""Tests for contract schemas and serialization."""

import pytest
from member2.contracts.schemas import (
    CategoryType,
    ContentEntityAuditResult,
    Finding,
    FindingAction,
    PageSnapshot,
    SeverityLevel,
    SiteSnapshot,
)


def test_site_snapshot_pages_aggregation():
    homepage = PageSnapshot(url="https://example.com/", title="Home")
    page1 = PageSnapshot(url="https://example.com/about", title="About")
    page2 = PageSnapshot(url="https://example.com/", title="Duplicate Home")

    site = SiteSnapshot(
        site="example.com",
        homepage=homepage,
        pages=[page1, page2],
    )

    all_pages = site.all_pages()
    assert len(all_pages) == 2
    assert all_pages[0].url == "https://example.com/"
    assert all_pages[1].url == "https://example.com/about"


def test_finding_adobe_contract_fields():
    finding = Finding(
        id="EC-001",
        category=CategoryType.ENTITY,
        title="Unclear brand identity",
        severity=SeverityLevel.HIGH,
        confidence=0.91,
        evidence="Homepage lacks descriptive title and H1.",
        affected_urls=["https://example.com/"],
        suggested_action=FindingAction(
            summary="Update title and H1.",
            priority=SeverityLevel.HIGH,
        ),
    )

    data = finding.model_dump()
    assert data["id"] == "EC-001"
    assert data["title"] == "Unclear brand identity"
    assert data["severity"] == "high"
    assert "evidence" in data
    assert "suggested_action" in data
    assert data["suggested_action"]["summary"] == "Update title and H1."


def test_audit_result_serialization():
    result = ContentEntityAuditResult(
        skill="entity-content-freshness-trust",
        status="success",
        site="example.com",
        total_findings=0,
    )
    json_str = result.model_dump_json()
    assert "entity-content-freshness-trust" in json_str
    assert "severity_counts" in json_str


def test_site_snapshot_from_site_inspection():
    inspection_dict = {
        "site": "testbrand.com",
        "root_url": "https://testbrand.com/",
        "pages": [
            {
                "url": "https://testbrand.com/",
                "title": "Test Brand Homepage",
                "body_text": "We are Test Brand providing AI solutions.",
                "headings": [{"level": 1, "text": "Test Brand AI"}],
                "metadata": {"description": "Test Brand official site"},
                "structured_data": [{"@type": "Organization", "name": "Test Brand"}],
                "links": [{"url": "https://testbrand.com/about"}],
            },
            {
                "url": "https://testbrand.com/about",
                "title": "About Test Brand",
                "body_text": "Founded in 2021 in San Francisco.",
                "headings": [{"level": 1, "text": "About Us"}],
                "metadata": {},
                "structured_data": [],
                "links": [],
            },
        ],
    }

    snapshot = SiteSnapshot.from_site_inspection(inspection_dict)
    assert snapshot.site == "testbrand.com"
    assert snapshot.homepage.url == "https://testbrand.com/"
    assert snapshot.homepage.title == "Test Brand Homepage"
    assert len(snapshot.pages) == 1
    assert snapshot.pages[0].url == "https://testbrand.com/about"
    assert len(snapshot.all_pages()) == 2

