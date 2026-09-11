# Report & Orchestration Layer (`src/report`)

The report and orchestration layer coordinates multi-skill execution, deduplicates cross-skill findings, validates URL evidence, computes calibrated readiness scores, and synthesizes the final executive audit report.

## Module Structure

- **`orchestrator.py`**: Top-level `AuditOrchestrator` coordinating the execution of specialist inspection, entity/trust, and engagement skills, enforcing URL evidence grounding, and isolating partial skill failures.
- **`models.py`**: Shared Pydantic contract models for final outputs (`FinalAuditReport`, `ReportFinding`, `ActionableRecommendation`, `SkillStatus`, `ReportSummary`).
- **`normalizer.py`**: Converts heterogeneous findings from specialist subsystems into standardized `ReportFinding` models.
- **`deduplicator.py`**: Cross-skill deduplicator that detects identical or overlapping findings across subsystems and merges affected URL lists.
- **`builder.py`**: `ReportBuilder` synthesizing the overall Brand AI-Readiness score (0–100), letter grade (A–F), severity breakdowns, and actionable remediation roadmap.

## Quick Usage

```python
from src.report import run_full_audit, FinalAuditReport

# Run comprehensive multi-skill audit
report: FinalAuditReport = run_full_audit(
    target="https://example.com",
    confidence_threshold=0.70,
    max_pages=10,
    max_depth=2,
    enable_rendering=True,
)

print(f"Site: {report.site}")
print(f"Score: {report.overall_score}/100 (Grade: {report.readiness_grade})")
print(f"Total Findings: {len(report.findings)}")

# Export formatted outputs
json_output = report.to_json(indent=2)
markdown_summary = report.to_markdown()
```
