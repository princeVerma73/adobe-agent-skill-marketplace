"""Phase 9D Regression Tests — Editorial & Third-Party Date Extraction False Positives.

Deterministic local tests verifying:
1. Editorial news articles mentioning third-party dates/years (e.g. "since 1997" at Microsoft) do NOT produce false CO-001.
2. NEGATIVE TEST: Genuine same-entity founding year contradictions across authoritative pages MUST still produce CO-001.
3. Third-party editorial pricing tests continue to pass.
"""

import pytest
from src.entity_trust.contracts.schemas import SiteSnapshot, PageSnapshot
from src.entity_trust.runner import audit_content_and_entity


def test_third_party_editorial_date_no_conflict_theverge():
    """FIX: Editorial article quoting third-party career dates ('since 1997') must not trigger CO-001."""
    payload = {
        "site": "theverge.com",
        "homepage": {
            "url": "https://www.theverge.com/",
            "title": "The Verge",
            "text": "The Verge covers the future of technology, science, art, and culture.",
            "html": "<html><head><title>The Verge</title></head><body><h1>The Verge</h1><p>Founded in 2011.</p></body></html>",
            "images": [],
            "structured_data": [
                {
                    "@type": "Organization",
                    "name": "The Verge",
                    "foundingDate": "2011-11-01",
                }
            ],
        },
        "pages": [
            {
                "url": "https://www.theverge.com/news/993791/microsoft-frank-shaw-leaving-head-of-comms",
                "title": "Microsoft Comms Head Leaving",
                "text": "Shaw has been at the heart of Microsoft’s communications since 1997, helping the company navigate Windows and Office.",
                "html": "<html><head><title>Microsoft Comms</title></head><body><p>Shaw has been at the heart of Microsoft’s communications since 1997...</p></body></html>",
            },
            {
                "url": "https://www.theverge.com/tech/994087/matt-mullenweg-automattic-ceo-return",
                "title": "Automattic Leadership",
                "text": "Automattic, founded in 2005, operates WordPress.com and other digital products.",
                "html": "<html><body><p>Automattic, founded in 2005, operates WordPress.com</p></body></html>",
            }
        ],
        "structured_data": [],
        "metadata": {},
        "crawl_metadata": {"pages_crawled": 3},
    }

    result = audit_content_and_entity(payload)
    co001_findings = [f for f in result.findings if f.id.startswith("CO-") and "founding" in f.title.lower()]
    assert len(co001_findings) == 0, f"Expected 0 false CO-001 founding year contradictions, got: {[f.evidence for f in co001_findings]}"


def test_genuine_same_entity_founding_year_contradiction_must_fire_co001():
    """NEGATIVE TEST: Genuine conflicting founding dates for the audited entity MUST produce CO-001."""
    payload = {
        "site": "theverge.com",
        "homepage": {
            "url": "https://www.theverge.com/",
            "title": "The Verge",
            "text": "The Verge is a technology publication.",
            "html": "<html><head><title>The Verge</title></head><body><h1>The Verge</h1></body></html>",
            "images": [],
            "structured_data": [
                {
                    "@type": "Organization",
                    "name": "The Verge",
                    "foundingDate": "2011-11-01",
                }
            ],
        },
        "pages": [
            {
                "url": "https://www.theverge.com/about/",
                "title": "About The Verge",
                "text": "The Verge was founded in 2018 by Vox Media to provide tech reviews and culture analysis.",
                "html": "<html><body><h1>About Us</h1><p>The Verge was founded in 2018 by Vox Media...</p></body></html>",
            }
        ],
        "structured_data": [],
        "metadata": {},
        "crawl_metadata": {"pages_crawled": 2},
    }

    result = audit_content_and_entity(payload)
    co001_findings = [f for f in result.findings if f.id.startswith("CO-") and "founding" in f.title.lower()]
    assert len(co001_findings) >= 1, "Expected CO-001 to fire for genuine same-entity founding year contradiction!"
    assert any("2011" in f.evidence and "2018" in f.evidence for f in co001_findings)
