"""Fact Extractor Layer.

Extracts structured business facts (founding date, headquarters, contact, pricing,
leadership, metrics) from page text, HTML, and Schema.org JSON-LD.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from .fact_normalizer import FactNormalizer, NormalizedFact
from .html_parser import ParsedPageContent


@dataclass
class ExtractedFact:
    fact_type: str
    raw_value: str
    normalized: NormalizedFact
    source_url: str
    context_snippet: str
    confidence: float = 0.90


class FactExtractor:
    """Extracts verifiable facts from parsed page content."""

    # Regex patterns for business facts
    FOUNDING_PATTERNS = [
        re.compile(r"(?:founded|established|started)\s+(?:in|back in|during)\s+([12]\d{3})\b", re.I),
        re.compile(r"\best\.?\s*([12]\d{3})\b", re.I),
        re.compile(r"\bsince\s+([12]\d{3})\b", re.I),
    ]

    HEADQUARTERS_PATTERNS = [
        re.compile(r"(?:headquartered|headquarters|based|located)\s+in\s+([A-Z][a-zA-Z\s,]+?)(?:\.|\;|\n|\band\b)", re.I),
        re.compile(r"offices?\s+(?:are\s+)?in\s+([A-Z][a-zA-Z\s,]+?)(?:\.|\;|\n)", re.I),
        re.compile(r"(?:established|founded)\s+(?:in|during)?\s*\d{4}\s+in\s+([A-Z][a-zA-Z\s,]+?)(?:\.|\;|\n|\band\b)", re.I),
    ]

    PRICING_PATTERNS = [
        re.compile(r"(?:plans?\s+start(?:ing)?\s+at|starts?\s+at|starting\s+from|pricing:\s*)([\$€£₹]\s*\d+(?:,\d+)*(?:\.\d+)?|\d+\s*(?:USD|EUR|INR|GBP))", re.I),
        re.compile(r"(\$\d+(?:,\d+)*(?:\.\d+)?)\s*(?:\/mo|\/month|per month)", re.I),
        re.compile(r"(₹\s*\d+(?:,\d+)*|INR\s*\d+(?:,\d+)*)\s*(?:\/mo|\/month|per month)?", re.I),
    ]

    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")

    METRIC_PATTERNS = [
        re.compile(r"\b(\d+(?:,\d+)*\+?\s+(?:customers|clients|users|enterprises|countries|team members|partners))\b", re.I)
    ]

    EDITORIAL_URL_PATTERNS = [
        re.compile(r"/(?:news|article|articles|story|stories|tech/\d+|blog|blogs|opinion|reviews)/", re.I),
    ]

    LEGAL_URL_PATTERNS = [
        re.compile(r"/(?:legal|terms|privacy|ssa|policy|policies|compliance|agreements?|tos|gdpr|law|disclaimer)/?", re.I),
    ]

    MONTH_PREFIX_PATTERN = re.compile(
        r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d+$",
        re.I,
    )

    THIRD_PARTY_BRAND_PATTERN = re.compile(
        r"\b(?:Anthropic|Apple|T-Mobile|Google|Microsoft|OpenAI|Amazon|Netflix|Meta|Tesla|Spotify)\b['’]?s?\s+",
        re.I,
    )

    @classmethod
    def _is_editorial_page(cls, url: str) -> bool:
        return any(pat.search(url) for pat in cls.EDITORIAL_URL_PATTERNS)

    @classmethod
    def _is_legal_page(cls, url: str) -> bool:
        return any(pat.search(url) for pat in cls.LEGAL_URL_PATTERNS)

    @classmethod
    def _is_about_or_company_page(cls, url: str) -> bool:
        return bool(re.search(r"/(?:about|company|corporate|who-we-are|our-story|overview)/?", url, re.I))

    @classmethod
    def _extract_brand_name(cls, url: str, meta_site_name: str = "") -> str:
        if meta_site_name:
            return meta_site_name.strip()
        host = url
        if "://" in host:
            host = host.split("://", 1)[1]
        host = host.split("/", 1)[0].split("?")[0].split(":")[0]
        parts = host.split(".")
        meaningful = [
            p for p in parts
            if p.lower() not in (
                "www", "docs", "doc", "api", "app", "dev", "staging", "cdn",
                "com", "org", "net", "io", "so", "edu", "gov", "co", "uk", "de", "ai"
            )
        ]
        if meaningful:
            return meaningful[0].lower()
        return ""

    @classmethod
    def extract_from_page(cls, parsed: ParsedPageContent) -> List[ExtractedFact]:
        facts: List[ExtractedFact] = []
        text = parsed.clean_text
        is_editorial = cls._is_editorial_page(parsed.url)
        is_legal = cls._is_legal_page(parsed.url)
        is_about = cls._is_about_or_company_page(parsed.url)
        brand = cls._extract_brand_name(parsed.url, parsed.meta_site_name)

        # 1. Structured Data extraction (JSON-LD)
        for obj in parsed.json_ld_objects:
            facts.extend(cls._extract_from_json_ld(obj, parsed.url))

        # 2. Founding Year from text
        for pat in cls.FOUNDING_PATTERNS:
            for match in pat.finditer(text):
                raw = match.group(1)
                norm = FactNormalizer.normalize_founding_year(raw)
                if norm:
                    snippet = cls._get_snippet(text, match.start(), match.end())
                    # Skip if snippet references known third-party brands
                    if cls.THIRD_PARTY_BRAND_PATTERN.search(snippet):
                        continue
                    # On editorial pages (news, blog, reviews), require explicit brand anchoring or about-page context
                    if is_editorial and not is_about:
                        if not (brand and brand in snippet.lower()):
                            continue
                        # In editorial text, bare "since YYYY" often refers to personal tenure/events; require founding keywords
                        if not re.search(r"\b(?:founded|established|started|est\.?)\b", snippet, re.I):
                            continue
                    facts.append(
                        ExtractedFact(
                            fact_type="founding_year",
                            raw_value=raw,
                            normalized=norm,
                            source_url=parsed.url,
                            context_snippet=snippet,
                            confidence=0.92,
                        )
                    )

        # 3. Headquarters from text
        # Exclude matches occurring within legal/policy/terms pages unless explicitly an About page
        if not (is_legal and not is_about):
            for pat in cls.HEADQUARTERS_PATTERNS:
                for match in pat.finditer(text):
                    raw = match.group(1).strip()
                    if len(raw) > 2 and len(raw) < 50:
                        norm = FactNormalizer.normalize_location(raw)
                        if norm:
                            snippet = cls._get_snippet(text, match.start(), match.end())
                            # Skip if snippet references known third-party brands
                            if cls.THIRD_PARTY_BRAND_PATTERN.search(snippet):
                                continue
                            # Skip legal jurisdiction / governing law / customer location clauses
                            if re.search(r"\b(?:user|customer|party|parties|dispute|arbitration|court|courts|resident|citizen|jurisdiction|denominated currency)\s+(?:is\s+)?located\s+in\b", snippet, re.I):
                                continue
                            if is_editorial and not is_about:
                                if not (brand and brand in snippet.lower()):
                                    continue
                            # If not on an About/Company page or homepage, require entity anchoring or explicit corporate keywords
                            is_homepage = parsed.url.rstrip("/").count("/") <= 3
                            if not is_about and not is_homepage:
                                has_entity_anchor = (brand and brand in snippet.lower()) or bool(re.search(r"\b(?:headquarter|headquartered|headquarters|corporate office|main office|our office)\b", snippet, re.I))
                                if not has_entity_anchor:
                                    continue
                            facts.append(
                                ExtractedFact(
                                    fact_type="headquarters",
                                    raw_value=raw,
                                    normalized=norm,
                                    source_url=parsed.url,
                                    context_snippet=snippet,
                                    confidence=0.85,
                                )
                            )

        # 4. Pricing from text (Skip non-product generic article text quoting third parties)
        if not is_editorial:
            for pat in cls.PRICING_PATTERNS:
                for match in pat.finditer(text):
                    raw = match.group(1).strip()
                    snippet = cls._get_snippet(text, match.start(), match.end())
                    # Skip if snippet is explicitly referencing third-party brands
                    if cls.THIRD_PARTY_BRAND_PATTERN.search(snippet):
                        continue
                    norm = FactNormalizer.normalize_price(raw)
                    if norm:
                        facts.append(
                            ExtractedFact(
                                fact_type="price",
                                raw_value=raw,
                                normalized=norm,
                                source_url=parsed.url,
                                context_snippet=snippet,
                                confidence=0.88,
                            )
                        )

        # 5. Email & Phone
        for match in cls.EMAIL_PATTERN.finditer(text):
            email = match.group(0).strip().lower()
            if not email.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                norm = NormalizedFact(fact_type="email", canonical_value=email, raw_value=email)
                snippet = cls._get_snippet(text, match.start(), match.end())
                facts.append(
                    ExtractedFact(
                        fact_type="email",
                        raw_value=email,
                        normalized=norm,
                        source_url=parsed.url,
                        context_snippet=snippet,
                        confidence=0.95,
                    )
                )

        for match in cls.PHONE_PATTERN.finditer(text):
            raw_phone = match.group(0).strip()
            norm = FactNormalizer.normalize_phone(raw_phone)
            if norm:
                snippet = cls._get_snippet(text, match.start(), match.end())
                facts.append(
                    ExtractedFact(
                        fact_type="phone",
                        raw_value=raw_phone,
                        normalized=norm,
                        source_url=parsed.url,
                        context_snippet=snippet,
                        confidence=0.89,
                    )
                )

        # 6. Quantitative metrics
        for pat in cls.METRIC_PATTERNS:
            for match in pat.finditer(text):
                raw_metric = match.group(1).strip()
                # Check if match is preceded by a month name (e.g., "September 12 Customers")
                preceding_text = text[max(0, match.start() - 30):match.start()].strip()
                if cls.MONTH_PREFIX_PATTERN.search(preceding_text):
                    continue
                # Check if number is a lone footnote or item number at sentence end e.g. "equally. 7 Users can"
                if re.search(r"[\.\?\!]\s*$", preceding_text) and re.match(r"^\d{1,2}\s+[A-Z]", raw_metric):
                    continue
                norm = NormalizedFact(
                    fact_type="metric",
                    canonical_value=raw_metric.lower(),
                    raw_value=raw_metric,
                )
                snippet = cls._get_snippet(text, match.start(), match.end())
                # On editorial/news pages, metric must represent organizational scale, not article narrative
                if is_editorial and not is_about:
                    if not (brand and brand in snippet.lower()) and not re.search(r"\b(?:over|more than|serving|trusted by|scale|worldwide|globally|\bmillion\b|\bbillion\b|\bk\+?\b)\b", snippet, re.I):
                        continue
                facts.append(
                    ExtractedFact(
                        fact_type="metric",
                        raw_value=raw_metric,
                        normalized=norm,
                        source_url=parsed.url,
                        context_snippet=snippet,
                        confidence=0.86,
                    )
                )

        return facts

    @classmethod
    def _extract_from_json_ld(cls, obj: Dict[str, Any], source_url: str) -> List[ExtractedFact]:
        facts: List[ExtractedFact] = []
        if not isinstance(obj, dict):
            return facts

        # Founding Date in Schema
        founding_date = obj.get("foundingDate") or obj.get("foundingYear")
        if founding_date:
            norm = FactNormalizer.normalize_founding_year(str(founding_date))
            if norm:
                facts.append(
                    ExtractedFact(
                        fact_type="founding_year",
                        raw_value=str(founding_date),
                        normalized=norm,
                        source_url=source_url,
                        context_snippet=f"Schema.org JSON-LD foundingDate: {founding_date}",
                        confidence=0.98,
                    )
                )

        # Address in Schema
        address = obj.get("address")
        if isinstance(address, dict):
            locality = address.get("addressLocality") or ""
            region = address.get("addressRegion") or ""
            country = address.get("addressCountry") or ""
            full_loc = f"{locality}, {region} {country}".strip(", ")
            if full_loc:
                norm = FactNormalizer.normalize_location(full_loc)
                if norm:
                    facts.append(
                        ExtractedFact(
                            fact_type="headquarters",
                            raw_value=full_loc,
                            normalized=norm,
                            source_url=source_url,
                            context_snippet=f"Schema.org address: {full_loc}",
                            confidence=0.96,
                        )
                    )
        elif isinstance(address, str):
            norm = FactNormalizer.normalize_location(address)
            if norm:
                facts.append(
                    ExtractedFact(
                        fact_type="headquarters",
                        raw_value=address,
                        normalized=norm,
                        source_url=source_url,
                        context_snippet=f"Schema.org address: {address}",
                        confidence=0.95,
                    )
                )

        # Telephone & Email in Schema
        telephone = obj.get("telephone")
        if telephone:
            norm = FactNormalizer.normalize_phone(str(telephone))
            if norm:
                facts.append(
                    ExtractedFact(
                        fact_type="phone",
                        raw_value=str(telephone),
                        normalized=norm,
                        source_url=source_url,
                        context_snippet=f"Schema.org telephone: {telephone}",
                        confidence=0.98,
                    )
                )

        email = obj.get("email")
        if email:
            clean_email = str(email).strip().lower()
            norm = NormalizedFact(fact_type="email", canonical_value=clean_email, raw_value=clean_email)
            facts.append(
                ExtractedFact(
                    fact_type="email",
                    raw_value=clean_email,
                    normalized=norm,
                    source_url=source_url,
                    context_snippet=f"Schema.org email: {clean_email}",
                    confidence=0.98,
                )
            )

        return facts

    @staticmethod
    def _get_snippet(text: str, start: int, end: int, window: int = 60) -> str:
        s = max(0, start - window)
        e = min(len(text), end + window)
        prefix = "..." if s > 0 else ""
        suffix = "..." if e < len(text) else ""
        return f"{prefix}{text[s:e].strip()}{suffix}"
