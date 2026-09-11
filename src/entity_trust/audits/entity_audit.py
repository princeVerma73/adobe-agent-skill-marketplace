"""Entity Intelligence Audit.

Evaluates whether an AI system can reliably identify the organization, its purpose,
industry, offerings, and disambiguate it from other entities.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from ..contracts.schemas import (
    CategoryType,
    EntityProfile,
    Finding,
    FindingAction,
    PageSnapshot,
    SeverityLevel,
    SiteSnapshot,
)
from ..core.html_parser import ParsedPageContent, parse_page_html


GENERIC_TITLES = {"home", "welcome", "index", "homepage", "home page", "default", "landing"}
GENERIC_H1S = {
    "welcome", "welcome to our website", "welcome to us", "home",
    "innovative solutions", "the future is here", "transforming business",
    "making a difference", "leading the way",
}

INDUSTRY_KEYWORDS = [
    "software", "saas", "fintech", "healthcare", "consulting", "e-commerce", "retail",
    "manufacturing", "logistics", "education", "edtech", "biotech", "aerospace",
    "legal", "real estate", "hospitality", "telecommunications", "cybersecurity",
    "cloud computing", "media", "energy", "automotive", "finance", "banking",
]


def _extract_domain_brand(site_or_url: str) -> str:
    """Extracts a clean brand/organization name from domain/hostname."""
    host = site_or_url
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split("/", 1)[0].split("?")[0].split(":")[0]
    parts = host.split(".")
    # Remove common subdomains and tlds
    meaningful = [
        p for p in parts
        if p.lower() not in (
            "www", "docs", "doc", "api", "app", "dev", "staging", "cdn",
            "com", "org", "net", "io", "so", "edu", "gov", "co", "uk", "de", "ai"
        )
    ]
    if meaningful:
        cand = meaningful[0]
        if cand.lower() == "python":
            return "Python"
        if cand.lower() == "fastapi":
            return "FastAPI"
        if cand.lower() == "mozilla":
            return "Mozilla"
        if cand.lower() == "notion":
            return "Notion"
        if cand.lower() == "theverge":
            return "The Verge"
        if cand.lower() == "wikimedia":
            return "Wikimedia"
        if cand.lower() == "nasa":
            return "NASA"
        if cand.lower() == "mit":
            return "MIT"
        return cand.capitalize()
    return host


def _clean_title_brand(title: str, domain_brand: str = "") -> Tuple[str, float]:
    """Cleans raw title string into an organization name candidate and confidence score."""
    if not title:
        return "", 0.0

    # Split title on common delimiters: " - ", " | ", " : ", " — ", " – ", " • "
    parts = [p.strip() for p in re.split(r"[-–—|\:\•]", title) if p.strip()]
    if not parts:
        return "", 0.0

    candidates: List[Tuple[str, str]] = []
    for part in parts:
        # Strip version numbers like 3.14.7, 3.x, v2.0
        cleaned = re.sub(r"\bv?\d+(?:\.\d+)+[a-z\d]*\b", "", part, flags=re.I)
        cleaned = re.sub(r"\b\d+\.x\b", "", cleaned, flags=re.I)
        # Strip generic documentation / app suffixes
        cleaned = re.sub(
            r"\b(?:Documentation|Docs|Doc|Manual|Reference|Guide|API|Tutorial|Official Site|Official Website|Homepage|Home)\b",
            "",
            cleaned,
            flags=re.I,
        ).strip()
        cleaned = cleaned.strip(" .,-–—:|•")
        if cleaned and cleaned.lower() not in GENERIC_TITLES:
            candidates.append((cleaned, part))

    if not candidates:
        return "", 0.0

    # If one part matches domain brand (e.g. "Mozilla" when domain is mozilla.org), prefer that
    if domain_brand:
        for cand, _ in candidates:
            if cand.lower() == domain_brand.lower():
                return cand, 0.70

    # If a candidate has 1-3 words and is not a long tagline/slogan, prefer it
    for cand, _ in candidates:
        words = cand.split()
        if 1 <= len(words) <= 3:
            is_slogan = any(w.lower() in ("for", "not", "is", "the", "with", "from", "your", "works") for w in words) and len(words) > 2
            if not is_slogan:
                return cand, 0.65

    best_cand = candidates[0][0]
    return best_cand, 0.55


def audit_entity(
    snapshot: SiteSnapshot,
    parsed_pages: List[ParsedPageContent],
) -> Tuple[List[Finding], EntityProfile]:
    findings: List[Finding] = []
    homepage_parsed = parsed_pages[0] if parsed_pages else parse_page_html(snapshot.homepage.url)
    homepage_url = snapshot.homepage.url
    domain_brand = _extract_domain_brand(snapshot.site or homepage_url)

    # 1. Discover Organization Name & Names Across Surfaces
    discovered_names: Dict[str, str] = {}  # source -> name
    name_source = "fallback"

    # From JSON-LD Schema
    schema_org_found = False
    schema_org_name = ""
    for page in parsed_pages:
        for item in page.json_ld_objects:
            t = str(item.get("@type", ""))
            if any(k in t.lower() for k in ("organization", "corporation", "localbusiness", "company")):
                schema_org_found = True
                name = item.get("name")
                if name:
                    schema_org_name = str(name).strip()
                    discovered_names["schema_org"] = schema_org_name
                    name_source = "schema_org"

    # From OpenGraph / Meta Site Name
    if homepage_parsed.meta_site_name:
        discovered_names["meta_site_name"] = homepage_parsed.meta_site_name
        if not schema_org_name:
            name_source = "meta_site_name"

    # From Homepage Title (with version/documentation cleaning)
    title = homepage_parsed.title
    title_brand, title_conf = _clean_title_brand(title, domain_brand=domain_brand)
    if title_brand:
        discovered_names["title"] = title_brand
        if not schema_org_name and not homepage_parsed.meta_site_name:
            name_source = "title"

    # From Footer Copyright (e.g. "© 2026 Acme Corp Pvt Ltd")
    footer_brand = ""
    for stmt in homepage_parsed.copyright_statements:
        match = re.search(r"(?:19|20)\d{2}\s+([A-Za-z0-9\s,\.\-&]+)", stmt)
        if match:
            cand = match.group(1).strip().rstrip(".,")
            if (
                2 < len(cand) <= 50
                and cand.lower() not in ("all rights reserved", "inc", "llc")
                and not any(w in cand.lower() for w in ("by individual", "license", "creative commons", "contributors", "terms of use", "privacy notice"))
            ):
                footer_brand = cand
                discovered_names["footer_copyright"] = footer_brand
                if not schema_org_name and not homepage_parsed.meta_site_name:
                    name_source = "footer_copyright"
                break

    # Determine Consolidated Primary Name
    primary_name = (
        schema_org_name
        or discovered_names.get("meta_site_name")
        or footer_brand
        or title_brand
        or domain_brand
        or snapshot.site
    )

    if not schema_org_name and not discovered_names.get("meta_site_name") and not footer_brand and not title_brand:
        name_source = "domain"

    # 2. Check 1: Organization Name Ambiguity & Weak H1/Title
    h1 = homepage_parsed.h1s[0].strip() if homepage_parsed.h1s else ""
    is_weak_title = not title or title.strip().lower() in GENERIC_TITLES
    is_weak_h1 = not h1 or h1.lower() in GENERIC_H1S or len(h1.split()) < 2

    if is_weak_title and is_weak_h1:
        findings.append(
            Finding(
                id="EC-001",
                category=CategoryType.ENTITY,
                title="Generic homepage title and heading obscure brand identity",
                severity=SeverityLevel.HIGH,
                confidence=0.92,
                evidence=(
                    f"Homepage at '{homepage_url}' uses non-descriptive identity elements: "
                    f"Title='{title or '[Empty]'}' and H1='{h1 or '[Empty]'}'."
                ),
                affected_urls=[homepage_url],
                suggested_action=FindingAction(
                    summary=(
                        f"Update the homepage <title> and main <h1> to explicitly state the brand name "
                        f"and core value proposition (e.g., '{primary_name} - AI Document Processing')."
                    ),
                    priority=SeverityLevel.HIGH,
                ),
            )
        )

    # 3. Check 2 & 4: Organization Description & Disambiguation
    # Combine homepage meta description, homepage body text, and about page text
    about_text = ""
    for page in parsed_pages:
        if "about" in page.url.lower():
            about_text += f" {page.clean_text}"

    combined_text = f"{homepage_parsed.meta_description} {homepage_parsed.clean_text[:1200]} {about_text[:1500]}"

    detected_industry = None
    for ind in INDUSTRY_KEYWORDS:
        if re.search(rf"\b{re.escape(ind)}\b", combined_text, re.I):
            detected_industry = ind
            break

    # Look for definitive entity definition phrases
    definition_pattern = re.compile(
        rf"(?:{re.escape(primary_name)}|we|our company|this company)\s+(?:is|provides|delivers|specializes in|develops|builds)\s+([^.]{{15,200}})",
        re.I,
    )
    def_match = definition_pattern.search(combined_text)
    primary_description = def_match.group(0).strip() if def_match else homepage_parsed.meta_description

    # Evaluate entity disambiguation clarity
    has_concrete_description = bool(def_match or len(homepage_parsed.meta_description) > 30)
    has_industry = detected_industry is not None

    if not has_concrete_description or not has_industry:
        # Calibrate severity: low-confidence title/domain fallback downgrades severity to MEDIUM
        is_low_conf_name = (name_source in ("title", "domain", "fallback") and not schema_org_found and not footer_brand)
        ec_severity = SeverityLevel.MEDIUM if is_low_conf_name else (
            SeverityLevel.HIGH if not has_concrete_description else SeverityLevel.MEDIUM
        )

        findings.append(
            Finding(
                id="EC-002",
                category=CategoryType.ENTITY,
                title="Insufficient organization disambiguation and business description",
                severity=ec_severity,
                confidence=0.89 if not is_low_conf_name else 0.75,
                evidence=(
                    f"The website provides the entity name '{primary_name}', but fails to provide a clear, "
                    f"unambiguous statement of what the organization does, its industry category, and whom it serves. "
                    f"Detected industry: {detected_industry or 'None'}. Description snippet: '{primary_description[:100] if primary_description else 'None'}..."
                ),
                affected_urls=[homepage_url],
                suggested_action=FindingAction(
                    summary=(
                        "Add a concise 1-2 sentence organization definition in plain readable text on the homepage "
                        "and About page declaring organization type, industry, target audience, and primary offerings."
                    ),
                    priority=ec_severity,
                ),
            )
        )

    # 4. Check 3: Schema.org Organization Presence
    if not schema_org_found:
        findings.append(
            Finding(
                id="EC-003",
                category=CategoryType.ENTITY,
                title="Missing Schema.org Organization structured data",
                severity=SeverityLevel.MEDIUM,
                confidence=0.95,
                evidence=(
                    f"No JSON-LD Schema.org 'Organization' or 'LocalBusiness' definition was found on "
                    f"'{homepage_url}' or secondary pages. Structured entity metadata enables search engines "
                    f"and AI systems to ground the entity without heuristic guessing."
                ),
                affected_urls=[homepage_url],
                suggested_action=FindingAction(
                    summary=(
                        "Implement JSON-LD Schema.org 'Organization' or 'Corporation' on the homepage with fields: "
                        "@context, @type, name, url, logo, description, and sameAs links."
                    ),
                    priority=SeverityLevel.MEDIUM,
                ),
            )
        )

    # 5. Build Consolidated Entity Profile
    if schema_org_found and has_concrete_description:
        conf_score = 0.92
    elif schema_org_found or footer_brand:
        conf_score = 0.80 if has_concrete_description else 0.65
    elif name_source in ("title", "domain"):
        conf_score = 0.70 if has_concrete_description else 0.50
    else:
        conf_score = 0.50

    profile = EntityProfile(
        name=primary_name,
        type="Organization",
        description=primary_description or None,
        industry=detected_industry,
        confidence_score=conf_score,
    )

    return findings, profile
