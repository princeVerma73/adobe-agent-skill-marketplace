"""Static HTML extraction and content sufficiency heuristics.

Extracts SEO metadata, canonical links, robots directives, headings,
visible body text, hyperlinks, JSON-LD structured data, and OpenGraph/Twitter cards.
Detects when static HTML is insufficient and requires client-side JavaScript rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
from bs4 import BeautifulSoup, Comment

from src.inspection.models import (
    Heading,
    Link,
    PageInspection,
    PageMetadata,
    TechnicalIssue,
)
from src.inspection.url import (
    is_private_or_local_target,
    is_same_site,
    is_valid_url,
    normalize_url,
)

# Common SPA / client-side rendering indicators
SPA_CONTAINER_PATTERNS = [
    re.compile(r'<div[^>]+id=["\'](?:root|app|__next|__nuxt|main-app|app-root)["\'][^>]*>\s*</div>', re.IGNORECASE),
    re.compile(r'<div[^>]+id=["\'](?:root|app|__next|__nuxt|main-app|app-root)["\'][^>]*>\s*<!--.*?-->\s*</div>', re.IGNORECASE | re.DOTALL),
]

NOSCRIPT_JS_REQUIRED_PATTERNS = [
    re.compile(r"you\s+need\s+to\s+enable\s+javascript", re.IGNORECASE),
    re.compile(r"javascript\s+is\s+required", re.IGNORECASE),
    re.compile(r"enable\s+javascript\s+to\s+run\s+this\s+app", re.IGNORECASE),
    re.compile(r"javascript\s+is\s+disabled", re.IGNORECASE),
    re.compile(r"please\s+enable\s+javascript", re.IGNORECASE),
]

FRAMEWORK_SCRIPT_PATTERNS = [
    re.compile(r"static/js/main\.[a-z0-9]+\.js", re.IGNORECASE),
    re.compile(r"_next/static/", re.IGNORECASE),
    re.compile(r"_nuxt/", re.IGNORECASE),
    re.compile(r"react", re.IGNORECASE),
    re.compile(r"vue", re.IGNORECASE),
    re.compile(r"angular", re.IGNORECASE),
]


@dataclass
class ExtractedData:
    """Structured extraction output from static or rendered HTML."""
    title: Optional[str] = None
    metadata: PageMetadata = field(default_factory=PageMetadata)
    headings: List[Heading] = field(default_factory=list)
    body_text: str = ""
    links: List[Link] = field(default_factory=list)
    structured_data: List[Dict[str, Any]] = field(default_factory=list)
    raw_text: str = ""


def _clean_text(text: Optional[str]) -> str:
    """Normalize whitespace in text content."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_headings(soup: BeautifulSoup) -> List[Heading]:
    """Extract H1-H6 headings in document order."""
    headings: List[Heading] = []
    for elem in soup.find_all(re.compile(r"^h[1-6]$", re.IGNORECASE)):
        tag_name = elem.name.lower()
        level = int(tag_name[1])
        text = _clean_text(elem.get_text())
        if text:
            headings.append(Heading(level=level, text=text))
    return headings


def extract_links(soup: BeautifulSoup, base_url: str) -> List[Link]:
    """Extract normalized links with anchor text, rel, and internal/external detection."""
    links: List[Link] = []
    seen: set = set()

    # Determine effective base URL if <base href="..."> is present
    effective_base = base_url
    base_elem = soup.find("base", href=True)
    if base_elem and base_elem.get("href"):
        try:
            effective_base = urllib.parse.urljoin(base_url, base_elem["href"].strip())
        except Exception:
            effective_base = base_url

    for a_tag in soup.find_all("a", href=True):
        raw_href = a_tag["href"].strip()
        if not raw_href or raw_href.startswith("#"):
            continue

        # Skip non-web schemes
        if re.match(r"^(javascript|mailto|tel|data|ftp|file):", raw_href, re.IGNORECASE):
            continue

        try:
            resolved_url = urllib.parse.urljoin(effective_base, raw_href)
        except Exception:
            continue

        if not is_valid_url(resolved_url) or is_private_or_local_target(resolved_url):
            continue

        try:
            norm_url = normalize_url(resolved_url)
        except Exception:
            continue

        anchor_text = _clean_text(a_tag.get_text())
        rel_attr = a_tag.get("rel")
        rel_val = " ".join(rel_attr) if isinstance(rel_attr, list) else rel_attr

        is_internal = is_same_site(base_url, norm_url)

        # Deduplicate identical link instances by (url, text, rel)
        dedup_key = (norm_url, anchor_text, rel_val)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        links.append(
            Link(
                url=norm_url,
                text=anchor_text,
                is_internal=is_internal,
                rel=rel_val,
            )
        )

    return links


