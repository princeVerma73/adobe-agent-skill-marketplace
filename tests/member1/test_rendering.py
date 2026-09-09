"""Deterministic unit tests for selective Playwright rendering, safety bounds, and fallbacks."""

from unittest.mock import MagicMock, patch
import pytest

from src.extraction.extract import ExtractedData
from src.inspection.models import Heading, Link, PageInspection, PageMetadata
from src.rendering.render import (
    BLOCKED_RESOURCE_TYPES,
    PlaywrightError,
    PlaywrightTimeoutError,
    RenderConfig,
    RenderResult,
    render_and_inspect_page,
    render_page_playwright,
)


class TestRenderingSafetyAndSSRF:
    """Tests for SSRF pre-check, private targets, and resource bounds."""

    def test_ssrf_rejects_localhost_and_private_ips(self):
        unsafe_targets = [
            "http://localhost:8000/app",
            "http://127.0.0.1:3000",
            "http://192.168.1.50/dashboard",
            "http://10.0.0.1",
            "http://app.local",
            "http://[::1]:8080",
        ]
        for url in unsafe_targets:
            result = render_page_playwright(url)
            assert result.is_rendered is False
            assert "safety check failed" in result.error

    def test_blocked_resource_types_defined(self):
        assert "image" in BLOCKED_RESOURCE_TYPES
        assert "media" in BLOCKED_RESOURCE_TYPES
        assert "font" in BLOCKED_RESOURCE_TYPES


class TestPlaywrightMockedExecution:
    """Deterministic browser rendering tests using mocked Playwright objects."""

    def _create_mock_playwright(self, rendered_html: str, rendered_body_text: str):
        """Helper to create a mock Playwright instance hierarchy."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_page.content.return_value = rendered_html
        mock_page.inner_text.return_value = rendered_body_text

        return mock_pw, mock_browser, mock_context, mock_page

    def test_successful_browser_rendering(self):
        rendered_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Dynamic App Title</title>
            <meta name="description" content="Loaded dynamically by React">
        </head>
        <body>
            <h1>Rendered Heading</h1>
            <p>Rendered client paragraph text.</p>
            <a href="https://example.com/item">Item Link</a>
        </body>
        </html>
        """
        mock_pw, mock_browser, mock_context, mock_page = self._create_mock_playwright(
            rendered_html=rendered_html,
            rendered_body_text="Rendered Heading Rendered client paragraph text. Item Link",
        )

        cfg = RenderConfig(timeout_ms=5000)
        result = render_page_playwright(
            url="https://example.com/app",
            config=cfg,
            playwright_instance=mock_pw,
        )

        assert result.is_rendered is True
        assert result.error is None
        assert "Rendered Heading" in result.rendered_text
        assert result.extracted is not None
        assert result.extracted.title == "Dynamic App Title"
        assert len(result.extracted.headings) == 1
        assert result.extracted.headings[0].text == "Rendered Heading"

        # Verify browser cleanup called
        mock_page.close.assert_called_once()
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()

    def test_playwright_route_interception_aborts_unsafe_and_heavy_requests(self):
        mock_pw, mock_browser, mock_context, mock_page = self._create_mock_playwright(
            rendered_html="<html><body><h1>Test</h1></body></html>",
            rendered_body_text="Test",
        )

        # Capture route handler passed to page.route
        route_handler = None
        def mock_route_fn(pattern, handler):
            nonlocal route_handler
            route_handler = handler
        mock_page.route.side_effect = mock_route_fn

        render_page_playwright(
            url="https://example.com",
            config=RenderConfig(block_heavy_resources=True),
            playwright_instance=mock_pw,
        )

        assert route_handler is not None

        # 1. Test heavy image resource is aborted
        mock_route_img = MagicMock()
        mock_route_img.request.url = "https://example.com/pic.png"
        mock_route_img.request.resource_type = "image"
        route_handler(mock_route_img)
        mock_route_img.abort.assert_called_once_with("blockedbyclient")

        # 2. Test private target in route is aborted (SSRF inside page)
        mock_route_private = MagicMock()
        mock_route_private.request.url = "http://127.0.0.1:8080/secret"
        mock_route_private.request.resource_type = "fetch"
        route_handler(mock_route_private)
        mock_route_private.abort.assert_called_once_with("blockedbyclient")

        # 3. Test safe script / html request is allowed
        mock_route_safe = MagicMock()
        mock_route_safe.request.url = "https://example.com/api/data.json"
        mock_route_safe.request.resource_type = "fetch"
        route_handler(mock_route_safe)
        mock_route_safe.continue_.assert_called_once()

    def test_browser_timeout_returns_failure_result(self):
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_page.goto.side_effect = PlaywrightTimeoutError("Navigation timeout")

        cfg = RenderConfig(timeout_ms=3000)
        result = render_page_playwright(
            url="https://example.com/slow",
            config=cfg,
            playwright_instance=mock_pw,
        )

        assert result.is_rendered is False
        assert "timed out" in result.error
        mock_browser.close.assert_called_once()

    def test_browser_error_handled_gracefully(self):
        mock_pw = MagicMock()
        mock_pw.chromium.launch.side_effect = PlaywrightError("Browser executable missing")

        result = render_page_playwright(
            url="https://example.com",
            playwright_instance=mock_pw,
        )

        assert result.is_rendered is False
        assert "Browser executable missing" in result.error

    def test_rendering_without_playwright_installed_returns_error(self):
        with patch("src.rendering.render.PLAYWRIGHT_AVAILABLE", False):
            result = render_page_playwright(url="https://example.com")
            assert result.is_rendered is False
            assert "Playwright is not installed" in result.error


