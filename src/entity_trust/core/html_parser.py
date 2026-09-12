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
    emails: List[str] = field(default_factory=list)
    phone_numbers: List[str] = field(default_factory=list)
    social_links: List[str] = field(default_factory=list)
    nav_items: List[str] = field(default_factory=list)
    paragraphs: List[str] = field(default_factory=list)


# Keywords suggesting an image represents an informational chart/graphic/metric
INFORMATIVE_IMG_PATTERNS = re.compile(
    r"(infographic|statistic|metric|chart|diagram|badge|award|certif|timeline|feature|result|score|founded|overview)",
    re.IGNORECASE,
)

COPYRIGHT_REGEX = re.compile(
    r"(?:©|&copy;|copyright)\s*(?:(?:19|20)\d{2}\s*[-–—]\s*)?((?:19|20)\d{2})\b(?:\s+([A-Za-z0-9\s,\.\-]+))?",
    re.IGNORECASE,
)

EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

SOCIAL_DOMAIN_REGEX = re.compile(
    r"(?:twitter\.com|x\.com|linkedin\.com|github\.com|facebook\.com|youtube\.com|instagram\.com)/([A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)

IGNORED_NAV_WORDS = {
    "home", "index", "login", "log in", "signin", "sign in", "signup", "sign up",
    "register", "logout", "log out", "cart", "checkout", "search", "menu", "close",
    "back", "next", "previous", "view all", "learn more", "read more", "get started",
    "cookie", "cookies", "privacy policy", "terms of service", "terms", "legal",
    "all rights reserved", "toggle navigation", "navigation", "skip to content",
}


def _filter_valid_email(email_str: str) -> Optional[str]:
    """Filters out invalid asset emails and dummy placeholders."""
    em = email_str.strip().lower()
    if any(em.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".js", ".css", ".ico", ".woff", ".woff2")):
        return None
    if any(d in em for d in ("example.com", "domain.com", "sentry.io", "w3.org", "yourname@", "user@", "username@", "test@test")):
        return None
    return em


