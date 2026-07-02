#!/usr/bin/env python3
"""List available newspaper codes from the selectpuq CSV."""

import argparse
import csv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="List available newspaper codes from CSV, with optional filtering"
    )
    parser.add_argument(
        "--filter",
        "-f",
        help="Filter newspapers by name substring (case-insensitive)",
    )
    parser.add_argument(
        "--codes-only",
        action="store_true",
        help="Output only codes (space-separated, ready for --newspaper-codes)",
    )
    args = parser.parse_args()

    csv_path = Path(__file__).parent.parent / "assets" / "enewspaper_selectpuq_journaux.csv"

    if not csv_path.exists():
        print(f"[ERROR] CSV file not found: {csv_path}")
        return 1

    newspapers = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get("value", "").strip()
            name = row.get("text", "").strip()

            # Skip header or empty rows
            if not code or code.startswith("---"):
                continue

            # Apply filter if provided
            if args.filter and args.filter.lower() not in name.lower():
                continue

            newspapers.append((code, name))

    if args.codes_only:
        # Output space-separated codes ready for --newspaper-codes
        codes = [code for code, _ in newspapers]
        print(" ".join(codes))
    else:
        # Output formatted table
        if newspapers:
            print(f"{'Code':<6} {'Name'}")
            print("-" * 70)
            for code, name in newspapers:
                print(f"{code:<6} {name}")
            print()
            print(f"Total: {len(newspapers)} newspaper(s)")
        else:
            print("No newspapers found matching the filter.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

