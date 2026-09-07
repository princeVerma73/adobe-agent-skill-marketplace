---
name: audit-orchestrator
description: Coordinate the specialist website audit skills and emit one evidence-backed final report.
license: Apache-2.0
---
# Audit Orchestrator
Input: website URL and inspection data.
Procedure: validate → inspect → compose specialist skills → merge → deduplicate → validate evidence → normalize severity → prioritize actions → emit final report.
Required output fields: site, audited_at, summary, findings. Each finding: id, title, severity, evidence, suggested_action.
