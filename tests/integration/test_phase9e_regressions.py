"""Phase 9E Regression Tests.

Validates the precision targeted fixes from black-box generalization evaluation:
1. Legal jurisdiction text ("located in the EEA / UK") does not generate false headquarters CO-* findings.
2. Negative test: Genuine cross-page headquarters contradictions still fire CO-*.
3. Cross-product metric differences across distinct named products do not generate false metric CO-* findings.
4. Negative test: Genuine conflicting metrics for the same entity/product still fire CO-*.
5. Robots.txt-disallowed pages emit ROBOTS_TXT_DISALLOWED but not HTTP_UNREACHABLE.
6. Negative test: Genuine network fetch failures still emit HTTP_UNREACHABLE.
"""

import pytest
from src.inspection.models import PageInspection, TechnicalIssue
from src.inspection.technical import check_http_status, check_robots_blocking
from src.entity_trust.contracts.schemas import SiteSnapshot, PageSnapshot
from src.entity_trust.runner import audit_content_and_entity


def test_1_legal_jurisdiction_text_does_not_fire_headquarters_contradiction():
    """Legal jurisdiction clauses ('located in the EEA', 'located in the UK') must not be extracted as headquarters."""
    snapshot = SiteSnapshot(
        site="stripe.com",
        homepage=PageSnapshot(
            url="https://stripe.com/in",
            html="<html><head><title>Stripe India</title></head><body><h1>Financial Infrastructure</h1></body></html>",
            text="Financial infrastructure for the internet",
        ),
        pages=[
            PageSnapshot(
                url="https://stripe.com/in/legal/ssa",
                html="<html><head><title>Stripe Services Agreement</title></head><body><p>Claims shall be resolved in state courts located in San Mateo County, California.</p></body></html>",
                text="Claims shall be resolved in state courts located in San Mateo County, California.",
            ),
            PageSnapshot(
                url="https://stripe.com/in/legal/ssa-services-terms",
                html="<html><head><title>Services Terms</title></head><body><p>Denominated Currency means euro if User is located in the EEA; GBP if User is located in the UK.</p></body></html>",
                text="Denominated Currency means euro if User is located in the EEA; GBP if User is located in the UK.",
            ),
        ],
    )
    result = audit_content_and_entity(snapshot)
    co_headquarters = [f for f in result.findings if f.id.startswith("CO-") and "Headquarters" in f.title]
    assert len(co_headquarters) == 0, f"Expected 0 headquarters CO-* findings, got {len(co_headquarters)}: {[f.evidence for f in co_headquarters]}"


def test_2_negative_genuine_headquarters_contradiction_still_fires():
    """Genuine corporate headquarters contradictions across pages must still trigger CO-*."""
    snapshot = SiteSnapshot(
        site="acme.com",
        homepage=PageSnapshot(
            url="https://acme.com",
            html="<html><head><title>Acme Corp</title></head><body><p>Acme Corp is headquartered in Austin, Texas.</p></body></html>",
            text="Acme Corp is headquartered in Austin, Texas.",
        ),
        pages=[
            PageSnapshot(
                url="https://acme.com/about",
                html="<html><head><title>About Acme</title></head><body><p>Acme Corp is headquartered in Seattle, Washington.</p></body></html>",
                text="Acme Corp is headquartered in Seattle, Washington.",
            ),
        ],
    )
    result = audit_content_and_entity(snapshot)
    co_headquarters = [f for f in result.findings if f.id.startswith("CO-") and "Headquarters" in f.title]
    assert len(co_headquarters) == 1, f"Expected 1 headquarters CO-* finding, got {len(co_headquarters)}"
    assert "Austin" in co_headquarters[0].evidence and "Seattle" in co_headquarters[0].evidence


