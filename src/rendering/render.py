"""Selective Playwright rendering engine for dynamic JavaScript-heavy pages.

Executes bounded, safe, read-only browser rendering using Playwright Chromium
only when static HTML extraction is insufficient.
Enforces timeouts, resource bounds, SSRF safety, and graceful fallbacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import time
from typing import Any, Dict, List, Optional

from src.crawler.http import DEFAULT_USER_AGENT
from src.extraction.extract import (
    ExtractedData,
    extract_static_html,
    is_rendering_needed,
    populate_page_inspection,
)
from src.inspection.models import (
    PageInspection,
    PageMetadata,
    TechnicalIssue,
)
from src.inspection.url import (
    InvalidURLError,
    PrivateTargetError,
    extract_hostname,
    is_private_or_local_target,
    is_valid_url,
    normalize_url,
)

logger = logging.getLogger(__name__)

# Resource types to abort in browser to enforce resource limits and fast rendering
BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}

# Exception classes with fallback if playwright is not installed in the python environment
try:
    from playwright.sync_api import (  # type: ignore
        sync_playwright,
        TimeoutError as PlaywrightTimeoutError,
        Error as PlaywrightError,
    )
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    sync_playwright = None
    PLAYWRIGHT_AVAILABLE = False

    class PlaywrightError(Exception):
        """Fallback Playwright error when playwright package is not installed."""
        pass

    class PlaywrightTimeoutError(PlaywrightError):
        """Fallback Playwright timeout error when playwright package is not installed."""
        pass


@dataclass
class RenderConfig:
    """Configuration options for Playwright rendering."""
    timeout_ms: int = 10000  # 10s timeout
    wait_until: str = "domcontentloaded"
    block_heavy_resources: bool = True
    user_agent: str = DEFAULT_USER_AGENT
    viewport_width: int = 1280
    viewport_height: int = 800
    headless: bool = True


@dataclass
class RenderResult:
    """Result of Playwright browser rendering attempt."""
    url: str
    original_url: str
    html: str = ""
    rendered_text: str = ""
    is_rendered: bool = False
    duration_ms: float = 0.0
    error: Optional[str] = None
    extracted: Optional[ExtractedData] = None


def render_page_playwright(
    url: str,
    config: Optional[RenderConfig] = None,
    playwright_instance: Optional[Any] = None,
) -> RenderResult:
    """Render a dynamic web page using Playwright Chromium.
    
    Enforces:
    - Pre-navigation URL & SSRF safety check
    - Strict execution and navigation timeout
    - Request route interception to block unsafe schemas and heavy resources
    - Read-only navigation (no form fills, no state mutations)
    - Graceful error handling (no unhandled exceptions)
    """
    start_time = time.perf_counter()
    cfg = config or RenderConfig()
    original_url = url

    # 1. SSRF & URL safety pre-check
    try:
        normalized_url = normalize_url(url)
    except (InvalidURLError, PrivateTargetError) as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return RenderResult(
            url=url,
            original_url=original_url,
            is_rendered=False,
            duration_ms=elapsed_ms,
            error=f"URL safety check failed: {exc}",
        )

    # 2. Check Playwright availability if no mock instance is injected
    if playwright_instance is None and (not PLAYWRIGHT_AVAILABLE or sync_playwright is None):
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return RenderResult(
            url=normalized_url,
            original_url=original_url,
            is_rendered=False,
            duration_ms=elapsed_ms,
            error="Playwright is not installed or available in this environment.",
        )

    # 3. Execute browser navigation safely
    def _execute_render(pw) -> RenderResult:
        browser = None
        context = None
        page = None
        try:
            browser = pw.chromium.launch(
                headless=cfg.headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            context = browser.new_context(
                user_agent=cfg.user_agent,
                viewport={"width": cfg.viewport_width, "height": cfg.viewport_height},
                java_script_enabled=True,
            )
            page = context.new_page()
            page.set_default_timeout(cfg.timeout_ms)
            page.set_default_navigation_timeout(cfg.timeout_ms)

            # SSRF route interception and heavy resource blocking
            def _handle_route(route):
                req = route.request
                req_url = getattr(req, "url", "")
                # Block non-http schemes
                if req_url.startswith(("data:", "blob:", "about:")):
                    route.continue_()
                    return

                # Validate hostname safety
                host = extract_hostname(req_url)
                if host and is_private_or_local_target(host):
                    route.abort("blockedbyclient")
                    return

                # Block heavy media resources if configured
                resource_type = getattr(req, "resource_type", "")
                if cfg.block_heavy_resources and resource_type in BLOCKED_RESOURCE_TYPES:
                    route.abort("blockedbyclient")
                    return

                route.continue_()

            page.route("**/*", _handle_route)

            # Navigate to target (GET only)
            page.goto(normalized_url, wait_until=cfg.wait_until, timeout=cfg.timeout_ms)

            # Extract rendered HTML and visible DOM text
            rendered_html = page.content() or ""
            try:
                rendered_text = page.inner_text("body") or ""
            except Exception:
                rendered_text = ""

            extracted = extract_static_html(rendered_html, base_url=normalized_url)
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

            return RenderResult(
                url=normalized_url,
                original_url=original_url,
                html=rendered_html,
                rendered_text=rendered_text,
                is_rendered=True,
                duration_ms=elapsed_ms,
                extracted=extracted,
            )

        except PlaywrightTimeoutError:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return RenderResult(
                url=normalized_url,
                original_url=original_url,
                is_rendered=False,
                duration_ms=elapsed_ms,
                error=f"Playwright navigation timed out after {cfg.timeout_ms}ms.",
            )
        except PlaywrightError as exc:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return RenderResult(
                url=normalized_url,
                original_url=original_url,
                is_rendered=False,
                duration_ms=elapsed_ms,
                error=f"Playwright rendering failed: {exc}",
            )
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return RenderResult(
                url=normalized_url,
                original_url=original_url,
                is_rendered=False,
                duration_ms=elapsed_ms,
                error=f"Unexpected browser error: {exc}",
            )
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass

    if playwright_instance is not None:
        return _execute_render(playwright_instance)

    try:
        with sync_playwright() as pw:
            return _execute_render(pw)
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return RenderResult(
            url=normalized_url,
            original_url=original_url,
            is_rendered=False,
            duration_ms=elapsed_ms,
            error=f"Failed to initialize Playwright environment: {exc}",
        )


def render_and_inspect_page(
    url: str,
    static_html: Optional[str] = None,
    page_inspection: Optional[PageInspection] = None,
    config: Optional[RenderConfig] = None,
    force_render: bool = False,
    playwright_instance: Optional[Any] = None,
) -> PageInspection:
    """Selectively render a page with Playwright if static HTML is insufficient, and populate PageInspection.
    
    Workflow:
    1. If page_inspection is not provided, creates a minimal PageInspection.
    2. Performs baseline static extraction on static_html.
    3. Evaluates if dynamic rendering is needed (or if force_render=True).
    4. If needed, runs Playwright rendering within bounds.
    5. If rendering succeeds: records is_rendered=True, rendered_text, and updates DOM observations.
    6. If rendering fails: records TechnicalIssue and gracefully falls back to static extraction.
    """
    cfg = config or RenderConfig()
    try:
        norm_url = normalize_url(url)
    except Exception:
        norm_url = url

    page = page_inspection or PageInspection(
        url=norm_url,
        original_url=url,
    )

    # 1. Base static extraction
    html_source = static_html or ""
    static_extracted = extract_static_html(html_source, base_url=norm_url)
    page.raw_html_available = bool(html_source)
    page.source_text = static_extracted.body_text
    page.title = static_extracted.title
    page.metadata = static_extracted.metadata
    page.headings = static_extracted.headings
    page.body_text = static_extracted.body_text
    page.links = static_extracted.links
    page.structured_data = static_extracted.structured_data

    # 2. Check if rendering is required
    needs_render, reason = is_rendering_needed(
        html=html_source,
        extracted=static_extracted,
        base_url=norm_url,
    )

    if not needs_render and not force_render:
        page.is_rendered = False
        return page

    # 3. Attempt selective browser rendering
    render_res = render_page_playwright(
        url=norm_url,
        config=cfg,
        playwright_instance=playwright_instance,
    )

    if render_res.is_rendered and render_res.extracted:
        page.is_rendered = True
        page.rendered_text = render_res.rendered_text or render_res.extracted.body_text
        # Update with rendered observations
        if render_res.extracted.title:
            page.title = render_res.extracted.title
        if render_res.extracted.metadata:
            page.metadata = render_res.extracted.metadata
        if render_res.extracted.headings:
            page.headings = render_res.extracted.headings
        if render_res.extracted.body_text:
            page.body_text = render_res.extracted.body_text
        if render_res.extracted.links:
            page.links = render_res.extracted.links
        if render_res.extracted.structured_data:
            page.structured_data = render_res.extracted.structured_data
    else:
        # Fallback to static extraction and record technical issue
        page.is_rendered = False
        if render_res.error:
            page.technical_issues.append(
                TechnicalIssue(
                    code="RENDERING_FAILED",
                    message=f"Browser rendering failed: {render_res.error}. Fell back to static HTML.",
                    severity="warning",
                    details={"reason": reason, "error": render_res.error},
                )
            )

    return page
