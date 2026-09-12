"""URL validation and normalization utility for the inspection layer.

Provides deterministic, offline URL validation, normalization, hostname extraction,
same-site comparison, and SSRF boundary detection.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Optional
from urllib.parse import urlparse, urlunparse


# Custom exceptions
class InvalidURLError(ValueError):
    """Raised when a URL is malformed, unsupported, or unsafe."""
    pass


class PrivateTargetError(InvalidURLError):
    """Raised when a URL targets a loopback, private, or link-local address."""
    pass


# Allowed web schemes
ALLOWED_SCHEMES = {"http", "https"}

# Obvious private/loopback host strings
_PRIVATE_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "0.0.0.0",
    "127.0.0.1",
    "::1",
    "::",
}

_PRIVATE_DOMAIN_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".lan",
    ".test",
    ".example",
    ".invalid",
)


def _clean_host_str(host_str: str) -> str:
    """Clean and strip brackets and whitespace from host string."""
    cleaned = host_str.strip().lower()
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1]
    return cleaned


def _extract_raw_host(target: str) -> str:
    """Extract raw host or IP string from a URL, domain, or IP address offline."""
    if not target or not isinstance(target, str):
        return ""

    raw = target.strip()
    if not raw:
        return ""

    # Check if target itself is a direct IPv6 literal (with or without brackets)
    clean_target = _clean_host_str(raw)
    try:
        ipaddress.ip_address(clean_target)
        return clean_target
    except ValueError:
        pass

    # If scheme is present
    if "://" in raw or raw.startswith("//"):
        try:
            parsed = urlparse(raw)
            if parsed.hostname:
                return _clean_host_str(parsed.hostname)
            # Fallback if unbracketed IPv6 in netloc
            netloc = parsed.netloc or parsed.path.split("/")[0]
            return _clean_host_str(netloc)
        except Exception:
            return ""

    # Handle bracketed host: [::1]:8080 or [::1]/path
    if raw.startswith("["):
        end_bracket = raw.find("]")
        if end_bracket != -1:
            return raw[1:end_bracket].lower()

    # If it contains slash, take first component
    first_part = raw.split("/")[0]

    # Try direct IP parse on first_part
    try:
        ipaddress.ip_address(first_part)
        return first_part.lower()
    except ValueError:
        pass

    # If port is attached to a standard hostname e.g. example.com:8080
    if ":" in first_part and first_part.count(":") == 1:
        first_part = first_part.split(":")[0]

    return _clean_host_str(first_part)


def is_private_or_local_target(hostname_or_url: str) -> bool:
    """Check whether a target hostname or URL points to a private, loopback, or link-local target.
    
    IMPORTANT: This function operates strictly offline without performing DNS resolution.
    It inspects literal hostnames and IP addresses.
    """
    host = _extract_raw_host(hostname_or_url)
    if not host:
        return True

    if host in _PRIVATE_HOSTNAMES:
        return True

    for suffix in _PRIVATE_DOMAIN_SUFFIXES:
        if host.endswith(suffix):
            return True

    # Check if host is an IP literal
    try:
        ip = ipaddress.ip_address(host)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_unspecified
            or ip.is_reserved
            or ip.is_multicast
        )
    except ValueError:
        # Not a raw IP literal
        pass

    return False


def extract_hostname(url_or_domain: str) -> Optional[str]:
    """Extract lowercase hostname from a URL or bare domain.
    
    Returns None if no valid hostname could be determined.
    """
    host = _extract_raw_host(url_or_domain)
    return host if host else None


def is_same_domain(url1: str, url2: str) -> bool:
    """Check whether two URLs or domains share the exact same hostname.
    
    Returns False if either URL is invalid.
    """
    host1 = extract_hostname(url1)
    host2 = extract_hostname(url2)
    if not host1 or not host2:
        return False
    return host1 == host2


def is_same_site(url1: str, url2: str) -> bool:
    """Check whether two URLs belong to the same site (matching registrable domain or subdomains).
    
    For example:
    - `https://example.com/a` and `https://example.com/b` -> True
    - `https://blog.example.com` and `https://example.com` -> True
    - `https://example.com` and `https://other.com` -> False
    """
    host1 = extract_hostname(url1)
    host2 = extract_hostname(url2)
    if not host1 or not host2:
        return False

    if host1 == host2:
        return True

    # If either is an IP address, require exact match
    try:
        ipaddress.ip_address(host1)
        return host1 == host2
    except ValueError:
        pass

    try:
        ipaddress.ip_address(host2)
        return host1 == host2
    except ValueError:
        pass

    parts1 = host1.split(".")
    parts2 = host2.split(".")

    if len(parts1) < 2 or len(parts2) < 2:
        return host1 == host2

    # Compare last two domain components (e.g., example.com)
    domain1 = ".".join(parts1[-2:])
    domain2 = ".".join(parts2[-2:])
    return domain1 == domain2


def normalize_url(url: str, default_scheme: str = "https") -> str:
    """Validate and normalize a URL into canonical representation.
    
    Rules:
    - Accepts http/https URLs and bare domains (defaults to https://)
    - Rejects unsupported schemes (file://, ftp://, javascript:, data:, mailto:, tel:)
    - Rejects malformed URLs and URLs without valid hostname
    - Rejects SSRF private/loopback/link-local targets
    - Lowercases hostname
    - Removes URL fragments
    - Preserves meaningful paths and query parameters
    - Normalizes trailing slash on root and non-root paths cleanly
    
    Raises:
        InvalidURLError: If URL is invalid, malformed, or has an unsupported scheme.
        PrivateTargetError: If target points to a local or private address.
    """
    if not url or not isinstance(url, str):
        raise InvalidURLError("URL must be a non-empty string.")

    raw = url.strip()
    if not raw:
        raise InvalidURLError("URL cannot be whitespace only.")

    # Check for unsupported explicit schemes
    scheme_match = re.match(r"^([a-zA-Z0-9+.-]+):", raw)
    if scheme_match:
        found_scheme = scheme_match.group(1).lower()
        if found_scheme not in ALLOWED_SCHEMES:
            raise InvalidURLError(f"Unsupported URL scheme: {found_scheme}://")
    else:
        # Check if bare target is an unbracketed IPv6 literal
        try:
            ip = ipaddress.ip_address(raw.split("/")[0])
            if ip.version == 6:
                path_part = raw[len(raw.split("/")[0]):]
                raw = f"{default_scheme}://[{ip}]{path_part}"
            else:
                raw = f"{default_scheme}://{raw}"
        except ValueError:
            raw = f"{default_scheme}://{raw}"

    try:
        parsed = urlparse(raw)
    except Exception as exc:
        raise InvalidURLError(f"Malformed URL: {exc}") from exc

    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise InvalidURLError(f"Unsupported URL scheme: {scheme}://")

    # Hostname extraction and validation
    hostname = parsed.hostname
    if not hostname:
        # Check if unbracketed IPv6 was passed inside netloc
        clean_netloc = parsed.netloc.split("/")[0]
        try:
            ip = ipaddress.ip_address(clean_netloc)
            hostname = str(ip)
        except ValueError:
            raise InvalidURLError("URL must contain a valid hostname.")

    hostname = hostname.lower()

    # SSRF / private target check
    if is_private_or_local_target(hostname):
        raise PrivateTargetError(f"Target '{hostname}' resolves to a local or private address.")

    # Validate host characters (must not contain spaces or illegal control chars)
    if " " in hostname or "\t" in hostname or "\n" in hostname:
        raise InvalidURLError("Hostname contains illegal whitespace.")

    # Format netloc (IPv6 needs brackets in netloc)
    is_ipv6 = False
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.version == 6:
            is_ipv6 = True
    except ValueError:
        pass

    formatted_host = f"[{hostname}]" if is_ipv6 else hostname

    # Port handling
    port = parsed.port
    netloc = formatted_host
    if port:
        # Standard ports can be omitted
        if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
            netloc = formatted_host
        else:
            netloc = f"{formatted_host}:{port}"

    # Path normalization
    path = parsed.path
    if not path or path == "/":
        path = ""
    else:
        # Remove redundant trailing slash for non-root paths unless path is empty
        if path.endswith("/") and len(path) > 1:
            path = path.rstrip("/")

    # Query preservation
    query = parsed.query

    # Reconstruct normalized URL without fragment
    normalized = urlunparse((scheme, netloc, path, "", query, ""))
    return normalized


def is_valid_url(url: str) -> bool:
    """Return True if URL is valid, safe, and supported; False otherwise."""
    try:
        normalize_url(url)
        return True
    except (InvalidURLError, ValueError, Exception):
        return False


KNOWN_REGIONAL_SLUGS = {
    "africa", "mena", "apac", "latam", "global", "emea", "sea",
    "international", "row", "latinamerica", "middleeast",
}

NON_LOCALE_SEGMENTS = {
    "api", "app", "doc", "docs", "dev", "img", "css", "tag", "faq", "buy",
    "pub", "cdn", "nav", "web", "src", "lib", "all", "top", "new",
    "raw", "git", "hub", "bot", "job", "pdf", "rss", "bin", "pkg",
    "art", "ops", "org", "tmp", "log", "ui", "js", "v1", "v2", "v3",
    "search", "help", "support", "account", "login", "auth", "signin",
    "legal", "privacy", "terms", "download", "downloads", "static",
}

_LOCALE_COMPOUND = re.compile(
    r"^[a-zA-Z]{2,4}[-_][a-zA-Z]{2,4}$"
)
_LOCALE_2_LETTER = re.compile(
    r"^[a-zA-Z]{2}$"
)
_LOCALE_3_LETTER = re.compile(
    r"^[a-zA-Z]{3}$"
)


def extract_locale_prefix(url_or_path: str) -> Optional[str]:
    """Extract lowercase locale prefix from a URL or path, if present.
    
    Examples:
        'https://www.adobe.com/in/' -> 'in'
        'https://www.adobe.com/in/products' -> 'in'
        '/ae_ar/about' -> 'ae_ar'
        '/cis_en/' -> 'cis_en'
        '/mena_ar/' -> 'mena_ar'
        '/africa/' -> 'africa'
        'https://docs.python.org/3' -> None
        'https://fastapi.tiangolo.com/' -> None
        '/api/v1/users' -> None
    """
    if not url_or_path or not isinstance(url_or_path, str):
        return None
    
    # Extract path
    if "://" in url_or_path or url_or_path.startswith("//"):
        try:
            path = urlparse(url_or_path).path
        except Exception:
            return None
    else:
        path = url_or_path.split("?")[0].split("#")[0]
        
    segments = [s.strip().lower() for s in path.strip("/").split("/") if s.strip()]
    if not segments:
        return None
        
    first = segments[0]
    if first in NON_LOCALE_SEGMENTS:
        return None
    if first in KNOWN_REGIONAL_SLUGS:
        return first
    if _LOCALE_COMPOUND.match(first):
        return first
    if _LOCALE_2_LETTER.match(first):
        return first
    if _LOCALE_3_LETTER.match(first) and first not in NON_LOCALE_SEGMENTS:
        return first
        
    return None


def is_locale_root(url_or_path: str) -> bool:
    """Return True if url_or_path represents a bare locale/regional root.
    
    Examples:
        'https://www.adobe.com/in' -> True
        'https://www.adobe.com/in/' -> True
        '/ae_ar' -> True
        '/africa/' -> True
        'https://www.adobe.com/in/products' -> False
    """
    if not url_or_path or not isinstance(url_or_path, str):
        return False
    if "://" in url_or_path or url_or_path.startswith("//"):
        try:
            path = urlparse(url_or_path).path
        except Exception:
            return False
    else:
        path = url_or_path.split("?")[0].split("#")[0]
    
    segments = [s.strip().lower() for s in path.strip("/").split("/") if s.strip()]
    if len(segments) == 1:
        return extract_locale_prefix(segments[0]) is not None
    return False


def is_same_locale(url1: str, url2: str) -> bool:
    """Check whether two URLs share the same locale prefix scope."""
    loc1 = extract_locale_prefix(url1)
    loc2 = extract_locale_prefix(url2)
    return loc1 == loc2


def is_regional_sibling(root_url: str, candidate_url: str) -> bool:
    """Check if candidate_url is a regional/locale sibling variant of root_url.
    
    Returns True only when root_url is locale-scoped and candidate_url belongs
    to a different locale prefix on the same site.
    """
    root_loc = extract_locale_prefix(root_url)
    if not root_loc:
        return False
    
    if not is_same_site(root_url, candidate_url):
        return False
        
    cand_loc = extract_locale_prefix(candidate_url)
    if cand_loc and cand_loc != root_loc:
        return True
        
    return False
