"""End-to-end integration tests for member2 runner on all fixtures."""

import json
from pathlib import Path
from member2.runner import audit_content_and_entity
from member2.contracts.schemas import ContentEntityAuditResult


FIXTURES_DIR = (
    Path(__file__).parent / "fixtures"
    if (Path(__file__).parent / "fixtures").exists()
    else Path(__file__).parent.parent / "fixtures"
)


def test_runner_on_clear_entity():
    with open(FIXTURES_DIR / "clear_entity_site.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    result = audit_content_and_entity(data)
    assert isinstance(result, ContentEntityAuditResult)
    assert result.site == "acmecloud.ai"
    assert result.status == "success"
    assert result.entity_profile is not None
    assert result.entity_profile.name == "Acme Cloud AI"
    # Acme Cloud AI has clean data, no critical issues
    assert result.severity_counts.critical == 0


def test_runner_on_conflicting_facts():
    with open(FIXTURES_DIR / "conflicting_facts_site.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    result = audit_content_and_entity(data)
    assert result.site == "quantumtech.io"
    assert result.total_findings > 0

    categories = {f.category for f in result.findings}
    assert "consistency" in categories

    consistency_findings = [f for f in result.findings if f.category == "consistency"]
    assert len(consistency_findings) >= 2  # founding_year and headquarters/price conflicts


def test_runner_on_ambiguous_entity():
    with open(FIXTURES_DIR / "ambiguous_entity_site.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    result = audit_content_and_entity(data)
    assert result.site == "apexglobal.net"
    assert result.severity_counts.high > 0

    # Ensure every finding strictly conforms to Adobe mandatory fields
    for f in result.findings:
        assert f.id
        assert f.title
        assert f.severity in ("critical", "high", "medium", "low", "info")
        assert f.evidence
        assert f.suggested_action.summary
        assert f.suggested_action.priority


def test_runner_on_stale_content():
    with open(FIXTURES_DIR / "stale_content_site.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    result = audit_content_and_entity(data)
    assert result.site == "legacysystems.org"
    freshness_findings = [f for f in result.findings if f.category == "freshness"]
    assert len(freshness_findings) >= 2


def test_runner_on_facts_in_images():
    with open(FIXTURES_DIR / "facts_in_images_site.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    result = audit_content_and_entity(data)
    assert result.site == "visualdata.io"
    image_findings = [f for f in result.findings if f.id == "CC-001"]
    assert len(image_findings) == 1
