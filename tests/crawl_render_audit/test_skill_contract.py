"""Skill contract and metadata validation tests for crawl-render-audit."""

import json
from pathlib import Path
import re
import httpx
import pytest

from src.crawler.http import SafeHTTPClient
from src.inspection import (
    InspectionPipeline,
    PageInspection,
    SiteInspection,
    inspect_site,
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SKILL_MD_PATH = ROOT_DIR / "skills" / "crawl-render-audit" / "SKILL.md"
MARKETPLACE_JSON_PATH = ROOT_DIR / "marketplace.json"


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from markdown file text without external dependencies."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if not match:
        return {}
    raw_yaml = match.group(1)
    data = {}
    for line in raw_yaml.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            data[key.strip()] = val.strip()
    return data


class TestSkillMetadataAndDocumentation:
    """Validate that crawl-render-audit adheres to Agent Skill specifications."""

    def test_skill_md_exists(self):
        assert SKILL_MD_PATH.exists(), f"SKILL.md not found at {SKILL_MD_PATH}"

    def test_skill_frontmatter_validity(self):
        content = SKILL_MD_PATH.read_text(encoding="utf-8")
        frontmatter = _parse_frontmatter(content)

        assert "name" in frontmatter
        assert frontmatter["name"] == "crawl-render-audit"
        assert "description" in frontmatter
        assert len(frontmatter["description"]) > 20
        assert "license" in frontmatter

    def test_skill_required_sections_present(self):
        content = SKILL_MD_PATH.read_text(encoding="utf-8")

        required_sections = [
            "Purpose",
            "When to Use",
            "Safe and Read-Only Behavior",
            "Inputs",
            "Outputs",
            "Usage and Pipeline Integration",
        ]
        for section in required_sections:
            assert section in content, f"Missing required section '{section}' in SKILL.md"

    def test_skill_references_inspect_site(self):
        content = SKILL_MD_PATH.read_text(encoding="utf-8")
        assert "inspect_site" in content
        assert "SiteInspection" in content


class TestMarketplaceComposition:
    """Validate marketplace.json structure and single entrypoint constraint."""

    def test_marketplace_json_validity(self):
        assert MARKETPLACE_JSON_PATH.exists(), f"marketplace.json not found at {MARKETPLACE_JSON_PATH}"
        data = json.loads(MARKETPLACE_JSON_PATH.read_text(encoding="utf-8"))

        assert "name" in data
        assert "skills" in data
        assert isinstance(data["skills"], list)

    def test_marketplace_contains_crawl_render_audit_skill(self):
        data = json.loads(MARKETPLACE_JSON_PATH.read_text(encoding="utf-8"))
        skill_ids = [s.get("id") for s in data["skills"]]
        assert "crawl-render-audit" in skill_ids

        crawl_skill = next(s for s in data["skills"] if s.get("id") == "crawl-render-audit")
        assert crawl_skill["path"] == "skills/crawl-render-audit"

    def test_exactly_one_entrypoint_skill_defined(self):
        data = json.loads(MARKETPLACE_JSON_PATH.read_text(encoding="utf-8"))
        entrypoint_skills = [s for s in data["skills"] if s.get("entrypoint") is True]

        assert len(entrypoint_skills) == 1
        assert entrypoint_skills[0]["id"] == "audit-orchestrator"


class TestSkillExecutionContract:
    """Validate that the skill pipeline invocation matches the documented interface contract."""

    def test_inspect_site_returns_documented_model_structure(self):
        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if url_str == "https://example.com/robots.txt":
                return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
            if url_str == "https://example.com":
                return httpx.Response(
                    200,
                    text="""<html><head><title>Test Page</title><meta name="description" content="Test description"></head><body><h1>Hello World</h1><p>Test content.</p></body></html>""",
                    headers={"Content-Type": "text/html"},
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        client = SafeHTTPClient(transport=transport, verify_dns=False)

        result = inspect_site(
            url="https://example.com",
            max_pages=2,
            client=client,
            discover_sitemaps=False,
            enable_rendering=False,
        )

        # Verify top-level outputs documented in SKILL.md
        assert isinstance(result, SiteInspection)
        assert result.site == "example.com"
        assert result.root_url == "https://example.com"
        assert result.robots.checked is True
        assert result.robots.found is True
        assert isinstance(result.pages, list)
        assert len(result.pages) == 1

        # Verify page-level outputs documented in SKILL.md
        page = result.pages[0]
        assert isinstance(page, PageInspection)
        assert page.url == "https://example.com"
        assert page.title == "Test Page"
        assert page.metadata.description == "Test description"
        assert len(page.headings) == 1
        assert page.headings[0].text == "Hello World"
        assert isinstance(page.technical_issues, list)
        assert isinstance(result.summary_counts, dict)
