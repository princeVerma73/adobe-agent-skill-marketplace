"""Report Builder for assembling and synthesizing the unified audit report.

Normalizes cross-skill findings, eliminates duplicates, attaches recommendations,
computes the Brand AI-Readiness score, and formats final outputs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from src.entity_trust.contracts.schemas import (
    EntityProfile,
    SeverityCounts,
    SeverityLevel,
)
from src.recommendations.engine import RecommendationEngine
from src.report.deduplicator import deduplicate_findings
from src.report.models import FinalAuditReport, ReportFinding
from src.report.normalizer import (
    normalize_engagement_finding,
    normalize_member2_finding,
    normalize_technical_issue,
    validate_evidence,
)


def calculate_readiness_score(counts: SeverityCounts) -> tuple[float, str]:
    """Calculates overall Brand AI-Readiness score (0-100) and letter grade."""
    # Deductions per finding severity
    deductions = (
        (counts.critical * 25.0)
        + (counts.high * 10.0)
        + (counts.medium * 4.0)
        + (counts.low * 1.0)
    )
    score = max(0.0, min(100.0, 100.0 - deductions))

    if score >= 90.0:
        grade = "A"
    elif score >= 80.0:
        grade = "B"
    elif score >= 70.0:
        grade = "C"
    elif score >= 60.0:
        grade = "D"
    else:
        grade = "F"

    return round(score, 1), grade


class ReportBuilder:
    """Builder that composes the unified final audit report across all skills."""

    def __init__(
        self,
        site: str,
        root_url: str,
        entity_profile: Optional[EntityProfile] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.site = site
        self.root_url = root_url
        self.entity_profile = entity_profile
        self.metadata = metadata or {}
        self.raw_findings: List[ReportFinding] = []
        self.skill_statuses: Dict[str, str] = {
            "crawl-render-audit": "pending",
            "entity-content-freshness-trust": "pending",
            "engagement-recommendations": "pending",
        }
        self.known_urls: Set[str] = {root_url}

    def add_known_urls(self, urls: List[str]) -> "ReportBuilder":
        """Registers audited URLs for evidence validation."""
        self.known_urls.update(urls)
        return self

    def add_technical_issues(
        self,
        issues_with_urls: List[tuple[Any, str]],
        status: str = "success",
    ) -> "ReportBuilder":
        """Ingests raw TechnicalIssue objects from Member 1."""
        self.skill_statuses["crawl-render-audit"] = status
        for issue, page_url in issues_with_urls:
            self.raw_findings.append(normalize_technical_issue(issue, page_url))
            self.known_urls.add(page_url)
        return self

    def add_member2_findings(
        self,
        findings: List[Any],
        entity_profile: Optional[EntityProfile] = None,
        status: str = "success",
    ) -> "ReportBuilder":
        """Ingests semantic trust and content findings from Member 2."""
        self.skill_statuses["entity-content-freshness-trust"] = status
        if entity_profile:
            self.entity_profile = entity_profile
        for f in findings:
            self.raw_findings.append(normalize_member2_finding(f))
        return self

    def add_engagement_findings(
        self,
        findings: List[Any],
        status: str = "success",
    ) -> "ReportBuilder":
        """Ingests engagement and navigation findings from Member 3."""
        self.skill_statuses["engagement-recommendations"] = status
        for f in findings:
            self.raw_findings.append(normalize_engagement_finding(f))
        return self

    def set_skill_status(self, skill_name: str, status: str) -> "ReportBuilder":
        """Sets the execution status of a skill (e.g. success, failure, skipped)."""
        self.skill_statuses[skill_name] = status
        return self

    def build(self) -> FinalAuditReport:
        """Assembles, validates, deduplicates, and scores the final audit report."""
        # 1. Evidence validation filter
        valid_findings = [
            f for f in self.raw_findings
            if validate_evidence(f, self.known_urls)
        ]

        # 2. Cross-skill deduplication
        deduped = deduplicate_findings(valid_findings)

        # 3. Calculate quantitative severity breakdown
        counts = SeverityCounts()
        for f in deduped:
            if f.severity == SeverityLevel.CRITICAL:
                counts.critical += 1
            elif f.severity == SeverityLevel.HIGH:
                counts.high += 1
            elif f.severity == SeverityLevel.MEDIUM:
                counts.medium += 1
            elif f.severity == SeverityLevel.LOW:
                counts.low += 1
            elif f.severity == SeverityLevel.INFO:
                counts.info += 1

        # 4. Brand AI-Readiness score
        overall_score, grade = calculate_readiness_score(counts)

        # 5. Generate actionable recommendations
        recommendations = RecommendationEngine.generate_recommendations(deduped)

        # 6. Overall audit execution status
        failed_skills = [k for k, v in self.skill_statuses.items() if "fail" in v.lower() or "error" in v.lower()]
        if len(failed_skills) == len(self.skill_statuses):
            overall_status = "error"
        elif failed_skills:
            overall_status = "partial_failure"
        else:
            overall_status = "success"

        # Summary dictionary
        summary = {
            "total_findings": len(deduped),
            "critical": counts.critical,
            "high": counts.high,
            "medium": counts.medium,
            "total_recommendations": len(recommendations),
            "pages_analyzed": len(self.known_urls),
            "crawled_urls": list(sorted(self.known_urls)),
            "brand_ai_readiness_score": overall_score,
            "readiness_grade": grade,
            "score_heuristic_disclaimer": "Internal marketplace composite heuristic (100 - weighted severity deductions; not an official Adobe metric)",
        }

        return FinalAuditReport(
            site=self.site,
            root_url=self.root_url,
            status=overall_status,
            overall_score=overall_score,
            readiness_grade=grade,
            severity_counts=counts,
            entity_profile=self.entity_profile,
            findings=deduped,
            recommendations=recommendations,
            skill_statuses=self.skill_statuses,
            summary=summary,
            metadata=self.metadata,
        )
