# Content Clarity & Consistency Reference Rules

## Problem Statement
AI reasoning engines can only ground answers in plain, readable, crawlable text. When crucial operational facts are locked inside raster images, or when pages provide contradicting numbers, AI systems produce hallucinations or lose confidence in the brand.

## Detection Rules
- **CC-001 (Facts in Non-Text Images)**: Informational infographics, metric blocks, or certificates stored as images without equivalent crawlable text or descriptive `alt` attributes.
- **CC-002 (Vague Marketing Superlatives)**: Superlative buzzwords ("world-class", "industry-leading", "seamless") devoid of concrete numbers, certifications, or technical specifics.
- **CC-003 (Missing Essential Attributes)**: Absence of verifiable headquarters location or direct contact mechanisms.
- **CO-001+ (Cross-Page Fact Discrepancies)**: Normalized contradictions across pages (e.g. founding year differs between Homepage and About page; prices differ between Pricing and Features).

## Normalization Heuristics
- Currency: `"$999"`, `"999 USD"`, `"₹999"`, `"INR 999"` -> Normalized canonical value.
- Locations: Geographic tokens cross-checked for city/state/country containment.
- Founding Year: 4-digit temporal regex matching within corporate history phrases.
