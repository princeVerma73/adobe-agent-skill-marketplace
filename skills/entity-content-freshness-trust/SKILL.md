---
name: entity-content-freshness-trust
description: Audit whether important facts are explicit, machine-readable, current, corroborated, and associated with the correct entity.
license: Apache-2.0
---

# Entity, Content, Freshness & Trust Audit Skill

## Purpose
The `entity-content-freshness-trust` skill evaluates whether search engines, knowledge engines, and AI agents can correctly comprehend, ground, and trust a brand or organization's website. It audits entity identity disambiguation, structured Schema.org markup, facts locked in non-text images, temporal currency, and cross-page factual consistency without mutating remote site state.

## When to Use
Use this skill when:
- An orchestrator or audit pipeline needs to evaluate whether a website's brand identity is explicit and machine-readable.
- Verifying Schema.org `Organization` or `LocalBusiness` JSON-LD coverage.
- Identifying critical facts (certifications, metrics, timelines) locked inside image assets lacking text alternatives.
- Detecting stale dates, outdated announcements presented as current, and copyright lag.
- Discovering cross-page factual contradictions (founding years, pricing, headquarters, phone numbers) across different pages on the domain.
- Calibrating audit findings with high-precision confidence scoring and false-positive suppression.

## Safe and Read-Only Behavior
This skill operates strictly on static or pre-extracted website snapshots:
- **No Mutation:** Never submits forms, modifies state, or performs intrusive actions.
- **Offline Analysis:** Operates purely on serialized `SiteInspection` or `SiteSnapshot` structures.
- **Strict Evidence Standard:** Discards speculative findings where textual or metadata evidence does not meet confidence thresholds.

## Inputs
| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `snapshot` | `SiteInspection` \| `SiteSnapshot` \| `dict` | *(required)* | Pre-extracted site inspection observation or snapshot. |
| `confidence_threshold` | `float` | `0.70` | Minimum confidence score (0.0 to 1.0) required to report a finding. |

## Outputs
Returns a standardized `ContentEntityAuditResult` matching Adobe Hackathon contracts:
- **`skill`**: `"entity-content-freshness-trust"`
- **`status`**: `"success"`
- **`site`**: Domain hostname.
- **`total_findings`**: Total number of findings meeting confidence threshold.
- **`severity_counts`**: Breakdown across `critical`, `high`, `medium`, `low`, and `info`.
- **`entity_profile`**: Consolidated brand knowledge profile (`name`, `type`, `description`, `industry`, `confidence_score`).
- **`findings`**: List of `Finding` objects containing:
  - `id`: Machine-readable code (e.g., `EC-001`, `CC-001`, `FR-001`, `CO-001`).
  - `category`: `entity`, `content_clarity`, `freshness`, or `consistency`.
  - `title`: Human-readable summary.
  - `severity`: `critical`, `high`, `medium`, `low`, or `info`.
  - `confidence`: Calibrated certainty score (0.00 to 1.00).
  - `evidence`: Specific textual excerpt and source URL attribution.
  - `affected_urls`: List of relevant page URLs.
  - `suggested_action`: Actionable remediation with `summary` and `priority`.

## Usage and Pipeline Integration

```python
from src.entity_trust import audit_entity_trust
from src.inspection import inspect_site

# 1. Generate inspection observation from Member 1
site_inspection = inspect_site(url="https://example.com", max_pages=10)

# 2. Run Member 2 audit
audit_result = audit_entity_trust(site_inspection, confidence_threshold=0.70)

# 3. Access calibrated findings
print(f"Site: {audit_result.site}")
print(f"Identified Entity: {audit_result.entity_profile.name} (Industry: {audit_result.entity_profile.industry})")
print(f"Total Findings: {audit_result.total_findings}")

for finding in audit_result.findings:
    print(f"[{finding.severity.upper()}] {finding.id}: {finding.title}")
    print(f"  Confidence: {finding.confidence}")
    print(f"  Evidence: {finding.evidence}")
    print(f"  Action: {finding.suggested_action.summary}\n")
```
