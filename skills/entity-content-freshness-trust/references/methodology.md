# Entity, Content, Freshness & Trust: Methodology & Heuristics

This reference document outlines the engineering rationale and heuristic thresholds implemented in `skills/entity-content-freshness-trust` and `src/entity_trust/`.

---

## 1. Confidence Calibration & Thresholds

- **Confidence Threshold (`confidence_threshold = 0.70`):**
  - Implemented in `src/entity_trust/core/confidence.py` via `filter_and_rank_findings()`.
  - Suppresses weak or speculative pattern matches below 0.70 confidence to prevent false alarms on non-standard page designs.
  - High-confidence structural defects (e.g., Schema.org absence at `0.95`, copyright lag at `0.91`, contradictory facts at `0.85-0.90`) are retained and prioritized.

---

## 2. Entity Disambiguation & Identity Extraction

- **Multi-Surface Identity Discovery (`src/entity_trust/audits/entity_audit.py`):**
  - Synthesizes entity name from four prioritized surfaces in descending authority:
    1. Schema.org JSON-LD (`@type: "Organization"`, `"Corporation"`, etc.)
    2. OpenGraph / Twitter meta site name (`og:site_name`)
    3. Homepage title brand prefix (filtering `GENERIC_TITLES` such as 'home', 'welcome', 'index')
    4. Footer copyright declarations (regex extraction from `© YYYY [Company Name]`)
- **Core Value Proposition Disambiguation:**
  - Evaluates homepage title and primary `<h1>` against `GENERIC_H1S` (e.g., 'Welcome', 'Innovative Solutions').
  - Scans combined homepage and `/about` text for explicit entity definitions using regex patterns (`[Brand] is/provides/specializes in...`) and matches against `INDUSTRY_KEYWORDS` (e.g., SaaS, fintech, healthcare, education).
  - Flags `EC-002` only when both structured definition and recognizable industry classification are missing.

---

## 3. Fact Normalization & Contradiction Detection

- **Canonical Representation (`src/entity_trust/core/fact_normalizer.py`):**
  - **Prices:** Normalizes currencies via `CURRENCY_MAP` (`$`, `USD`, `€`, `EUR`, `₹`, `INR`, `GBP`, `CAD`, `AUD`) and converts amounts to canonical float comparisons (tolerance `< $0.01`).
  - **Founding Years:** Extracts 4-digit years (`19\d\d|20\d\d`) and compares numeric values directly.
  - **Geographic Locations:** Uses `LOCATION_SYNONYMS` ('sf' $\to$ 'san francisco', 'nyc' $\to$ 'new york city', 'bengaluru' $\to$ 'bangalore', 'new delhi' $\to$ 'delhi') and token intersection so subset mentions (e.g., "Delhi" vs. "New Delhi, India") do not trigger false contradiction alerts.
  - **Phone Numbers:** Strips all non-digit characters and uses suffix matching to treat local vs. international dialing formats as compatible.
- **Knowledge Graph Conflict Detection (`src/entity_trust/core/fact_graph.py`):**
  - Emits `CT-001` with `HIGH` severity only when two distinct pages on the same domain assert normalized facts of the same type that violate compatibility rules.

---

## 4. Freshness & Temporal Decay Logic

- **Reference Epoch (`CURRENT_YEAR = 2026`):**
  - Implemented in `src/entity_trust/audits/freshness_audit.py`.
- **Copyright Lag (`FR-001`):**
  - Lag $< 2$ years is considered within normal maintenance cycles.
  - Lag $\ge 2$ years is flagged as `MEDIUM` severity.
  - Lag $\ge 4$ years is escalated to `HIGH` severity as strong evidence of domain dormancy.
- **Announcement / News Currency (`FR-002`):**
  - Evaluates temporal currency only on pages identified as temporal feeds (`news`, `blog`, `press`, `events`, `announcements`, `updates`).
  - Evergreen pages (such as `/about`, `/contact`, `/pricing`, `/docs`) are strictly excluded from feed staleness checks to prevent false positives.
  - Flags staleness only if the newest dated entry in an active feed is $\ge 3$ years behind the reference year.

---

## 5. Content Clarity & Unstructured Facts

- **Facts Locked in Non-Text Elements (`CC-001`):**
  - Targeted image scanner (`IMAGE_FACT_INDICATORS`) searches image filenames, classes, and captions for statistical indicators (`stat`, `metric`, `infographic`, `revenue`, `growth`, `chart`, `figure`).
  - Emits a finding only if the image lacks alt text or uses generic placeholders (`alt="image"`, `alt="chart"`), preventing search engines and screen readers from accessing key data.
- **Unsubstantiated Superlative Claims (`CC-002`):**
  - Scans body text for superlative marketing assertions (`VAGUE_PATTERNS` such as 'world-class', 'industry-leading', 'cutting-edge') and checks for corresponding quantitative figures (`\d+%`, `\d+ users`, `\d+ years`).
  - Requires at least 2 distinct vague claims without supporting data before triggering a finding.
