#!/usr/bin/env python3
"""CI gate: parse eval output and pass/fail against a statistical threshold.

promptfoo's own exit code is 0 on success and 1 on *any* failure, so it can't
express "pass if at least 90% of trials succeed" -- the case the promptfoo-eval
experiment flagged as needing a custom wrapper. This is that wrapper.

It reads a promptfoo results JSON, computes the observed pass rate, and gates
on the *lower* confidence bound clearing the target (via `threshold_test`), so
the verdict accounts for how many trials were actually run.

Usage:
    python threshold_check.py results.json --target 0.90
    python threshold_check.py results.json --target 0.90 --confidence 0.95

Exit code 0 if the gate passes, 1 if it fails, 2 on a usage/parse error.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from significance import threshold_test


def extract_counts(data: Any) -> tuple[int, int]:
    """Pull (successes, total) out of a promptfoo results document.

    Handles the two shapes promptfoo emits:
    * a top-level or nested ``stats`` block with ``successes``/``failures``
    * a ``results`` array whose entries carry a ``success`` boolean

    Raises ValueError if neither is present, rather than guessing.
    """
    # Unwrap the common `{"results": {...}}` envelope.
    root = data.get("results", data) if isinstance(data, dict) else data

    # Shape 1: an explicit stats block (preferred -- it is authoritative).
    stats = None
    if isinstance(root, dict) and isinstance(root.get("stats"), dict):
        stats = root["stats"]
    elif isinstance(data, dict) and isinstance(data.get("stats"), dict):
        stats = data["stats"]
    if stats is not None and "successes" in stats:
        successes = int(stats["successes"])
        failures = int(stats.get("failures", 0))
        total = successes + failures
        if total <= 0:
            raise ValueError("stats block reports zero trials")
        return successes, total

    # Shape 2: a per-result array with `success` booleans.
    rows = None
    if isinstance(root, dict) and isinstance(root.get("results"), list):
        rows = root["results"]
    elif isinstance(root, list):
        rows = root
    if rows is not None:
        total = len(rows)
        if total == 0:
            raise ValueError("results array is empty")
        successes = 0
        for row in rows:
            if isinstance(row, dict):
                if "success" in row:
                    successes += 1 if row["success"] else 0
                elif "pass" in row:
                    successes += 1 if row["pass"] else 0
                else:
                    raise ValueError("result row has no 'success'/'pass' field")
            else:
                raise ValueError("result row is not an object")
        return successes, total

    raise ValueError("could not find a stats block or results array in the input")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("results", help="path to a promptfoo results JSON file")
    parser.add_argument(
        "--target", type=float, required=True,
        help="minimum acceptable pass rate, e.g. 0.90",
    )
    parser.add_argument(
        "--confidence", type=float, default=0.95,
        help="confidence level for the interval (default 0.95)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        with open(args.results, encoding="utf-8") as fh:
            data = json.load(fh)
        successes, total = extract_counts(data)
        result = threshold_test(successes, total, args.target, args.confidence)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"threshold-check: {exc}", file=sys.stderr)
        return 2

    print(result)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
