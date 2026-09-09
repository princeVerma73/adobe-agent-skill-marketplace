"""Crawler and HTTP fetching utilities."""

from src.crawler.http import (
    DEFAULT_MAX_REDIRECTS,
    DEFAULT_MAX_RESPONSE_SIZE,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    FetchResponse,
    SafeHTTPClient,
    fetch_url,
)

__all__ = [
    "DEFAULT_MAX_REDIRECTS",
    "DEFAULT_MAX_RESPONSE_SIZE",
    "DEFAULT_TIMEOUT",
    "DEFAULT_USER_AGENT",
    "FetchResponse",
    "SafeHTTPClient",
    "fetch_url",
]
