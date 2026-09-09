"""Deterministic unit tests for HTML extraction and rendering heuristics."""

import pytest
from src.extraction.extract import (
    extract_headings,
    extract_links,
    extract_metadata,
    extract_static_html,
    extract_structured_data,
    extract_visible_text,
    is_rendering_needed,
    populate_page_inspection,
)
from src.inspection.models import Heading, Link, PageInspection, PageMetadata


SAMPLE_RICH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>   Acme Corp - High Quality Tools &amp; Widgets   </title>
    <meta name="description" content="Acme Corp provides state-of-the-art tools and machinery worldwide.">
    <meta name="robots" content="index, follow, max-snippet:-1">
    <link rel="canonical" href="/products/main">
    <!-- Open Graph -->
    <meta property="og:title" content="Acme Corp Tools">
    <meta property="og:description" content="Discover professional grade widgets.">
    <meta property="og:type" content="website">
    <meta property="og:image" content="https://example.com/images/og.png">
    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:site" content="@AcmeCorp">
    <!-- Other Meta -->
    <meta name="keywords" content="tools, widgets, engineering">
    <!-- Structured Data -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Acme Corp",
        "url": "https://example.com"
    }
    </script>
    <script type="application/ld+json">
    [
        {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Super Anvil",
            "price": "99.99"
        }
    ]
    </script>
    <style>
        .hidden-css { display: none; color: red; }
    </style>
</head>
<body>
    <header>
        <h1>Welcome to Acme Corp</h1>
        <nav>
            <a href="/">Home</a>
            <a href="/about" rel="noopener">About Us</a>
            <a href="https://blog.example.com/updates">Blog</a>
            <a href="https://external-partner.org/sponsor" rel="nofollow">Sponsor</a>
            <a href="javascript:void(0)">Ignore JS</a>
            <a href="mailto:info@example.com">Email Us</a>
            <a href="#section2">Skip Link</a>
        </nav>
    </header>
    <main>
        <h2>Featured Offerings</h2>
        <p>We build durable and reliable tools for all industrial applications.</p>
        <h3>Heavy Machinery</h3>
        <p>Our anvils and hammers are rated for industrial stress loads and certified standard.</p>
        <h4>Specifications</h4>
        <p>Detailed parameters and stress thresholds.</p>
        <h5>Sub-spec Details</h5>
        <p>Minor details here.</p>
        <h6>Fine Print</h6>
        <p>Terms apply.</p>
    </main>
    <script>
        console.log("analytics tracker");
    </script>
