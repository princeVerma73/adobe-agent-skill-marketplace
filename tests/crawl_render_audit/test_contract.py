"""Contract verification tests for Member 1 inspection layer exports and interfaces."""

from src.inspection import (
    Heading,
    Link,
    PageInspection,
    PageMetadata,
    RobotsTxtInspection,
    SiteInspection,
    SitemapInspection,
    TechnicalIssue,
    extract_hostname,
    is_same_domain,
    is_same_site,
    is_valid_url,
    normalize_url,
)


def test_public_contract_imports_and_instantiation():
    """Verify that all public contracts can be imported and cleanly composed."""
    raw_url = "example.com/blog"
    norm_url = normalize_url(raw_url)
    assert norm_url == "https://example.com/blog"

    hostname = extract_hostname(norm_url)
    assert hostname == "example.com"

    page = PageInspection(
        url=norm_url,
        original_url=raw_url,
        title="Sample Blog",
        headings=[Heading(level=1, text="Blog Title")],
        links=[Link(url="https://example.com/item", text="Item", is_internal=True)],
        metadata=PageMetadata(title="Sample Blog", description="Demo description"),
        technical_issues=[TechnicalIssue(code="CONTRACT_CHECK", message="All good", severity="info")],
    )

    site = SiteInspection(
        site=hostname,
        root_url="https://example.com",
        robots=RobotsTxtInspection(checked=True, found=True),
        sitemap=SitemapInspection(checked=True, found=True),
        pages=[page],
    )

    assert site.site == "example.com"
    assert len(site.pages) == 1
    assert site.pages[0].url == "https://example.com/blog"
