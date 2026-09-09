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


def audit_entity(
    snapshot: SiteSnapshot,
    parsed_pages: List[ParsedPageContent],
) -> Tuple[List[Finding], EntityProfile]:
    findings: List[Finding] = []
    homepage_parsed = parsed_pages[0] if parsed_pages else parse_page_html(snapshot.homepage.url)
    homepage_url = snapshot.homepage.url

    # 1. Discover Organization Name & Names Across Surfaces
    discovered_names: Dict[str, str] = {}  # source -> name

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

    # From OpenGraph / Meta Site Name
    if homepage_parsed.meta_site_name:
        discovered_names["meta_site_name"] = homepage_parsed.meta_site_name

    # From Homepage Title (e.g. "Acme Corp | Enterprise Cloud Storage" or "Acme Corp - Home")
    title = homepage_parsed.title
    title_brand = ""
    if title:
        parts = re.split(r"[-–—|\:\•]", title)
        for part in parts:
            p = part.strip()
            if p.lower() not in GENERIC_TITLES and len(p) > 1:
                title_brand = p
                discovered_names["title"] = title_brand
                break

    # From Footer Copyright (e.g. "© 2026 Acme Corp Pvt Ltd")
    footer_brand = ""
    for stmt in homepage_parsed.copyright_statements:
        match = re.search(r"(?:19|20)\d{2}\s+([A-Za-z0-9\s,\.\-&]+)", stmt)
        if match:
            cand = match.group(1).strip().rstrip(".,")
            if len(cand) > 2 and cand.lower() not in ("all rights reserved", "inc", "llc"):
                footer_brand = cand
                discovered_names["footer_copyright"] = footer_brand
                break

    # Determine Consolidated Primary Name
    primary_name = (
        schema_org_name
        or discovered_names.get("meta_site_name")
        or title_brand
        or footer_brand
        or snapshot.site
    )

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
        findings.append(
            Finding(
                id="EC-002",
                category=CategoryType.ENTITY,
                title="Insufficient organization disambiguation and business description",
                severity=SeverityLevel.HIGH if not has_concrete_description else SeverityLevel.MEDIUM,
                confidence=0.89,
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
                    priority=SeverityLevel.HIGH,
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
    profile = EntityProfile(
        name=primary_name,
        type="Organization",
        description=primary_description or None,
        industry=detected_industry,
        confidence_score=0.92 if (has_concrete_description and schema_org_found) else (0.75 if has_concrete_description else 0.50),
    )

    return findings, profile
