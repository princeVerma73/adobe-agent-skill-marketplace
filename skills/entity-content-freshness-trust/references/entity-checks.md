# Entity Verification Reference Rules

## Problem Statement
AI agents and knowledge graphs fail to index or ground organizations when:
1. Brand names are ambiguous or generic (e.g., "Welcome to us", "ABC Solutions").
2. No explicit sentence exists defining what the entity is, its industry, and who it serves.
3. Schema.org structured metadata (`Organization`, `Corporation`, `LocalBusiness`) is missing.

## Detection Criteria
- **EC-001 (Brand Identity Obscured)**: Homepage `<title>` or `<h1>` uses non-descriptive filler ("Home", "Welcome", "Default").
- **EC-002 (Insufficient Disambiguation)**: Lack of clear sentence pattern declaring company type, industry category, or target market.
- **EC-003 (Missing Schema.org Organization)**: No valid JSON-LD metadata providing grounded `@type: Organization` attributes.

## Remediation Guidelines
- Include a high-impact H1 combining brand name and core category: e.g. `Acme Corp | Enterprise Cloud Security`.
- Add a 1-sentence plain text summary in `<meta name="description">` and first paragraph of homepage: `"[Brand] is a [country/type] [industry] company providing [products/services] to [target audience]."`.
- Deploy JSON-LD Organization schema containing `@id`, `name`, `url`, `logo`, `sameAs`, and `description`.
