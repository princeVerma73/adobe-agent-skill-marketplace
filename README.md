# Brand AI-Readiness Audit Marketplace

An autonomous, multi-skill agent marketplace built for the **Adobe University Hackathon 2026 (Round 3)**. It evaluates any public website across technical discoverability, semantic entity grounding, content freshness, and on-site user engagement to produce an executive-grade Brand AI-Readiness audit report.

---

## Executive Summary (30-Second Overview)

- **What is this?** A modular, production-grade agent skill marketplace that inspects websites and audits their readiness for discovery, comprehension, and synthesis by AI search engines and autonomous agents.
- **What problem does it solve?** In the emerging era of AI-driven search and agentic web exploration, brands frequently suffer from indexing invisibility, entity ambiguity, conflicting cross-page facts, and orphaned navigation journeys. This marketplace identifies these vulnerabilities deterministically.
- **What are the four skills?**
  1. `audit-orchestrator` (Marketplace Entrypoint): Coordinates execution, deduplicates cross-skill findings, validates evidence URLs, and compiles the final report.
  2. `crawl-render-audit`: Safe, bounded crawling, RFC 9309 robots handling, recursive XML sitemaps, and selective Playwright DOM rendering for single-page applications.
  3. `entity-content-freshness-trust`: Entity identity disambiguation, Schema.org verification, temporal decay, visual data accessibility, and cross-page factual consistency.
  4. `engagement-recommendations`: Navigation pathways, conversion orientation, heading progression, CTA clarity, context retention, and prioritized remediation actions.
- **How do they compose?** The `audit-orchestrator` passes a unified `SiteInspection` contract model from `crawl-render-audit` to both downstream specialist skills in parallel, collects and normalizes their findings, deduplicates equivalent issues, and builds a consolidated report.
- **What does the final report contain?** A Brand AI-Readiness score (0–100), letter grade (A–F), severity breakdown, entity profile, deduplicated evidence-backed findings with affected URLs, and a prioritized remediation roadmap.
- **What makes this marketplace different?** Strict DOM-grounded evidence validation to minimize unsupported claims, SSRF network protection, graceful partial-failure degradation, and real-world false-positive calibration across diverse web archetypes.
- **What evidence demonstrates generalization and reliability?** An adversarial 8-site real-world evaluation spanning documentation, SaaS, journalism, higher education, nonprofits, and government portals, backed by a 278-test deterministic test suite.

---

## Architecture

```
                       audit-orchestrator (Entrypoint)
                                      │
                                      ▼
                             crawl-render-audit
                                      │
                         SiteInspection Data Contract
                                      │
                     ┌────────────────┴────────────────┐
                     ▼                                 ▼
       entity-content-freshness-trust     engagement-recommendations
                     │                                 │
                     └────────────────┬────────────────┘
                                      │
                                      ▼
                        Normalizer & Deduplicator
                                      │
                                      ▼
                              Final Audit Report
                         (Structured JSON & Markdown)
```

### Specialist Skills Overview

- **`audit-orchestrator` (`skills/audit-orchestrator`)**: Single entrypoint (`"entrypoint": true` in `marketplace.json`). Manages end-to-end execution, normalizes finding schemas across skills, merges identical issues across pages, computes overall readiness score and letter grade, and outputs the `FinalAuditReport`.
- **`crawl-render-audit` (`skills/crawl-render-audit`)**: Deterministic, read-only crawler. Performs bounded BFS traversal, XML sitemap extraction, SSRF validation, and selective Playwright headless rendering when static HTML lacks content.
- **`entity-content-freshness-trust` (`skills/entity-content-freshness-trust`)**: Audits whether brand identity is explicit, Schema.org `Organization` metadata exists, critical numbers are accessible in text rather than trapped in images, content is temporally current, and cross-page claims are factually consistent.
- **`engagement-recommendations` (`skills/engagement-recommendations`)**: Evaluates user and agent orientation, primary CTAs, heading hierarchy (H1–H6), internal link topology, contact reachability, and deep landing context retention.

