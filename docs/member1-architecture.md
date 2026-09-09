# Member 1 — Crawl, Render & Technical Discoverability Architecture

## Overview

Member 1 implements the foundational data collection and inspection layer for the Adobe Agent Skill Marketplace. It converts an unverified target website URL into rich, structured, and normalized machine-readable evidence models (`SiteInspection`) without modifying remote state.

```
Target URL ──> [URL Validation & SSRF Guard]
                   │
                   ▼
               [Robots.txt & Sitemap Discovery]
                   │
                   ▼
               [Bounded BFS Crawler]
                   │
                   ▼
               [HTML Extraction & Selective Playwright Rendering]
                   │
                   ▼
               [Technical Discoverability Rule Engine]
                   │
                   ▼
               [Normalized SiteInspection Model]
                   │
                   ├──> Member 2 (Entity, Content, Freshness, Trust)
                   └──> Member 3 (Engagement, Recommendations, Orchestration)
```

---

## Phase Breakdown (Phases 1–8)

### Phase 1: URL Validation & SSRF Security Boundary (`src/inspection/url.py`)
- **Protocol Whitelisting:** Enforces `http://` and `https://` schemes. Rejects unsafe schemes (`file://`, `ftp://`, `javascript:`, `data:`).
- **Hostname Normalization:** Strips default ports (80/443), trailing dots, removes URL fragments, normalizes paths, and handles internationalized domain names (IDN / Punycode).
- **SSRF Boundary Protection:**
  - Blocks loopback targets (`127.0.0.0/8`, `localhost`, `[::1]`).
  - Blocks RFC 1918 private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
  - Blocks link-local addresses and cloud instance metadata services (`169.254.0.0/16`, `169.254.169.254`, `fe80::/10`).
  - Blocks unspecified/broadcast IPs (`0.0.0.0/8`, `255.255.255.255`).
  - Implements both offline IP parsing and DNS pre-resolution checks.

### Phase 2: Safe HTTP Client & robots.txt Parser (`src/crawler/http.py`, `src/crawler/robots.py`)
- **Read-Only Safety Guarantee:** Restricts HTTP methods strictly to `GET` and `HEAD`. Prohibits state-altering methods (`POST`, `PUT`, `PATCH`, `DELETE`).
- **Network Boundaries:**
  - Configurable request timeouts (default 10.0s).
  - Maximum body size limit (default 5 MB) preventing memory exhaustion from large downloads.
  - Redirect depth control (max 5 hops) with continuous SSRF re-validation on every redirect hop.
- **RFC 9309 Compliant robots.txt Parsing:**
  - Respects `User-agent:` matching hierarchy (exact agent match falling back to wildcard `*`).
  - Evaluates `Allow` and `Disallow` rules based on longest-match path semantics.
  - Extracts `Crawl-delay` and declared `Sitemap:` URLs.
  - Fail-safe semantics: Missing `robots.txt` (404) defaults to allowed; server errors (5xx) or timeouts record clear diagnostic evidence.

### Phase 3: XML Sitemap Discovery & Bounded BFS Crawler (`src/crawler/sitemap.py`, `src/crawler/crawler.py`)
- **Sitemap Discovery & Parsing:**
  - Discovers sitemaps declared in `robots.txt` or standard fallback paths (`/sitemap.xml`, `/sitemap_index.xml`).
  - Recursively resolves XML sitemap indexes (`<sitemapindex>`) and urlsets (`<urlset>`).
  - Supports gzip-compressed sitemaps (`.xml.gz`).
  - Namespace-resilient parsing with regex fallback for non-compliant XML feeds.
- **Bounded BFS Crawl Engine:**
  - Breadth-first traversal starting from canonical root URL.
  - Strict boundary enforcement via `max_pages` (default 10) and `max_depth` (default 2).
  - Domain isolation: Confines crawling to same registrable domain and subdomains (`same_site_only=True`).
  - Continuous robots.txt check before fetching each discovered URL.
  - Visited URL deduplication and normalization preventing infinite crawl loops.

