"""Robots.txt inspection and compliance checking.

Fetches and parses robots.txt to determine agent crawl permissions, sitemap
declarations, crawl-delay directives, and retains raw text evidence.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple
import urllib.parse

from src.inspection.models import RobotsTxtInspection
from src.inspection.url import extract_hostname, is_valid_url, normalize_url

if TYPE_CHECKING:
    from src.crawler.http import SafeHTTPClient

DEFAULT_AUDIT_USER_AGENT = "Adobe-BrandAuditBot/1.0 (+https://adobe.com/agent-marketplace-audit)"


class RobotsParser:
    """Deterministic, standard-compliant parser for robots.txt content."""

    def __init__(self, raw_text: Optional[str] = None) -> None:
        self.raw_text: str = raw_text or ""
        self.sitemaps: List[str] = []
        self.crawl_delay: Optional[float] = None
        # Mapping: normalized user_agent -> list of (is_allow: bool, path_pattern: str)
        self.rules: Dict[str, List[Tuple[bool, str]]] = {}
        if self.raw_text:
            self._parse()

    def _parse(self) -> None:
        lines = self.raw_text.splitlines()
        current_agents: List[str] = []
        in_rule_section: bool = False

        for raw_line in lines:
            # Strip comments and whitespace
            line = raw_line.split("#")[0].strip()
            if not line:
                continue

            if ":" not in line:
                continue

            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip()

            if key == "user-agent":
                agent = val.lower()
                if in_rule_section:
                    current_agents = []
                    in_rule_section = False
                current_agents.append(agent)
                if agent not in self.rules:
                    self.rules[agent] = []
            elif key == "sitemap":
                if val:
                    self.sitemaps.append(val)
            elif key == "crawl-delay":
                try:
                    self.crawl_delay = float(val)
                except ValueError:
                    pass
            elif key == "disallow":
                if not current_agents:
                    continue
                in_rule_section = True
                # Empty disallow means allow all (no restriction)
                if not val:
                    for agent in current_agents:
                        self.rules[agent].append((True, ""))
                else:
                    for agent in current_agents:
                        self.rules[agent].append((False, val))
            elif key == "allow":
                if not current_agents:
                    continue
                in_rule_section = True
                if val:
                    for agent in current_agents:
                        self.rules[agent].append((True, val))

    def _match_path(self, pattern: str, path: str) -> bool:
        """Check if path matches a robots.txt pattern (supporting * and $)."""
        if not pattern:
            return True

        # Escape pattern special characters except * and $
        regex_parts = []
        for char in pattern:
            if char == "*":
                regex_parts.append(".*")
            elif char == "$":
                regex_parts.append("$")
            else:
                regex_parts.append(re.escape(char))

        regex_str = "^" + "".join(regex_parts)
        if not regex_str.endswith("$"):
            # robots.txt patterns are prefix matches unless terminated with $
            regex_str += ".*"

        try:
            return bool(re.match(regex_str, path))
        except re.error:
            return path.startswith(pattern)

    def is_allowed(self, path_or_url: str, user_agent: str = DEFAULT_AUDIT_USER_AGENT) -> bool:
        """Check whether a given path or URL is permitted for the specified user agent.
        
        Evaluates the most specific matching rule (longest path pattern), with
        Allow taking precedence over Disallow for equal-length rules.
        """
        # Extract path component
        if "://" in path_or_url:
            parsed = urllib.parse.urlparse(path_or_url)
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"
        else:
            path = path_or_url if path_or_url.startswith("/") else f"/{path_or_url}"

        ua_clean = user_agent.strip().lower()
        ua_token = ua_clean.split("/")[0].split("-")[0]  # e.g., 'adobe' or 'brandauditbot'

        # Find best matching user-agent rules block
        matching_rules: Optional[List[Tuple[bool, str]]] = None

        # 1. Exact or substring match for specific user-agent
        for agent_key, rules in self.rules.items():
            if agent_key in ua_clean or ua_token in agent_key:
                matching_rules = rules
                break

        # 2. Fallback to wildcard '*'
        if matching_rules is None and "*" in self.rules:
            matching_rules = self.rules["*"]

        # If no matching agent block or no rules, allowed by default
        if not matching_rules:
            return True

        # Find matching rules and select by longest matching pattern (RFC 9309)
        candidate_matches: List[Tuple[int, bool, str]] = []  # (length, is_allow, pattern)
        for is_allow, pattern in matching_rules:
            if self._match_path(pattern, path):
                candidate_matches.append((len(pattern), is_allow, pattern))

        if not candidate_matches:
            return True

        # Sort candidate matches:
        # 1. Longest pattern length first
        # 2. is_allow True first (Allow beats Disallow on tie)
        candidate_matches.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return candidate_matches[0][1]


def inspect_robots_txt(
    site_url: str,
    target_path_or_url: Optional[str] = None,
    client: Optional[SafeHTTPClient] = None,
    user_agent: str = DEFAULT_AUDIT_USER_AGENT,
) -> RobotsTxtInspection:
    """Fetch and inspect robots.txt for a website.
    
    Distinguishes:
    1. robots.txt found (200) and policy allows target -> found=True, allowed_for_agent=True
    2. robots.txt found (200) and policy disallows target -> found=True, allowed_for_agent=False
    3. robots.txt missing (404/410) -> found=False, allowed_for_agent=True (unrestricted by RFC)
    4. robots.txt unavailable/error (5xx/network/timeout) -> found=False, allowed_for_agent=None (indeterminate)
    
    Args:
        site_url: Base domain or root URL of the target site.
        target_path_or_url: Specific path or URL to check permissions for (defaults to site root).
        client: Optional configured SafeHTTPClient (uses default safe fetcher if None).
        user_agent: User-Agent string to evaluate rules against.
        
    Returns:
        RobotsTxtInspection populated with observation data and error states.
    """
    try:
        norm_site = normalize_url(site_url)
    except Exception as exc:
        return RobotsTxtInspection(
            checked=False,
            found=False,
            allowed_for_agent=None,
            error=f"Invalid site URL: {exc}",
        )

    parsed = urllib.parse.urlparse(norm_site)
    scheme = parsed.scheme if parsed.scheme in ("http", "https") else "https"
    hostname = parsed.hostname or extract_hostname(site_url)

    if not hostname:
        return RobotsTxtInspection(
            checked=False,
            found=False,
            allowed_for_agent=None,
            error="Missing or invalid hostname.",
        )

    port_part = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
    robots_url = f"{scheme}://{hostname}{port_part}/robots.txt"

    # Fetch robots.txt safely
    if client is not None:
        fetch_resp = client.get(robots_url)
    else:
        from src.crawler.http import fetch_url
        fetch_resp = fetch_url(robots_url, user_agent=user_agent)

    target_check = target_path_or_url or norm_site

    # Case 3: robots.txt missing (404/410) -> explicitly absent, unrestricted by standard convention
    if fetch_resp.status_code in (404, 410):
        return RobotsTxtInspection(
            checked=True,
            found=False,
            status_code=fetch_resp.status_code,
            allowed_for_agent=True,
            error=None,
        )

    # Case 4: robots.txt unavailable / error (5xx, connection error, timeout, non-200) -> indeterminate
    if not fetch_resp.success or fetch_resp.status_code != 200:
        error_msg = fetch_resp.error or (
            f"Server returned HTTP status code {fetch_resp.status_code}"
            if fetch_resp.status_code
            else "Failed to retrieve robots.txt"
        )
        return RobotsTxtInspection(
            checked=True,
            found=False,
            status_code=fetch_resp.status_code,
            allowed_for_agent=None,
            error=error_msg,
        )

    # Cases 1 & 2: robots.txt found (200) -> parse and evaluate rule policy
    raw_text = fetch_resp.text
    parser = RobotsParser(raw_text)
    is_allowed = parser.is_allowed(target_check, user_agent=user_agent)

    # Normalize sitemap URLs
    clean_sitemaps: List[str] = []
    for sm in parser.sitemaps:
        try:
            if is_valid_url(sm):
                clean_sitemaps.append(normalize_url(sm))
            else:
                clean_sitemaps.append(sm)
        except Exception:
            clean_sitemaps.append(sm)

    return RobotsTxtInspection(
        checked=True,
        found=True,
        status_code=200,
        allowed_for_agent=is_allowed,
        sitemap_urls=clean_sitemaps,
        crawl_delay=parser.crawl_delay,
        raw_text=raw_text,
        error=None,
    )