All skills operate strictly read-only — no forms are submitted, no authenticated or destructive actions are performed, and robots.txt is respected on every crawl.

---

## Evaluation & Generalization Evidence

The marketplace was evaluated against 8 diverse, live, publicly accessible websites across multiple domains and architectures during Phase 9 adversarial testing, followed by targeted calibration (Phase 9B):

| Site | Category | Score Before | Score After | Findings Before | Findings After |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Python Docs** | Documentation | 61 | 67 | 9 | 9 |
| **Notion** | SaaS / Software | 50 | 50 | 8 | 8 |
| **The Verge** | News / Publisher | 53 | 68 | 8 | 5 |
| **MIT** | University | 33 | 33 | 13 | 13 |
| **Wikimedia** | Nonprofit | 0 | 55 | 39 | 12 |
| **FastAPI** | Developer / Tech | 67 | 73 | 6 | 6 |
| **Mozilla** | Technology | 21 | 57 | 13 | 10 |
| **NASA** | Public / Content | 60 | 66 | 7 | 7 |

> **Note:** Readiness scores are an internal marketplace heuristic and are NOT an Adobe metric.

- **Verified Runtime:** **201.83 seconds** for the full eight-site Phase 9B evaluation with rendering enabled.
- **Defect Stability:** Clean and stable sites (such as Notion and MIT) experienced zero unintended score fluctuations during calibration, confirming high regression safety.

---

## False-Positive Hardening

Live adversarial evaluation revealed five distinct real-world defect classes where naive heuristics generated spurious findings on production websites:

1. **Legitimate same-page donation/plan tiers:** Multi-tier pricing buttons (e.g. $5, $10, $20 on donation forms) were incorrectly flagged as factual contradictions.
2. **Third-party editorial pricing:** Numbers cited inside news reviews and editorial articles were erroneously attributed to the audited publisher's own identity.
3. **Departmental email addresses:** Legitimate distinct contact emails (`press@`, `jobs@`, `info@`) across organizational divisions were treated as conflicting claims.
4. **Documentation/version titles:** Software documentation titles (e.g. "3.12 Documentation") were misidentified as primary entity brand names.
5. **Localized homepage paths:** Internationalized root paths (e.g. `/en-US/`) were not recognized as valid root landing pages.

### The Engineering Feedback Loop

Every identified defect followed a rigorous validation and remediation lifecycle:
```
Real-World Failure Identified
            ↓
Root-Cause Mechanism Analysis
            ↓
Targeted Mechanism-Level Fix (No Heuristic Suppressions)
            ↓
Deterministic Regression Fixture Added
            ↓
Real-Site Re-Verification Across All 8 Sites
```

**Concrete Example — Wikimedia Foundation:**
- **Initial Result:** 39 findings / Score 0 (heavily penalized by spurious contradictions across donation tiers and multi-language subdomains).
- **Targeted Mechanism Fix:** Context-aware entity scoping and plan/donation tier recognition.
- **Calibrated Result:** 12 findings / Score 55 (accurately preserving legitimate findings such as missing Schema.org JSON-LD and deep navigation improvements).

Importantly, the regression test suite verifies that genuinely ambiguous entity sites still trigger `HIGH EC-002` findings, proving that false-positive fixes did not globally suppress genuine detections.

---

## Known Limitations

In accordance with transparent engineering principles, the marketplace operates within the following established technical boundaries:

- **Bounded Crawl Depth & Page Budget:** Crawls are bounded by configurable limits (default: 10 pages, depth 2) to maintain predictable performance and respect host resources.
- **WAF / Bot Protection:** Sites protected by strict anti-bot mechanisms or Web Application Firewalls (HTTP 403 / Cloudflare challenges) may yield partial inspection data.
- **No External API Corroboration:** Fact consistency and entity grounding are evaluated strictly within on-site content and cross-page internal consistency, without querying third-party external APIs.
- **Content-Dependent Extraction:** Entity and trust conclusions rely on accessible on-page text, meta tags, and structured data present in the rendered DOM.
- **Heuristic Scoring:** The overall Brand AI-Readiness score is an internal heuristic synthesis intended for prioritization, not an official Adobe benchmark.