### Phase 4: HTML Extraction & Selective Playwright Rendering (`src/extraction/extract.py`, `src/rendering/render.py`)
- **HTML & Metadata Extraction:**
  - Extracts page `<title>`, `<meta name="description">`, `<link rel="canonical">`, and `<meta name="robots">`.
  - Parses OpenGraph (`og:*`) and Twitter Card (`twitter:*`) properties.
  - Extracts clean, ordered heading hierarchy (`H1` through `H6`).
  - Extracts visible body text with noise stripping (removes `<script>`, `<style>`, `<noscript>`, `<svg>`, navigation menus).
  - Discovers internal and external hyperlinks with anchor text and `rel` attributes.
  - Extracts and normalizes JSON-LD structured data schemas (`@context`, `@type`).
- **Selective Playwright Rendering:**
  - Static HTML analysis detects SPA framework footprints (React, Vue, Angular, Next.js, Nuxt, Svelte, empty root mounting containers).
  - Calculates static vs rendered text length ratio discrepancy.
  - Conditionally boots headless Chromium to render JavaScript-heavy SPAs.
  - High performance & safety: Aborts non-essential heavy network assets (images, media, fonts, stylesheets) during browser rendering.

### Phase 5: Technical Discoverability Checks & Evidence Engine (`src/inspection/technical.py`)
Deterministic, rule-based technical checks that produce structured `TechnicalIssue` evidence items:

| Category | Issue Code | Severity | Description |
| :--- | :--- | :--- | :--- |
| **HTTP & Crawl** | `HTTP_ERROR` | `error` | Page returned 4xx or 5xx HTTP status code |
| | `SLOW_RESPONSE` | `warning` | Page response time exceeded threshold (> 2500ms) |
| | `REDIRECT_LOOP` | `error` | Redirect chain depth exceeded safety limit |
| | `DISALLOWED_BY_ROBOTS` | `info` | Page was skipped due to robots.txt disallow rule |
| | `MISSING_ROBOTS_TXT` | `info` | Target site does not provide a robots.txt file |
| | `MISSING_SITEMAP` | `info` | No valid XML sitemap was found on the site |
| **Metadata** | `MISSING_TITLE` | `error` | Page is missing a `<title>` tag |
| | `SHORT_TITLE` / `LONG_TITLE` | `warning` | Title tag length outside optimal range (< 10 or > 70 chars) |
| | `MISSING_DESCRIPTION` | `warning` | Meta description tag is missing |
| | `SHORT_DESCRIPTION` / `LONG_DESCRIPTION` | `warning` | Meta description length outside optimal range (< 50 or > 160 chars) |
| **Headings** | `MISSING_H1` | `warning` | Page lacks an `<h1>` heading tag |
| | `MULTIPLE_H1` | `warning` | Page defines multiple `<h1>` headings |
| | `SKIPPED_HEADING_LEVEL` | `warning` | Heading hierarchy skips levels (e.g. H1 directly to H3) |
| **Links & Indexing** | `NO_INTERNAL_LINKS` | `warning` | Page contains no internal navigation links |
| | `BROKEN_LINK` | `warning` | Page references a malformed URL |
| | `FRAGMENT_ONLY_LINK` | `info` | Page contains anchor links pointing only to `#` |
| | `NOINDEX_DIRECTIVE` | `info` | Page specifies `noindex` in robots meta or headers |
| | `MISSING_CANONICAL` | `info` | Page does not specify a canonical link |
| | `CANONICAL_MISMATCH` | `warning` | Canonical URL does not match actual page URL |
| **Rendering** | `SPA_DETECTED` | `info` | Page relies on client-side SPA framework |
| | `RENDERING_REQUIRED` | `warning` | Critical content is missing in static HTML source |
| | `CLIENT_RENDERED_CONTENT_DISCREPANCY` | `warning` | Significant text gap between raw source and rendered DOM |
| **Structured Data**| `MISSING_STRUCTURED_DATA`| `info` | Page contains no JSON-LD or schema structured data |
| | `INVALID_JSON_LD` | `error` | Page contains malformed JSON-LD script block |

