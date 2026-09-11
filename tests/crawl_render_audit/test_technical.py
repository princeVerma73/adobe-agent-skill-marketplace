"""Deterministic unit tests for technical discoverability and SEO audit rules."""

import pytest
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
from src.inspection.technical import (
    audit_technical_discoverability,
    check_body_text_content,
    check_canonical,
    check_headings_h1,
    check_http_status,
    check_meta_description,
    check_redirect_chain,
    check_robots_blocking,
    check_sitemap_and_robots_discoverability,
    check_static_rendered_gap,
    check_title,
    inspect_page_technical,
)


class TestHttpStatusChecks:
    """Tests for HTTP status and reachability check."""

    def test_200_ok_returns_no_issue(self):
        page = PageInspection(url="https://example.com", original_url="https://example.com", status_code=200)
        issues = check_http_status(page)
        assert len(issues) == 0

    def test_404_not_found(self):
        page = PageInspection(url="https://example.com/missing", original_url="https://example.com/missing", status_code=404)
        issues = check_http_status(page)
        assert len(issues) == 1
        assert issues[0].code == "HTTP_NOT_FOUND"
        assert issues[0].severity == "error"

    def test_500_server_error(self):
        page = PageInspection(url="https://example.com/crash", original_url="https://example.com/crash", status_code=500)
        issues = check_http_status(page)
        assert len(issues) == 1
        assert issues[0].code == "HTTP_SERVER_ERROR"

    def test_403_client_error(self):
        page = PageInspection(url="https://example.com/forbidden", original_url="https://example.com/forbidden", status_code=403)
        issues = check_http_status(page)
        assert len(issues) == 1
        assert issues[0].code == "HTTP_CLIENT_ERROR"

    def test_unreachable_status_none(self):
        page = PageInspection(url="https://example.com/down", original_url="https://example.com/down", status_code=None)
        issues = check_http_status(page)
        assert len(issues) == 1
        assert issues[0].code == "HTTP_UNREACHABLE"


class TestRobotsBlockingChecks:
    """Tests for robots.txt disallow and robots meta tag directives."""

    def test_allowed_page_returns_no_issue(self):
        page = PageInspection(url="https://example.com", original_url="https://example.com", allowed_by_robots=True)
        assert len(check_robots_blocking(page)) == 0

    def test_robots_txt_disallowed(self):
        page = PageInspection(url="https://example.com/private", original_url="https://example.com/private", allowed_by_robots=False)
        issues = check_robots_blocking(page)
        assert len(issues) == 1
        assert issues[0].code == "ROBOTS_TXT_DISALLOWED"

    def test_robots_meta_noindex(self):
        page = PageInspection(
            url="https://example.com/hidden",
            original_url="https://example.com/hidden",
            metadata=PageMetadata(robots_meta="noindex, nofollow"),
        )
        issues = check_robots_blocking(page)
        assert any(i.code == "ROBOTS_META_NOINDEX" for i in issues)


class TestTitleChecks:
    """Tests for missing and short title tags."""

    def test_valid_title_returns_no_issue(self):
        page = PageInspection(url="https://example.com", original_url="https://example.com", title="Comprehensive Example Guide")
        assert len(check_title(page)) == 0

    def test_missing_title(self):
        page = PageInspection(url="https://example.com", original_url="https://example.com", title=None)
        issues = check_title(page)
        assert len(issues) == 1
        assert issues[0].code == "MISSING_TITLE"

    def test_empty_title_whitespace(self):
        page = PageInspection(url="https://example.com", original_url="https://example.com", title="   ")
        issues = check_title(page)
        assert len(issues) == 1
        assert issues[0].code == "MISSING_TITLE"

    def test_short_title(self):
        page = PageInspection(url="https://example.com", original_url="https://example.com", title="Hi")
        issues = check_title(page)
        assert len(issues) == 1
        assert issues[0].code == "SHORT_TITLE"


class TestMetaDescriptionChecks:
    """Tests for missing meta description."""

    def test_valid_description(self):
        page = PageInspection(
            url="https://example.com",
            original_url="https://example.com",
            metadata=PageMetadata(description="A great website offering professional services worldwide."),
        )
        assert len(check_meta_description(page)) == 0

    def test_missing_description(self):
        page = PageInspection(url="https://example.com", original_url="https://example.com", metadata=PageMetadata())
        issues = check_meta_description(page)
        assert len(issues) == 1
        assert issues[0].code == "MISSING_META_DESCRIPTION"


