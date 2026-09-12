"""Context retention audit rule (Area 10).

Evaluates whether deeper pages provide sufficient orienting context, brand identity,
and parent navigation for visitors or AI agents arriving directly on that page.
"""

import re
import urllib.parse
from typing import Any, Dict, List

from src.entity_trust.contracts.schemas import FindingAction, SeverityLevel
from src.engagement.models import EngagementFinding
from src.inspection.url import is_locale_root


def check_context_retention(
    site_domain: str,
    homepage_url: str,
    pages_data: List[Dict[str, Any]],
) -> List[EngagementFinding]:
    """Audits deeper pages for direct-landing context retention and breadcrumbs."""
    findings: List[EngagementFinding] = []
    hp_canonical = homepage_url.rstrip("/")

    for page in pages_data:
        url = page.get("url", "")
        if url.rstrip("/") == hp_canonical:
            continue  # Homepage is the root

        # Regional root portals (e.g. /au/, /at/, /ae_ar/, /africa/) are localized homepages,
        # not deep content landing pages requiring a parent link back to the audited locale.
        if is_locale_root(url):
            continue

        crawl_depth = page.get("crawl_depth", 0)
        parsed_path = urllib.parse.urlparse(url).path.strip("/")
        path_segments = [s for s in parsed_path.split("/") if s]

        # Consider deep only if it has path segments (root domain has empty path)
        if not path_segments:
            continue

        title = (page.get("title") or "").strip()
        headings = page.get("headings", [])
        links = page.get("links", [])

        # 1. Check if the page links back to homepage/root or localized root
        has_home_link = False
        parsed_hp = urllib.parse.urlparse(homepage_url)
        root_domain_url = f"{parsed_hp.scheme}://{parsed_hp.netloc}".rstrip("/")
        brand_kw = site_domain.split(".")[0].lower() if site_domain else ""

        for link in links:
            raw_target = (link.get("url") or "").strip()
            t = raw_target.rstrip("/")
            anchor = (link.get("text") or "").strip().lower()
            rel = (link.get("rel") or "").lower()

            if t in (hp_canonical, f"{hp_canonical}/", root_domain_url, f"{root_domain_url}/"):
                has_home_link = True
                break
            if "home" in rel:
                has_home_link = True
                break
            if anchor in ("home", "homepage", "index", "main") or (brand_kw and brand_kw in anchor and len(anchor) < 30):
                has_home_link = True
                break

            # Check for localized homepage paths (e.g., /en-US/, /en/, /de/, /fr/, /ae_ar/)
            parsed_link = urllib.parse.urlparse(raw_target)
            link_host = parsed_link.netloc.lower()
            root_host = parsed_hp.netloc.lower()
            if not link_host or link_host == root_host:
                if is_locale_root(parsed_link.path):
                    has_home_link = True
                    break

        if not has_home_link:
            findings.append(
                EngagementFinding(
                    id="ENG-015",
                    category="engagement",
                    title="Deep landing page lacks navigation link back to homepage",
                    severity=SeverityLevel.MEDIUM,
                    confidence=0.90,
                    evidence=(
                        f"Direct landing page '{url}' has no link back to the root homepage '{homepage_url}'. "
                        "Visitors arriving from external search engines or AI direct references cannot navigate "
                        "back to the main brand portal."
                    ),
                    affected_urls=[url],
                    suggested_action=FindingAction(
                        summary=(
                            f"Include a logo/home link or breadcrumb navigation on '{url}' that connects back "
                            f"to the homepage ('{homepage_url}')."
                        ),
                        priority=SeverityLevel.MEDIUM,
                    ),
                )
            )

        # 2. Check if deep page lacks any H1 heading
        has_h1 = any(h.get("level") == 1 and (h.get("text") or "").strip() for h in headings)
        if not has_h1:
            findings.append(
                EngagementFinding(
                    id="ENG-016",
                    category="engagement",
                    title="Direct landing page lacks clear orienting H1 heading",
                    severity=SeverityLevel.MEDIUM,
                    confidence=0.87,
                    evidence=(
                        f"Page '{url}' does not have an <h1> heading defining the page topic. "
                        "Users landing directly on this page receive no prominent topical orientation."
                    ),
                    affected_urls=[url],
                    suggested_action=FindingAction(
                        summary=f"Add a descriptive primary <h1> heading to '{url}' clarifying the section subject.",
                        priority=SeverityLevel.MEDIUM,
                    ),
                )
            )

    return findings
