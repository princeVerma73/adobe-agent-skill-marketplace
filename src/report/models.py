"""Data models for final multi-skill report composition.

Defines the unified finding model and the comprehensive FinalAuditReport
conforming to Adobe Agent Skill Marketplace standards.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.entity_trust.contracts.schemas import (
    EntityProfile,
    FindingAction,
    SeverityCounts,
    SeverityLevel,
)
from src.recommendations.models import ActionableRecommendation


class ReportFinding(BaseModel):
    """Normalized finding representation across all specialist skills.

    Unifies Member 1 technical issues, Member 2 semantic trust findings,
    and Member 3 engagement observations into a singular standardized schema.
    """
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique code e.g. EC-001, ENG-001, TECH-HTTP-404")
    category: str = Field(..., description="Category: technical, entity, content_clarity, freshness, consistency, engagement")
    title: str = Field(..., description="Human-readable issue title")
    severity: SeverityLevel = Field(..., description="Severity: critical, high, medium, low, info")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Calibrated confidence score")
    evidence: str = Field(..., description="Concrete textual or structural evidence excerpt")
    affected_urls: List[str] = Field(default_factory=list, description="Target URLs affected by this finding")
    suggested_action: FindingAction = Field(..., description="Remediation summary and priority")


class FinalAuditReport(BaseModel):
    """Unified Adobe Brand AI-Readiness Audit Report."""
    model_config = ConfigDict(extra="ignore")

    site: str = Field(..., description="Target site domain")
    root_url: str = Field(..., description="Canonical root URL")
    audited_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = Field(default="success", description="Audit status: success, partial_failure, error")
    overall_score: float = Field(default=100.0, ge=0.0, le=100.0, description="Brand AI-readiness score 0-100")
    readiness_grade: str = Field(default="A", description="Readiness grade: A, B, C, D, F")
    severity_counts: SeverityCounts = Field(default_factory=SeverityCounts)
    entity_profile: Optional[EntityProfile] = Field(default=None, description="Consolidated brand identity profile")
    findings: List[ReportFinding] = Field(default_factory=list, description="All prioritized, deduplicated findings")
    recommendations: List[ActionableRecommendation] = Field(
        default_factory=list, description="Prioritized remediation roadmap"
    )
    skill_statuses: Dict[str, str] = Field(
        default_factory=dict, description="Execution status for each participating skill"
    )
    summary: Dict[str, Any] = Field(default_factory=dict, description="Quantitative audit metrics and counts")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Crawl parameters and execution metadata")

    def to_dict(self) -> Dict[str, Any]:
        """Returns dictionary representation."""
        return self.model_dump()

    def to_json(self, indent: int = 2) -> str:
        """Serializes report to formatted JSON string."""
        return self.model_dump_json(indent=indent)

    def to_markdown(self) -> str:
        """Renders report as an executive Markdown document with tables and remediation roadmap."""
        md_lines = [
            f"# Brand AI-Readiness Audit Report: {self.site}",
            "",
            f"> **Target URL:** `{self.root_url}`  ",
            f"> **Audited At:** `{self.audited_at}`  ",
            f"> **Audit Status:** `{self.status.upper()}`  ",
            f"> **Brand AI-Readiness Score:** **{self.overall_score:.1f}/100** (Grade: **{self.readiness_grade}**)",
            "",
            "---",
            "",
            "## 1. Executive Summary",
            "",
            f"An autonomous multi-skill audit was performed across **{self.summary.get('pages_analyzed', len(self.summary.get('crawled_urls', [])) or 1)}** page(s) on `{self.site}`. "
            f"A total of **{len(self.findings)}** evidence-backed findings were identified and prioritized.",
            "",
            "### Severity Breakdown",
            "",
            "| Severity | Count | Weight |",
            "| :--- | :---: | :--- |",
            f"| **CRITICAL** | {self.severity_counts.critical} | -25 pts |",
            f"| **HIGH** | {self.severity_counts.high} | -10 pts |",
            f"| **MEDIUM** | {self.severity_counts.medium} | -4 pts |",
            f"| **LOW** | {self.severity_counts.low} | -1 pt |",
            f"| **INFO** | {self.severity_counts.info} | 0 pts |",
            "",
        ]

        # Entity Profile section
        if self.entity_profile and self.entity_profile.name:
            ep = self.entity_profile
            md_lines.extend([
                "---",
                "",
                "## 2. Identified Brand & Entity Profile",
                "",
                f"- **Entity Name:** {ep.name}",
                f"- **Entity Type:** {ep.type}",
                f"- **Industry Classification:** {ep.industry or 'Unspecified'}",
                f"- **Location / Headquarters:** {ep.location or 'Unspecified'}",
                f"- **Founding Year:** {ep.founding_year or 'Unspecified'}",
                f"- **Contact Channel:** {ep.contact_email or ep.contact_phone or 'None Discovered'}",
                f"- **Entity Confidence Score:** {ep.confidence_score:.2f}",
                "",
            ])

        # Findings section
        md_lines.extend([
            "---",
            "",
            f"## 3. Prioritized Audit Findings ({len(self.findings)})",
            "",
        ])

        if not self.findings:
            md_lines.append("No critical, high, or medium issues detected! The site demonstrates excellent AI readiness.\n")
        else:
            md_lines.extend([
                "| ID | Severity | Category | Title | Affected URLs |",
                "| :--- | :---: | :--- | :--- | :--- |",
            ])
            for f in self.findings:
                urls_str = "<br/>".join(f"`{u}`" for u in f.affected_urls[:2])
                if len(f.affected_urls) > 2:
                    urls_str += f"<br/>*(+{len(f.affected_urls)-2} more)*"
                sev_badge = f"**{f.severity.value.upper()}**"
                md_lines.append(
                    f"| `{f.id}` | {sev_badge} | `{f.category}` | {f.title} | {urls_str or 'Site-wide'} |"
                )
            md_lines.append("")

            # Detailed evidence subsection
            md_lines.extend([
                "### Detailed Observations & Evidence",
                "",
            ])
            for i, f in enumerate(self.findings, 1):
                md_lines.extend([
                    f"#### {i}. [{f.severity.value.upper()}] {f.id}: {f.title}",
                    f"- **Category:** `{f.category}` | **Confidence:** `{f.confidence:.2f}`",
                    f"- **Evidence:** {f.evidence}",
                    f"- **Affected URL(s):** {', '.join(f.affected_urls) if f.affected_urls else 'Site-wide'}",
                    f"- **Remediation:** {f.suggested_action.summary}",
                    "",
                ])

        # Actionable Recommendations section
        md_lines.extend([
            "---",
            "",
            f"## 4. Actionable Remediation Roadmap ({len(self.recommendations)})",
            "",
        ])

        if not self.recommendations:
            md_lines.append("No immediate remediation actions required.\n")
        else:
            for i, rec in enumerate(self.recommendations, 1):
                md_lines.extend([
                    f"### Action {i}: {rec.title} [{rec.priority.value.upper()}]",
                    f"- **Finding Reference:** `{rec.finding_id}` (`{rec.category}`)",
                    f"- **Diagnosis:** {rec.what_is_wrong}",
                    f"- **Prescribed Change:** {rec.what_should_be_changed}",
                    f"- **Why It Matters:** {rec.why_it_matters}",
                    f"- **Verification Procedure:** {rec.verification_steps}",
                    f"- **Target Locations:** {', '.join(f'`{u}`' for u in rec.where_it_occurs) if rec.where_it_occurs else 'Site-wide'}",
                    "",
                ])

        # Skill Statuses section
        md_lines.extend([
            "---",
            "",
            "## 5. Skill Execution Statuses",
            "",
        ])
        for skill_name, status_str in self.skill_statuses.items():
            md_lines.append(f"- **`{skill_name}`:** {status_str}")
        md_lines.append("")

        return "\n".join(md_lines)
