"""Comprehensive audit script for entity-content-freshness-trust skill."""

import sys
import json
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[3]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.entity_trust import audit_entity_trust, SiteSnapshot


def main():
    if len(sys.argv) < 2:
        print("Usage: python audit.py <snapshot.json> [--threshold 0.70]")
        sys.exit(1)

    threshold = 0.70
    if len(sys.argv) >= 4 and sys.argv[2] == "--threshold":
        threshold = float(sys.argv[3])

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)

    result = audit_entity_trust(data, confidence_threshold=threshold)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
