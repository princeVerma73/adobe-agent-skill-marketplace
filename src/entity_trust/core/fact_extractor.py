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

    THIRD_PARTY_BRAND_PATTERN = re.compile(
        r"\b(?:Anthropic|Apple|T-Mobile|Google|Microsoft|OpenAI|Amazon|Netflix|Meta|Tesla|Spotify)\b['’]?s?\s+",
        re.I,
    )

    @classmethod
    def _is_editorial_page(cls, url: str) -> bool:
        return any(pat.search(url) for pat in cls.EDITORIAL_URL_PATTERNS)

    @classmethod
    def extract_from_page(cls, parsed: ParsedPageContent) -> List[ExtractedFact]:
        facts: List[ExtractedFact] = []
        text = parsed.clean_text
        is_editorial = cls._is_editorial_page(parsed.url)

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
        for pat in cls.HEADQUARTERS_PATTERNS:
            for match in pat.finditer(text):
                raw = match.group(1).strip()
                if len(raw) > 2 and len(raw) < 50:
                    norm = FactNormalizer.normalize_location(raw)
                    if norm:
                        snippet = cls._get_snippet(text, match.start(), match.end())
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
                norm = NormalizedFact(
                    fact_type="metric",
                    canonical_value=raw_metric.lower(),
                    raw_value=raw_metric,
                )
                snippet = cls._get_snippet(text, match.start(), match.end())
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