class TestHeadingChecks:
    """Tests for H1 hierarchy and presence."""

    def test_single_h1_returns_no_issue(self):
        page = PageInspection(
            url="https://example.com",
            original_url="https://example.com",
            headings=[Heading(level=1, text="Main Title"), Heading(level=2, text="Sub")],
        )
        assert len(check_headings_h1(page)) == 0

    def test_missing_h1(self):
        page = PageInspection(
            url="https://example.com",
            original_url="https://example.com",
            headings=[Heading(level=2, text="Sub"), Heading(level=3, text="Sub-sub")],
        )
        issues = check_headings_h1(page)
        assert len(issues) == 1
        assert issues[0].code == "MISSING_H1"

    def test_multiple_h1(self):
        page = PageInspection(
            url="https://example.com",
            original_url="https://example.com",
            headings=[Heading(level=1, text="First H1"), Heading(level=1, text="Second H1")],
        )
        issues = check_headings_h1(page)
        assert len(issues) == 1
        assert issues[0].code == "MULTIPLE_H1"
        assert issues[0].details["h1_count"] == 2


class TestCanonicalChecks:
    """Tests for canonical presence, domain matching, and validity."""

    def test_valid_same_domain_canonical(self):
        page = PageInspection(
            url="https://example.com/item?ref=1",
            original_url="https://example.com/item?ref=1",
            metadata=PageMetadata(canonical_url="https://example.com/item"),
        )
        assert len(check_canonical(page)) == 0

    def test_missing_canonical(self):
        page = PageInspection(url="https://example.com", original_url="https://example.com", metadata=PageMetadata())
        issues = check_canonical(page)
        assert len(issues) == 1
        assert issues[0].code == "MISSING_CANONICAL"

    def test_canonical_domain_mismatch(self):
        page = PageInspection(
            url="https://example.com/page",
            original_url="https://example.com/page",
            metadata=PageMetadata(canonical_url="https://other-domain.com/page"),
        )
        issues = check_canonical(page)
        assert len(issues) == 1
        assert issues[0].code == "CANONICAL_DOMAIN_MISMATCH"

    def test_canonical_protocol_mismatch(self):
        page = PageInspection(
            url="https://example.com/page",
            original_url="https://example.com/page",
            metadata=PageMetadata(canonical_url="http://example.com/page"),
        )
        issues = check_canonical(page)
        assert len(issues) == 1
        assert issues[0].code == "CANONICAL_PROTOCOL_MISMATCH"

    def test_invalid_canonical_url(self):
        page = PageInspection(
            url="https://example.com/page",
            original_url="https://example.com/page",
            metadata=PageMetadata(canonical_url="htp:/invalid-url"),
        )
        issues = check_canonical(page)
        assert len(issues) == 1
        assert issues[0].code == "CANONICAL_URL_INVALID"


class TestBodyTextChecks:
    """Tests for empty and sparse body text."""

    def test_sufficient_body_text(self):
        page = PageInspection(
            url="https://example.com",
            original_url="https://example.com",
            body_text="This is a rich and detailed article describing all aspects of technical SEO and web crawling architecture.",
        )
        assert len(check_body_text_content(page)) == 0

    def test_empty_body_text(self):
        page = PageInspection(url="https://example.com", original_url="https://example.com", body_text="")
        issues = check_body_text_content(page)
        assert len(issues) == 1
        assert issues[0].code == "EMPTY_BODY_TEXT"

    def test_low_body_text(self):
        page = PageInspection(url="https://example.com", original_url="https://example.com", body_text="Too short.")
        issues = check_body_text_content(page)
        assert len(issues) == 1
        assert issues[0].code == "LOW_BODY_TEXT"


class TestRedirectChainChecks:
    """Tests for excessive redirect chains and redirect loops."""

    def test_single_url_no_redirect(self):
        page = PageInspection(url="https://example.com", original_url="https://example.com", redirect_chain=["https://example.com"])
        assert len(check_redirect_chain(page)) == 0

    def test_acceptable_redirect(self):
        page = PageInspection(
            url="https://example.com/new",
            original_url="https://example.com/old",
            redirect_chain=["https://example.com/old", "https://example.com/new"],
        )
        assert len(check_redirect_chain(page)) == 0

    def test_excessive_redirect_chain(self):
        page = PageInspection(
            url="https://example.com/d",
            original_url="https://example.com/a",
            redirect_chain=[
                "https://example.com/a",
                "https://example.com/b",
                "https://example.com/c",
                "https://example.com/d",
            ],
        )
        issues = check_redirect_chain(page)
        assert any(i.code == "EXCESSIVE_REDIRECT_CHAIN" for i in issues)

    def test_redirect_loop_detected(self):
        page = PageInspection(
            url="https://example.com/a",
            original_url="https://example.com/a",
            redirect_chain=[
                "https://example.com/a",
                "https://example.com/b",
                "https://example.com/a",
            ],
        )
        issues = check_redirect_chain(page)
        assert any(i.code == "REDIRECT_LOOP" for i in issues)


