"""Master Orchestration Entrypoint for Member 2.

Exposes `audit_content_and_entity` which transforms a `SiteSnapshot` into
a fully calibrated `ContentEntityAuditResult` containing standardized findings.
"""

from __future__ import annotations

from typing import Any, Dict, List, Union
from .contracts.schemas import (
    ContentEntityAuditResult,
    Finding,
    PageSnapshot,
    SiteSnapshot,
)
from .core.confidence import filter_and_rank_findings
from .core.fact_graph import FactGraph
from .core.html_parser import ParsedPageContent, parse_page_html
from .audits.entity_audit import audit_entity
from .audits.content_clarity_audit import audit_content_clarity
from .audits.freshness_audit import audit_freshness
from .audits.consistency_audit import audit_consistency


def audit_content_and_entity(
    snapshot: Union[SiteSnapshot, Dict[str, Any], Any],
    confidence_threshold: float = 0.70,
) -> ContentEntityAuditResult:
    """Audits website snapshot for entity identity, content clarity, freshness, and factual consistency.

    Parameters:
        snapshot: Either a SiteSnapshot, Member 1 SiteInspection model, or a conforming dictionary.
        confidence_threshold: Minimum confidence score (0.0 to 1.0) required to include a finding.

    Returns:
        ContentEntityAuditResult containing findings, severity counts, and entity profile.
    """
    if isinstance(snapshot, SiteSnapshot):
        site_snapshot = snapshot
    elif hasattr(snapshot, "root_url") and hasattr(snapshot, "pages"):
        # Direct Member 1 SiteInspection object
        site_snapshot = SiteSnapshot.from_site_inspection(snapshot)
    elif isinstance(snapshot, dict) and "pages" in snapshot and "homepage" not in snapshot:
        # Serialized Member 1 SiteInspection dict
        site_snapshot = SiteSnapshot.from_site_inspection(snapshot)
    elif isinstance(snapshot, dict):
        site_snapshot = SiteSnapshot.model_validate(snapshot)
    else:
        site_snapshot = SiteSnapshot.from_site_inspection(snapshot)

    # 1. Parse all pages into structured ParsedPageContent objects
    parsed_pages: List[ParsedPageContent] = []
    for page in site_snapshot.all_pages():
        parsed = parse_page_html(
            url=page.url,
            html=page.html,
            fallback_text=page.text,
            fallback_title=page.title,
            pre_extracted_images=page.images,
            pre_extracted_json_ld=page.structured_data,
        )
        parsed_pages.append(parsed)

    all_findings: List[Finding] = []

    # 2. Entity Audit
    entity_findings, entity_profile = audit_entity(site_snapshot, parsed_pages)
    all_findings.extend(entity_findings)

    # 3. Content Clarity Audit
    clarity_findings = audit_content_clarity(site_snapshot, parsed_pages)
    all_findings.extend(clarity_findings)

    # 4. Freshness Audit
    freshness_findings = audit_freshness(site_snapshot, parsed_pages)
    all_findings.extend(freshness_findings)

    # 5. Cross-Page Consistency Audit (Fact Graph)
    fact_graph = FactGraph(site=site_snapshot.site)
    consistency_findings = audit_consistency(site_snapshot, parsed_pages, fact_graph)
    all_findings.extend(consistency_findings)

    # 6. Confidence Calibration, False Positive Suppression & Ranking
    filtered_findings, severity_counts = filter_and_rank_findings(
        findings=all_findings,
        confidence_threshold=confidence_threshold,
    )

    # 7. Construct Final Result Contract
    return ContentEntityAuditResult(
        skill="entity-content-freshness-trust",
        status="success",
        site=site_snapshot.site,
        total_findings=len(filtered_findings),
        severity_counts=severity_counts,
        entity_profile=entity_profile,
        findings=filtered_findings,
        metadata={
            "pages_analyzed": len(parsed_pages),
            "fact_graph_summary": fact_graph.get_summary(),
            "confidence_threshold_applied": confidence_threshold,
        },
    )


# Canonical alias matching the Adobe Agent Marketplace skill identifier
audit_entity_trust = audit_content_and_entity

