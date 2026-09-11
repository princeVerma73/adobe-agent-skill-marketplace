"""Tests for information freshness and temporal decay."""

import json
from pathlib import Path
from src.entity_trust.contracts.schemas import SiteSnapshot
from src.entity_trust.core.html_parser import parse_page_html
from src.entity_trust.audits.freshness_audit import audit_freshness


FIXTURES_DIR = (
    Path(__file__).parent / "fixtures"
    if (Path(__file__).parent / "fixtures").exists()
    else Path(__file__).parent.parent / "fixtures"
)


def test_stale_copyright_and_announcements():
    with open(FIXTURES_DIR / "stale_content_site.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    snapshot = SiteSnapshot.model_validate(data)
    parsed_pages = [parse_page_html(p.url, p.html, p.text) for p in snapshot.all_pages()]

    findings = audit_freshness(snapshot, parsed_pages, current_year=2026)
    finding_ids = [f.id for f in findings]

    assert "FR-001" in finding_ids  # Stale copyright (2021 vs 2026 -> 5 years lag)
    assert "FR-002" in finding_ids  # Stale news (2020 vs 2026 -> 6 years lag)

    fr001 = next(f for f in findings if f.id == "FR-001")
    assert "2021" in fr001.evidence
    assert fr001.confidence >= 0.85
