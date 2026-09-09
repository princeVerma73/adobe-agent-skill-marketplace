# Adobe University Hackathon 2026 — Round 3

## Team Ownership & Architecture

- **Member 1 (Completed):** Crawl + Rendering + Technical Discoverability — `src/inspection`, `src/crawler`, `src/rendering`, `src/extraction`, `skills/crawl-render-audit`
- **Member 2 (Pending/In Progress):** Entity + Content + Freshness + Trust — `skills/entity-content-freshness-trust`
- **Member 3 (Pending/In Progress):** Engagement + Recommendations + Orchestration — `skills/engagement-recommendations`, `skills/audit-orchestrator`, `src/report`
- **All:** Integration, unseen-site testing, false-positive reduction, final packaging.

---

## Member 1 Completed Work (Phases 1–8)

Member 1 delivers the read-only inspection foundation for the audit marketplace. It converts any target URL into structured, evidence-backed inspection models without modifying remote site state.

### Completed Phases & Subsystems

1. **Phase 1 — URL Validation & SSRF Boundary (`src/inspection/url.py`):**
   - Protocol whitelist (`http://`, `https://` only; rejects non-web schemes).
   - Hostname canonicalization, port stripping, and punycode/IDN support.
   - Comprehensive SSRF security boundary blocking loopback (`127.0.0.0/8`, `::1`), private RFC 1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local / AWS metadata (`169.254.0.0/16`), and unsafe targets via offline and DNS resolution guards.

2. **Phase 2 — Safe HTTP & robots.txt Parser (`src/crawler/http.py`, `src/crawler/robots.py`):**
   - Safe HTTP client restricted strictly to read-only `GET` and `HEAD` requests.
   - Configurable timeouts, redirect depth limits (max 5), and 5 MB maximum body size guard.
   - RFC 9309 compliant `robots.txt` parser supporting User-Agent matching (exact & `*` fallback), `Allow`/`Disallow` path evaluation with longest-match precedence, `Crawl-delay`, and `Sitemap:` extraction.

3. **Phase 3 — XML Sitemap Discovery & Bounded BFS Crawler (`src/crawler/sitemap.py`, `src/crawler/crawler.py`):**
   - Recursive XML sitemap index and urlset parsing, gzip decompression (`.xml.gz`), and regex fallback for non-standard XML.
   - Bounded breadth-first search (BFS) crawler with configurable `max_pages` (default 10) and `max_depth` (default 2).
   - Strict same-domain / registrable domain boundary isolation and continuous robots.txt adherence.

4. **Phase 4 — HTML Extraction & Selective Playwright Rendering (`src/extraction/extract.py`, `src/rendering/render.py`):**
   - Clean extraction of page metadata (title, meta description, canonical URL, robots meta, OpenGraph, Twitter Cards).
   - Structured heading hierarchy (`H1`–`H6`), noise-stripped visible body text, internal/external hyperlinks, and JSON-LD structured data schemas.
   - Selective Playwright headless browser rendering triggered by SPA framework detection (React, Vue, Angular, Next.js, Nuxt, Svelte) and static-to-rendered text discrepancy thresholds, with resource aborts (images, media, fonts) for performance and safety.

5. **Phase 5 — Technical Discoverability Checks (`src/inspection/technical.py`):**
   - Deterministic rule engine emitting structured `TechnicalIssue(code, message, severity, details)` for HTTP errors, redirect chains, crawl blocks, missing/duplicate titles & descriptions, heading hierarchy violations, broken links, noindex flags, missing canonicals, SPA/rendering gaps, and malformed JSON-LD schemas.

6. **Phase 6 — Unified Inspection Pipeline (`src/inspection/pipeline.py`):**
   - Single top-level interface `inspect_site(...)` orchestrating URL validation, robots inspection, sitemap discovery, bounded crawling, selective rendering, extraction, and technical rule evaluation into a normalized `SiteInspection` object.
   - Graceful error isolation ensuring network and parsing failures produce structured evidence without crashing.

7. **Phase 7 — Crawl & Render Audit Skill (`skills/crawl-render-audit/SKILL.md`):**
   - Skill packaging following Adobe Agent Marketplace conventions with validated inputs, outputs, and execution examples.

8. **Phase 8 — Downstream Integration Contract & Test Validation (`src/inspection/models.py`, `tests/member1/`):**
   - Frozen, neutral Pydantic data contract guaranteeing shared schemas for Member 2 and Member 3.
   - Comprehensive test suite with **193 passed tests** across 13 test suites.

---

## Member 1 Data Contract

Downstream skills (Member 2 and Member 3) consume the normalized `SiteInspection` output model:

```
URL → inspect_site() → SiteInspection
                         ├── site: str
                         ├── root_url: str
                         ├── robots: RobotsTxtInspection
                         ├── sitemap: SitemapInspection
                         ├── pages: List[PageInspection]
                         │     ├── url, status_code, response_time_ms
                         │     ├── title, metadata (OG, Twitter, canonical, robots_meta)
                         │     ├── headings: List[Heading] (level, text)
                         │     ├── body_text, source_text, rendered_text
                         │     ├── links: List[Link] (url, text, is_internal)
                         │     ├── structured_data: List[Dict] (JSON-LD)
                         │     └── technical_issues: List[TechnicalIssue]
                         └── summary_counts: Dict[str, int]
```

---

## Member 1 Test Suite Status

Member 1 includes 13 test modules covering unit, property, and integration contract scenarios:

| Test Module | Coverage Area | Status |
| :--- | :--- | :--- |
| `tests/member1/test_url.py` | URL normalization, scheme validation, SSRF boundary guards | Passed |
| `tests/member1/test_http.py` | Safe read-only HTTP client, timeouts, redirects, body size limits | Passed |
| `tests/member1/test_robots.py` | robots.txt parsing, user-agent rules, crawl-delay, sitemaps | Passed |
| `tests/member1/test_sitemap.py` | XML sitemaps, sitemap indexes, gzip decompression, malformed XML | Passed |
| `tests/member1/test_crawler.py` | Bounded BFS crawling, depth/page limits, domain confinement | Passed |
| `tests/member1/test_extraction.py` | Metadata, headings, body text, links, JSON-LD structured data | Passed |
| `tests/member1/test_rendering.py` | SPA detection, Playwright rendering, asset blocking, text diffs | Passed |
| `tests/member1/test_technical.py` | Technical discoverability rules, SEO & accessibility checks | Passed |
| `tests/member1/test_models.py` | Pydantic data models, JSON serialization & deserialization | Passed |
| `tests/member1/test_pipeline.py` | End-to-end `InspectionPipeline` orchestration & error handling | Passed |
| `tests/member1/test_contract.py` | Output schema neutrality & contract immutability | Passed |
| `tests/member1/test_skill_contract.py` | `crawl-render-audit` skill documentation & parameter alignment | Passed |
| `tests/member1/test_integration_contract.py` | Comprehensive multi-page mock integration & contract verification | Passed |
| **Total Test Suite** | **13 modules** | **193 passed** |

---

## Quickstart (Member 1 Inspection)

```python
from src.inspection import inspect_site

# Run inspection pipeline
result = inspect_site(
    url="https://example.com",
    max_pages=10,
    max_depth=2,
    discover_sitemaps=True,
    enable_rendering=True,
)

print(f"Site: {result.site}")
print(f"Pages crawled: {len(result.pages)}")
print(f"Discovered sitemaps: {result.sitemap.total_discovered_urls} URLs")
for page in result.pages:
    print(f"- {page.url} ({page.status_code}) -> {len(page.technical_issues)} issues")
```

