"""Command Line Interface for Member 2 Audit Module.

Allows testing snapshots and fixtures locally without running the full crawler or orchestrator.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from .contracts.schemas import SiteSnapshot
from .runner import audit_content_and_entity


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit website snapshot for Entity Identity, Content Clarity, Freshness, and Consistency."
    )
    parser.add_argument(
        "--fixture",
        "-f",
        type=str,
        required=True,
        help="Path to a JSON file containing a SiteSnapshot structure.",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=0.70,
        help="Confidence threshold for findings (default: 0.70).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional path to write the JSON findings result.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print pretty formatted JSON to stdout.",
    )

    args = parser.parse_args()

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"Error: Fixture file not found: {fixture_path}", file=sys.stderr)
        sys.exit(1)

    with open(fixture_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    result = audit_content_and_entity(raw_data, confidence_threshold=args.threshold)
    result_json = result.model_dump_json(indent=2)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(result_json)
        print(f"Audit report saved to: {out_path}")

    if args.pretty or not args.output:
        print(result_json)


if __name__ == "__main__":
    main()
