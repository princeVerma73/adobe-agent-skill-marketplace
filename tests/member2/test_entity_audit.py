"""Tests for entity identification and ambiguity detection."""

import json
from pathlib import Path
from member2.contracts.schemas import SiteSnapshot
from member2.core.html_parser import parse_page_html
from member2.audits.entity_audit import audit_entity


FIXTURES_DIR = (
    Path(__file__).parent / "fixtures"
    if (Path(__file__).parent / "fixtures").exists()
    else Path(__file__).parent.parent / "fixtures"
)


def test_clear_entity_detection():
    with open(FIXTURES_DIR / "clear_entity_site.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    snapshot = SiteSnapshot.model_validate(data)
    parsed_pages = [parse_page_html(p.url, p.html, p.text) for p in snapshot.all_pages()]

    findings, profile = audit_entity(snapshot, parsed_pages)

    assert profile.name == "Acme Cloud AI"
    assert profile.industry == "software"
    assert profile.confidence_score >= 0.90
    # No ambiguity findings on clear entity
    ambiguity_findings = [f for f in findings if f.id == "EC-002"]
    assert len(ambiguity_findings) == 0


def test_ambiguous_entity_detection():
    with open(FIXTURES_DIR / "ambiguous_entity_site.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    snapshot = SiteSnapshot.model_validate(data)
    parsed_pages = [parse_page_html(p.url, p.html, p.text) for p in snapshot.all_pages()]

    findings, profile = audit_entity(snapshot, parsed_pages)

    finding_ids = [f.id for f in findings]
    # Expect generic H1/title and lack of disambiguation
    assert "EC-001" in finding_ids
    assert "EC-002" in finding_ids
    assert "EC-003" in finding_ids
