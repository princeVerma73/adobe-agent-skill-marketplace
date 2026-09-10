"""Master Audit Orchestrator (Member 3).

Coordinates the end-to-end multi-skill website audit:
  Target URL / Inspection
      ↓
  Member 1: crawl-render-audit (inspect_site)
      ↓
  Member 2: entity-content-freshness-trust (audit_entity_trust)
      ↓
  Member 3: engagement-recommendations (audit_engagement)
      ↓
  Master Aggregation, Normalization, Deduplication & Evidence Validation
      ↓
  Actionable Remediation Engine
      ↓
  Final Unified Adobe Brand AI-Readiness Audit Report
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

from src.engagement.runner import audit_engagement
from src.entity_trust.runner import audit_entity_trust
from src.inspection.pipeline import inspect_site
from src.report.builder import ReportBuilder
from src.report.models import FinalAuditReport

logger = logging.getLogger(__name__)


class AuditOrchestrator:
    """Master orchestrator executing the full multi-agent website audit workflow."""

    def __init__(
        self,
        confidence_threshold: float = 0.70,
        max_pages: int = 10,
        max_depth: int = 2,
        enable_rendering: bool = True,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.enable_rendering = enable_rendering

    def run_audit(
        self,
        target: Union[str, Dict[str, Any], Any],
        options: Optional[Dict[str, Any]] = None,
    ) -> FinalAuditReport:
        """Runs the complete website audit across Member 1, 2, and 3 skills.

        Parameters:
            target: Website URL string (e.g. "https://example.com"), a SiteInspection
                    model, a SiteSnapshot, or pre-extracted dict.
            options: Optional override dictionary for crawl depth, pages, or thresholds.

        Returns:
            FinalAuditReport containing all findings, entity profile, and recommendations.
        """
        opts = options or {}
        max_pages = opts.get("max_pages", self.max_pages)
        max_depth = opts.get("max_depth", self.max_depth)
        enable_rendering = opts.get("enable_rendering", self.enable_rendering)
        confidence_threshold = opts.get("confidence_threshold", self.confidence_threshold)

        # ---------------------------------------------------------
        # Phase 1: Member 1 Inspection / Crawling
        # ---------------------------------------------------------
        site_inspection: Any = None
        site_domain: str = "unknown"
        root_url: str = ""
        known_urls: List[str] = []
        technical_issues_with_urls: List[tuple[Any, str]] = []
        m1_status = "success"

        if isinstance(target, str):
            root_url = target
            try:
                site_inspection = inspect_site(
                    url=target,
                    max_pages=max_pages,
                    max_depth=max_depth,
                    enable_rendering=enable_rendering,
                )
                site_domain = site_inspection.site
                root_url = site_inspection.root_url
                for p in site_inspection.pages:
                    known_urls.append(p.url)
                    for issue in getattr(p, "technical_issues", []):
                        technical_issues_with_urls.append((issue, p.url))
            except Exception as exc:
                logger.error("Member 1 inspection failed: %s", exc)
                m1_status = f"error: {str(exc)}"
                site_domain = target.replace("https://", "").replace("http://", "").split("/")[0]
        else:
            # Pre-extracted inspection object or dict
            site_inspection = target
            if isinstance(target, dict):
                site_domain = target.get("site", "unknown")
                root_url = target.get("root_url") or (
                    target.get("homepage", {}).get("url") if isinstance(target.get("homepage"), dict) else ""
                ) or f"https://{site_domain}/"
                for p in target.get("pages", []):
                    u = p.get("url") if isinstance(p, dict) else getattr(p, "url", "")
                    if u:
                        known_urls.append(u)
                    for issue in (p.get("technical_issues", []) if isinstance(p, dict) else getattr(p, "technical_issues", [])):
                        technical_issues_with_urls.append((issue, u))
            else:
                site_domain = getattr(target, "site", "unknown")
                root_url = getattr(target, "root_url", f"https://{site_domain}/")
                for p in getattr(target, "pages", []):
                    u = getattr(p, "url", "")
                    if u:
                        known_urls.append(u)
                    for issue in getattr(p, "technical_issues", []):
                        technical_issues_with_urls.append((issue, u))

        if not known_urls and root_url:
            known_urls.append(root_url)

        # Initialize ReportBuilder
        builder = ReportBuilder(
            site=site_domain,
            root_url=root_url,
            metadata={
                "max_pages": max_pages,
                "max_depth": max_depth,
                "confidence_threshold": confidence_threshold,
                "enable_rendering": enable_rendering,
            },
        )
        builder.add_known_urls(known_urls)

        # Ingest Member 1 Technical Issues
        builder.add_technical_issues(technical_issues_with_urls, status=m1_status)

        # If Member 1 failed completely and we have no data, return early report
        if site_inspection is None and "error" in m1_status:
            builder.set_skill_status("entity-content-freshness-trust", "skipped: inspection failure")
            builder.set_skill_status("engagement-recommendations", "skipped: inspection failure")
            return builder.build()

        # ---------------------------------------------------------
        # Phase 2: Member 2 Semantic Trust & Fact Audit
        # ---------------------------------------------------------
        try:
            m2_result = audit_entity_trust(
                site_inspection,
                confidence_threshold=confidence_threshold,
            )
            builder.add_member2_findings(
                findings=m2_result.findings,
                entity_profile=m2_result.entity_profile,
                status="success",
            )
        except Exception as exc:
            logger.error("Member 2 audit failed: %s", exc)
            builder.set_skill_status("entity-content-freshness-trust", f"error: {str(exc)}")

        # ---------------------------------------------------------
        # Phase 3: Member 3 Engagement & Pathway Audit
        # ---------------------------------------------------------
        try:
            m3_result = audit_engagement(
                site_inspection,
                confidence_threshold=confidence_threshold,
            )
            builder.add_engagement_findings(
                findings=m3_result.findings,
                status="success",
            )
        except Exception as exc:
            logger.error("Member 3 audit failed: %s", exc)
            builder.set_skill_status("engagement-recommendations", f"error: {str(exc)}")

        # ---------------------------------------------------------
        # Phase 4: Report Synthesis & Actionable Roadmap
        # ---------------------------------------------------------
        return builder.build()


def run_full_audit(
    target: Union[str, Dict[str, Any], Any],
    confidence_threshold: float = 0.70,
    max_pages: int = 10,
    max_depth: int = 2,
    enable_rendering: bool = True,
) -> FinalAuditReport:
    """Convenience functional entrypoint for executing the full orchestrator audit."""
    orchestrator = AuditOrchestrator(
        confidence_threshold=confidence_threshold,
        max_pages=max_pages,
        max_depth=max_depth,
        enable_rendering=enable_rendering,
    )
    return orchestrator.run_audit(target)
