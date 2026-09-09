"""Safe HTTP fetching client for website inspection.

Enforces GET-only requests, non-browser user-agent, response size limits,
streaming truncation, redirect inspection, and SSRF prevention.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import socket
import time
from typing import TYPE_CHECKING, Dict, List, Optional
import urllib.parse

import httpx

from src.inspection.url import (
    InvalidURLError,
    PrivateTargetError,
    extract_hostname,
    is_private_or_local_target,
    normalize_url,
)

if TYPE_CHECKING:
    from src.inspection.models import PageInspection

# Constants
DEFAULT_USER_AGENT = "Adobe-BrandAuditBot/1.0 (+https://adobe.com/agent-marketplace-audit)"
DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_RESPONSE_SIZE = 2 * 1024 * 1024  # 2 MB
DEFAULT_MAX_REDIRECTS = 5
CHUNK_SIZE = 16 * 1024  # 16 KB chunks


@dataclass
class FetchResponse:
    """Structured result of a safe HTTP fetch observation."""
    url: str
    original_url: str
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    content: bytes = b""
    text: str = ""
    response_time_ms: Optional[float] = None
    redirect_chain: List[str] = field(default_factory=list)
    is_truncated: bool = False
    error: Optional[str] = None
    success: bool = True

    def to_page_inspection(self, crawl_depth: int = 0, title: Optional[str] = None) -> PageInspection:
        """Convert fetch observation into a PageInspection data model."""
        from src.inspection.models import PageInspection, PageMetadata, TechnicalIssue

        issues: List[TechnicalIssue] = []
        if self.error:
            issues.append(
                TechnicalIssue(
                    code="FETCH_ERROR",
                    message=self.error,
                    severity="error",
                    details={"url": self.url, "original_url": self.original_url},
                )
            )
        if self.is_truncated:
            issues.append(
                TechnicalIssue(
                    code="RESPONSE_TRUNCATED",
                    message="Response body exceeded maximum allowed size and was truncated.",
                    severity="warning",
                    details={"bytes_read": len(self.content)},
                )
            )
        if self.status_code and self.status_code >= 400:
            issues.append(
                TechnicalIssue(
                    code=f"HTTP_{self.status_code}",
                    message=f"Server returned HTTP status code {self.status_code}.",
                    severity="warning" if self.status_code < 500 else "error",
                    details={"status_code": self.status_code},
                )
            )

        return PageInspection(
            url=self.url,
            original_url=self.original_url,
            status_code=self.status_code,
            content_type=self.content_type,
            response_time_ms=self.response_time_ms,
            redirect_chain=self.redirect_chain,
            crawl_depth=crawl_depth,
            raw_html_available=bool(self.content),
            source_text=self.text if self.text else None,
            title=title,
            metadata=PageMetadata(title=title),
            technical_issues=issues,
        )


def _verify_resolved_ips(hostname: str, port: int) -> None:
    """Resolve hostname via DNS and ensure none of the resolved IPs are private/local.
    
    Raises:
        PrivateTargetError: If any resolved IP is loopback, private, link-local, or local.
        InvalidURLError: If DNS resolution fails.
    """
    if is_private_or_local_target(hostname):
        raise PrivateTargetError(f"Target '{hostname}' is a private or local address.")

    # If hostname is already an IP literal, standard check in is_private_or_local_target was sufficient
    try:
        ipaddress.ip_address(hostname)
        return
    except ValueError:
        pass

    try:
        addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise InvalidURLError(f"DNS resolution failed for '{hostname}': {exc}") from exc
    except Exception as exc:
        raise InvalidURLError(f"Socket resolution error for '{hostname}': {exc}") from exc

    for item in addr_info:
        ip_str = item[4][0]
        if is_private_or_local_target(ip_str):
            raise PrivateTargetError(
                f"Hostname '{hostname}' resolved to unsafe private/local IP: {ip_str}"
            )


class SafeHTTPClient:
    """Defensive HTTP client for public web inspection.
    
    Enforces:
    - GET-only operations
    - Safe redirect tracking with SSRF checks on every hop
    - DNS resolution safety checks
    - Response body streaming with size caps
    - Timing and metadata collection
    """

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        max_response_size: int = DEFAULT_MAX_RESPONSE_SIZE,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        user_agent: str = DEFAULT_USER_AGENT,
        verify_dns: bool = True,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.timeout = timeout
        self.max_response_size = max_response_size
        self.max_redirects = max_redirects
        self.user_agent = user_agent
        self.verify_dns = verify_dns
        self.transport = transport

    def get(self, url: str) -> FetchResponse:
        """Fetch a URL safely using HTTP GET."""
        original_url = url
        try:
            current_url = normalize_url(url)
        except (InvalidURLError, PrivateTargetError) as exc:
            return FetchResponse(
                url=url,
                original_url=original_url,
                error=f"URL validation failed: {exc}",
                success=False,
            )

        redirect_chain: List[str] = [current_url]
        redirect_count = 0

        client_kwargs = {
            "timeout": self.timeout,
            "follow_redirects": False,
            "headers": {"User-Agent": self.user_agent},
        }
        if self.transport is not None:
            client_kwargs["transport"] = self.transport

        with httpx.Client(**client_kwargs) as client:
            while True:
                # Host & SSRF checks
                hostname = extract_hostname(current_url)
                if not hostname:
                    return FetchResponse(
                        url=current_url,
                        original_url=original_url,
                        redirect_chain=redirect_chain,
                        error="Missing or invalid hostname.",
                        success=False,
                    )

                if is_private_or_local_target(hostname):
                    return FetchResponse(
                        url=current_url,
                        original_url=original_url,
                        redirect_chain=redirect_chain,
                        error=f"Target '{hostname}' is a private or local address.",
                        success=False,
                    )

                # Optional network-level DNS safety verification
                if self.verify_dns and self.transport is None:
                    try:
                        parsed = urllib.parse.urlparse(current_url)
                        port = parsed.port or (443 if parsed.scheme == "https" else 80)
                        _verify_resolved_ips(hostname, port)
                    except (PrivateTargetError, InvalidURLError) as exc:
                        return FetchResponse(
                            url=current_url,
                            original_url=original_url,
                            redirect_chain=redirect_chain,
                            error=f"DNS safety check failed: {exc}",
                            success=False,
                        )

                # Execute request with timing
                start_time = time.perf_counter()
                try:
                    request = client.build_request("GET", current_url)
                    response = client.send(request, stream=True)
                except httpx.TimeoutException:
                    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    return FetchResponse(
                        url=current_url,
                        original_url=original_url,
                        response_time_ms=elapsed_ms,
                        redirect_chain=redirect_chain,
                        error="Request timed out.",
                        success=False,
                    )
                except httpx.RequestError as exc:
                    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    return FetchResponse(
                        url=current_url,
                        original_url=original_url,
                        response_time_ms=elapsed_ms,
                        redirect_chain=redirect_chain,
                        error=f"Request error: {exc}",
                        success=False,
                    )
                except Exception as exc:
                    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    return FetchResponse(
                        url=current_url,
                        original_url=original_url,
                        response_time_ms=elapsed_ms,
                        redirect_chain=redirect_chain,
                        error=f"Unexpected error: {exc}",
                        success=False,
                    )

                # Check for redirect status codes
                if response.status_code in (301, 302, 303, 307, 308):
                    response.close()
                    location = response.headers.get("location")
                    if not location:
                        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                        return FetchResponse(
                            url=current_url,
                            original_url=original_url,
                            status_code=response.status_code,
                            headers=dict(response.headers),
                            content_type=response.headers.get("content-type"),
                            response_time_ms=elapsed_ms,
                            redirect_chain=redirect_chain,
                            error="Redirect status received without Location header.",
                            success=True,
                        )

                    redirect_count += 1
                    if redirect_count > self.max_redirects:
                        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                        return FetchResponse(
                            url=current_url,
                            original_url=original_url,
                            status_code=response.status_code,
                            response_time_ms=elapsed_ms,
                            redirect_chain=redirect_chain,
                            error=f"Maximum redirects ({self.max_redirects}) exceeded.",
                            success=False,
                        )

                    # Resolve relative redirect URL
                    resolved_target = urllib.parse.urljoin(current_url, location)
                    try:
                        next_url = normalize_url(resolved_target)
                    except (InvalidURLError, PrivateTargetError) as exc:
                        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                        return FetchResponse(
                            url=resolved_target,
                            original_url=original_url,
                            status_code=response.status_code,
                            response_time_ms=elapsed_ms,
                            redirect_chain=redirect_chain,
                            error=f"Redirect to unsafe/invalid URL blocked: {exc}",
                            success=False,
                        )

                    # Detect redirect loops
                    if next_url in redirect_chain:
                        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                        return FetchResponse(
                            url=next_url,
                            original_url=original_url,
                            status_code=response.status_code,
                            response_time_ms=elapsed_ms,
                            redirect_chain=redirect_chain,
                            error=f"Redirect loop detected to '{next_url}'.",
                            success=False,
                        )

                    redirect_chain.append(next_url)
                    current_url = next_url
                    continue

                # Non-redirect response: stream body up to size limit
                try:
                    collected_bytes = bytearray()
                    is_truncated = False

                    for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
                        space_left = self.max_response_size - len(collected_bytes)
                        if len(chunk) > space_left:
                            collected_bytes.extend(chunk[:space_left])
                            is_truncated = True
                            break
                        collected_bytes.extend(chunk)
                finally:
                    response.close()

                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                raw_content = bytes(collected_bytes)

                # Decode text safely
                encoding = response.encoding or "utf-8"
                try:
                    text_content = raw_content.decode(encoding, errors="replace")
                except Exception:
                    text_content = raw_content.decode("utf-8", errors="replace")

                content_type = response.headers.get("content-type")

                return FetchResponse(
                    url=current_url,
                    original_url=original_url,
                    status_code=response.status_code,
                    content_type=content_type,
                    headers=dict(response.headers),
                    content=raw_content,
                    text=text_content,
                    response_time_ms=elapsed_ms,
                    redirect_chain=redirect_chain,
                    is_truncated=is_truncated,
                    error=None,
                    success=True,
                )


def fetch_url(
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
    max_response_size: int = DEFAULT_MAX_RESPONSE_SIZE,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    user_agent: str = DEFAULT_USER_AGENT,
    verify_dns: bool = True,
    transport: Optional[httpx.BaseTransport] = None,
) -> FetchResponse:
    """Convenience helper to safely fetch a single URL."""
    client = SafeHTTPClient(
        timeout=timeout,
        max_response_size=max_response_size,
        max_redirects=max_redirects,
        user_agent=user_agent,
        verify_dns=verify_dns,
        transport=transport,
    )
    return client.get(url)