---

## Sample Reports

Pre-generated, verified audit reports conforming strictly to the `FinalAuditReport` data contract are available in the `examples/` directory:

- **[`examples/sample-report-fastapi.json`](examples/sample-report-fastapi.json)** — Complete audit report for FastAPI documentation site (Overall Score: 73.0, Grade: C, 6 findings).
- **[`examples/sample-report-wikimedia.json`](examples/sample-report-wikimedia.json)** — Complete audit report for Wikimedia Foundation site (Overall Score: 55.0, Grade: D, 12 findings).

---

## Quickstart & Usage

### 1. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Run the Full Test Suite

```bash
pytest -q
```
*Expected: 278 passed in ~1.5s.*

### 3. Run a Live Audit via the CLI

```bash
# Output formatted JSON report
python skills/audit-orchestrator/scripts/run_audit.py https://example.com

# Generate an Executive Markdown Report
python skills/audit-orchestrator/scripts/run_audit.py https://example.com --format markdown --output report.md

# Audit with custom crawl boundaries
python skills/audit-orchestrator/scripts/run_audit.py https://example.com --max-pages 10 --max-depth 2
```

### 4. Python Programmatic API

```python
from src.report import run_full_audit

report = run_full_audit(
    target="https://fastapi.tiangolo.com",
    confidence_threshold=0.70,
    max_pages=10,
    max_depth=2,
    enable_rendering=True,
)

print(f"Site: {report.site}")
print(f"Score: {report.overall_score}/100 (Grade: {report.readiness_grade})")
print(f"Findings ({len(report.findings)} total):")
for f in report.findings:
    print(f"  [{f.severity.upper()}] {f.id}: {f.title}")
```

---

## Marketplace Structure

```
Adobe-Agent-Marketplace/
├── marketplace.json                      # Marketplace manifest with audit-orchestrator entrypoint
├── README.md                             # Judge-facing documentation and evaluation evidence
├── requirements.txt                      # Python dependencies
├── pytest.ini                            # Test configuration
├── .gitignore                            # Clean artifact ignore rules
├── examples/                             # Validated sample audit reports
│   ├── sample-report-fastapi.json
│   └── sample-report-wikimedia.json
├── skills/                               # Contest skill implementations
│   ├── audit-orchestrator/               # Entrypoint: Multi-agent coordination & reporting
│   ├── crawl-render-audit/               # Bounded crawling, rendering, technical checks
│   ├── entity-content-freshness-trust/   # Knowledge graph, freshness, contradiction analysis
│   └── engagement-recommendations/       # UX pathways, CTA clarity, remediation roadmap
├── src/                                  # Canonical production runtime packages
│   ├── inspection/                       # Data contracts, technical rule engine, pipeline orchestration
│   ├── crawler/                          # Safe HTTP client, sitemap parser, bounded BFS crawler
│   ├── extraction/                       # HTML/metadata/heading/JSON-LD extraction
│   ├── rendering/                        # Headless Playwright rendering, SPA detection
│   ├── entity_trust/                     # Entity, clarity, freshness, consistency engines
│   ├── engagement/                       # Journey, hierarchy, CTA, link topology engines
│   ├── recommendations/                  # Prescriptive remediation engine
│   └── report/                           # Orchestration, deduplication, scoring, final report
└── tests/                                # 278 comprehensive unit & integration tests
    ├── fixtures/                         # Deterministic HTML/snapshot regression fixtures
    ├── integration/                      # End-to-end multi-skill integration tests
    ├── crawl_render_audit/               # Technical inspection test suite
    ├── entity_content_freshness_trust/   # Entity & trust test suite
    └── engagement_recommendations/       # Engagement & orchestration test suite
```
