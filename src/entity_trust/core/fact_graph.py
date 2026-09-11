"""Fact Graph Layer.

In-memory knowledge graph that connects:
  Organization -> Fact Types -> Normalized Values -> Evidence Source URLs & Snippets.
Identifies multi-page factual discrepancies with high confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from .fact_extractor import ExtractedFact
from .fact_normalizer import NormalizedFact


@dataclass
class FactEvidence:
    url: str
    raw_value: str
    context_snippet: str
    confidence: float


@dataclass
class FactCluster:
    fact_type: str
    normalized_value: NormalizedFact
    evidence_list: List[FactEvidence] = field(default_factory=list)


@dataclass
class FactConflict:
    fact_type: str
    cluster_a: FactCluster
    cluster_b: FactCluster
    confidence: float

    @property
    def affected_urls(self) -> List[str]:
        urls = {e.url for e in self.cluster_a.evidence_list} | {e.url for e in self.cluster_b.evidence_list}
        return sorted(list(urls))


class FactGraph:
    """Graph structure managing facts across all pages of a site snapshot."""

    def __init__(self, site: str):
        self.site = site
        # fact_type -> list of FactCluster
        self._clusters: Dict[str, List[FactCluster]] = {}

    def add_fact(self, fact: ExtractedFact) -> None:
        clusters = self._clusters.setdefault(fact.fact_type, [])
        evidence = FactEvidence(
            url=fact.source_url,
            raw_value=fact.raw_value,
            context_snippet=fact.context_snippet,
            confidence=fact.confidence,
        )

        # Check if fact matches an existing cluster in this fact_type
        matched = False
        for cluster in clusters:
            if not cluster.normalized_value.is_conflict(fact.normalized):
                # Merges into cluster (they agree)
                cluster.evidence_list.append(evidence)
                matched = True
                break

        if not matched:
            # Create new cluster
            new_cluster = FactCluster(
                fact_type=fact.fact_type,
                normalized_value=fact.normalized,
                evidence_list=[evidence],
            )
            clusters.append(new_cluster)

    @staticmethod
    def _is_multi_tier_or_plan_option(ca: FactCluster, cb: FactCluster) -> bool:
        """Determines if two price clusters represent legitimate multi-tier plans or donation options."""
        snippets_a = " ".join(e.context_snippet.lower() for e in ca.evidence_list)
        snippets_b = " ".join(e.context_snippet.lower() for e in cb.evidence_list)
        all_snippets = f"{snippets_a} {snippets_b}"

        # 1. Check for donation option groups (e.g. Wikimedia donation buttons)
        if any(w in all_snippets for w in ("donate", "donation", "please select an amount", "any amount helps", "once monthly yearly")):
            return True

        # 2. Check for differing billing frequencies (annual vs monthly)
        has_annual_a = any(w in snippets_a for w in ("annual", "yearly", "year", "per year", "/year", "/yr", "total"))
        has_monthly_a = any(w in snippets_a for w in ("monthly", "month", "per month", "/month", "/mo"))
        has_annual_b = any(w in snippets_b for w in ("annual", "yearly", "year", "per year", "/year", "/yr", "total"))
        has_monthly_b = any(w in snippets_b for w in ("monthly", "month", "per month", "/month", "/mo"))

        if (has_annual_a and not has_monthly_a and has_monthly_b and not has_annual_b) or \
           (has_monthly_a and not has_annual_a and has_annual_b and not has_monthly_b):
            return True

        # 3. Check for distinct named plan tiers
        tiers = ["starter", "basic", "pro", "professional", "enterprise", "team", "business", "individual", "personal", "family", "student", "standard", "premium", "max"]
        tier_a = [t for t in tiers if t in snippets_a]
        tier_b = [t for t in tiers if t in snippets_b]
        if tier_a and tier_b and set(tier_a) != set(tier_b):
            return True

        return False

    def detect_conflicts(self) -> List[FactConflict]:
        """Scans all fact types for multiple conflicting clusters across pages."""
        conflicts: List[FactConflict] = []

        for fact_type, clusters in self._clusters.items():
            if len(clusters) < 2:
                continue

            # Compare pairs of clusters
            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    ca = clusters[i]
                    cb = clusters[j]
                    if ca.normalized_value.is_conflict(cb.normalized_value):
                        # Ensure the conflicting evidence comes from distinct pages
                        urls_a = {e.url for e in ca.evidence_list}
                        urls_b = {e.url for e in cb.evidence_list}

                        # If all evidence for both clusters comes from the EXACT same page(s),
                        # this represents multiple selectable options on that page, not a cross-page contradiction.
                        distinct_pages_a = urls_a - urls_b
                        distinct_pages_b = urls_b - urls_a
                        if not distinct_pages_a and not distinct_pages_b:
                            continue

                        # For pricing facts: check if they represent multi-tier or billing period options
                        if fact_type == "price" and self._is_multi_tier_or_plan_option(ca, cb):
                            continue

                        # Compute joint confidence
                        max_conf_a = max(e.confidence for e in ca.evidence_list)
                        max_conf_b = max(e.confidence for e in cb.evidence_list)
                        joint_conf = round(min(max_conf_a, max_conf_b) * 0.95, 2)

                        conflicts.append(
                            FactConflict(
                                fact_type=fact_type,
                                cluster_a=ca,
                                cluster_b=cb,
                                confidence=joint_conf,
                            )
                        )

        return conflicts

    def get_consensus_facts(self) -> Dict[str, str]:
        """Returns fact types that have single undisputed consensus values."""
        consensus: Dict[str, str] = {}
        for fact_type, clusters in self._clusters.items():
            if len(clusters) == 1:
                consensus[fact_type] = clusters[0].normalized_value.canonical_value
        return consensus

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_fact_types": len(self._clusters),
            "fact_types": list(self._clusters.keys()),
            "total_facts_recorded": sum(
                len(c.evidence_list) for clist in self._clusters.values() for c in clist
            ),
        }
