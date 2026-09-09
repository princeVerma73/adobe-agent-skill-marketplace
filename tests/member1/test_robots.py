"""Unit tests for robots.txt parsing and inspection without live network calls."""

import pytest
import httpx

from src.crawler.http import SafeHTTPClient
from src.inspection.models import RobotsTxtInspection
from src.inspection.robots import RobotsParser, inspect_robots_txt


SAMPLE_ROBOTS_TXT = """
# Robots.txt for Example.com
User-agent: *
Disallow: /admin/
Disallow: /private/
Allow: /private/public-doc
Disallow: /secret.html$
Crawl-delay: 2.5
Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/sitemap-products.xml

User-agent: Googlebot
Disallow: /nogoogle/

User-agent: Adobe-BrandAuditBot
Disallow: /no-adobe/
Allow: /admin/
"""


class TestRobotsParser:
    """Test unit behavior of the RobotsParser."""

    def test_sitemap_and_crawl_delay_extraction(self):
        parser = RobotsParser(SAMPLE_ROBOTS_TXT)
        assert parser.sitemaps == [
            "https://example.com/sitemap.xml",
            "https://example.com/sitemap-products.xml",
        ]
        assert parser.crawl_delay == 2.5

    def test_wildcard_agent_rule_evaluation(self):
        parser = RobotsParser(SAMPLE_ROBOTS_TXT)
        # Random bot fallback to '*'
        assert parser.is_allowed("/public", user_agent="RandomBot/1.0") is True
        assert parser.is_allowed("/admin/users", user_agent="RandomBot/1.0") is False
        assert parser.is_allowed("/private/secret", user_agent="RandomBot/1.0") is False
        # Allow rule takes precedence because it is more specific (longer path)
        assert parser.is_allowed("/private/public-doc", user_agent="RandomBot/1.0") is True
        # End of string matching ($)
        assert parser.is_allowed("/secret.html", user_agent="RandomBot/1.0") is False
        assert parser.is_allowed("/secret.html.bak", user_agent="RandomBot/1.0") is True

    def test_specific_user_agent_precedence(self):
        parser = RobotsParser(SAMPLE_ROBOTS_TXT)
        # Adobe-BrandAuditBot has specific block
        assert parser.is_allowed("/no-adobe/page", user_agent="Adobe-BrandAuditBot/1.0") is False
        # Specific allow in Adobe block overrides wildcard disallow for /admin/
        assert parser.is_allowed("/admin/dashboard", user_agent="Adobe-BrandAuditBot/1.0") is True

    def test_empty_disallow_allows_all(self):
        text = """
        User-agent: *
        Disallow:
        """
        parser = RobotsParser(text)
        assert parser.is_allowed("/admin") is True
        assert parser.is_allowed("/any/path") is True

    def test_empty_or_whitespace_robots(self):
        parser = RobotsParser("")
        assert parser.is_allowed("/any") is True
        assert parser.sitemaps == []
        assert parser.crawl_delay is None

    def test_malformed_lines_handled_gracefully(self):
        text = """
        User-agent: *
        Just a random broken line
        Disallow /missing-colon
        Crawl-delay: not-a-number
        Disallow: /bad
        """
        parser = RobotsParser(text)
        assert parser.is_allowed("/bad") is False
        assert parser.is_allowed("/good") is True
        assert parser.crawl_delay is None


class TestInspectRobotsTxtFourCases:
    """Test inspect_robots_txt distinguishing all 4 policy states."""

    def test_case_1_robots_found_and_allowed(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/robots.txt"
            return httpx.Response(200, text=SAMPLE_ROBOTS_TXT)

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        inspection = inspect_robots_txt("https://example.com", target_path_or_url="/public", client=client)
        assert isinstance(inspection, RobotsTxtInspection)
        assert inspection.checked is True
        assert inspection.found is True
        assert inspection.status_code == 200
        assert inspection.allowed_for_agent is True
        assert inspection.error is None
        assert inspection.crawl_delay == 2.5
        assert len(inspection.sitemap_urls) == 2
        assert "https://example.com/sitemap.xml" in inspection.sitemap_urls
        assert inspection.raw_text == SAMPLE_ROBOTS_TXT

    def test_case_2_robots_found_and_disallowed(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=SAMPLE_ROBOTS_TXT)

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        inspection = inspect_robots_txt(
            "https://example.com",
            target_path_or_url="/no-adobe/secret",
            client=client,
            user_agent="Adobe-BrandAuditBot/1.0",
        )
        assert inspection.checked is True
        assert inspection.found is True
        assert inspection.status_code == 200
        assert inspection.allowed_for_agent is False
        assert inspection.error is None

    def test_case_3_robots_missing_404_unrestricted(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="Not Found")

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        inspection = inspect_robots_txt("https://example.com", client=client)
        assert inspection.checked is True
        assert inspection.found is False
        assert inspection.status_code == 404
        assert inspection.allowed_for_agent is True
        assert inspection.sitemap_urls == []
        assert inspection.error is None

    def test_case_3_robots_missing_410_unrestricted(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(410, text="Gone")

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        inspection = inspect_robots_txt("https://example.com", client=client)
        assert inspection.checked is True
        assert inspection.found is False
        assert inspection.status_code == 410
        assert inspection.allowed_for_agent is True
        assert inspection.error is None

    def test_case_4_robots_server_error_500_indeterminate(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error")

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        inspection = inspect_robots_txt("https://example.com", client=client)
        assert inspection.checked is True
        assert inspection.found is False
        assert inspection.status_code == 500
        # Must NOT falsely claim allowed_for_agent is True
        assert inspection.allowed_for_agent is None
        assert inspection.error is not None
        assert "500" in inspection.error

    def test_case_4_robots_server_error_503_indeterminate(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="Service Unavailable")

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        inspection = inspect_robots_txt("https://example.com", client=client)
        assert inspection.checked is True
        assert inspection.found is False
        assert inspection.status_code == 503
        assert inspection.allowed_for_agent is None
        assert inspection.error is not None

    def test_case_4_robots_connection_failure_indeterminate(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection timed out or network down")

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        inspection = inspect_robots_txt("https://example.com", client=client)
        assert inspection.checked is True
        assert inspection.found is False
        assert inspection.status_code is None
        # Must NOT falsely claim allowed_for_agent is True
        assert inspection.allowed_for_agent is None
        assert inspection.error is not None
        assert "Connection" in inspection.error or "timed out" in inspection.error
