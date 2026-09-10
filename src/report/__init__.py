"""Report Composition and Master Orchestration Module (Member 3).

Synthesizes specialist audit findings from Member 1 (Technical),
Member 2 (Semantic Trust & Content), and Member 3 (Engagement & UX)
into unified, actionable Brand AI-Readiness reports.
"""

from .models import FinalAuditReport, ReportFinding
from .builder import ReportBuilder, calculate_readiness_score
from .deduplicator import deduplicate_findings
from .orchestrator import AuditOrchestrator, run_full_audit

__all__ = [
    "FinalAuditReport",
    "ReportFinding",
    "ReportBuilder",
    "calculate_readiness_score",
    "deduplicate_findings",
    "AuditOrchestrator",
    "run_full_audit",
]