def parse_page_html(
    url: str,
    html: Optional[str] = None,
    fallback_text: Optional[str] = None,
    fallback_title: Optional[str] = None,
    pre_extracted_images: Optional[List[Dict[str, Any]]] = None,
    pre_extracted_json_ld: Optional[List[Dict[str, Any]]] = None,
    pre_extracted_metadata: Optional[Dict[str, Any]] = None,
    pre_extracted_links: Optional[List[str]] = None,
) -> ParsedPageContent:
    """Parses raw HTML or falls back to text/metadata snapshot."""
    parsed = ParsedPageContent(url=url)
    parsed.title = (fallback_title or "").strip()
    parsed.clean_text = (fallback_text or "").strip()

    if pre_extracted_json_ld:
        parsed.json_ld_objects.extend(pre_extracted_json_ld)

    if pre_extracted_metadata:
        if isinstance(pre_extracted_metadata, dict):
            desc = pre_extracted_metadata.get("description")
            if desc and not parsed.meta_description:
                parsed.meta_description = str(desc).strip()
            og_dict = pre_extracted_metadata.get("open_graph", {})
            if isinstance(og_dict, dict):
                og_desc = og_dict.get("og:description")
                if og_desc and not parsed.meta_description:
                    parsed.meta_description = str(og_desc).strip()
                og_site = og_dict.get("og:site_name")
                if og_site and not parsed.meta_site_name:
                    parsed.meta_site_name = str(og_site).strip()

    if pre_extracted_links:
        for link_url in pre_extracted_links:
            if not isinstance(link_url, str):
                continue
            if link_url.startswith("mailto:"):
                clean_em = _filter_valid_email(link_url.replace("mailto:", "").split("?")[0])
                if clean_em and clean_em not in parsed.emails:
                    parsed.emails.append(clean_em)
            elif link_url.startswith("tel:"):
                phone = link_url.replace("tel:", "").strip()
                if phone and phone not in parsed.phone_numbers:
                    parsed.phone_numbers.append(phone)
            elif SOCIAL_DOMAIN_REGEX.search(link_url):
                if link_url not in parsed.social_links:
                    parsed.social_links.append(link_url)

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
        # If no HTML, scan fallback text for copyright, emails, and lead description
        for match in COPYRIGHT_REGEX.finditer(parsed.clean_text):
            parsed.copyright_statements.append(match.group(0))
        for match in EMAIL_REGEX.finditer(parsed.clean_text):
            clean_em = _filter_valid_email(match.group(0))
            if clean_em and clean_em not in parsed.emails:
                parsed.emails.append(clean_em)
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
        name = (meta.get("name") or meta.get("property") or meta.get("itemprop") or "").lower()
        content = (meta.get("content") or "").strip()
        if not content:
            continue

        if (
            name in ("description", "og:description", "twitter:description")
            or name.endswith(":description")
            or name == "description"
        ) and not parsed.meta_description:
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

    # Fallback for meta_description from JSON-LD if not present in meta tags
    if not parsed.meta_description and parsed.json_ld_objects:
        for item in parsed.json_ld_objects:
            desc = item.get("description")
            if desc and isinstance(desc, str) and len(desc.strip()) > 10:
                parsed.meta_description = desc.strip()
                break

    # 5. Links, mailto, tel, and social links
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if href.startswith("mailto:"):
            raw_em = href.replace("mailto:", "").split("?")[0].strip()
            clean_em = _filter_valid_email(raw_em)
            if clean_em and clean_em not in parsed.emails:
                parsed.emails.append(clean_em)
        elif href.startswith("tel:"):
            phone = href.replace("tel:", "").strip()
            if phone and phone not in parsed.phone_numbers:
                parsed.phone_numbers.append(phone)
        elif SOCIAL_DOMAIN_REGEX.search(href):
            if href not in parsed.social_links:
                parsed.social_links.append(href)

    # 6. Navigation Items / Offerings
    nav_elements = soup.find_all(["nav", "header"])
    for nav in nav_elements:
        for item in nav.find_all(["a", "li", "button"]):
            text = item.get_text(separator=" ", strip=True)
            text_cleaned = re.sub(r"\s+", " ", text).strip()
            words = text_cleaned.split()
            if 1 <= len(words) <= 4 and len(text_cleaned) <= 35:
                if text_cleaned.lower() not in IGNORED_NAV_WORDS and text_cleaned not in parsed.nav_items:
                    parsed.nav_items.append(text_cleaned)

    # 7. Substantive Paragraphs
    for p in soup.find_all("p"):
        p_txt = p.get_text(separator=" ", strip=True)
        p_clean = re.sub(r"\s+", " ", p_txt).strip()
        if len(p_clean) >= 30:
            parsed.paragraphs.append(p_clean)

    # Fallback for meta_description from first substantive paragraph if still empty
    if not parsed.meta_description and parsed.paragraphs:
        for p_clean in parsed.paragraphs:
            if not any(k in p_clean.lower() for k in ("cookie", "javascript", "browser", "rights reserved", "terms of use")):
                parsed.meta_description = p_clean
                break

    # 8. Images with Alt / Captions
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

    # 9. Footer Text
    footers = soup.find_all(["footer", "div"], class_=re.compile(r"footer", re.I))
    if footers:
        footer_parts = [f.get_text(separator=" ", strip=True) for f in footers]
        parsed.footer_text = " ".join(footer_parts)

    # 10. Clean text
    # Remove script, style, noscript
    for s in soup(["script", "style", "noscript", "svg"]):
        s.decompose()

    body = soup.body or soup
    body_text = body.get_text(separator=" ", strip=True)
    if body_text:
        # Collapse excessive whitespace
        parsed.clean_text = re.sub(r"\s+", " ", body_text)

    # 11. Copyright extraction from text and footer
    search_text = f"{parsed.footer_text} {parsed.clean_text}"
    for match in COPYRIGHT_REGEX.finditer(search_text):
        stmt = match.group(0).strip()
        if stmt not in parsed.copyright_statements:
            parsed.copyright_statements.append(stmt)

    # 12. Email extraction from clean text and footer
    for match in EMAIL_REGEX.finditer(search_text):
        clean_em = _filter_valid_email(match.group(0))
        if clean_em and clean_em not in parsed.emails:
            parsed.emails.append(clean_em)

    return parsed
