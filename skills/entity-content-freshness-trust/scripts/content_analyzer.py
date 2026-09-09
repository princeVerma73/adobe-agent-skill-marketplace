"""Content analyzer standalone skill script."""

import sys
import json
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[3]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

try:
    from src.entity_trust.contracts.schemas import SiteSnapshot
    from src.entity_trust.core.html_parser import parse_page_html
    from src.entity_trust.audits.content_clarity_audit import audit_content_clarity
except ImportError:
    from member2.contracts.schemas import SiteSnapshot
    from member2.core.html_parser import parse_page_html
    from member2.audits.content_clarity_audit import audit_content_clarity


def main():
    if len(sys.argv) < 2:
        print("Usage: python content_analyzer.py <snapshot.json>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)

    if hasattr(SiteSnapshot, "from_site_inspection") and ("root_url" in data or "pages" in data) and "homepage" not in data:
        snapshot = SiteSnapshot.from_site_inspection(data)
    else:
        snapshot = SiteSnapshot.model_validate(data)

    parsed = [
        parse_page_html(
            url=p.url,
            html=p.html,
            fallback_text=p.text,
            fallback_title=p.title,
            pre_extracted_images=p.images,
            pre_extracted_json_ld=p.structured_data,
        )
        for p in snapshot.all_pages()
    ]
    findings = audit_content_clarity(snapshot, parsed)
    print(json.dumps([f.model_dump() for f in findings], indent=2))


if __name__ == "__main__":
    main()
