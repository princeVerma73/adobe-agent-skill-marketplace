# Freshness & Temporal Verification Reference

## Problem Statement
AI engines (such as Perplexity, ChatGPT Search, Gemini) place heavy weights on publication timestamps and recent updates. Websites with unmaintained dates or legacy announcements presented as active updates risk being classified as stale or untrustworthy.

## Detection Rules
- **FR-001 (Copyright Lag)**: Latest footer copyright is 2 or more years behind the current calendar year.
- **FR-002 (Stale News / Announcement Feed)**: The latest publication date in the company press / news / blog feed is older than 3 years while displayed as current.

## Remediation Guidelines
- Automate copyright date rendering via server-side templates or build scripts.
- Explicitly mark legacy archive pages with metadata (`<meta name="robots" content="noindex">` or an explicit archive disclaimer).
- Keep primary product pricing and feature logs updated with current publication dates.