### Phase 6: Unified Inspection Pipeline (`src/inspection/pipeline.py`)
- High-level orchestrator exposing `inspect_site(...)` and `InspectionPipeline`.
- Accepts configuration via `PipelineConfig` (page limits, depth limits, timeouts, rendering toggles).
- Resilient execution: Traps network failures, timeouts, and invalid targets, producing structured diagnostic models without raising unhandled exceptions.
- Produces quantitative summary counts (`inspected_pages`, `error_pages`, `disallowed_pages`, `total_issues`).

### Phase 7: Crawl & Render Audit Skill (`skills/crawl-render-audit/SKILL.md`)
- Conforms to Adobe Agent Marketplace skill specifications.
- Declares standard inputs (`url`, `max_pages`, `max_depth`, `timeout`, `same_site_only`, `respect_robots`, `discover_sitemaps`, `enable_rendering`).
- Provides clean Python and CLI integration examples for the master `audit-orchestrator`.

### Phase 8: Downstream Integration Contract & Test Validation (`src/inspection/models.py`, `tests/member1/`)
- Frozen data models with full Pydantic v2 support (`SiteInspection`, `PageInspection`, `RobotsTxtInspection`, `SitemapInspection`, `PageMetadata`, `Heading`, `Link`, `TechnicalIssue`).
- Output neutrality: Outputs raw evidence without baking in subjective scoring, downstream brand trust assumptions, or hardcoded recommendations.
- Verified test suite: **193 passed tests** across 13 dedicated test suites.

---

## Integration Contract Reference

Downstream consumers (Member 2 and Member 3) can reliably access:

```python
from src.inspection import SiteInspection, inspect_site

inspection: SiteInspection = inspect_site("https://example.com")

# Top-level site attributes
site_domain: str = inspection.site
root_url: str = inspection.root_url
audited_at = inspection.audited_at

# robots.txt findings
has_robots: bool = inspection.robots.found
is_allowed: bool = inspection.robots.allowed_for_agent
declared_sitemaps: list[str] = inspection.robots.sitemap_urls

# Sitemap findings
has_sitemap: bool = inspection.sitemap.found
sitemap_urls: list[str] = inspection.sitemap.sample_urls
total_urls: int = inspection.sitemap.total_discovered_urls

# Page-level observations
for page in inspection.pages:
    url: str = page.url
    status: int = page.status_code
    title: str = page.title
    meta_desc: str = page.metadata.description
    headings: list = page.headings          # list of Heading(level, text)
    body_text: str = page.body_text        # clean visible text
    links: list = page.links                # list of Link(url, text, is_internal)
    schemas: list = page.structured_data    # list of JSON-LD schema dicts
    is_rendered: bool = page.is_rendered    # Playwright JS rendered flag
    issues: list = page.technical_issues    # list of TechnicalIssue(code, message, severity, details)
```

---

## Test Suite Verification

Member 1 contains 193 automated tests validating all components:

```
tests/member1/test_url.py                    - URL normalization & SSRF boundaries
tests/member1/test_http.py                   - Safe read-only HTTP & body limits
tests/member1/test_robots.py                 - robots.txt parsing & path matching
tests/member1/test_sitemap.py                - XML sitemaps & gzip index traversal
tests/member1/test_crawler.py                - Bounded BFS crawling & domain limits
tests/member1/test_extraction.py             - HTML metadata, headings, text & JSON-LD
tests/member1/test_rendering.py              - SPA detection & Playwright rendering
tests/member1/test_technical.py              - Technical discoverability rules engine
tests/member1/test_models.py                 - Pydantic models serialization/validation
tests/member1/test_pipeline.py               - Unified InspectionPipeline orchestration
tests/member1/test_contract.py               - Schema immutability & neutrality
tests/member1/test_skill_contract.py         - SKILL.md interface and parameter fidelity
tests/member1/test_integration_contract.py   - Multi-page integration mock verification
--------------------------------------------------------------------------------------
Total: 193 passed tests
```
