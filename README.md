# Adobe Brand AI-Readiness Audit Agent Skill Marketplace

The **Adobe Brand AI-Readiness Audit Marketplace** is an autonomous multi-skill intelligence pipeline designed for Adobe University Hackathon 2026 (Round 3). It solves the critical problem of brand invisibility and misrepresentation in the emerging era of AI search engines, answer engines, and autonomous agents by systematically evaluating any public website across technical discoverability, semantic entity grounding, content freshness, and on-site engagement. The pipeline produces an executive-grade `FinalAuditReport` in JSON and Markdown formats featuring evidence-backed findings, calibrated confidence scoring, and a prioritized remediation roadmap.

---

## Skills in this marketplace

### crawl-render-audit
The **Website Intelligence** skill (`skills/crawl-render-audit`) performs bounded, RFC 9309-compliant web crawling, recursive XML sitemap discovery, SSRF-guarded network fetching, and clean HTML metadata/structural extraction. When single-page application (SPA) frameworks or static-to-rendered text discrepancies are detected, it selectively engages a headless Playwright rendering engine with aggressive resource filtering (blocking images/media/fonts) for optimal performance. It analyzes technical discoverability (HTTP status, redirect loops, heading hierarchies, robots meta directives, canonical validity, and structured schema existence) and outputs a standardized `SiteInspection` contract model.

### entity-content-freshness-trust
The **Entity & Trust Analysis** skill (`skills/entity-content-freshness-trust`) evaluates whether AI agents and search engines can unambiguously identify the organization, its core offerings, and its corporate legitimacy. It performs knowledge-graph fact extraction and cross-page contradiction analysis, detects factual/statistical data trapped in non-text images without accessible equivalents, flags unsubstantiated superlative marketing claims, and evaluates content freshness and timestamp decay. It outputs a normalized list of semantic `Finding` records alongside a consolidated `EntityProfile`.

### engagement-recommendations
The **Engagement & Recommendations** skill (`skills/engagement-recommendations`) assesses on-site human and agent navigation pathways, user orientation, and conversion readiness. It checks for prominent homepage value propositions, clear primary calls-to-action (CTAs), accessible contact and support channels, descriptive anchor texts, and context retention (verifying deep landing pages link back to the brand portal while intelligently recognizing legitimate terminal pages). It outputs prioritized engagement findings and maps detected defects to concrete, mechanism-sound remediation strategies.

### audit-orchestrator
The **Audit Orchestration** skill (`skills/audit-orchestrator`) serves as the **single marketplace entrypoint** (`"entrypoint": true` in `marketplace.json`). It coordinates the asynchronous execution of the specialist skills, normalizes and deduplicates findings across technical and semantic boundaries, applies calibrated severity scoring, verifies evidence URL authenticity, and generates the final unified `FinalAuditReport`.

---

## How the entrypoint composes them

The orchestrator executes an end-to-end, multi-stage audit pipeline:

```
                  ┌────────────────────────────────────────┐
                  │ Target Website URL or Serialized Input │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │          crawl-render-audit            │
                  │   (Crawl, Render, Technical Audit)     │
                  └───────────────────┬────────────────────┘
                                      │
                         SiteInspection Data Contract
                                      │
                     ┌────────────────┴────────────────┐
                     ▼                                 ▼
      ┌──────────────────────────────┐  ┌──────────────────────────────┐
      │entity-content-freshness-trust│  │  engagement-recommendations  │
      │(Entity, Clarity, Freshness)  │  │(Engagement, Context, Actions)│
      └──────────────┬───────────────┘  └──────────────┬───────────────┘
                     │                                 │
                     └────────────────┬────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │        Normalizer & Deduplicator       │
                  │ (Cross-Skill Merging & Evidence Check) │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │             Report Builder             │
                  │  (Severity Counts, Scoring, Roadmap)   │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │            FinalAuditReport            │
                  │        (Structured JSON & Markdown)    │
                  └────────────────────────────────────────┘
```

The orchestration logic is implemented in:
- **`src/report/orchestrator.py`** — Handles execution flow, dispatches inputs to specialist subsystems, verifies URL evidence grounding, and aggregates skill statuses.
- **`src/report/deduplicator.py`** — Deduplicates equivalent findings across skills (e.g. cross-skill heading hierarchy equivalence) and merges multi-page occurrences into consolidated affected URL sets.
- **`src/report/builder.py`** — Computes the Brand AI-Readiness score (0–100), assigns letter grades (A–F), aggregates severity counts, and synthesizes the prioritized actionable recommendation roadmap.

---

## Architecture & Data Contracts

### 1. Unified Shared Contract
All specialist skills communicate via immutable, typed Pydantic models defined in `src/inspection/models.py`, `src/entity_trust/contracts/schemas.py`, and `src/report/models.py`:

```
SiteInspection
 ├── site: str
 ├── root_url: str
 ├── robots: RobotsTxtInspection
 ├── sitemap: SitemapInspection
 ├── pages: List[PageInspection]
 │     ├── url, original_url, status_code, response_time_ms
 │     ├── title, metadata (OG, Twitter, canonical, robots_meta)
 │     ├── headings: List[Heading] (level, text)
 │     ├── body_text, clean_text, source_text, rendered_text
 │     ├── links: List[Link] (url, text, is_internal)
 │     ├── structured_data: List[Dict] (JSON-LD)
 │     └── technical_issues: List[TechnicalIssue]
 └── summary_counts: Dict[str, int]
```

### 2. Output Schema (`FinalAuditReport`)
The resulting report conforms strictly to the contest specification:
```json
{
  "site": "example.com",
  "root_url": "https://example.com",
  "audited_at": "2026-09-11T00:00:00Z",
  "status": "success",
  "overall_score": 88.0,
  "readiness_grade": "B",
  "severity_counts": {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 1,
    "info": 0
  },
  "summary": {
    "total_findings": 4,
    "critical": 0,
    "high": 1,
    "medium": 2,
    "pages_analyzed": 5
  },
  "entity_profile": {
    "name": "Example Corp",
    "type": "Organization",
    "industry": "software"
  },
  "findings": [
    {
      "id": "EC-003",
      "category": "entity",
      "title": "Missing Schema.org Organization structured data",
      "severity": "medium",
      "confidence": 0.95,
      "evidence": "No JSON-LD Schema.org 'Organization' definition was found...",
      "affected_urls": ["https://example.com"],
      "suggested_action": {
        "summary": "Implement JSON-LD Schema.org 'Organization' metadata...",
        "priority": "medium"
      }
    }
  ],
  "recommendations": [...]
}
```

---

## Safety, Read-Only Boundary & Security

- **Strictly Read-Only:** All network operations use HTTP `GET` and `HEAD` requests only. No write, mutation, `POST`, `PUT`, `DELETE`, or form-submission actions exist in production code.
- **SSRF Guard:** Comprehensive network boundary validation in `src/inspection/url.py` blocks private subnets (RFC 1918), loopback (`127.0.0.0/8`, `::1`), link-local / cloud metadata services (`169.254.0.0/16`), and non-web protocols.
- **Robots & Concurrency Governance:** Strict RFC 9309 parser obeys `Disallow` directives, User-Agent precedence, and `Crawl-delay` rate limits.
- **Anti-Hallucination Evidence Validation:** Every finding emitted in the final report is strictly validated against audited page URLs and extracted DOM content.

---

## Quickstart & Usage

### CLI Execution via Entrypoint Skill

```bash
# Run a complete audit against a live website (outputs formatted JSON)
python skills/audit-orchestrator/scripts/run_audit.py https://example.com

# Run audit and generate an executive Markdown report
python skills/audit-orchestrator/scripts/run_audit.py https://example.com --format markdown --output report.md

# Run audit with custom crawl limits
python skills/audit-orchestrator/scripts/run_audit.py https://example.com --max-pages 10 --max-depth 2
```

### Python API Execution

```python
from src.report import run_full_audit

# Run comprehensive multi-skill audit
report = run_full_audit(
    target="https://example.com",
    confidence_threshold=0.70,
    max_pages=10,
    max_depth=2,
)

print(f"Site: {report.site}")
print(f"Score: {report.overall_score}/100 (Grade: {report.readiness_grade})")
print(f"Total Findings: {len(report.findings)}")
for finding in report.findings:
    print(f"- [{finding.id}] ({finding.severity}): {finding.title}")
```

---

## Verification & Test Suite

The marketplace includes a comprehensive, multi-layer automated test suite spanning unit, property, mock contract, and end-to-end integration tests:

| Subsystem / Test Area | Test Modules | Test Coverage |
| :--- | :--- | :--- |
| **Website Intelligence** | `tests/member1/` (13 modules) | URL validation, SSRF boundary, safe HTTP, robots parsing, XML sitemaps, crawler, extraction, Playwright rendering, technical rules |
| **Entity & Trust Analysis** | `tests/member2/` (9 modules) | Fact extraction, fact graph, contradiction detection, content clarity, freshness decay, confidence scoring |
| **Engagement & Recommendations** | `tests/member3/` (9 modules) | Orientation, CTAs, contact paths, heading hierarchy, anchor texts, context retention, recommendation engine |
| **Pipeline Integration & Orchestration** | `tests/integration/` | End-to-end pipeline execution, cross-skill deduplication, schema validation, graceful failure handling |
| **Total Automated Suite** | **33 test modules** | **265 passed (100% pass rate)** |

Run the test suite:
```bash
pytest -q
```