</body>
</html>
"""


class TestStaticHTMLExtraction:
    """Tests for metadata, headings, body text, links, and structured data."""

    def test_title_and_metadata_extraction(self):
        extracted = extract_static_html(SAMPLE_RICH_HTML, base_url="https://example.com")

        assert extracted.title == "Acme Corp - High Quality Tools & Widgets"
        assert extracted.metadata.description == "Acme Corp provides state-of-the-art tools and machinery worldwide."
        assert extracted.metadata.canonical_url == "https://example.com/products/main"
        assert extracted.metadata.robots_meta == "index, follow, max-snippet:-1"

        # OpenGraph
        assert extracted.metadata.open_graph.get("og:title") == "Acme Corp Tools"
        assert extracted.metadata.open_graph.get("og:description") == "Discover professional grade widgets."
        assert extracted.metadata.open_graph.get("og:type") == "website"

        # Twitter
        assert extracted.metadata.twitter_card.get("twitter:card") == "summary_large_image"
        assert extracted.metadata.twitter_card.get("twitter:site") == "@AcmeCorp"

        # Extra
        assert extracted.metadata.extra.get("keywords") == "tools, widgets, engineering"

    def test_headings_hierarchy_and_order(self):
        extracted = extract_static_html(SAMPLE_RICH_HTML, base_url="https://example.com")
        headings = extracted.headings

        assert len(headings) == 6
        assert headings[0] == Heading(level=1, text="Welcome to Acme Corp")
        assert headings[1] == Heading(level=2, text="Featured Offerings")
        assert headings[2] == Heading(level=3, text="Heavy Machinery")
        assert headings[3] == Heading(level=4, text="Specifications")
        assert headings[4] == Heading(level=5, text="Sub-spec Details")
        assert headings[5] == Heading(level=6, text="Fine Print")

    def test_visible_body_text_excludes_noise(self):
        extracted = extract_static_html(SAMPLE_RICH_HTML, base_url="https://example.com")
        body_text = extracted.body_text

        assert "Welcome to Acme Corp" in body_text
        assert "We build durable and reliable tools" in body_text
        assert "analytics tracker" not in body_text  # Script tag text removed
        assert "display: none" not in body_text  # Style tag text removed
        assert "  " not in body_text  # Whitespace normalized

    def test_link_extraction_and_internal_classification(self):
        extracted = extract_static_html(SAMPLE_RICH_HTML, base_url="https://example.com/home")
        links = extracted.links

        target_urls = {l.url: l for l in links}

        # Root internal link
        assert "https://example.com" in target_urls
        assert target_urls["https://example.com"].is_internal is True

        # Subpath internal link
        assert "https://example.com/about" in target_urls
        assert target_urls["https://example.com/about"].is_internal is True
        assert target_urls["https://example.com/about"].rel == "noopener"

        # Subdomain same-site link
        assert "https://blog.example.com/updates" in target_urls
        assert target_urls["https://blog.example.com/updates"].is_internal is True

        # External link
        assert "https://external-partner.org/sponsor" in target_urls
        assert target_urls["https://external-partner.org/sponsor"].is_internal is False
        assert target_urls["https://external-partner.org/sponsor"].rel == "nofollow"

        # Skipped / filtered links
        all_urls_list = [l.url for l in links]
        assert not any("javascript" in u for u in all_urls_list)
        assert not any("mailto" in u for u in all_urls_list)
        assert not any("#section2" in u for u in all_urls_list)

    def test_structured_data_json_ld(self):
        extracted = extract_static_html(SAMPLE_RICH_HTML, base_url="https://example.com")
        schemas = extracted.structured_data

        assert len(schemas) == 2
        assert schemas[0]["@type"] == "Organization"
        assert schemas[0]["name"] == "Acme Corp"
        assert schemas[1]["@type"] == "Product"
        assert schemas[1]["name"] == "Super Anvil"

    def test_malformed_json_ld_ignored_gracefully(self):
        html_with_bad_json = """
        <html>
        <head>
            <script type="application/ld+json">
                { "broken": json without quotes ...
            </script>
            <script type="application/ld+json">
                {"@type": "Valid", "name": "Success"}
            </script>
        </head>
        <body><p>Content</p></body>
        </html>
        """
        extracted = extract_static_html(html_with_bad_json, base_url="https://example.com")
        assert len(extracted.structured_data) == 1
        assert extracted.structured_data[0]["@type"] == "Valid"

    def test_fallback_title_from_og_title(self):
        html = """<html><head><meta property="og:title" content="Social Title"></head><body><h1>Hi</h1></body></html>"""
        extracted = extract_static_html(html, base_url="https://example.com")
        assert extracted.title == "Social Title"

    def test_base_href_handling(self):
        html = """<html><head><base href="https://example.com/v2/"></head><body><a href="docs">Docs</a></body></html>"""
        extracted = extract_static_html(html, base_url="https://example.com/root")
        assert len(extracted.links) == 1
        assert extracted.links[0].url == "https://example.com/v2/docs"


class TestRenderingHeuristics:
    """Tests for detecting when static HTML is insufficient."""

    def test_sufficient_static_page_does_not_need_rendering(self):
        needs_render, reason = is_rendering_needed(SAMPLE_RICH_HTML, base_url="https://example.com")
        assert needs_render is False

    def test_empty_spa_root_container_triggers_rendering(self):
        spa_html = """<!DOCTYPE html><html><head><title>App</title></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>"""
        needs_render, reason = is_rendering_needed(spa_html, base_url="https://example.com")
        assert needs_render is True
        assert "Single-Page Application" in reason

    def test_noscript_js_warning_triggers_rendering(self):
        noscript_html = """<!DOCTYPE html><html><head><title>App</title></head><body><noscript>You need to enable JavaScript to run this app.</noscript><div id="content"></div></body></html>"""
        needs_render, reason = is_rendering_needed(noscript_html, base_url="https://example.com")
        assert needs_render is True
        assert "Noscript" in reason

    def test_short_body_with_scripts_triggers_rendering(self):
        minimal_html = """<!DOCTYPE html><html><head><title>App</title></head><body><div>Loading...</div><script src="/vendor.js"></script></body></html>"""
        needs_render, reason = is_rendering_needed(minimal_html, base_url="https://example.com", min_body_chars=50)
        assert needs_render is True
        assert "Insufficient visible body text" in reason

    def test_empty_html_handled_safely(self):
        needs_render, reason = is_rendering_needed("", base_url="https://example.com")
        assert needs_render is False


class TestPopulatePageInspection:
    """Tests for populating PageInspection model."""

    def test_populate_static_inspection(self):
        page = PageInspection(
            url="https://example.com",
            original_url="https://example.com",
        )
        populated = populate_page_inspection(page, SAMPLE_RICH_HTML)

        assert populated.title == "Acme Corp - High Quality Tools & Widgets"
        assert populated.is_rendered is False
        assert populated.raw_html_available is True
        assert populated.source_text is not None
        assert "Welcome to Acme Corp" in populated.source_text
        assert len(populated.headings) == 6
        assert len(populated.links) >= 4
        assert len(populated.structured_data) == 2
        assert populated.metadata.description is not None

    def test_populate_rendered_inspection(self):
        page = PageInspection(
            url="https://example.com/app",
            original_url="https://example.com/app",
            source_text="Static Loading...",
        )
        rendered_html = """<html><head><title>Hydrated App</title></head><body><h1>Hydrated Title</h1><p>Full content loaded.</p></body></html>"""
        populated = populate_page_inspection(
            page,
            html=rendered_html,
            is_rendered=True,
            rendered_text="Hydrated Title Full content loaded.",
        )

        assert populated.is_rendered is True
        assert populated.title == "Hydrated App"
        assert populated.rendered_text == "Hydrated Title Full content loaded."
        assert populated.source_text == "Static Loading..."
        assert len(populated.headings) == 1
        assert populated.headings[0].text == "Hydrated Title"
