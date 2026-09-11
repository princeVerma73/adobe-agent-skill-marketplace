"""Unit tests for shared Pydantic data models."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from src.inspection.models import (
    Heading,
    Link,
    PageInspection,
    PageMetadata,
    RobotsTxtInspection,
    SiteInspection,
    SitemapInspection,
    TechnicalIssue,
)


class TestModelsMinimalAndDefaults:
    """Test minimal construction and default values across all models."""

    def test_heading_model(self):
        heading = Heading(level=2, text="Main Section")
        assert heading.level == 2
        assert heading.text == "Main Section"

    def test_heading_level_validation(self):
        with pytest.raises(ValidationError):
            Heading(level=0, text="Invalid")
        with pytest.raises(ValidationError):
            Heading(level=7, text="Invalid")

    def test_link_defaults(self):
        link = Link(url="https://example.com/about")
        assert link.url == "https://example.com/about"
        assert link.text == ""
        assert link.is_internal is True
        assert link.rel is None

    def test_page_metadata_defaults(self):
        meta = PageMetadata()
        assert meta.title is None
        assert meta.description is None
        assert meta.canonical_url is None
        assert meta.robots_meta is None
        assert meta.open_graph == {}
        assert meta.twitter_card == {}
        assert meta.extra == {}

        # Ensure default factories are independent instances
        meta2 = PageMetadata()
        meta.open_graph["og:title"] = "Test"
        assert "og:title" not in meta2.open_graph

    def test_technical_issue_defaults(self):
        issue = TechnicalIssue(code="MISSING_H1", message="Page lacks an H1 tag")
        assert issue.code == "MISSING_H1"
        assert issue.message == "Page lacks an H1 tag"
        assert issue.severity == "warning"
        assert issue.details == {}

    def test_robots_txt_inspection_defaults(self):
        robots = RobotsTxtInspection()
        assert robots.checked is False
        assert robots.found is False
        assert robots.status_code is None
        assert robots.allowed_for_agent is True
        assert robots.sitemap_urls == []
        assert robots.crawl_delay is None
        assert robots.raw_text is None

    def test_sitemap_inspection_defaults(self):
        sitemap = SitemapInspection()
        assert sitemap.checked is False
        assert sitemap.found is False
        assert sitemap.status_code is None
        assert sitemap.discovered_sitemap_urls == []
        assert sitemap.total_discovered_urls == 0
        assert sitemap.sample_urls == []
        assert sitemap.raw_content is None


class TestPageAndSiteInspectionModels:
    """Test PageInspection and SiteInspection nested models and full lifecycle."""

    def test_minimal_page_inspection(self):
        page = PageInspection(
            url="https://example.com/products",
            original_url="example.com/products",
        )
        assert page.url == "https://example.com/products"
        assert page.original_url == "example.com/products"
        assert page.status_code is None
        assert page.crawl_depth == 0
        assert page.allowed_by_robots is True
        assert page.is_rendered is False
        assert page.raw_html_available is False
        assert page.rendered_text is None
        assert page.source_text is None
        assert page.title is None
        assert page.headings == []
        assert page.links == []
        assert page.structured_data == []
        assert page.technical_issues == []
        assert isinstance(page.metadata, PageMetadata)

    def test_fully_populated_page_inspection(self):
        page = PageInspection(
            url="https://example.com/products",
            original_url="http://example.com/products",
            status_code=200,
            content_type="text/html; charset=utf-8",
            response_time_ms=145.2,
            redirect_chain=["http://example.com/products", "https://example.com/products"],
            crawl_depth=1,
            allowed_by_robots=True,
            is_rendered=True,
            raw_html_available=True,
            rendered_text="Product Catalog",
            source_text="Product Catalog Raw",
            title="Products - Example Inc.",
            metadata=PageMetadata(
                title="Products - Example Inc.",
                description="Browse our items",
                canonical_url="https://example.com/products",
                open_graph={"og:type": "product"},
            ),
            headings=[
                Heading(level=1, text="Catalog"),
                Heading(level=2, text="Featured Items"),
            ],
            body_text="Catalog content details...",
            links=[
                Link(url="https://example.com/item/1", text="Item 1", is_internal=True),
                Link(url="https://external.com", text="Partner", is_internal=False, rel="nofollow"),
            ],
            structured_data=[
                {"@context": "https://schema.org", "@type": "Product", "name": "Item 1"}
            ],
            technical_issues=[
                TechnicalIssue(code="SLOW_TTFB", message="Page took over 100ms", severity="info")
            ],
        )

        assert page.status_code == 200
        assert len(page.headings) == 2
        assert len(page.links) == 2
        assert len(page.structured_data) == 1
        assert len(page.technical_issues) == 1
        assert page.metadata.open_graph["og:type"] == "product"

    def test_minimal_site_inspection(self):
        site = SiteInspection(
            site="example.com",
            root_url="https://example.com",
        )
        assert site.site == "example.com"
        assert site.root_url == "https://example.com"
        assert isinstance(site.audited_at, datetime)
        assert site.total_duration_ms is None
        assert isinstance(site.robots, RobotsTxtInspection)
        assert isinstance(site.sitemap, SitemapInspection)
        assert site.pages == []
        assert site.summary_counts == {}

    def test_json_serialization_and_deserialization(self):
        page = PageInspection(
            url="https://example.com",
            original_url="https://example.com",
            status_code=200,
            title="Home",
            headings=[Heading(level=1, text="Welcome")],
            technical_issues=[TechnicalIssue(code="TEST", message="Test issue")],
        )

        site = SiteInspection(
            site="example.com",
            root_url="https://example.com",
            audited_at=datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc),
            total_duration_ms=520.5,
            robots=RobotsTxtInspection(checked=True, found=True, status_code=200),
            sitemap=SitemapInspection(checked=True, found=True, total_discovered_urls=10),
            pages=[page],
            summary_counts={"total_pages": 1, "issues_count": 1},
        )

        json_data = site.model_dump_json()
        assert isinstance(json_data, str)
        assert "example.com" in json_data
        assert "Welcome" in json_data

        # Verify round-trip deserialization
        restored = SiteInspection.model_validate_json(json_data)
        assert restored.site == "example.com"
        assert len(restored.pages) == 1
        assert restored.pages[0].headings[0].text == "Welcome"
        assert restored.robots.status_code == 200
        assert restored.sitemap.total_discovered_urls == 10
        assert restored.total_duration_ms == 520.5

    def test_missing_required_fields_raises_validation_error(self):
        with pytest.raises(ValidationError):
            PageInspection()  # url and original_url are required

        with pytest.raises(ValidationError):
            SiteInspection()  # site and root_url are required
