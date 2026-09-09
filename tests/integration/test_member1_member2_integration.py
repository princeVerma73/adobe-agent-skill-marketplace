"""Integration contract test: Member 1 (SiteInspection) -> Member 2 (audit_entity_trust)."""

from datetime import datetime, timezone
import pytest

from src.inspection.models import (
    Heading,
    Link,
    PageInspection,
    PageMetadata,
    SiteInspection,
    TechnicalIssue,
)
from src.entity_trust import audit_entity_trust, ContentEntityAuditResult, SeverityLevel


@pytest.fixture
def mock_site_inspection() -> SiteInspection:
    """Realistic multi-page SiteInspection observation produced by Member 1."""
    homepage = PageInspection(
        url="https://novastack.io/",
        original_url="https://novastack.io",
        status_code=200,
        title="NovaStack | Enterprise Distributed Cloud Database",
        body_text="NovaStack provides distributed cloud database solutions for global enterprises. Founded in 2021 in Seattle, WA. Contact us at support@novastack.io.",
        headings=[
            Heading(level=1, text="NovaStack Cloud Database"),
            Heading(level=2, text="High Availability & Scale"),
        ],
        metadata=PageMetadata(
            title="NovaStack | Enterprise Distributed Cloud Database",
            description="NovaStack is an enterprise cloud database provider.",
            open_graph={"og:site_name": "NovaStack", "og:description": "Distributed database for modern enterprises."},
        ),
        links=[
            Link(url="https://novastack.io/pricing", text="Pricing", is_internal=True),
            Link(url="https://novastack.io/about", text="About", is_internal=True),
        ],
        structured_data=[
            {
                "@context": "https://schema.org",
                "@type": "Organization",
                "name": "NovaStack Inc",
                "url": "https://novastack.io",
                "foundingDate": "2021",
                "address": {
                    "addressLocality": "Seattle",
                    "addressRegion": "WA",
                    "addressCountry": "USA",
                },
                "email": "support@novastack.io",
            }
        ],
    )

    pricing_page = PageInspection(
        url="https://novastack.io/pricing",
        original_url="https://novastack.io/pricing",
        status_code=200,
        title="Pricing | NovaStack",
        body_text="Simple transparent pricing. Starter plan starting from $49/mo. Enterprise custom quote.",
        headings=[Heading(level=1, text="NovaStack Pricing Plans")],
        metadata=PageMetadata(title="Pricing | NovaStack"),
        links=[Link(url="https://novastack.io/", text="Home", is_internal=True)],
        structured_data=[],
    )

    return SiteInspection(
        site="novastack.io",
        root_url="https://novastack.io/",
        audited_at=datetime.now(timezone.utc),
        total_duration_ms=450.0,
        pages=[homepage, pricing_page],
        summary_counts={"total_pages": 2, "error_pages": 0},
    )


def test_member1_to_member2_direct_ingestion(mock_site_inspection: SiteInspection):
    """Verifies that Member 2 consumes Member 1's SiteInspection without error."""
    result = audit_entity_trust(mock_site_inspection)

    assert isinstance(result, ContentEntityAuditResult)
    assert result.status == "success"
    assert result.site == "novastack.io"
    assert result.skill == "entity-content-freshness-trust"

    # Entity Profile extracted from Member 1 structured data and body text
    profile = result.entity_profile
    assert profile is not None
    assert profile.name == "NovaStack Inc"
    assert profile.industry in ("cloud computing", "software", None)

    # Validate findings contract
    for finding in result.findings:
        assert finding.id.startswith(("EC-", "CC-", "FR-", "CO-"))
        assert finding.severity in SeverityLevel
        assert finding.confidence >= 0.70
        assert len(finding.evidence) > 0
        assert finding.suggested_action.summary
        assert len(finding.affected_urls) > 0


def test_member1_to_member2_serialized_dict_ingestion(mock_site_inspection: SiteInspection):
    """Verifies that Member 2 consumes serialized dict of Member 1's SiteInspection."""
    inspection_dict = mock_site_inspection.model_dump()
    result = audit_entity_trust(inspection_dict)

    assert isinstance(result, ContentEntityAuditResult)
    assert result.site == "novastack.io"
    assert result.status == "success"
    assert result.entity_profile.name == "NovaStack Inc"
