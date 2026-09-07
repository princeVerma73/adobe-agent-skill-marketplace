# MEMBER 1 — INSPECTION LAYER

Your primary workspace.

Goal: convert a URL into normalized, read-only inspection data for the audit skills.

Suggested modules:
- `models.py` — shared data contract
- `url.py` — URL validation/normalization
- `robots.py` — robots.txt
- `sitemap.py` — sitemap discovery/parsing
- `http.py` — safe fetching
- `crawl.py` — bounded same-site crawl
- `render.py` — optional JS rendering
- `extract.py` — text/headings/links/metadata/JSON-LD

Start here first. Agree on the data contract with Members 2 and 3 before freezing it.
