"""Engagement & Recommendations Audit Module (Member 3).

Audits visitor orientation, information hierarchy, CTA pathways,
internal link topology, and conversion journeys.
"""

from .models import (
    EngagementAuditResult,
    EngagementFinding,
    EngagementMetrics,
)
from .runner import audit_engagement

__all__ = [
    "EngagementAuditResult",
    "EngagementFinding",
    "EngagementMetrics",
    "audit_engagement",
]
