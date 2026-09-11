# Engagement & Recommendations: Methodology & Heuristics

This reference document outlines the engineering rationale and heuristic thresholds implemented in `skills/engagement-recommendations` and `src/engagement/`, `src/recommendations/`.

---

## 1. Homepage Orientation & Value Proposition

- **Brand Orientation (`src/engagement/rules/orientation.py`):**
  - **`ENG-001` (Brand Clarity):** Evaluates homepage `<title>` and main `<h1>` against `GENERIC_TITLES` and `GENERIC_H1S`. Requires the main heading to be substantive ($\ge 2$ words) and explicit.
  - **`ENG-002` (Value Proposition):** Scans introductory paragraphs for concise value statements ($\ge 15$ words) explaining core capabilities, avoiding immediate landing bounce.

---

## 2. Navigation, Anchors & Heading Hierarchies

- **Descriptive Hyperlink Anchors (`src/engagement/rules/navigation.py`):**
  - **`ENG-003` (Vague Anchors):** Identifies generic anchor texts (`click here`, `read more`, `learn more`, `here`, or empty anchors `[Empty Anchor]`) on interactive links. Empty links or unlabeled icons in navigation menus impair screen readers and search crawler graph construction.
  - **`ENG-004` (Primary Navigation):** Verifies that the homepage includes navigation links pointing to discovered subpage sections.
- **Structural Heading Hierarchy (`src/engagement/rules/hierarchy.py`):**
  - **`ENG-005` (Heading Skips):** Detects structural level jumps in heading trees (e.g. `<h1>` followed directly by `<h3>` or `<h4>` without an intervening `<h2>`).
  - **`ENG-006` (Multiple H1s):** Detects multiple `<h1>` declarations on a single document. Deduplicated downstream with `TECH-MULTIPLE_H1` to avoid redundant penalties.
  - **`ENG-007` (Content Scannability):** Flags text-dense content blocks ($\ge 400$ words) that lack intermediate `<h2>` or `<h3>` subheadings for visual chunking.

---

## 3. Conversions, Contact Paths & Call-to-Action

- **Call-to-Action Detection (`src/engagement/rules/cta.py`):**
  - **`ENG-008` (Homepage CTA):** Matches links and buttons against conversion action patterns (`get started`, `sign up`, `try free`, `book demo`, `request demo`, `contact sales`, `download`, `buy now`). Ensures prospective users have an identifiable conversion path.
- **Support & Contact Discovery (`src/engagement/rules/contact.py`):**
  - **`ENG-012` (Contact Pathway):** Inspects all crawled pages for links matching contact patterns (`/contact`, `/support`, `/help`, `/feedback`) or visible email/telephone identifiers.

---

## 4. Graph Linking & Context Retention

- **Internal Link Graph Analysis (`src/engagement/rules/linking.py`):**
  - **`ENG-009` (Orphaned Internal Pages):** Employs an internal link graph across crawled URLs. Flags pages with 0 incoming internal links from other audited pages on the domain.
  - **`ENG-010` (High In-Degree Linking):** Recognizes hub pages with $\ge 4$ incoming links to prioritize crawling depth.
  - **`ENG-014` (Dead-End Pages):** Flags pages with 0 outgoing internal links. Legitimate terminal pages (e.g. thank you, confirmation, or legal/privacy pages) are accounted for to prevent false alarms.
- **Context Retention on Direct Landing (`src/engagement/rules/context_retention.py`):**
  - **`ENG-015` (Deep Landing Context Loss):** Verifies that visitors landing directly on secondary/deep subpages from search engines or AI direct references can return to the root brand portal via root links, breadcrumbs, `rel="home"`, or logo/brand keywords in anchor tags.

---

## 5. Recommendation Synthesis & Prioritization

- **Deterministic Remediation Mapping (`src/recommendations/engine.py`):**
  - Transforms validated findings into structured `ActionableRecommendation` objects containing:
    - Diagnostic summary (`what_is_wrong`)
    - Prescriptive technical fix (`what_should_be_changed`)
    - Business impact justification (`why_it_matters`)
    - Concrete validation steps (`verification_steps`)
  - Prioritizes high-severity accessibility, entity ambiguity, and conversion blockers before informational optimization items.
