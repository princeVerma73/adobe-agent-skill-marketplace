"""Skill contract and metadata validation tests for entity-content-freshness-trust."""

import json
from pathlib import Path
import re
import pytest

from src.entity_trust import audit_entity_trust, ContentEntityAuditResult

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SKILL_MD_PATH = ROOT_DIR / "skills" / "entity-content-freshness-trust" / "SKILL.md"
MARKETPLACE_JSON_PATH = ROOT_DIR / "marketplace.json"
REFERENCES_DIR = ROOT_DIR / "skills" / "entity-content-freshness-trust" / "references"
SCRIPTS_DIR = ROOT_DIR / "skills" / "entity-content-freshness-trust" / "scripts"


def _parse_frontmatter(content: str) -> dict:
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
    """Validate that entity-content-freshness-trust adheres to Agent Skill specifications."""

    def test_skill_md_exists_and_has_valid_frontmatter(self):
        assert SKILL_MD_PATH.exists(), f"SKILL.md not found at {SKILL_MD_PATH}"
        text = SKILL_MD_PATH.read_text(encoding="utf-8")
        meta = _parse_frontmatter(text)

        assert meta.get("name") == "entity-content-freshness-trust"
        assert "description" in meta and len(meta["description"]) > 10
        assert meta.get("license") == "Apache-2.0"

    def test_registered_in_marketplace_json(self):
        assert MARKETPLACE_JSON_PATH.exists(), "marketplace.json not found"
        with open(MARKETPLACE_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        skill_ids = [s["id"] for s in data.get("skills", [])]
        assert "entity-content-freshness-trust" in skill_ids

    def test_reference_guides_exist(self):
        assert (REFERENCES_DIR / "entity-checks.md").exists()
        assert (REFERENCES_DIR / "content-checks.md").exists()
        assert (REFERENCES_DIR / "freshness-checks.md").exists()

    def test_scripts_exist(self):
        assert (SCRIPTS_DIR / "audit.py").exists()
        assert (SCRIPTS_DIR / "consistency.py").exists()
        assert (SCRIPTS_DIR / "content_analyzer.py").exists()
        assert (SCRIPTS_DIR / "entity_detector.py").exists()
        assert (SCRIPTS_DIR / "freshness.py").exists()
