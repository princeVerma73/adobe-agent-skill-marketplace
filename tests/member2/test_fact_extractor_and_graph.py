"""Tests for FactExtractor and FactGraph conflict detection."""

from member2.core.fact_extractor import FactExtractor
from member2.core.fact_graph import FactGraph
from member2.core.html_parser import parse_page_html


def test_fact_extraction_and_graph_conflict():
    page1 = parse_page_html(
        url="https://test.com/",
        fallback_text="We are an AI company. Founded in 2015. Headquartered in San Francisco, CA. Pricing: $49/mo.",
    )
    page2 = parse_page_html(
        url="https://test.com/about",
        fallback_text="About our firm. Established in 2018 in London. Pricing: $99/mo.",
    )

    graph = FactGraph(site="test.com")
    for f in FactExtractor.extract_from_page(page1):
        graph.add_fact(f)
    for f in FactExtractor.extract_from_page(page2):
        graph.add_fact(f)

    conflicts = graph.detect_conflicts()
    conflict_types = {c.fact_type for c in conflicts}

    assert "founding_year" in conflict_types
    assert "headquarters" in conflict_types
    assert "price" in conflict_types

    # Verify founding_year conflict details
    founding_conflict = next(c for c in conflicts if c.fact_type == "founding_year")
    assert "https://test.com/" in founding_conflict.affected_urls
    assert "https://test.com/about" in founding_conflict.affected_urls
    assert founding_conflict.confidence >= 0.80
