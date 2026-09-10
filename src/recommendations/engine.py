"""Recommendation Engine for transforming audit findings into actionable remediation guidance.

Generates structured, non-generic recommendations with diagnostic cause,
prescriptive solution, impact justification, and verifiable test steps.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from src.entity_trust.contracts.schemas import SeverityLevel
from src.recommendations.models import ActionableRecommendation


# Canonical knowledge base for specific finding types
RECOMMENDATION_TEMPLATES: Dict[str, Dict[str, str]] = {
    # Member 3: Engagement
    "ENG-001": {
        "title": "Clarify Homepage Brand Identity and Core Purpose",
        "what_is_wrong": "The homepage uses generic or missing <title> and <h1> orientation tags, preventing visitors and AI agents from understanding the brand's core mission.",
        "what_should_be_changed": "Rewrite the homepage <title> tag to format '[Brand Name] - [Primary Offering]' and provide a descriptive primary <h1> heading summarizing the main value proposition.",
        "why_it_matters": "When AI agents (Perplexity, SearchGPT, Gemini) inspect a domain, the homepage <title> and <h1> provide primary anchor facts. Non-descriptive titles cause AI hallucination or classification failure.",
        "verification_steps": "Re-run the engagement audit and verify that the homepage <title> and <h1> contain brand and value proposition keywords, and ENG-001 is resolved.",
    },
    "ENG-001-TITLE": {
        "title": "Provide Informative Homepage Title Tag",
        "what_is_wrong": "The homepage <title> tag is generic or missing, providing no brand or service context in browser tabs and search engine result snippets.",
        "what_should_be_changed": "Update <title> with the official company or organization name followed by the primary solution category (under 60 characters).",
        "why_it_matters": "Search engines and AI indexing spiders prioritize <title> content for entity grounding.",
        "verification_steps": "Inspect the HTML head of the homepage and confirm <title> contains brand identity and primary offering.",
    },
    "ENG-002": {
        "title": "Add Concise Value Proposition to Homepage",
        "what_is_wrong": "The homepage introductory body text is too brief to communicate the organization's products, target audience, or primary use cases.",
        "what_should_be_changed": "Add 2-3 clear introductory sentences above the fold explaining what the product or organization does, who it serves, and key capabilities.",
        "why_it_matters": "AI answer engines synthesize introductory website text to generate company overviews.",
        "verification_steps": "Re-run the engagement audit and confirm that the homepage introductory text exceeds minimum orientation thresholds.",
    },
    "ENG-003": {
        "title": "Replace Vague Anchor Text with Descriptive Links",
        "what_is_wrong": "Navigation hyperlinks use non-descriptive anchor texts such as 'click here', 'read more', or empty text.",
        "what_should_be_changed": "Replace vague phrases with destination-specific text (e.g. change 'Click Here' to 'Explore Enterprise Security Features').",
        "why_it_matters": "Descriptive anchor text provides semantic context to search crawlers and screen readers regarding the destination page content.",
        "verification_steps": "Re-run the navigation check and verify that all hyperlinks contain descriptive destination-specific anchor text.",
    },
    "ENG-004": {
        "title": "Implement Primary Navigation Linking to Core Sections",
        "what_is_wrong": "The homepage lacks a primary navigation bar or menu linking to core subpages discovered on the domain.",
        "what_should_be_changed": "Add a standard global navigation header on the homepage with direct links to main sections (e.g., About, Solutions, Pricing, Contact).",
        "why_it_matters": "Visitors and search crawlers landing on the root domain need predictable discovery pathways to navigate the site architecture.",
        "verification_steps": "Re-run the engagement audit to ensure the homepage contains links to core subpages and ENG-004 is cleared.",
    },
    "ENG-005": {
        "title": "Repair Broken Heading Hierarchy",
        "what_is_wrong": "Headings skip intermediate structural levels (e.g., jumping from <h1> directly to <h3> or <h4> without an intervening <h2>).",
        "what_should_be_changed": "Renumber headings sequentially: <h1> for page title, <h2> for major sections, and <h3> for nested subsections.",
        "why_it_matters": "Screen readers and automated document summarizers rely on logical heading tree hierarchies to map document structure.",
        "verification_steps": "Re-run the engagement audit and verify that no heading level skips are detected in the document outline.",
    },
    "ENG-006": {
        "title": "Consolidate Multiple H1 Headings into a Single Page Heading",
        "what_is_wrong": "Multiple <h1> tags exist on the same page, diluting primary topic focus.",
        "what_should_be_changed": "Retain one primary <h1> representing the page title and convert secondary section titles to <h2>.",
        "why_it_matters": "Search bots use a single primary <h1> to identify the dominant topic of the page.",
        "verification_steps": "Inspect the page HTML and confirm only one top-level <h1> exists per page.",
    },
    "ENG-007": {
        "title": "Introduce Subheadings into Dense Content Sections",
        "what_is_wrong": "The page contains long text blocks without <h2> or <h3> subheadings, creating an un-scannable reading experience.",
        "what_should_be_changed": "Break long text into thematic subsections of 100-200 words introduced by descriptive <h2>/<h3> subheadings.",
        "why_it_matters": "Subheadings enable fast human skimming and help AI document chunkers partition text into discrete semantic blocks.",
        "verification_steps": "Re-run the hierarchy audit and ensure long content pages have adequate subheading density.",
    },
    "ENG-008": {
        "title": "Add Clear Primary Call-to-Action to Homepage",
        "what_is_wrong": "The homepage does not present a prominent primary call-to-action (CTA) button or next-step link.",
        "what_should_be_changed": "Place an identifiable primary action button (e.g. 'Get Started', 'Start Free Trial', 'Book Demo') in the hero section.",
        "why_it_matters": "Without an obvious next action, prospective customers drop off and autonomous purchasing agents cannot navigate conversion funnels.",
        "verification_steps": "Re-run the engagement audit and confirm that a prominent CTA link is detected on the homepage.",
    },
    "ENG-009": {
        "title": "Integrate Orphaned Page into Site Navigation",
        "what_is_wrong": "An internal page has zero incoming links from any other inspected page on the website.",
        "what_should_be_changed": "Add contextual internal links pointing to this page from relevant category overview pages, header navigation, or related articles.",
        "why_it_matters": "Orphaned pages receive zero PageRank equity and risk being dropped from search indices due to lack of internal link discovery.",
        "verification_steps": "Re-run the internal linking audit and verify that the page receives at least 1-2 incoming internal links.",
    },
    "ENG-011": {
        "title": "Add Continuation Links to Content Pages",
        "what_is_wrong": "A substantive informational page concludes without onward links to related topics, documentation, or next steps.",
        "what_should_be_changed": "Add a 'Related Resources', 'Next Steps', or 'Recommended Articles' section at the end of the page.",
        "why_it_matters": "Continuation links prevent user drop-off and guide AI exploration agents through multi-step research journeys.",
        "verification_steps": "Re-run the engagement audit and ensure the content page provides onward internal navigation paths.",
    },
    "ENG-012": {
        "title": "Publish Identifiable Contact and Support Channels",
        "what_is_wrong": "No contact page, customer support pathway, email address, or phone number was found across inspected pages.",
        "what_should_be_changed": "Create a dedicated /contact or /support page with a verified email address, contact form, or customer helpline linked in header/footer.",
        "why_it_matters": "AI trust frameworks and consumer protection algorithms heavily penalize anonymous commercial websites lacking verifiable contact data.",
        "verification_steps": "Re-run the engagement audit and verify that contact links or email channels are discovered.",
    },
    "ENG-013": {
        "title": "Provide Actionable Next Steps on Commercial and Pricing Pages",
        "what_is_wrong": "A pricing or solutions page details offerings but lacks actionable signup, checkout, or inquiry links.",
        "what_should_be_changed": "Add explicit action buttons (e.g. 'Choose Plan', 'Get Started', 'Contact Sales') underneath each tier or offering.",
        "why_it_matters": "Conversion funnels are broken if prospects cannot transition from evaluation to transaction.",
        "verification_steps": "Re-run the conversion audit and confirm that actionable signup/purchase links are present.",
    },
    "ENG-014": {
        "title": "Eliminate Dead-End Page by Adding Navigation",
        "what_is_wrong": "The page has zero outgoing internal links, permanently halting user and crawler journeys.",
        "what_should_be_changed": "Include standard global navigation headers, footer links, or a 'Return to Home' button on this page.",
        "why_it_matters": "Dead ends waste crawl budget and trap users, forcing them to use the browser back button or abandon the site.",
        "verification_steps": "Re-run the dead-end check and confirm that the page provides outgoing internal navigation.",
    },
    "ENG-015": {
        "title": "Add Homepage Breadcrumbs to Deep Landing Pages",
        "what_is_wrong": "A deep subpage does not provide a navigation link back to the root homepage.",
        "what_should_be_changed": "Add breadcrumb navigation (e.g., 'Home > Category > Page') and ensure the site logo links directly to the root homepage.",
        "why_it_matters": "Users arriving directly from search engines need instant orientation and a path back to the parent brand portal.",
        "verification_steps": "Re-run the context retention audit and confirm that deep pages link back to the homepage.",
    },
    "ENG-016": {
        "title": "Add Topic Heading to Direct Landing Page",
        "what_is_wrong": "The direct landing page lacks an <h1> heading to introduce the page topic.",
        "what_should_be_changed": "Add an explicit <h1> heading at the top of the body content describing the page subject.",
        "why_it_matters": "An <h1> heading is essential for human scannability and automated content extraction.",
        "verification_steps": "Inspect the page and confirm an <h1> heading is present.",
    },

    # Member 2: Entity & Trust
    "EC-001": {
        "title": "Disambiguate Brand Identity in Homepage Title and H1",
        "what_is_wrong": "Generic title and heading elements conceal the true organization name.",
        "what_should_be_changed": "Replace generic titles like 'Welcome' or 'Home' with official brand name and primary business description.",
        "why_it_matters": "AI knowledge engines cannot disambiguate the entity without explicit brand identity markers.",
        "verification_steps": "Re-run the entity audit and confirm the brand name is successfully identified in the Entity Profile.",
    },
    "EC-002": {
        "title": "Provide Explicit Organization Description and Industry Classification",
        "what_is_wrong": "The website lacks clear business description text or industry disambiguation keywords.",
        "what_should_be_changed": "Add descriptive copy explicitly naming the company, industry sector, and core capabilities in the about section and homepage.",
        "why_it_matters": "Disambiguation is necessary for inclusion in AI knowledge graphs like Wikidata, Google Knowledge Graph, and Perplexity.",
        "verification_steps": "Re-run the entity audit and confirm industry and description are detected with high confidence.",
    },
    "EC-003": {
        "title": "Add Schema.org Organization Structured Data Markup",
        "what_is_wrong": "The site does not publish Schema.org Organization or LocalBusiness JSON-LD markup.",
        "what_should_be_changed": "Embed a JSON-LD script on the homepage with '@type': 'Organization', 'name', 'url', 'logo', and contact points.",
        "why_it_matters": "Structured data is the primary machine-readable format used by search crawlers to construct verified knowledge panels.",
        "verification_steps": "Validate the homepage with Google's Rich Results Test or re-run the entity audit.",
    },
    "CC-001": {
        "title": "Provide Text Equivalents for Critical Data in Images",
        "what_is_wrong": "Important metrics, certifications, or partnership facts are trapped inside images without descriptive alt text.",
        "what_should_be_changed": "Add descriptive alt attributes to image tags or present the underlying numerical data and credentials directly in HTML text.",
        "why_it_matters": "Text-only AI crawlers cannot parse pixel images, causing key credibility claims to be completely ignored.",
        "verification_steps": "Re-run the content clarity audit and verify CC-001 is resolved.",
    },
    "CC-002": {
        "title": "Substantiate Superlative Claims with Concrete Evidence",
        "what_is_wrong": "Unsubstantiated superlative buzzwords ('world-class', 'industry-leading') are used without supporting citations.",
        "what_should_be_changed": "Qualify superlative assertions with concrete statistics, awards, third-party benchmarks, or accredited certifications.",
        "why_it_matters": "AI fact-checkers down-weight websites that use unverified marketing puffery.",
        "verification_steps": "Re-run the clarity audit and ensure all major claims include verifiable metrics.",
    },
    "FR-001": {
        "title": "Update Stale Copyright Year",
        "what_is_wrong": "The footer copyright year is more than two years out of date, suggesting abandoned or neglected site maintenance.",
        "what_should_be_changed": "Update the copyright notice to the current year (or dynamic server-side timestamp).",
        "why_it_matters": "Search engine freshness algorithms penalize domains showing multi-year maintenance stagnation.",
        "verification_steps": "Re-run the freshness audit and confirm current copyright year is detected.",
    },
    "FR-002": {
        "title": "Archive or Update Stale Announcements",
        "what_is_wrong": "Old announcements or news items from past years are displayed on active landing pages as current updates.",
        "what_should_be_changed": "Move historical announcements into a dated /archive section and feature current developments on active pages.",
        "why_it_matters": "Displaying obsolete dates as current destroys brand credibility in AI summary generation.",
        "verification_steps": "Re-run the freshness audit and verify outdated news banners have been archived.",
    },
    "CO-001": {
        "title": "Resolve Cross-Page Factual Contradictions",
        "what_is_wrong": "Conflicting data points (such as founding dates, pricing, or locations) appear on different pages of the domain.",
        "what_should_be_changed": "Audit all pages and unify contradictory facts across the site into a single authoritative source of truth.",
        "why_it_matters": "Factual contradictions directly trigger AI hallucinations and cause AI search engines to flag the source as untrustworthy.",
        "verification_steps": "Re-run the consistency audit to confirm zero cross-page fact conflicts in the knowledge graph.",
    },

    # Member 1: Technical Discoverability
    "HTTP_NOT_FOUND": {
        "title": "Fix Broken Links and 404 Errors",
        "what_is_wrong": "A crawled URL returned an HTTP 404 Not Found response.",
        "what_should_be_changed": "Fix the broken source link or implement a 301 redirect from the 404 URL to the relevant active page.",
        "why_it_matters": "Broken links frustrate visitors and waste search crawler crawl budget.",
        "verification_steps": "Send an HTTP GET request to the target URL and verify it returns HTTP 200.",
    },
    "HTTP_SERVER_ERROR": {
        "title": "Resolve Internal Server Errors (HTTP 5xx)",
        "what_is_wrong": "The web server returned an HTTP 500/502/503 error during page fetch.",
        "what_should_be_changed": "Inspect backend server logs, database connections, and application runtime errors to resolve crashes.",
        "why_it_matters": "5xx errors lead to immediate de-indexing of affected URLs by search engines.",
        "verification_steps": "Request the affected URL and verify consistent HTTP 200 responses under load.",
    },
    "ROBOTS_TXT_DISALLOWED": {
        "title": "Review Robots.txt Blocking Directives",
        "what_is_wrong": "Important brand pages are disallowed from crawling by robots.txt rules.",
        "what_should_be_changed": "Update robots.txt to remove Disallow rules on public landing and product pages.",
        "why_it_matters": "Disallowed pages cannot be inspected, indexed, or cited by AI search agents.",
        "verification_steps": "Re-run the inspection pipeline and verify robots.allowed_for_agent is True.",
    },
    "CONTENT_GAP": {
        "title": "Address Client-Side Rendering Dependency Gap",
        "what_is_wrong": "Significant textual content is absent from static source HTML and only visible after executing client-side JavaScript.",
        "what_should_be_changed": "Implement Server-Side Rendering (SSR) or Static Site Generation (SSG) so critical content is present in raw HTML.",
        "why_it_matters": "Many lightweight AI crawlers do not execute JavaScript; content trapped in client SPAs remains invisible to them.",
        "verification_steps": "Fetch the raw HTML with curl or inspect static source to verify text is present without JS execution.",
    },
}


class RecommendationEngine:
    """Engine that translates findings into structured, actionable remediation recommendations."""

    @staticmethod
    def generate_recommendation(finding: Any) -> ActionableRecommendation:
        """Converts a finding (EngagementFinding, Finding, or ReportFinding) into an ActionableRecommendation."""
        fid = getattr(finding, "id", "")
        category = getattr(finding, "category", "general")
        if hasattr(category, "value"):
            category = category.value
        title = getattr(finding, "title", "Audit Finding")
        severity = getattr(finding, "severity", SeverityLevel.MEDIUM)
        if isinstance(severity, str):
            try:
                severity = SeverityLevel(severity.lower())
            except ValueError:
                severity = SeverityLevel.MEDIUM
        evidence = getattr(finding, "evidence", "")
        affected_urls = list(getattr(finding, "affected_urls", []))
        suggested_action = getattr(finding, "suggested_action", None)
        action_summary = getattr(suggested_action, "summary", "") if suggested_action else ""

        # 1. Match from template catalog
        template = None
        for key in RECOMMENDATION_TEMPLATES:
            if fid == key or fid.startswith(f"{key}-") or key in fid:
                template = RECOMMENDATION_TEMPLATES[key]
                break

        if template:
            rec_title = template["title"]
            what_is_wrong = f"{template['what_is_wrong']} Observation: {evidence}"
            what_should_be_changed = action_summary or template["what_should_be_changed"]
            why_it_matters = template["why_it_matters"]
            verification_steps = template["verification_steps"]
        else:
            # High quality dynamic fallback for unlisted findings
            rec_title = f"Remediate {title}"
            what_is_wrong = f"The following issue was detected during the audit: {evidence or title}."
            what_should_be_changed = action_summary or f"Review affected URLs and resolve the underlying issue: {title}."
            why_it_matters = (
                f"Issues categorized under '{category}' with severity '{severity.value}' negatively affect "
                "user experience, discoverability, or brand grounding in autonomous AI workflows."
            )
            verification_steps = (
                f"Re-run the {category} audit against affected URLs to confirm that {fid} is no longer reported."
            )

        return ActionableRecommendation(
            finding_id=fid,
            category=str(category),
            title=rec_title,
            priority=severity,
            what_is_wrong=what_is_wrong,
            where_it_occurs=affected_urls,
            what_should_be_changed=what_should_be_changed,
            why_it_matters=why_it_matters,
            verification_steps=verification_steps,
        )

    @classmethod
    def generate_recommendations(
        cls,
        findings: List[Any],
    ) -> List[ActionableRecommendation]:
        """Generates a deduplicated, prioritized list of recommendations for a set of findings."""
        recommendations: List[ActionableRecommendation] = []
        seen_ids = set()

        for f in findings:
            fid = getattr(f, "id", "")
            if fid in seen_ids:
                continue
            seen_ids.add(fid)
            recommendations.append(cls.generate_recommendation(f))

        # Sort by priority
        severity_rank = {
            SeverityLevel.CRITICAL: 5,
            SeverityLevel.HIGH: 4,
            SeverityLevel.MEDIUM: 3,
            SeverityLevel.LOW: 2,
            SeverityLevel.INFO: 1,
        }
        return sorted(
            recommendations,
            key=lambda r: severity_rank.get(r.priority, 0),
            reverse=True,
        )