def test_3_distinct_product_metrics_do_not_fire_metric_contradiction():
    """Distinct products described on different pages must not trigger cross-page metric contradictions."""
    snapshot = SiteSnapshot(
        site="apple.com",
        homepage=PageSnapshot(
            url="https://apple.com",
            html="<html><head><title>Apple</title></head><body><h1>Apple</h1></body></html>",
            text="Apple official portal",
        ),
        pages=[
            PageSnapshot(
                url="https://apple.com/newsroom/watch-ultra-4",
                html="<html><head><title>Apple Watch Ultra 4</title></head><body><p>Apple Watch Ultra 4 features 500 team members.</p></body></html>",
                text="Apple Watch Ultra 4 is supported by 500 team members.",
            ),
            PageSnapshot(
                url="https://apple.com/newsroom/watch-series-12",
                html="<html><head><title>Apple Watch Series 12</title></head><body><p>Apple Watch Series 12 was built by 100 team members.</p></body></html>",
                text="Apple Watch Series 12 was built by 100 team members.",
            ),
        ],
    )
    result = audit_content_and_entity(snapshot)
    co_metrics = [f for f in result.findings if f.id.startswith("CO-") and "Metric" in f.title]
    assert len(co_metrics) == 0, f"Expected 0 metric CO-* findings, got {len(co_metrics)}: {[f.evidence for f in co_metrics]}"


def test_4_negative_genuine_metric_contradiction_for_same_entity_still_fires():
    """Genuinely conflicting metrics about the same entity/product across pages must still trigger CO-*."""
    snapshot = SiteSnapshot(
        site="acme.com",
        homepage=PageSnapshot(
            url="https://acme.com",
            html="<html><head><title>Acme Corp</title></head><body><p>Acme Corp is trusted by 50,000 customers worldwide.</p></body></html>",
            text="Acme Corp is trusted by 50,000 customers worldwide.",
        ),
        pages=[
            PageSnapshot(
                url="https://acme.com/overview",
                html="<html><head><title>Acme Overview</title></head><body><p>Acme Corp is trusted by 10,000 customers worldwide.</p></body></html>",
                text="Acme Corp is trusted by 10,000 customers worldwide.",
            ),
        ],
    )
    result = audit_content_and_entity(snapshot)
    co_metrics = [f for f in result.findings if f.id.startswith("CO-") and "Metric" in f.title]
    assert len(co_metrics) == 1, f"Expected 1 metric CO-* finding, got {len(co_metrics)}"
    assert "50,000" in co_metrics[0].evidence and "10,000" in co_metrics[0].evidence


def test_5_robots_disallowed_page_does_not_fire_http_unreachable():
    """A page disallowed by robots.txt must emit ROBOTS_TXT_DISALLOWED, but NOT HTTP_UNREACHABLE."""
    disallowed_page = PageInspection(
        url="https://en.wikipedia.org/wiki/Special:Random",
        original_url="https://en.wikipedia.org/wiki/Special:Random",
        status_code=None,
        allowed_by_robots=False,
    )
    http_issues = check_http_status(disallowed_page)
    robots_issues = check_robots_blocking(disallowed_page)

    http_codes = [i.code for i in http_issues]
    robots_codes = [i.code for i in robots_issues]

    assert "HTTP_UNREACHABLE" not in http_codes, f"HTTP_UNREACHABLE should be suppressed for robots disallowed pages, got {http_codes}"
    assert "ROBOTS_TXT_DISALLOWED" in robots_codes, f"ROBOTS_TXT_DISALLOWED should fire, got {robots_codes}"


def test_6_negative_genuine_network_failure_still_fires_http_unreachable():
    """A genuine connection failure (allowed_by_robots=True, status_code=None) MUST emit HTTP_UNREACHABLE."""
    unreachable_page = PageInspection(
        url="https://example.com/broken-endpoint",
        original_url="https://example.com/broken-endpoint",
        status_code=None,
        allowed_by_robots=True,
    )
    http_issues = check_http_status(unreachable_page)
    http_codes = [i.code for i in http_issues]

    assert "HTTP_UNREACHABLE" in http_codes, f"HTTP_UNREACHABLE must fire for genuine network failures, got {http_codes}"