def extract_structured_data(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Extract and parse JSON-LD structured data scripts."""
    structured_items: List[Dict[str, Any]] = []

    for script in soup.find_all("script", type=re.compile(r"application/ld\+json", re.IGNORECASE)):
        raw_content = script.string or script.get_text()
        if not raw_content or not raw_content.strip():
            continue

        try:
            parsed = json.loads(raw_content.strip())
            if isinstance(parsed, dict):
                structured_items.append(parsed)
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        structured_items.append(item)
        except (json.JSONDecodeError, ValueError):
            # Ignore malformed JSON-LD gracefully
            continue

    return structured_items


def extract_metadata(soup: BeautifulSoup, base_url: str) -> PageMetadata:
    """Extract metadata tags, canonical URL, robots meta, Open Graph, and Twitter tags."""
    title: Optional[str] = None
    title_elem = soup.find("title")
    if title_elem and title_elem.string:
        title = _clean_text(title_elem.string)

    meta_desc: Optional[str] = None
    robots_meta: Optional[str] = None
    canonical_url: Optional[str] = None
    open_graph: Dict[str, str] = {}
    twitter_card: Dict[str, str] = {}
    extra: Dict[str, str] = {}

    # Canonical URL
    canonical_elem = soup.find("link", rel=re.compile(r"\bcanonical\b", re.IGNORECASE), href=True)
    if canonical_elem and canonical_elem.get("href"):
        raw_canonical = canonical_elem["href"].strip()
        try:
            resolved_canonical = urllib.parse.urljoin(base_url, raw_canonical)
            if is_valid_url(resolved_canonical) and not is_private_or_local_target(resolved_canonical):
                canonical_url = normalize_url(resolved_canonical)
            else:
                canonical_url = raw_canonical
        except Exception:
            canonical_url = raw_canonical

    # Meta tags
    for meta in soup.find_all("meta"):
        content = meta.get("content")
        if content is None:
            continue
        content = _clean_text(content)

        name = meta.get("name", "").strip().lower()
        prop = meta.get("property", "").strip().lower()

        # Description
        if name == "description" and not meta_desc:
            meta_desc = content
        elif name in ("robots", "googlebot") and not robots_meta:
            robots_meta = content

        # OpenGraph (property="og:...")
        if prop.startswith("og:") or name.startswith("og:"):
            key = prop if prop.startswith("og:") else name
            open_graph[key] = content

        # Twitter (name="twitter:..." or property="twitter:...")
        if name.startswith("twitter:") or prop.startswith("twitter:"):
            key = name if name.startswith("twitter:") else prop
            twitter_card[key] = content

        # Other useful meta properties
        if name and name not in ("description", "robots", "googlebot") and not name.startswith(("og:", "twitter:")):
            extra[name] = content

    # If title wasn't found in <title>, fallback to og:title
    if not title and "og:title" in open_graph:
        title = open_graph["og:title"]

    return PageMetadata(
        title=title,
        description=meta_desc,
        canonical_url=canonical_url,
        robots_meta=robots_meta,
        open_graph=open_graph,
        twitter_card=twitter_card,
        extra=extra,
    )


def extract_visible_text(soup: BeautifulSoup) -> str:
    """Extract visible body text content stripping scripts, styles, and other non-visible elements."""
    body = soup.find("body") or soup

    # Remove non-visible elements
    for element in body(
        ["script", "style", "noscript", "svg", "canvas", "template", "iframe", "head", "audio", "video", "source"]
    ):
        element.decompose()

    # Remove comments
    for comment in body.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    raw_text = body.get_text(separator=" ", strip=True)
    return _clean_text(raw_text)


def extract_static_html(html: str, base_url: str) -> ExtractedData:
    """Extract all relevant SEO, technical, and structured data from static HTML source."""
    if not html or not isinstance(html, str):
        return ExtractedData()

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    metadata = extract_metadata(soup, base_url)
    headings = extract_headings(soup)
    links = extract_links(soup, base_url)
    structured_data = extract_structured_data(soup)
    body_text = extract_visible_text(soup)

    return ExtractedData(
        title=metadata.title,
        metadata=metadata,
        headings=headings,
        body_text=body_text,
        links=links,
        structured_data=structured_data,
        raw_text=body_text,
    )


def is_rendering_needed(
    html: str,
    extracted: Optional[ExtractedData] = None,
    min_body_chars: int = 80,
    base_url: str = "",
) -> Tuple[bool, str]:
    """Detect whether static HTML appears insufficient for meaningful page content.
    
    Heuristics:
    1. Presence of empty SPA root containers (<div id="root"></div>, <div id="app"></div>, etc.).
    2. Explicit <noscript> requiring JavaScript.
    3. Body text is absent or very short (< min_body_chars) while <script> tags exist.
    4. Absence of headings, paragraphs, and links while client framework scripts are present.
    
    Returns:
        (needs_rendering, reason_string)
    """
    if not html or not isinstance(html, str):
        return False, "Empty or invalid HTML source"

    if extracted is None:
        extracted = extract_static_html(html, base_url=base_url)

    # Check 1: Explicit noscript JavaScript requirement
    for pattern in NOSCRIPT_JS_REQUIRED_PATTERNS:
        if pattern.search(html):
            return True, "Noscript JavaScript requirement notice detected"

    # Check 2: Empty SPA root container
    for pattern in SPA_CONTAINER_PATTERNS:
        if pattern.search(html):
            return True, "Empty Single-Page Application (SPA) root container detected"

    # Check 3: Visible body text is very short while scripts are present
    has_scripts = bool(re.search(r"<script\b[^>]*>", html, re.IGNORECASE))
    body_len = len(extracted.body_text)

    if has_scripts and body_len < min_body_chars:
        return True, f"Insufficient visible body text ({body_len} chars < {min_body_chars} threshold) with scripts present"

    # Check 4: No headings and sparse content while framework script markers exist
    has_framework_scripts = any(pat.search(html) for pat in FRAMEWORK_SCRIPT_PATTERNS)
    if has_framework_scripts and len(extracted.headings) == 0 and body_len < 150:
        return True, "Framework script markers present with no headings and sparse content"

    return False, "Static HTML contains sufficient content"


def populate_page_inspection(
    page: PageInspection,
    html: str,
    base_url: Optional[str] = None,
    is_rendered: bool = False,
    rendered_text: Optional[str] = None,
) -> PageInspection:
    """Populate or enrich a PageInspection model with extracted data."""
    effective_url = base_url or page.url
    extracted = extract_static_html(html, base_url=effective_url)

    page.raw_html_available = bool(html)
    page.title = extracted.title
    page.metadata = extracted.metadata
    page.headings = extracted.headings
    page.body_text = extracted.body_text
    page.links = extracted.links
    page.structured_data = extracted.structured_data

    if is_rendered:
        page.is_rendered = True
        page.rendered_text = rendered_text if rendered_text is not None else extracted.body_text
        if page.source_text is None:
            page.source_text = extracted.body_text
    else:
        page.source_text = extracted.body_text

    return page
