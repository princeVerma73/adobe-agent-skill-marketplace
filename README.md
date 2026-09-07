# Adobe University Hackathon 2026 — Round 3

## Team ownership

**Member 1:** Crawl + rendering + technical discoverability — `src/inspection`, `src/crawler`, `src/rendering`, `src/extraction`

**Member 2:** Entity + content + freshness + trust — `skills/entity-content-freshness-trust`

**Member 3:** Engagement + recommendations + orchestration — `skills/engagement-recommendations`, `skills/audit-orchestrator`, `src/report`

**All:** integration, unseen-site testing, false-positive reduction, final packaging.

## Member 1 starting flow

`URL → validation → robots.txt → sitemap → bounded crawl → HTTP/HTML → rendering → text/headings/links/metadata/JSON-LD → normalized inspection data`

The implementation must remain read-only, respect robots.txt, avoid authenticated areas/rate abuse, and provide evidence that downstream skills can use.
