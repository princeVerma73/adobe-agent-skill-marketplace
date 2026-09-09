# Member 1 — Inspection Layer (`src/inspection`)

The inspection layer provides the foundational crawling, rendering, extraction, and technical analysis pipeline for the brand audit marketplace.

## Module Structure

- **`models.py`**: Shared Pydantic data contract models (`SiteInspection`, `PageInspection`, `RobotsTxtInspection`, `SitemapInspection`, `PageMetadata`, `Heading`, `Link`, `TechnicalIssue`).
- **`url.py`**: Protocol validation, URL normalization, and SSRF security boundary protection.
- **`robots.py`**: RFC 9309 robots.txt parser with path matching, user-agent precedence, and directive extraction.
- **`technical.py`**: Deterministic technical discoverability rule engine evaluating SEO, rendering gaps, status codes, headings, links, and structured data.
- **`pipeline.py`**: Unified `InspectionPipeline` and top-level `inspect_site(...)` entrypoint orchestrating all inspection stages.

## Supporting Packages

- **`src/crawler`**: Safe read-only HTTP client (`http.py`), recursive XML sitemap parser (`sitemap.py`), and bounded BFS crawler (`crawler.py`).
- **`src/extraction`**: Noise-stripped HTML, heading hierarchy, metadata, link, and JSON-LD extractor (`extract.py`).
- **`src/rendering`**: Headless Playwright renderer with SPA detection and selective browser rendering (`render.py`).

## Quick Usage

```python
from src.inspection import inspect_site, SiteInspection

# Inspect a website
inspection: SiteInspection = inspect_site(
    url="https://example.com",
    max_pages=10,
    max_depth=2,
    discover_sitemaps=True,
    enable_rendering=True,
)
```

