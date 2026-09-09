"""Standardized contracts for Member 2 and cross-member integration.

All members (Member 1: Crawler, Member 2: Content/Entity/Freshness,
Member 3: Engagement/Orchestrator) adhere to these interfaces.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class SeverityLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class CategoryType(str, Enum):
    ENTITY = "entity"
    CONTENT_CLARITY = "content_clarity"
    FRESHNESS = "freshness"
    CONSISTENCY = "consistency"


class StructuredDataItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: Optional[str] = Field(default=None, alias="@type")
    context: Optional[str] = Field(default=None, alias="@context")
    data: Dict[str, Any] = Field(default_factory=dict)


class PageSnapshot(BaseModel):
    """Snapshot of a single crawled web page provided by Member 1."""
    url: str
    title: Optional[str] = ""
    text: Optional[str] = ""
    html: Optional[str] = ""
    headers: Dict[str, str] = Field(default_factory=dict)
    links: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    images: List[Dict[str, Any]] = Field(default_factory=list)
    structured_data: List[Dict[str, Any]] = Field(default_factory=list)


class SiteSnapshot(BaseModel):
    """Standardized website analysis input object.

    Member 1 provides this object. Member 2 only relies on this interface.
    """
    site: str
    homepage: PageSnapshot
    pages: List[PageSnapshot] = Field(default_factory=list)
    structured_data: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    crawl_metadata: Dict[str, Any] = Field(default_factory=dict)

    def all_pages(self) -> List[PageSnapshot]:
        """Returns all pages including the homepage without duplicates."""
        seen_urls = set()
        pages = []
        if self.homepage and self.homepage.url:
            seen_urls.add(self.homepage.url)
            pages.append(self.homepage)
        for page in self.pages:
            if page.url not in seen_urls:
                seen_urls.add(page.url)
                pages.append(page)
        return pages

    @classmethod
    def from_site_inspection(cls, inspection: Any) -> "SiteSnapshot":
        """Converts Member 1's SiteInspection model (or raw dict) into a SiteSnapshot."""
        if isinstance(inspection, dict):
            site = inspection.get("site", "unknown")
            root_url = inspection.get("root_url", "")
            raw_pages = inspection.get("pages", [])
        else:
            site = getattr(inspection, "site", "unknown")
            root_url = getattr(inspection, "root_url", "")
            raw_pages = getattr(inspection, "pages", [])

        converted_pages: List[PageSnapshot] = []
        for p in raw_pages:
            if isinstance(p, dict):
                p_url = p.get("url", "")
                p_title = p.get("title") or ""
                p_text = (
                    p.get("body_text")
                    or p.get("rendered_text")
                    or p.get("source_text")
                    or p.get("text")
                    or ""
                )
                p_html = p.get("html") or p.get("source_text") or ""
                meta_dict = p.get("metadata") or {}
                if hasattr(meta_dict, "model_dump"):
                    meta_dict = meta_dict.model_dump()
                p_links = [
                    l.get("url") if isinstance(l, dict) else getattr(l, "url", str(l))
                    for l in p.get("links", [])
                ]
                p_struct = p.get("structured_data") or []
                p_images = p.get("images") or []
                p_headers = p.get("headers") or {}
            else:
                p_url = getattr(p, "url", "")
                p_title = getattr(p, "title", "") or ""
                p_text = (
                    getattr(p, "body_text", None)
                    or getattr(p, "rendered_text", None)
                    or getattr(p, "source_text", None)
                    or getattr(p, "text", "")
                    or ""
                )
                p_html = getattr(p, "html", None) or getattr(p, "source_text", "") or ""
                meta_obj = getattr(p, "metadata", None)
                meta_dict = (
                    meta_obj.model_dump()
                    if hasattr(meta_obj, "model_dump")
                    else (meta_obj if isinstance(meta_obj, dict) else {})
                )
                if not p_title and meta_dict.get("title"):
                    p_title = meta_dict["title"]
                raw_links = getattr(p, "links", [])
                p_links = [getattr(l, "url", str(l)) for l in raw_links]
                p_struct = getattr(p, "structured_data", [])
                p_images = getattr(p, "images", [])
                p_headers = getattr(p, "headers", {})

            converted_pages.append(
                PageSnapshot(
                    url=p_url,
                    title=p_title,
                    text=p_text,
                    html=p_html,
                    headers=p_headers,
                    links=p_links,
                    metadata=meta_dict,
                    images=p_images,
                    structured_data=p_struct,
                )
            )

        homepage = None
        other_pages = []
        for cp in converted_pages:
            if not homepage and (
                cp.url == root_url or cp.url.rstrip("/") == root_url.rstrip("/")
            ):
                homepage = cp
            else:
                other_pages.append(cp)

        if not homepage:
            if converted_pages:
                homepage = converted_pages[0]
                other_pages = converted_pages[1:]
            else:
                homepage = PageSnapshot(url=root_url or f"https://{site}/")

        return cls(
            site=site,
            homepage=homepage,
            pages=other_pages,
            structured_data=getattr(homepage, "structured_data", []),
            metadata=getattr(homepage, "metadata", {}),
        )


class FindingAction(BaseModel):
    """Suggested remediation action matching Adobe specifications."""
    summary: str
    priority: SeverityLevel = SeverityLevel.MEDIUM


class Finding(BaseModel):
    """Standardized finding object matching Adobe hackathon contract.

    Mandatory Adobe fields:
      - id
      - title
      - severity
      - evidence
      - suggested_action (summary, priority)
    Additional fields:
      - category
      - confidence (0.0 - 1.0)
      - affected_urls
    """
    id: str
    category: CategoryType
    title: str
    severity: SeverityLevel
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    affected_urls: List[str] = Field(default_factory=list)
    suggested_action: FindingAction


class SeverityCounts(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class EntityProfile(BaseModel):
    """Internal consolidated representation of the identified entity."""
    name: Optional[str] = None
    type: str = "Organization"
    description: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    founding_year: Optional[int] = None
    products: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    social_profiles: List[str] = Field(default_factory=list)
    confidence_score: float = 0.0


class ContentEntityAuditResult(BaseModel):
    """Final output object returned by Member 2 to the orchestrator."""
    skill: str = "entity-content-freshness-trust"
    status: str = "success"
    site: str
    audit_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_findings: int = 0
    severity_counts: SeverityCounts = Field(default_factory=SeverityCounts)
    entity_profile: Optional[EntityProfile] = None
    findings: List[Finding] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