class TestStaticRenderedGapChecks:
    """Tests for JavaScript content dependency discrepancies."""

    def test_static_page_not_rendered_returns_no_gap_issue(self):
        page = PageInspection(
            url="https://example.com",
            original_url="https://example.com",
            is_rendered=False,
            source_text="Static text content here.",
            rendered_text=None,
        )
        assert len(check_static_rendered_gap(page)) == 0

    def test_rendered_page_with_substantial_gap(self):
        source = "Loading..."
        rendered = "Welcome to our comprehensive catalog. " * 10
        page = PageInspection(
            url="https://example.com/spa",
            original_url="https://example.com/spa",
            is_rendered=True,
            source_text=source,
            rendered_text=rendered,
        )
        issues = check_static_rendered_gap(page)
        assert len(issues) == 1
        assert issues[0].code == "STATIC_RENDERED_CONTENT_GAP"
        assert issues[0].details["char_difference"] > 150


class TestSitemapAndRobotsDiscoverability:
    """Tests for site-level sitemap and robots.txt discoverability checks."""

    def test_missing_robots_txt(self):
        site = SiteInspection(
            site="example.com",
            root_url="https://example.com",
            robots=RobotsTxtInspection(checked=True, found=False, status_code=404),
        )
        issues = check_sitemap_and_robots_discoverability(site)
        assert any(i.code == "ROBOTS_TXT_NOT_FOUND" for i in issues)

    def test_missing_sitemap(self):
        site = SiteInspection(
            site="example.com",
            root_url="https://example.com",
            sitemap=SitemapInspection(checked=True, found=False, total_discovered_urls=0),
        )
        issues = check_sitemap_and_robots_discoverability(site)
        assert any(i.code == "SITEMAP_NOT_FOUND" for i in issues)

    def test_high_crawl_delay(self):
        site = SiteInspection(
            site="example.com",
            root_url="https://example.com",
            robots=RobotsTxtInspection(checked=True, found=True, crawl_delay=15.0),
        )
        issues = check_sitemap_and_robots_discoverability(site)
        assert any(i.code == "HIGH_CRAWL_DELAY" for i in issues)

    def test_page_not_in_sitemap_check(self):
        site = SiteInspection(
            site="example.com",
            root_url="https://example.com",
            sitemap=SitemapInspection(
                checked=True,
                found=True,
                total_discovered_urls=2,
                sample_urls=["https://example.com/home", "https://example.com/about"],
            ),
        )
        page = PageInspection(
            url="https://example.com/unlisted-product",
            original_url="https://example.com/unlisted-product",
            status_code=200,
            title="Unlisted Product",
            metadata=PageMetadata(description="Sample desc", canonical_url="https://example.com/unlisted-product"),
            headings=[Heading(level=1, text="Unlisted Product")],
            body_text="Rich content text describing unlisted product with sufficient length.",
        )
        issues = inspect_page_technical(page, site_inspection=site)
        assert any(i.code == "PAGE_NOT_IN_SITEMAP" for i in issues)


class TestFullAuditTechnicalDiscoverability:
    """End-to-end test of full technical audit across site and pages."""

    def test_audit_technical_discoverability_workflow(self):
        page1 = PageInspection(
            url="https://example.com",
            original_url="https://example.com",
            status_code=200,
            title="Acme Corporation - Quality Industrial Hardware",
            metadata=PageMetadata(
                description="Acme Corporation makes premium quality industrial hardware and widgets.",
                canonical_url="https://example.com",
            ),
            headings=[Heading(level=1, text="Acme Hardware")],
            body_text="Acme provides heavy machinery, anvil sets, and tools for global engineering teams.",
        )

        page2 = PageInspection(
            url="https://example.com/broken",
            original_url="https://example.com/broken",
            status_code=404,
            title=None,
            metadata=PageMetadata(),
            headings=[],
            body_text="",
        )

        site = SiteInspection(
            site="example.com",
            root_url="https://example.com",
            robots=RobotsTxtInspection(checked=True, found=True, status_code=200),
            sitemap=SitemapInspection(
                checked=True,
                found=True,
                total_discovered_urls=1,
                sample_urls=["https://example.com"],
            ),
            pages=[page1, page2],
        )

        audited_site = audit_technical_discoverability(site)

        # Page 1 should have 0 issues (clean page)
        assert len(audited_site.pages[0].technical_issues) == 0

        # Page 2 should have several issues (404, missing title, missing desc, missing H1, empty body, missing canonical)
        p2_codes = {i.code for i in audited_site.pages[1].technical_issues}
        assert "HTTP_NOT_FOUND" in p2_codes
        assert "MISSING_TITLE" in p2_codes
        assert "MISSING_META_DESCRIPTION" in p2_codes
        assert "MISSING_H1" in p2_codes
        assert "EMPTY_BODY_TEXT" in p2_codes
        assert "MISSING_CANONICAL" in p2_codes

        # Check summary counters populated
        assert audited_site.summary_counts["total_technical_issues"] >= len(p2_codes)
