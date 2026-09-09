# Member 2 - Entity, Content, Freshness & Trust Architecture

## Overview

Member 2 implements the knowledge verification, content clarity, and trust audit layer for the Adobe Agent Skill Marketplace. It evaluates whether AI search engines, answer bots, and automated agents can accurately discover, disambiguate, ground, and trust a brand or organization from its website observations.

```
SiteInspection (Member 1) / SiteSnapshot
                   │
                   ▼
       [Model Ingestion & Conversion]
                   │
    ┌──────────────┼──────────────┬──────────────┐
    ▼              ▼              ▼              ▼
[Entity Audit] [Content Clarity] [Freshness]  [Fact Extractor]
 (Identity,     (Facts in         (Copyright,   (Founding,
  Schema.org,    Images, Vague     Temporal      Locations,
  Ambiguity)     Claims)           Decay)        Pricing, Phone)
    │              │              │              │
    └──────────────┼──────────────┼──────────────┘
                   ▼              ▼
            [Fact Normalizer] [In-Memory Fact Graph]
                   │              │
                   └──────────────┼──────────────┐
                                  ▼              ▼
                       [Cross-Page Consistency]  │
                        (Conflict Resolution)   │
                                  │              │
                                  ▼              ▼
                     [Confidence & False-Positive Filter]
                             (>= 0.70 Threshold)
                                  │
                                  ▼
                    ContentEntityAuditResult (JSON)
```

---

## Architecture & Subsystems

### 1. Model Ingestion & Zero-Overhead Adaptation (`src/entity_trust/contracts/schemas.py`)
- **Direct Consumption:** Ingests Member 1's frozen `SiteInspection` Pydantic models directly via `SiteSnapshot.from_site_inspection()`.
- **Zero Redundant Parsing:** Reuses pre-extracted headings (`H1`-`H6`), JSON-LD structured data, metadata tags, and visible body text without costly re-parsing.
- **Backward Compatibility:** Simultaneously supports legacy `SiteSnapshot` and plain Python dictionary structures.

### 2. Entity Disambiguation & Identity Engine (`src/entity_trust/audits/entity_audit.py`)
- **Brand Identity Extraction:** Extracts official brand names across Schema.org `Organization` / `LocalBusiness`, OpenGraph `site_name`, `<title>`, and footer copyright statements.
- **Ambiguity Detection (EC-001):** Flags generic or empty homepage `<title>` and `<h1>` elements that conceal brand identity from search crawlers.
- **Disambiguation & Category (EC-002):** Validates the presence of explicit business category definitions and target industry classifications.
- **Schema.org Presence (EC-003):** Checks for grounded JSON-LD `Organization` schemas providing machine-readable identity.
- **Entity Profile Generation:** Constructs an aggregated `EntityProfile` declaring official name, industry, description, and confidence score.

### 3. Content Clarity & Unlocked Facts Engine (`src/entity_trust/audits/content_clarity_audit.py`)
- **Facts Locked in Images (CC-001):** Detects statistical infographics, awards, certifications, or performance metrics embedded visually in images lacking alt text or crawlable text equivalents.
- **Unsubstantiated Superlatives (CC-002):** Scans for hyperbolic marketing buzzwords (`world-class`, `industry-leading`, `unmatched`) that lack concrete numbers or technical specifications.
- **Missing Essential Attributes (CC-003):** Validates the site-wide existence of physical/geographic headquarters and direct contact channels (email/phone).

### 4. Freshness & Temporal Decay Engine (`src/entity_trust/audits/freshness_audit.py`)
- **Copyright Lag Detection (FR-001):** Evaluates footer copyright timestamps relative to the current reference year (2026), flagging dormant sites with 2+ years lag.
- **Stale Announcement Detection (FR-002):** Scans news, blog, and press release feeds for legacy items presented as active updates.

### 5. Multi-Page Fact Normalization & Graph Engine (`src/entity_trust/core/`)
- **Fact Extractor (`fact_extractor.py`):** Deterministic extraction of founding dates, headquarters, pricing structures, phone numbers, and metrics across all pages and JSON-LD markup.
- **Fact Normalizer (`fact_normalizer.py`):** Normalizes currencies (`$`, `USD`, `₹`, `INR`, `€`), locations (city synonyms and containment), and temporal values to canonical representations.
- **Fact Graph (`fact_graph.py`):** In-memory knowledge graph clustering facts and isolating cross-page factual contradictions (`CO-001+`).

### 6. Confidence Calibration & False-Positive Filter (`src/entity_trust/core/confidence.py`)
- **Threshold Enforcement:** Filters out low-certainty findings below a configurable confidence threshold (default `0.70`).
- **Deduplication:** Merges overlapping findings across pages.
- **Severity Ranking:** Sorts findings from `critical` down to `info` for prioritized remediation.

---

## Test Suite Status

Member 2 includes 8 dedicated test modules and 1 integration module, totaling **24 passed tests** alongside Member 1's 193 tests (**217 passed overall**):

| Test Module | Coverage Area | Status |
| :--- | :--- | :--- |
| `tests/member2/test_member2_contracts.py` | Contracts, Pydantic serialization, `SiteInspection` conversion | Passed |
| `tests/member2/test_entity_audit.py` | Brand disambiguation, missing Schema.org, title/H1 checks | Passed |
| `tests/member2/test_content_clarity_audit.py` | Facts locked in images, vague claims, missing attributes | Passed |
| `tests/member2/test_freshness_audit.py` | Outdated copyright, stale announcement feeds | Passed |
| `tests/member2/test_fact_normalizer.py` | Currency, founding year, and location normalization | Passed |
| `tests/member2/test_fact_extractor_and_graph.py` | Structured fact extraction and conflict graph clustering | Passed |
| `tests/member2/test_runner_e2e.py` | End-to-end audit execution on 5 realistic site fixtures | Passed |
| `tests/member2/test_member2_skill_contract.py` | Agent Skill metadata, SKILL.md, references, and scripts | Passed |
| `tests/integration/test_member1_member2_integration.py` | Member 1 `SiteInspection` -> Member 2 pipeline integration | Passed |
| **Total Test Suite** | **All Modules** | **217/217 passed** |
