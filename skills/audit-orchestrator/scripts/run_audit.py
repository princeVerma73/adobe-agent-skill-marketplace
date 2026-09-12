"""Master CLI execution script for audit-orchestrator entrypoint skill."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[3]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Ensure stdout handles UTF-8 gracefully across all platforms and locales
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.report import run_full_audit


def main():
    parser = argparse.ArgumentParser(
        description="Master Audit Orchestrator: Complete Brand AI-Readiness Audit"
    )
    parser.add_argument(
        "target",
        help="Target website URL (e.g. 'https://example.com') or path to JSON snapshot",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.70,
        help="Confidence threshold for findings (default: 0.70)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Maximum pages to crawl if target is a URL (default: 10)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="Maximum crawl depth if target is a URL (default: 2)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to save audit report output file",
    )

    args = parser.parse_args()

    target_input: Any
    target_path = Path(args.target)
    if target_path.exists() and target_path.is_file():
        with open(target_path, "r", encoding="utf-8") as f:
            target_input = json.load(f)
    else:
        target_input = args.target

    report = run_full_audit(
        target=target_input,
        confidence_threshold=args.threshold,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
    )

    if args.format == "markdown":
        output_content = report.to_markdown()
    else:
        output_content = report.to_json(indent=2)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(output_content)
        print(f"Report saved to: {out_path}")
    else:
        print(output_content)


if __name__ == "__main__":
    main()
