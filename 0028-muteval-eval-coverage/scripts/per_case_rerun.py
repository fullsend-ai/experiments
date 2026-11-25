"""Rerun selected 0028 mutants through every case, recording each case's result.

muteval stops a mutant's suite at the first failing eval, so `muteval-run.json`
cannot say which case killed a mutant. This script reuses muteval 0.11.0's own
pieces -- the promptfoo config loader, the mutant generator, the model call
(`config.invoke`: one user message, temperature 0) and the `starts-with` evals --
and only drops the short-circuit: every case runs for every mutant, `--runs`
times, with every output kept.

Mutants are picked by the signatures in `results/mutant-classification.md`, so
the rows match that table.

Usage, from the experiment directory with OPENAI_API_KEY set and muteval 0.11.0
installed (`pip install muteval==0.11.0`):

    python scripts/per_case_rerun.py --runs 3 --out results/per-case-rerun.json
"""

import argparse
import json
import sys

from muteval.adapters.promptfoo import from_promptfoo
from muteval.evals import coerce_outcome
from muteval.mutators import generate_mutants

# Row number in results/mutant-classification.md -> signature.
ROWS = {
    1: "78d204d612df",
    3: "bb2f6b133acd",
    4: "73be62f68a44",
    5: "2ef83972b07c",
    8: "4005df987289",
    9: "100a72f53753",
    10: "732846561686",
    11: "3c56b8f18dfd",
    12: "1821d4e418bb",
    15: "0c519cccf676",
    21: "7539d005a827",
    22: "fc7e5f22bc91",
    23: "ebcf3dc272d8",
    24: "b16aced5fdf8",
    25: "6754d0ad7639",
}


def run_suite(config, system):
    """Every case, every eval, no short-circuit."""
    cases = []
    for case in config.cases:
        output = config.invoke(system, case)
        failed = [
            name
            for ev, name in zip(
                config.evals, config.eval_names or [None] * len(config.evals)
            )
            if not coerce_outcome(ev(output, case), name=name).passed
        ]
        cases.append({"passed": not failed, "output": output})
    return cases


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="promptfooconfig.gpt-4o-mini.yaml")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", default="results/per-case-rerun.json")
    args = ap.parse_args()

    config = from_promptfoo(args.config)
    target = config.system if config.system is not None else config.prompt
    mutants = generate_mutants(target)
    by_sig = {m.signature: m for m in mutants}
    missing = [row for row, sig in ROWS.items() if sig not in by_sig]
    # The generator, not the package metadata, is what has to match the
    # committed run: 0.11.0 yields 28 mutants for this prompt (0.12.0 yields 22).
    if len(mutants) != 28 or missing:
        sys.exit(
            f"generated {len(mutants)} mutants, rows {missing} missing: "
            "this is not muteval 0.11.0's generator on 0016's prompt"
        )

    from muteval.system import as_system

    result = {
        "generator": "muteval 0.11.0 (28 mutants, rows matched by signature)",
        "model": "gpt-4o-mini",
        "runs": args.runs,
        # promptfoo's case descriptions don't survive the adapter; the PR
        # title identifies each case in 0016's config.
        "cases": [c.get("pr_title", "") for c in config.cases],
        "baseline": [run_suite(config, as_system(target)) for _ in range(args.runs)],
        "mutants": [],
    }
    for row, sig in ROWS.items():
        m = by_sig[sig]
        runs = [run_suite(config, m.system) for _ in range(args.runs)]
        result["mutants"].append(
            {
                "row": row,
                "signature": sig,
                "operator": m.operator,
                "description": m.description,
                "runs": runs,
            }
        )
        failing = [[i + 1 for i, c in enumerate(r) if not c["passed"]] for r in runs]
        print(
            f"row {row:2d} {m.operator:28s} failing cases per run: {failing}",
            flush=True,
        )

    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
