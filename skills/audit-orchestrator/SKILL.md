---
name: audit-orchestrator
description: Coordinate the specialist website audit skills, synthesize cross-skill findings, and emit a unified evidence-backed Brand AI-Readiness report.
license: Apache-2.0
---

# Audit Orchestrator Skill

## Purpose
The `audit-orchestrator` is the primary entrypoint skill for the Adobe Agent Skill Marketplace (`brand-ai-readiness-audit`). It coordinates the entire auditing lifecycle: safely inspecting the domain via Member 1 (`crawl-render-audit`), analyzing semantic trust and entity consistency via Member 2 (`entity-content-freshness-trust`), evaluating user pathways via Member 3 (`engagement-recommendations`), validating evidence, removing duplicates, computing a Brand AI-Readiness score (0–100), and compiling an actionable remediation roadmap.

## Workflow Pipeline
```
Target URL / Snapshot
      ↓
Member 1: crawl-render-audit (Bounded BFS, SSRF guard, selective Playwright rendering, technical discoverability)
      ↓
Member 2: entity-content-freshness-trust (Entity disambiguation, Schema.org, visual facts, temporal decay, fact graph)
      ↓
Member 3: engagement-recommendations (Landing orientation, navigation, hierarchy, CTAs, linking, dead ends, context)
      ↓
Master Aggregator & Finding Normalizer (Maps all issues into unified schema)
      ↓
Evidence Validator & Anti-Hallucination Guard (Verifies findings against raw observations)
      ↓
Cross-Skill Deduplicator & Severity Ranker (Merges redundant findings, consolidates affected URLs)
      ↓
Actionable Remediation Engine (Maps findings to prescriptive fixes with test verification steps)
      ↓
Readiness Scorer (Computes 0-100 score and letter grade A-F)
      ↓
Final Multi-Agent Audit Report (Structured JSON & Executive Markdown)
```

## Fault Tolerance & Graceful Degradation
The orchestrator isolates failures between individual skills:
- If Member 1 encounters network or DNS failure, a structured failure report is returned without crashing.
- If Member 2 or Member 3 raises an exception, the failure is recorded in `skill_statuses` (e.g. `"partial_failure"`), and the remaining skills' findings are preserved and presented.
- Never fabricates evidence or silences errors.

## Inputs
| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `target` | `str` \| `SiteInspection` \| `dict` | *(required)* | Website URL or pre-extracted inspection snapshot. |
| `confidence_threshold` | `float` | `0.70` | Minimum confidence score to retain findings. |
| `max_pages` | `int` | `10` | Maximum pages to crawl if target is a URL. |
| `max_depth` | `int` | `2` | Maximum link depth from root URL. |
| `enable_rendering` | `bool` | `True` | Conditionally execute headless Playwright for SPAs. |

## Outputs
Returns a `FinalAuditReport` model containing:
- **`site`**: Target website domain.
- **`root_url`**: Starting canonical URL.
- **`status`**: `"success"`, `"partial_failure"`, or `"error"`.
- **`overall_score`**: 0.0 to 100.0 Brand AI-Readiness score.
- **`readiness_grade`**: `"A"`, `"B"`, `"C"`, `"D"`, or `"F"`.
- **`severity_counts`**: Breakdown across critical, high, medium, low, and info.
- **`entity_profile`**: Disambiguated brand identity (name, industry, founding year, contact).
- **`findings`**: Deduplicated list of `ReportFinding` objects (`id`, `category`, `title`, `severity`, `confidence`, `evidence`, `affected_urls`, `suggested_action`).
- **`recommendations`**: List of `ActionableRecommendation` items with diagnosis, prescribed changes, why it matters, and verification steps.
- **`skill_statuses`**: Execution status for each skill.
- **`summary`**: Quantitative metrics and crawled URL lists.
- Methods: `to_json(indent=2)` and `to_markdown()`.

## Usage & Integration

### Python API
```python
from src.report import run_full_audit

# Run end-to-end multi-skill audit
report = run_full_audit(
    target="https://example.com",
    confidence_threshold=0.70,
    max_pages=10,
    max_depth=2,
)

print(f"Site: {report.site}")
print(f"Readiness Score: {report.overall_score}/100 (Grade: {report.readiness_grade})")
print(f"Total Findings: {len(report.findings)}")

# Export Markdown summary
markdown_text = report.to_markdown()

# Export standardized JSON
json_text = report.to_json(indent=2)
```

### Standalone CLI Execution
```bash
# Output JSON report
python skills/audit-orchestrator/scripts/run_audit.py https://example.com

# Output Markdown report saved to file
python skills/audit-orchestrator/scripts/run_audit.py https://example.com --format markdown --output report.md

# Audit existing snapshot JSON offline
python skills/audit-orchestrator/scripts/run_audit.py snapshot.json
```
