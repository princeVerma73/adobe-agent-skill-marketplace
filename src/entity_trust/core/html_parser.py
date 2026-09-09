"""HTML & DOM parsing layer for extracting text, semantic tags, metadata, and JSON-LD."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup


@dataclass
class ImageInfo:
    src: str
    alt: str
    title: str = ""
    caption: str = ""
    classes: List[str] = field(default_factory=list)
    is_informative_candidate: bool = False


@dataclass
class ParsedPageContent:
    url: str
    title: str = ""
    h1s: List[str] = field(default_factory=list)
    h2s: List[str] = field(default_factory=list)
    meta_description: str = ""
    meta_site_name: str = ""
    meta_dates: Dict[str, str] = field(default_factory=dict)
    clean_text: str = ""
    footer_text: str = ""
    images: List[ImageInfo] = field(default_factory=list)
    json_ld_objects: List[Dict[str, Any]] = field(default_factory=list)
    copyright_statements: List[str] = field(default_factory=list)


# Keywords suggesting an image represents an informational chart/graphic/metric
INFORMATIVE_IMG_PATTERNS = re.compile(
    r"(infographic|statistic|metric|chart|diagram|badge|award|certif|timeline|feature|result|score|founded|overview)",
    re.IGNORECASE,
)

COPYRIGHT_REGEX = re.compile(
    r"(?:©|&copy;|copyright)\s*(?:(?:19|20)\d{2}\s*[-–—]\s*)?((?:19|20)\d{2})\b(?:\s+([A-Za-z0-9\s,\.\-]+))?",
    re.IGNORECASE,
)


def parse_page_html(
    url: str,
    html: Optional[str] = None,
    fallback_text: Optional[str] = None,
    fallback_title: Optional[str] = None,
    pre_extracted_images: Optional[List[Dict[str, Any]]] = None,
    pre_extracted_json_ld: Optional[List[Dict[str, Any]]] = None,
) -> ParsedPageContent:
    """Parses raw HTML or falls back to text/metadata snapshot."""
    parsed = ParsedPageContent(url=url)
    parsed.title = (fallback_title or "").strip()
    parsed.clean_text = (fallback_text or "").strip()

    if pre_extracted_json_ld:
        parsed.json_ld_objects.extend(pre_extracted_json_ld)

    if pre_extracted_images:
        for img in pre_extracted_images:
            alt = img.get("alt", "").strip()
            src = img.get("src", "")
            is_inf = bool(INFORMATIVE_IMG_PATTERNS.search(src) or INFORMATIVE_IMG_PATTERNS.search(alt))
            parsed.images.append(
                ImageInfo(
                    src=src,
                    alt=alt,
                    title=img.get("title", ""),
                    caption=img.get("caption", ""),
                    classes=img.get("classes", []),
                    is_informative_candidate=is_inf,
                )
            )

    if not html:
        # If no HTML, scan fallback text for copyright
        for match in COPYRIGHT_REGEX.finditer(parsed.clean_text):
            parsed.copyright_statements.append(match.group(0))
        return parsed

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return parsed

    # 1. Title
    if soup.title and soup.title.string:
        parsed.title = soup.title.string.strip()

    # 2. Meta tags
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or "").lower()
        content = (meta.get("content") or "").strip()
        if not content:
            continue

        if name in ("description", "og:description", "twitter:description") and not parsed.meta_description:
            parsed.meta_description = content
        elif name in ("og:site_name", "application-name") and not parsed.meta_site_name:
            parsed.meta_site_name = content
        elif any(d in name for d in ("published", "modified", "updated", "date", "time")):
            parsed.meta_dates[name] = content

    # 3. Headings
    parsed.h1s = [h1.get_text(separator=" ", strip=True) for h1 in soup.find_all("h1") if h1.get_text(strip=True)]
    parsed.h2s = [h2.get_text(separator=" ", strip=True) for h2 in soup.find_all("h2") if h2.get_text(strip=True)]

    # 4. JSON-LD Extraction
    for script in soup.find_all("script", type="application/ld+json"):
        if script.string:
            try:
                data = json.loads(script.string.strip())
                if isinstance(data, list):
                    parsed.json_ld_objects.extend(data)
                elif isinstance(data, dict):
                    # Handle @graph
                    if "@graph" in data and isinstance(data["@graph"], list):
                        parsed.json_ld_objects.extend(data["@graph"])
                    else:
                        parsed.json_ld_objects.append(data)
            except Exception:
                continue

    # 5. Images with Alt / Captions
    if not parsed.images:
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            alt = (img.get("alt") or "").strip()
            title = (img.get("title") or "").strip()
            classes = img.get("class") or []
            if isinstance(classes, str):
                classes = classes.split()

            # Check parent figure/figcaption
            caption = ""
            parent_fig = img.find_parent("figure")
            if parent_fig:
                fig_cap = parent_fig.find("figcaption")
                if fig_cap:
                    caption = fig_cap.get_text(strip=True)

            img_signature = f"{src} {' '.join(classes)} {title}"
            is_inf = bool(INFORMATIVE_IMG_PATTERNS.search(img_signature))
            parsed.images.append(
                ImageInfo(
                    src=src,
                    alt=alt,
                    title=title,
                    caption=caption,
                    classes=classes,
                    is_informative_candidate=is_inf,
                )
            )

    # 6. Footer Text
    footers = soup.find_all(["footer", "div"], class_=re.compile(r"footer", re.I))
    if footers:
        footer_parts = [f.get_text(separator=" ", strip=True) for f in footers]
        parsed.footer_text = " ".join(footer_parts)

    # 7. Clean text
    # Remove script, style, noscript
    for s in soup(["script", "style", "noscript", "svg"]):
        s.decompose()

    body = soup.body or soup
    body_text = body.get_text(separator=" ", strip=True)
    if body_text:
        # Collapse excessive whitespace
        parsed.clean_text = re.sub(r"\s+", " ", body_text)

    # 8. Copyright extraction from text and footer
    search_text = f"{parsed.footer_text} {parsed.clean_text}"
    for match in COPYRIGHT_REGEX.finditer(search_text):
        stmt = match.group(0).strip()
        if stmt not in parsed.copyright_statements:
            parsed.copyright_statements.append(stmt)

    return parsed