class TestRenderAndInspectPageWorkflow:
    """Tests for selective rendering decision and PageInspection model enrichment."""

    def test_skips_rendering_when_static_html_sufficient(self):
        static_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Full Static Blog</title></head>
        <body>
            <h1>Complete Article</h1>
            <p>This is a complete article with plenty of text and meaningful content that does not need browser execution.</p>
        </body>
        </html>
        """
        # Call without playwright mock - should never attempt browser rendering
        page = render_and_inspect_page(
            url="https://example.com/blog",
            static_html=static_html,
        )

        assert page.is_rendered is False
        assert page.title == "Full Static Blog"
        assert len(page.headings) == 1
        assert page.headings[0].text == "Complete Article"
        assert page.rendered_text is None
        assert page.source_text is not None
        assert len(page.technical_issues) == 0

    def test_renders_and_enriches_when_spa_detected(self):
        spa_html = """<!DOCTYPE html><html><head><title>Loading...</title></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>"""
        rendered_html = """<!DOCTYPE html><html><head><title>Hydrated Store</title></head><body><h1>Online Store</h1><p>Catalog items loaded via client JS.</p></body></html>"""

        mock_pw, _, _, _ = TestPlaywrightMockedExecution()._create_mock_playwright(
            rendered_html=rendered_html,
            rendered_body_text="Online Store Catalog items loaded via client JS.",
        )

        page = render_and_inspect_page(
            url="https://example.com/store",
            static_html=spa_html,
            playwright_instance=mock_pw,
        )

        assert page.is_rendered is True
        assert page.title == "Hydrated Store"
        assert len(page.headings) == 1
        assert page.headings[0].text == "Online Store"
        assert page.source_text == "" or page.source_text is not None
        assert page.rendered_text == "Online Store Catalog items loaded via client JS."

    def test_falls_back_to_static_with_technical_issue_on_render_failure(self):
        spa_html = """<!DOCTYPE html><html><head><title>Static Minimal</title></head><body><div id="root"></div><script src="/app.js"></script></body></html>"""

        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.goto.side_effect = PlaywrightTimeoutError("Navigation timeout")

        page = render_and_inspect_page(
            url="https://example.com/spa-timeout",
            static_html=spa_html,
            playwright_instance=mock_pw,
        )

        assert page.is_rendered is False
        assert page.title == "Static Minimal"
        assert len(page.technical_issues) == 1
        assert page.technical_issues[0].code == "RENDERING_FAILED"
        assert "timed out" in page.technical_issues[0].message
