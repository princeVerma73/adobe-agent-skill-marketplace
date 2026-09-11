"""Tests for Area 1: Homepage Orientation Detection."""

import pytest
from src.engagement.rules.orientation import check_homepage_orientation
from src.entity_trust.contracts.schemas import SeverityLevel


def test_orientation_flags_generic_title_and_h1():
    """Verifies that generic titles and H1s trigger ENG-001 with high severity."""
    findings = check_homepage_orientation(
        homepage_url="https://example.com/",
        title="Home",
        h1s=["Welcome"],
        body_text="Welcome to our website.",
    )
    assert len(findings) >= 1
    f = next(f for f in findings if f.id == "ENG-001")
    assert f.severity == SeverityLevel.HIGH
    assert f.confidence >= 0.90
    assert "https://example.com/" in f.affected_urls
    assert "Title='Home'" in f.evidence
    assert f.suggested_action.summary
    assert f.suggested_action.priority == SeverityLevel.HIGH


def test_orientation_flags_generic_title_alone():
    """Verifies that generic title with descriptive H1 triggers ENG-001-TITLE."""
    findings = check_homepage_orientation(
        homepage_url="https://example.com/",
        title="Homepage",
        h1s=["Enterprise Document Processing System"],
        body_text="Acme Corp provides automated document parsing for financial services.",
    )
    assert any(f.id == "ENG-001-TITLE" for f in findings)
    f = next(f for f in findings if f.id == "ENG-001-TITLE")
    assert f.severity == SeverityLevel.MEDIUM


def test_orientation_flags_sparse_value_proposition():
    """Verifies that insufficient introductory text triggers ENG-002."""
    findings = check_homepage_orientation(
        homepage_url="https://example.com/",
        title="Acme Cloud Document Intelligence",
        h1s=["Acme Cloud AI Platform"],
        body_text="Hello world.",  # sparse text (< 10 words)
        meta_description="",
    )
    assert any(f.id == "ENG-002" for f in findings)
    f = next(f for f in findings if f.id == "ENG-002")
    assert f.severity == SeverityLevel.HIGH
    assert "insufficient orientation text" in f.evidence


def test_orientation_passes_for_clear_homepage():
    """Verifies that a well-oriented homepage produces zero orientation findings."""
    findings = check_homepage_orientation(
        homepage_url="https://acmecloud.ai/",
        title="Acme Cloud AI - Enterprise Document Intelligence Platform",
        h1s=["Acme Cloud AI Platform for Global Finance"],
        body_text=(
            "Acme Cloud AI is an enterprise software company providing AI-powered document intelligence "
            "solutions for financial institutions and banks worldwide."
        ),
        meta_description="Acme Cloud AI delivers automated document extraction systems to banks.",
    )
    assert len(findings) == 0
