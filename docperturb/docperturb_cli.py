#!/usr/bin/env python3
"""
docperturb_cli.py
-----------------
Command-line interface for the document perturbation engine.

Usage
-----
  # Single version, medium temperature, stdout:
  python docperturb_cli.py input.txt

  # Five variants at high temperature, written to ./variants/:
  python docperturb_cli.py input.txt -n 5 -t 0.8 -o variants/

  # Sampled temperatures (reference implementation style):
  python docperturb_cli.py input.txt -n 10 -T 0.1,0.3,0.5,0.7,0.9 -o variants/

  # Academic profile with protected terms:
  python docperturb_cli.py input.txt -p academic --protect "RSVP,Friedmann" -t 0.6

  # Multi-axis temperature vector:
  python docperturb_cli.py input.txt --tv-lexical 0.8 --tv-syntactic 0.3 --tv-semantic 0.1

  # Enable LLM backend (OpenAI-compatible):
  SYNONYM_LLM_BACKEND=openai OPENAI_API_KEY=sk-... \\
      python docperturb_cli.py input.txt -t 0.9 -p creative

  # JSON output for downstream processing:
  python docperturb_cli.py input.txt -n 3 --json
"""

import sys
import json
import random
import argparse
from pathlib import Path
from typing import Optional

from perturbation_engine import PerturbationEngine, MutationResult
from mutation_profiles   import list_profiles
from semantic_budget     import (
    SemanticBudget, TemperatureVector, ConservationConstraint
)


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="docperturb",
        description=(
            "Document-space perturbation engine.\n"
            "Generates semantically constrained alternate versions of a document."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Input / output
    p.add_argument("input", help="Path to input file, or '-' to read from stdin")
    p.add_argument("-o", "--output-dir", default=None,
                   help="Directory for output files (default: print to stdout)")
    p.add_argument("--json", action="store_true",
                   help="Emit JSON output (one object per version)")

    # Version control
    p.add_argument("-n", "--versions", type=int, default=1,
                   help="Number of variants to generate (default: 1)")

    # Temperature (scalar or vector)
    p.add_argument("-t", "--temperature", type=float, default=0.5,
                   help="Scalar temperature 0.0–1.0 (default: 0.5)")
    p.add_argument("-T", "--temperatures", type=str, default=None,
                   help="Comma-separated temperature pool, sampled per variant "
                        "(e.g. '0.1,0.3,0.5,0.7,0.9')")
    p.add_argument("--tv-lexical",   type=float, default=None,
                   help="Lexical axis temperature (overrides -t for word swaps)")
    p.add_argument("--tv-syntactic", type=float, default=None,
                   help="Syntactic axis temperature (sentence restructuring)")
    p.add_argument("--tv-semantic",  type=float, default=None,
                   help="Semantic axis temperature (LLM paraphrase)")

    # Budget (explicit override)
    p.add_argument("--budget-lexical",   type=float, default=None,
                   help="Lexical budget (cosine distance units, e.g. 0.05)")
    p.add_argument("--budget-syntactic", type=float, default=None,
                   help="Syntactic budget")
    p.add_argument("--budget-semantic",  type=float, default=None,
                   help="Semantic budget")
    p.add_argument("--max-step",         type=float, default=None,
                   help="Max single-mutation step size (curvature control)")

    # Profile and conservation
    p.add_argument("-p", "--profile", default="neutral",
                   choices=list_profiles(),
                   help="Mutation profile (default: neutral)")
    p.add_argument("--protect", type=str, default=None,
                   help="Comma-separated protected terms/phrases (e.g. 'RSVP,Friedmann')")
    p.add_argument("--protect-epsilon", type=float, default=0.05,
                   help="Conservation constraint tolerance (default: 0.05)")

    # Misc
    p.add_argument("-m", "--max-changes", type=int, default=None,
                   help="Hard cap on substitutions per version (default: auto)")
    p.add_argument("--seed", type=int, default=None,
                   help="Base RNG seed for reproducibility")
    p.add_argument("--verbose", action="store_true",
                   help="Print change log for each version")
    p.add_argument("--summary", action="store_true",
                   help="Print budget utilisation summary")

    return p


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_temp_vector(args) -> Optional[TemperatureVector]:
    if args.tv_lexical is None and args.tv_syntactic is None and args.tv_semantic is None:
        return None
    base = TemperatureVector.from_scalar(args.temperature)
    return TemperatureVector(
        lexical   = args.tv_lexical   if args.tv_lexical   is not None else base.lexical,
        syntactic = args.tv_syntactic if args.tv_syntactic is not None else base.syntactic,
        semantic  = args.tv_semantic  if args.tv_semantic  is not None else base.semantic,
    )


def _build_budget(args) -> Optional[SemanticBudget]:
    if all(v is None for v in [args.budget_lexical, args.budget_syntactic,
                                args.budget_semantic, args.max_step]):
        return None
    base = SemanticBudget.from_scalar(args.temperature)
    return SemanticBudget(
        lexical   = args.budget_lexical   if args.budget_lexical   is not None else base.lexical,
        syntactic = args.budget_syntactic if args.budget_syntactic is not None else base.syntactic,
        semantic  = args.budget_semantic  if args.budget_semantic  is not None else base.semantic,
        max_step  = args.max_step         if args.max_step         is not None else base.max_step,
    )


def _build_conservation(args) -> Optional[ConservationConstraint]:
    if not args.protect:
        return None
    phrases = [p.strip() for p in args.protect.split(",") if p.strip()]
    return ConservationConstraint(
        protected_phrases=phrases,
        epsilon=args.protect_epsilon,
    )


def _print_result(result: MutationResult, idx: int, total: int,
                  verbose: bool, summary: bool, as_json: bool) -> None:
    if as_json:
        obj = {
            "version":      idx,
            "temperature":  result.temperature,
            "profile":      result.profile,
            "seed":         result.seed,
            "budget_used":  result.budget_used,
            "budget_max":   result.budget_max,
            "utilisation":  result.utilisation,
            "changes": [
                {
                    "original":    c.original,
                    "replacement": c.replacement,
                    "tag":         c.penn_tag,
                    "step_drift":  c.step_drift,
                    "total_drift": c.total_drift,
                    "pass":        c.pass_name,
                }
                for c in result.changes
            ],
            "text": result.text,
        }
        print(json.dumps(obj, ensure_ascii=False))
        return

    bar = "=" * 62
    print(f"\n{bar}")
    print(f"  Version {idx}/{total}  |  t={result.temperature:.2f}  |  "
          f"profile={result.profile}  |  changes={len(result.changes)}  |  "
          f"seed={result.seed}")
    print(bar)
    print(result.text)

    if summary:
        print(f"\n  Budget: {result.budget_used:.4f} / {result.budget_max:.4f} "
              f"({result.utilisation*100:.1f}% used)")
        for pass_name, info in result.pass_summary.items():
            print(f"    {pass_name:10s}  changes={info['changes']}  "
                  f"spent={info['spent']:.4f}")

    if verbose and result.changes:
        print("\n  Change log:")
        for c in result.changes:
            print(f"    [{c.penn_tag:<4}]  {c.original!r:>20} → {c.replacement!r:<20}  "
                  f"Δ={c.step_drift:.4f}  Σ={c.total_drift:.4f}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    # Read input
    if args.input == "-":
        text = sys.stdin.read()
    else:
        text = Path(args.input).read_text(encoding="utf-8")
    if not text.strip():
        sys.exit("Input document is empty.")

    # Build components
    tv           = _build_temp_vector(args)
    budget       = _build_budget(args)
    conservation = _build_conservation(args)

    engine = PerturbationEngine(
        profile      = args.profile,
        budget       = budget,
        conservation = conservation,
    )

    # Temperature pool
    temp_pool = None
    if args.temperatures:
        temp_pool = [float(t.strip()) for t in args.temperatures.split(",")]

    # Output dir
    out_dir = Path(args.output_dir) if args.output_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.input).stem if args.input != "-" else "document"

    # Generate
    results = engine.generate_versions(
        text,
        n            = args.versions,
        temperature  = args.temperature,
        temperatures = temp_pool,
        temp_vector  = tv,
        max_changes  = args.max_changes,
        base_seed    = args.seed,
    )

    # Output
    for i, result in enumerate(results, 1):
        if out_dir:
            fname = f"{stem}_v{i:03d}_t{result.temperature:.2f}_{result.profile}.txt"
            out_path = out_dir / fname
            out_path.write_text(result.text, encoding="utf-8")
            print(f"Written: {out_path}  "
                  f"({len(result.changes)} changes, "
                  f"{result.utilisation*100:.0f}% budget used)")
            if args.verbose:
                for c in result.changes:
                    print(f"  {c.original!r} → {c.replacement!r}  "
                          f"[{c.penn_tag}] Δ={c.step_drift:.4f}")
        else:
            _print_result(result, i, args.versions,
                          args.verbose, args.summary, args.json)


if __name__ == "__main__":
    main()
