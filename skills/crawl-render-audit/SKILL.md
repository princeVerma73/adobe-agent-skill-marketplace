---
name: crawl-render-audit
description: Inspect and audit website crawlability, HTTP status, robots directives, XML sitemaps, static-vs-rendered JavaScript content, and technical discoverability evidence.
license: Apache-2.0
---

# Crawl & Render Audit Skill

## Purpose
The `crawl-render-audit` skill provides deterministic, evidence-based technical inspection of a target website. It systematically evaluates whether website content is reachable, machine-readable, and indexable by automated systems and AI agents without mutating site state.

## When to Use
Use this skill when:
- An orchestrator or downstream skill needs raw, structured inspection data and technical evidence for a domain.
- Auditing site technical health, robots.txt compliance, XML sitemaps, and HTTP status codes.
- Detecting client-side JavaScript rendering dependencies (SPA frameworks like React, Vue, Next.js, Nuxt) and content gaps between static source HTML and rendered DOM.
- Extracting clean metadata, heading hierarchy (H1–H6), visible body text, internal/external hyperlinks, and JSON-LD structured data.

## Safe and Read-Only Behavior
This skill enforces strict safety and non-destructive inspection boundaries:
- **GET-Only Navigation**: Operates strictly via read-only HTTP GET requests and browser page navigations.
- **No Mutations / Form Submissions**: Never fills forms, submits POST data, executes logins, or modifies remote state.
- **SSRF & Private Target Guard**: Validates URLs offline and blocks private IP addresses, loopback addresses (`localhost`, `127.0.0.1`, `[::1]`), link-local targets, and non-web schemes.
- **Bounded Resource Usage**: Respects configurable page counts (`max_pages`), crawl depths (`max_depth`), execution timeouts, and aborts unnecessary heavy media assets (images, media, fonts) during browser rendering.
- **Robots.txt Adherence**: Respects crawl directives and disallowed paths.

## Inputs
| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `url` | `str` | *(required)* | Target root URL or bare domain (e.g. `"https://example.com"` or `"example.com"`). |
| `max_pages` | `int` | `10` | Maximum number of pages to crawl during bounded BFS traversal. |
| `max_depth` | `int` | `2` | Maximum link depth level from root page. |
| `timeout` | `float` | `10.0` | Timeout in seconds for HTTP and browser requests. |
| `same_site_only` | `bool` | `True` | Confine crawl to the same registrable domain and subdomains. |
| `respect_robots` | `bool` | `True` | Respect robots.txt allow/disallow directives. |
| `discover_sitemaps` | `bool` | `True` | Automatically discover and parse XML sitemaps. |
| `enable_rendering` | `bool` | `True` | Selectively render dynamic/SPA pages with Playwright when static HTML is insufficient. |

## Outputs
Returns a unified `SiteInspection` object containing:
- **`site`**: Target domain hostname.
- **`root_url`**: Normalized canonical starting URL.
- **`robots`**: `RobotsTxtInspection` including existence, status code, directives, crawl-delay, and declared sitemaps.
- **`sitemap`**: `SitemapInspection` including discovered sitemaps, total URL counts, and sample URLs.
- **`pages`**: List of `PageInspection` records with:
  - URL, status code, response time, and redirect chain.
  - Extracted title, meta description, canonical URL, robots meta, OpenGraph, and Twitter tags.
  - Ordered headings hierarchy (`List[Heading]`).
  - Visible body text and extracted hyperlinks (`List[Link]`).
  - Parsed JSON-LD structured data schemas (`List[Dict[str, Any]]`).
  - Rendering flags: `is_rendered`, `source_text`, and `rendered_text`.
  - Machine-readable evidence: `technical_issues` (`List[TechnicalIssue]`).
- **`summary_counts`**: Summary counters for inspected pages, errors, disallowed pages, and technical issues.

## Usage and Pipeline Integration
Invoke the inspection pipeline using the built-in `inspect_site` function:

```python
from src.inspection import inspect_site

# Run full inspection pipeline
site_inspection = inspect_site(
    url="https://example.com",
    max_pages=10,
    max_depth=2,
    discover_sitemaps=True,
    enable_rendering=True,
)

# Access structured evidence
for page in site_inspection.pages:
    print(f"Page: {page.url} (Status: {page.status_code})")
    print(f"Title: {page.title}")
    print(f"Is Rendered: {page.is_rendered}")
    for issue in page.technical_issues:
        print(f"  - [{issue.severity.upper()}] {issue.code}: {issue.message}")
```
