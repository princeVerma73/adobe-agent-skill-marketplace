"""Unit tests for URL validation, normalization, and SSRF checks."""

import pytest
from src.inspection.url import (
    InvalidURLError,
    PrivateTargetError,
    extract_hostname,
    is_private_or_local_target,
    is_same_domain,
    is_same_site,
    is_valid_url,
    normalize_url,
)


class TestURLNormalizationAndValidation:
    """Test suite for URL normalization and validation."""

    def test_valid_https_url(self):
        url = "https://example.com"
        assert normalize_url(url) == "https://example.com"

    def test_valid_http_url(self):
        url = "http://example.com/blog"
        assert normalize_url(url) == "http://example.com/blog"

    def test_bare_domain_normalizes_to_https(self):
        assert normalize_url("example.com") == "https://example.com"
        assert normalize_url("store.adobe.com/products") == "https://store.adobe.com/products"

    def test_path_preservation_and_trailing_slash_normalization(self):
        assert normalize_url("https://example.com/products") == "https://example.com/products"
        assert normalize_url("https://example.com/products/") == "https://example.com/products"
        assert normalize_url("https://example.com/") == "https://example.com"

    def test_query_parameters_preserved(self):
        url = "https://example.com/search?q=adobe&category=ai&page=1"
        assert normalize_url(url) == "https://example.com/search?q=adobe&category=ai&page=1"

    def test_fragment_removal(self):
        url = "https://example.com/docs/api#installation"
        assert normalize_url(url) == "https://example.com/docs/api"

    def test_uppercase_hostname_normalization(self):
        url = "HTTPS://EXAMPLE.COM/AboutUs"
        assert normalize_url(url) == "https://example.com/AboutUs"

    def test_default_port_omission(self):
        assert normalize_url("https://example.com:443/test") == "https://example.com/test"
        assert normalize_url("http://example.com:80/test") == "http://example.com/test"
        assert normalize_url("https://example.com:8443/test") == "https://example.com:8443/test"

    @pytest.mark.parametrize("scheme_url", [
        "file:///etc/passwd",
        "ftp://ftp.example.com/resource",
        "javascript:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
        "mailto:info@example.com",
        "tel:+1234567890",
        "ssh://git@github.com",
    ])
    def test_unsupported_schemes_rejected(self, scheme_url):
        with pytest.raises(InvalidURLError):
            normalize_url(scheme_url)
        assert is_valid_url(scheme_url) is False

    @pytest.mark.parametrize("malformed", [
        "",
        "   ",
        "://missing-scheme",
        "http://",
        "https://",
        "http://   ",
        "http://invalid domain.com",
    ])
    def test_malformed_urls_rejected(self, malformed):
        with pytest.raises(InvalidURLError):
            normalize_url(malformed)
        assert is_valid_url(malformed) is False


class TestSSRFBoundaryDetection:
    """Test suite for offline SSRF private/local address detection."""

    @pytest.mark.parametrize("target", [
        "localhost",
        "http://localhost",
        "http://localhost:8080",
        "https://localhost/dashboard",
        "http://localhost.localdomain",
        "http://service.internal",
        "http://myhost.local",
    ])
    def test_localhost_and_internal_domains_rejected(self, target):
        with pytest.raises(PrivateTargetError):
            normalize_url(target)
        assert is_private_or_local_target(target) is True
        assert is_valid_url(target) is False

    @pytest.mark.parametrize("ip_target", [
        "127.0.0.1",
        "http://127.0.0.1",
        "http://127.0.0.1:9000",
        "0.0.0.0",
        "http://0.0.0.0",
        "10.0.0.1",
        "http://10.254.0.1/admin",
        "172.16.0.1",
        "http://172.31.255.255",
        "192.168.1.1",
        "http://192.168.0.100",
        "169.254.169.254",
        "http://169.254.169.254/latest/meta-data",
    ])
    def test_ipv4_private_and_loopback_rejected(self, ip_target):
        with pytest.raises(PrivateTargetError):
            normalize_url(ip_target)
        assert is_private_or_local_target(ip_target) is True
        assert is_valid_url(ip_target) is False

    @pytest.mark.parametrize("ipv6_target", [
        "::1",
        "[::1]",
        "http://[::1]",
        "http://[::1]:8080",
        "http://[fe80::1]",
        "http://[fc00::1]",
        "http://[fd12:3456:789a:1::1]",
    ])
    def test_ipv6_private_and_loopback_rejected(self, ipv6_target):
        with pytest.raises(PrivateTargetError):
            normalize_url(ipv6_target)
        assert is_private_or_local_target(ipv6_target) is True
        assert is_valid_url(ipv6_target) is False

    def test_public_ip_and_domain_allowed(self):
        assert is_private_or_local_target("8.8.8.8") is False
        assert is_private_or_local_target("https://example.com") is False
        assert is_private_or_local_target("adobe.com") is False


class TestURLHelpers:
    """Test suite for URL utility helper functions."""

    def test_extract_hostname(self):
        assert extract_hostname("https://example.com/path") == "example.com"
        assert extract_hostname("HTTP://SUB.EXAMPLE.COM:8080/path") == "sub.example.com"
        assert extract_hostname("adobe.com") == "adobe.com"
        assert extract_hostname("") is None
        assert extract_hostname("   ") is None

    def test_is_same_domain(self):
        assert is_same_domain("https://example.com/page1", "https://example.com/page2") is True
        assert is_same_domain("http://example.com", "https://example.com") is True
        assert is_same_domain("https://example.com", "https://other.com") is False
        assert is_same_domain("https://sub.example.com", "https://example.com") is False

    def test_is_same_site(self):
        assert is_same_site("https://example.com/a", "https://example.com/b") is True
        assert is_same_site("https://blog.example.com", "https://example.com") is True
        assert is_same_site("https://shop.example.com", "https://docs.example.com") is True
        assert is_same_site("https://example.com", "https://other.com") is False
        assert is_same_site("https://8.8.8.8", "https://8.8.8.8") is True
        assert is_same_site("https://8.8.8.8", "https://1.1.1.1") is False

    def test_is_valid_url_helper(self):
        assert is_valid_url("https://example.com") is True
        assert is_valid_url("http://sub.domain.co.uk/path?a=1") is True
        assert is_valid_url("http://127.0.0.1") is False
        assert is_valid_url("file:///test") is False
        assert is_valid_url("not a url") is False
