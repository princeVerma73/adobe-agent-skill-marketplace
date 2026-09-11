"""Entity detector standalone skill script."""

import sys
import json
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[3]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.entity_trust.contracts.schemas import SiteSnapshot
from src.entity_trust.core.html_parser import parse_page_html
from src.entity_trust.audits.entity_audit import audit_entity


def main():
    if len(sys.argv) < 2:
        print("Usage: python entity_detector.py <snapshot.json>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)

    if hasattr(SiteSnapshot, "from_site_inspection") and ("root_url" in data or "pages" in data) and "homepage" not in data:
        snapshot = SiteSnapshot.from_site_inspection(data)
    else:
        snapshot = SiteSnapshot.model_validate(data)

    parsed = [parse_page_html(p.url, p.html, p.text) for p in snapshot.all_pages()]
    findings, profile = audit_entity(snapshot, parsed)

    output = {
        "profile": profile.model_dump(),
        "findings": [f.model_dump() for f in findings],
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
