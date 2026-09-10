"""Data models for Member 3 Engagement Audit.

Represents engagement findings, metrics, and audit results conforming
to the repository's standardized finding contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.entity_trust.contracts.schemas import (
    FindingAction,
    SeverityCounts,
    SeverityLevel,
)


class EngagementFinding(BaseModel):
    """Standardized finding for engagement and user journey audit.

    Adheres strictly to the mandatory fields:
      - id
      - category ("engagement")
      - title
      - severity (SeverityLevel)
      - confidence (0.0 - 1.0)
      - evidence
      - affected_urls
      - suggested_action (summary, priority)
    """
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique code e.g. ENG-001, ENG-002")
    category: str = Field(default="engagement", description="Finding category")
    title: str = Field(..., description="Human-readable issue title")
    severity: SeverityLevel = Field(..., description="Severity: critical, high, medium, low, info")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    evidence: str = Field(..., description="Concrete textual or DOM evidence excerpt")
    affected_urls: List[str] = Field(default_factory=list, description="List of affected page URLs")
    suggested_action: FindingAction = Field(..., description="Remediation action and priority")


class EngagementMetrics(BaseModel):
    """Quantitative engagement and pathway metrics."""
    model_config = ConfigDict(extra="ignore")

    pages_audited: int = 0
    internal_link_count: int = 0
    external_link_count: int = 0
    orphan_page_count: int = 0
    dead_end_count: int = 0
    has_homepage_cta: bool = False
    has_contact_channel: bool = False
    avg_headings_per_page: float = 0.0


class EngagementAuditResult(BaseModel):
    """Output contract returned by the Engagement Audit engine."""
    model_config = ConfigDict(extra="ignore")

    skill: str = "engagement-recommendations"
    status: str = "success"
    site: str = Field(..., description="Target site domain or identifier")
    audit_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_findings: int = 0
    severity_counts: SeverityCounts = Field(default_factory=SeverityCounts)
    findings: List[EngagementFinding] = Field(default_factory=list)
    metrics: EngagementMetrics = Field(default_factory=EngagementMetrics)
    metadata: Dict[str, Any] = Field(default_factory=dict)
