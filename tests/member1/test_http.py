"""Unit tests for safe HTTP client using mocked transport."""

import socket
from unittest.mock import patch
import pytest
import httpx

from src.crawler.http import (
    DEFAULT_USER_AGENT,
    FetchResponse,
    SafeHTTPClient,
    _verify_resolved_ips,
    fetch_url,
)
from src.inspection.models import PageInspection
from src.inspection.url import InvalidURLError, PrivateTargetError


class TestSafeHTTPClient:
    """Test suite for safe HTTP client behavior without live network calls."""

    def test_successful_get_request(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            assert request.headers["User-Agent"] == DEFAULT_USER_AGENT
            return httpx.Response(
                200,
                text="<html><head><title>Test</title></head><body>Hello world</body></html>",
                headers={"Content-Type": "text/html; charset=utf-8", "X-Custom-Header": "value"},
            )

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)
        resp = client.get("https://example.com/page")

        assert resp.success is True
        assert resp.status_code == 200
        assert resp.content_type == "text/html; charset=utf-8"
        assert "Hello world" in resp.text
        assert resp.url == "https://example.com/page"
        assert resp.original_url == "https://example.com/page"
        assert resp.response_time_ms is not None
        assert resp.response_time_ms >= 0
        assert resp.is_truncated is False
        assert resp.error is None
        assert resp.headers["x-custom-header"] == "value"

    def test_custom_user_agent_and_timeout(self):
        custom_ua = "CustomAuditAgent/2.0"

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["User-Agent"] == custom_ua
            return httpx.Response(200, text="OK")

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(user_agent=custom_ua, timeout=5.0, transport=transport, verify_dns=False)
        resp = client.get("https://example.com")

        assert resp.success is True
        assert resp.status_code == 200

    def test_http_status_codes_and_errors(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/not-found":
                return httpx.Response(404, text="Not Found")
            elif request.url.path == "/server-error":
                return httpx.Response(500, text="Server Error")
            return httpx.Response(200, text="OK")

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        resp_404 = client.get("https://example.com/not-found")
        assert resp_404.status_code == 404
        assert resp_404.success is True

        resp_500 = client.get("https://example.com/server-error")
        assert resp_500.status_code == 500
        assert resp_500.success is True

    def test_request_timeout_handling(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("Read timed out")

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)
        resp = client.get("https://example.com/slow")

        assert resp.success is False
        assert resp.error == "Request timed out."
        assert resp.status_code is None

    def test_connection_error_handling(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)
        resp = client.get("https://example.com/broken")

        assert resp.success is False
        assert "Connection refused" in resp.error

    def test_allowed_public_redirect_chain(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/start":
                return httpx.Response(
                    301,
                    headers={"Location": "https://example.com/step2"},
                )
            elif request.url.path == "/step2":
                return httpx.Response(
                    302,
                    headers={"Location": "/final"},
                )
            elif request.url.path == "/final":
                return httpx.Response(200, text="Final Landing Page")
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)
        resp = client.get("https://example.com/start")

        assert resp.success is True
        assert resp.status_code == 200
        assert resp.url == "https://example.com/final"
        assert resp.original_url == "https://example.com/start"
        assert resp.redirect_chain == [
            "https://example.com/start",
            "https://example.com/step2",
            "https://example.com/final",
        ]
        assert resp.text == "Final Landing Page"

    def test_redirect_to_localhost_blocked(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"Location": "http://localhost:8080/admin"})

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)
        resp = client.get("https://example.com/redirect-to-local")

        assert resp.success is False
        assert "unsafe" in resp.error.lower() or "blocked" in resp.error.lower()
        assert resp.url == "http://localhost:8080/admin"

    def test_redirect_to_private_ip_blocked(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"Location": "http://192.168.1.1/router"})

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)
        resp = client.get("https://example.com/private-redirect")

        assert resp.success is False
        assert "blocked" in resp.error.lower() or "unsafe" in resp.error.lower()

    def test_redirect_to_unsupported_scheme_blocked(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"Location": "file:///etc/shadow"})

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)
        resp = client.get("https://example.com/file-redirect")

        assert resp.success is False
        assert "unsupported url scheme" in resp.error.lower()

    def test_max_redirects_exceeded(self):
        def handler(request: httpx.Request) -> httpx.Response:
            num = int(request.url.path.replace("/hop", "") or 0)
            return httpx.Response(302, headers={"Location": f"/hop{num + 1}"})

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(max_redirects=3, transport=transport, verify_dns=False)
        resp = client.get("https://example.com/hop0")

        assert resp.success is False
        assert "maximum redirects (3) exceeded" in resp.error.lower()

    def test_redirect_loop_detected(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/loop-a":
                return httpx.Response(302, headers={"Location": "/loop-b"})
            elif request.url.path == "/loop-b":
                return httpx.Response(302, headers={"Location": "/loop-a"})
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)
        resp = client.get("https://example.com/loop-a")

        assert resp.success is False
        assert "redirect loop detected" in resp.error.lower()

    def test_response_size_limit_and_truncation(self):
        large_body = b"A" * 1000  # 1000 bytes

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=large_body)

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(max_response_size=300, transport=transport, verify_dns=False)
        resp = client.get("https://example.com/large")

        assert resp.success is True
        assert resp.is_truncated is True
        assert len(resp.content) == 300
        assert len(resp.text) == 300

    def test_direct_private_target_initial_url_blocked(self):
        client = SafeHTTPClient(verify_dns=False)
        resp = client.get("http://127.0.0.1:8000")
        assert resp.success is False
        assert "private or local" in resp.error.lower() or "validation failed" in resp.error.lower()

    def test_to_page_inspection_conversion(self):
        resp = FetchResponse(
            url="https://example.com/about",
            original_url="example.com/about",
            status_code=200,
            content_type="text/html",
            content=b"<h1>About</h1>",
            text="<h1>About</h1>",
            response_time_ms=55.0,
            redirect_chain=["https://example.com/about"],
            is_truncated=False,
            success=True,
        )

        page = resp.to_page_inspection(crawl_depth=1, title="About Us")
        assert isinstance(page, PageInspection)
        assert page.url == "https://example.com/about"
        assert page.original_url == "example.com/about"
        assert page.status_code == 200
        assert page.crawl_depth == 1
        assert page.title == "About Us"
        assert page.raw_html_available is True
        assert page.source_text == "<h1>About</h1>"
        assert page.technical_issues == []


class TestDNSSSRFSafety:
    """Test DNS pre-flight safety and rebinding checks."""

    def test_dns_resolves_to_public_ip_passes(self):
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
            ]
            # Should not raise
            _verify_resolved_ips("example.com", 443)

    def test_dns_resolves_to_private_ip_blocked(self):
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443))
            ]
            with pytest.raises(PrivateTargetError) as exc_info:
                _verify_resolved_ips("internal.attacker.com", 443)
            assert "unsafe private/local IP" in str(exc_info.value)

    def test_dns_resolves_to_loopback_blocked(self):
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))
            ]
            with pytest.raises(PrivateTargetError):
                _verify_resolved_ips("rebinding.evil.com", 80)

    def test_dns_resolution_failure_handled(self):
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("Name or service not known")):
            with pytest.raises(InvalidURLError) as exc_info:
                _verify_resolved_ips("nonexistent-domain.xyz", 443)
            assert "DNS resolution failed" in str(exc_info.value)
