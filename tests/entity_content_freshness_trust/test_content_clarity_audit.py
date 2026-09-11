"""Tests for content clarity, facts in images, and missing core attributes."""

import json
from pathlib import Path
from src.entity_trust.contracts.schemas import SiteSnapshot
from src.entity_trust.core.html_parser import parse_page_html
from src.entity_trust.audits.content_clarity_audit import audit_content_clarity


FIXTURES_DIR = (
    Path(__file__).parent / "fixtures"
    if (Path(__file__).parent / "fixtures").exists()
    else Path(__file__).parent.parent / "fixtures"
)


def test_facts_locked_in_images_detection():
    with open(FIXTURES_DIR / "facts_in_images_site.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    snapshot = SiteSnapshot.model_validate(data)
    parsed_pages = [parse_page_html(p.url, p.html, p.text, pre_extracted_images=p.images) for p in snapshot.all_pages()]

    findings = audit_content_clarity(snapshot, parsed_pages)
    finding_ids = [f.id for f in findings]

    assert "CC-001" in finding_ids
    cc001 = next(f for f in findings if f.id == "CC-001")
    assert "infographic-customer-metrics.png" in cc001.evidence
    assert cc001.severity == "high"


def test_vague_claims_and_missing_attributes():
    with open(FIXTURES_DIR / "ambiguous_entity_site.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    snapshot = SiteSnapshot.model_validate(data)
    parsed_pages = [parse_page_html(p.url, p.html, p.text) for p in snapshot.all_pages()]

    findings = audit_content_clarity(snapshot, parsed_pages)
    finding_ids = [f.id for f in findings]

    assert "CC-002" in finding_ids  # Vague claims
    assert "CC-003" in finding_ids  # Missing contact/location
