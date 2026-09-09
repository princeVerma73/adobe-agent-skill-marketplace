"""Cross-Page Consistency Audit.

Leverages the FactExtractor, FactNormalizer, and FactGraph to detect
conflicting business facts (founding dates, pricing, headquarters, contact details)
published across different pages of the website.
"""

from __future__ import annotations

from typing import List, Tuple
from ..contracts.schemas import (
    CategoryType,
    Finding,
    FindingAction,
    SeverityLevel,
    SiteSnapshot,
)
from ..core.fact_extractor import FactExtractor
from ..core.fact_graph import FactConflict, FactGraph
from ..core.html_parser import ParsedPageContent


FACT_HUMAN_NAMES = {
    "founding_year": "Founding Year",
    "headquarters": "Headquarters Location",
    "price": "Product / Plan Pricing",
    "phone": "Telephone Number",
    "email": "Contact Email",
    "metric": "Reported Business Metric",
}


def audit_consistency(
    snapshot: SiteSnapshot,
    parsed_pages: List[ParsedPageContent],
    fact_graph: FactGraph,
) -> List[Finding]:
    findings: List[Finding] = []

    # 1. Extract all facts across all pages and feed into the FactGraph
    for page in parsed_pages:
        facts = FactExtractor.extract_from_page(page)
        for f in facts:
            fact_graph.add_fact(f)

    # 2. Detect conflicts across fact clusters
    conflicts = fact_graph.detect_conflicts()

    for idx, conflict in enumerate(conflicts, 1):
        friendly_name = FACT_HUMAN_NAMES.get(conflict.fact_type, conflict.fact_type.replace("_", " ").title())

        # Compile evidence from both conflicting clusters
        evidence_lines = []
        for cluster in (conflict.cluster_a, conflict.cluster_b):
            vals_and_urls = [
                f"'{e.raw_value}' on {e.url} (snippet: \"{e.context_snippet}\")"
                for e in cluster.evidence_list
            ]
            evidence_lines.append(f"Value [{cluster.normalized_value.canonical_value}]: {'; '.join(vals_and_urls)}")

        full_evidence = (
            f"Contradictory information detected for '{friendly_name}' across pages. "
            + " | ".join(evidence_lines)
            + ". Conflicting facts across authoritative pages diminish knowledge graph reliability."
        )

        severity = (
            SeverityLevel.HIGH
            if conflict.fact_type in ("founding_year", "price", "headquarters")
            else SeverityLevel.MEDIUM
        )

        findings.append(
            Finding(
                id=f"CO-{idx:03d}",
                category=CategoryType.CONSISTENCY,
                title=f"Cross-page factual contradiction: {friendly_name}",
                severity=severity,
                confidence=conflict.confidence,
                evidence=full_evidence,
                affected_urls=conflict.affected_urls,
                suggested_action=FindingAction(
                    summary=(
                        f"Reconcile '{friendly_name}' across affected pages ({', '.join(conflict.affected_urls)}) "
                        f"to present a single, canonical truth across the entire domain."
                    ),
                    priority=severity,
                ),
            )
        )

    return findings
