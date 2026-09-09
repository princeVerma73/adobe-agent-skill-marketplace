"""Content Clarity Audit.

Detects facts locked in non-text elements (images/graphics without text equivalents),
vague unsubstantiated marketing claims, and missing core organizational attributes.
"""

from __future__ import annotations

import re
from typing import List, Set
from ..contracts.schemas import (
    CategoryType,
    Finding,
    FindingAction,
    SeverityLevel,
    SiteSnapshot,
)
from ..core.html_parser import ParsedPageContent


# Vague marketing phrases that lack factual substance
VAGUE_PATTERNS = [
    re.compile(r"\b(world-class|best-in-class|industry-leading|cutting-edge|next-generation|game-changing)\s+(solutions?|services?|offerings?|products?)\b", re.I),
    re.compile(r"\b(we\s+empower\s+businesses\s+to\s+succeed|innovative\s+solutions\s+for\s+tomorrow|transforming\s+the\s+future)\b", re.I),
    re.compile(r"\b(unmatched|unparalleled|seamless)\s+(excellence|quality|performance|experience)\b", re.I),
]

# Patterns in image filenames, classes, or captions indicating factual/statistical content
IMAGE_FACT_INDICATORS = re.compile(
    r"(stat|metric|infographic|numbers|founded|timeline|award|certification|clients|growth|revenue|roi|percentage|chart|figure)",
    re.I,
)


def audit_content_clarity(
    snapshot: SiteSnapshot,
    parsed_pages: List[ParsedPageContent],
) -> List[Finding]:
    findings: List[Finding] = []

    # 1. Check A: Important Facts Locked in Non-Text Elements (Images without proper text or alt)
    for page in parsed_pages:
        for img in page.images:
            is_factual_img = bool(
                IMAGE_FACT_INDICATORS.search(img.src)
                or IMAGE_FACT_INDICATORS.search(img.title)
                or any(IMAGE_FACT_INDICATORS.search(c) for c in img.classes)
                or (img.caption and IMAGE_FACT_INDICATORS.search(img.caption))
            )

            if is_factual_img:
                # If the alt text is missing, generic, or too brief to convey the factual content
                is_missing_alt = not img.alt or img.alt.strip().lower() in ("image", "img", "graphic", "photo", "banner", "stat", "chart")
                is_insufficient_alt = len(img.alt.strip().split()) < 3

                if is_missing_alt or is_insufficient_alt:
                    evidence_src = img.src.split("/")[-1] or img.src
                    findings.append(
                        Finding(
                            id="CC-001",
                            category=CategoryType.CONTENT_CLARITY,
                            title="Factual and statistical metrics locked in non-text image without text equivalent",
                            severity=SeverityLevel.HIGH,
                            confidence=0.88,
                            evidence=(
                                f"Page '{page.url}' includes an informational graphic or metric asset ('{evidence_src}') "
                                f"with insufficient or missing text alternative: alt='{img.alt or '[None]'}'. "
                                f"Key operational facts, performance figures, or certifications embedded visually in images "
                                f"cannot be parsed by search engines or AI assistants."
                            ),
                            affected_urls=[page.url],
                            suggested_action=FindingAction(
                                summary=(
                                    "Render key statistics, facts, and metrics as crawlable HTML text, and provide "
                                    "descriptive alt text or captions detailing the numbers and data presented in the image."
                                ),
                                priority=SeverityLevel.HIGH,
                            ),
                        )
                    )

    # 2. Check B: Vague marketing claims lacking concrete factual support
    for page in parsed_pages:
        text = page.clean_text
        if len(text) < 50:
            continue

        vague_matches: List[str] = []
        for pat in VAGUE_PATTERNS:
            for match in pat.finditer(text):
                vague_matches.append(match.group(0))

        # Check if the page has concrete numbers, metrics, or factual statements to substantiate claims
        has_concrete_numbers = bool(re.search(r"\b(?:\d{2,}%|\d+(?:,\d{3})*\+?\s*(?:clients|users|hours|years|dollars|\$|€|₹))\b", text))
        has_concrete_descriptions = len(text.split()) > 150

        if len(vague_matches) >= 2 and not has_concrete_numbers:
            findings.append(
                Finding(
                    id="CC-002",
                    category=CategoryType.CONTENT_CLARITY,
                    title="Vague superlative claims without concrete supporting evidence",
                    severity=SeverityLevel.MEDIUM,
                    confidence=0.82,
                    evidence=(
                        f"Page '{page.url}' relies on generic superlative assertions ({', '.join(repr(m) for m in vague_matches[:3])}) "
                        f"without providing specific factual evidence, quantitative data, or technical capabilities."
                    ),
                    affected_urls=[page.url],
                    suggested_action=FindingAction(
                        summary=(
                            "Substantiate superlative claims with specific figures, validated case studies, "
                            "independent certifications, or concrete service specifications."
                        ),
                        priority=SeverityLevel.MEDIUM,
                    ),
                )
            )

    # 3. Check C: Missing Core Organization Attributes
    # Across the entire site snapshot, does the organization disclose location and contact information?
    all_site_text = " ".join(p.clean_text for p in parsed_pages)
    all_json_ld = [obj for p in parsed_pages for obj in p.json_ld_objects]

    has_location = bool(
        re.search(r"\b(headquartered|offices? in|based in|located in)\b", all_site_text, re.I)
        or any(obj.get("address") for obj in all_json_ld if isinstance(obj, dict))
    )
    has_contact = bool(
        re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", all_site_text)
        or re.search(r"\b(?:\+\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b", all_site_text)
        or any(obj.get("telephone") or obj.get("email") for obj in all_json_ld if isinstance(obj, dict))
    )

    missing_attrs: List[str] = []
    if not has_location:
        missing_attrs.append("geographic location / headquarters")
    if not has_contact:
        missing_attrs.append("direct contact details (email or telephone)")

    if missing_attrs:
        findings.append(
            Finding(
                id="CC-003",
                category=CategoryType.CONTENT_CLARITY,
                title=f"Missing essential organizational attributes: {', '.join(missing_attrs)}",
                severity=SeverityLevel.HIGH,
                confidence=0.86,
                evidence=(
                    f"A comprehensive scan across {len(parsed_pages)} crawled pages revealed no verifiable "
                    f"information for: {', '.join(missing_attrs)}. Absence of these fundamental attributes degrades "
                    f"entity trust and prevents AI systems from corroborating corporate legitimacy."
                ),
                affected_urls=[snapshot.homepage.url],
                suggested_action=FindingAction(
                    summary=(
                        f"Publish unambiguous details for {', '.join(missing_attrs)} in a standard Contact or About page "
                        f"and in Schema.org structured metadata."
                    ),
                    priority=SeverityLevel.HIGH,
                ),
            )
        )

    return findings
