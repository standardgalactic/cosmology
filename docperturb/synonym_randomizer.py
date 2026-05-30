#!/usr/bin/env python3
"""
synonym_randomizer.py
---------------------
Standalone synonym replacement script (original / compatibility layer).

This file retains the original clean API from the first implementation,
now backed by the full perturbation engine.  Import it directly for simple
use cases; use perturbation_engine.py for the full fiber-bundle framework.

Quick start
-----------
  python synonym_randomizer.py input.txt
  python synonym_randomizer.py input.txt -n 5 -t 0.7 -o variants/
  python synonym_randomizer.py input.txt -t 0.5 --seed 42 --verbose

Temperature guide
-----------------
  0.0  → no changes
  0.25 → subtle (shortest, most-common synonyms only)
  0.50 → moderate (default)
  0.75 → aggressive (wider pool, LLM if configured)
  1.0  → maximum

Dependencies
------------
  pip install nltk
  pip install sentence-transformers   # optional but recommended
"""

import sys
import random
import argparse
from pathlib import Path
from typing import Optional

try:
    from perturbation_engine import PerturbationEngine, MutationResult
    from semantic_budget import SemanticBudget, ConservationConstraint
    _ENGINE_AVAILABLE = True
except ImportError:
    _ENGINE_AVAILABLE = False


# ---------------------------------------------------------------------------
# Fallback: pure NLTK implementation (no engine dependencies)
# ---------------------------------------------------------------------------
if not _ENGINE_AVAILABLE:
    import re
    try:
        import nltk
        from nltk.corpus import wordnet as wn
        from nltk.tokenize import word_tokenize
        from nltk import pos_tag
    except ImportError:
        sys.exit("Install NLTK:  pip install nltk")

    _POS_MAP = {"J": wn.ADJ, "V": wn.VERB, "N": wn.NOUN, "R": wn.ADV}

    def _ensure() -> None:
        for r in ["wordnet","omw-1.4","punkt","punkt_tab",
                  "averaged_perceptron_tagger","averaged_perceptron_tagger_eng"]:
            try:
                nltk.data.find(f"corpora/{r}" if r in ("wordnet","omw-1.4")
                               else f"tokenizers/{r}" if "punkt" in r
                               else f"taggers/{r}")
            except LookupError:
                nltk.download(r, quiet=True)

    def _synonyms_sorted(word, wn_pos):
        pool = {}
        for syn in wn.synsets(word, pos=wn_pos):
            for lemma in syn.lemmas():
                c = lemma.name().replace("_", " ")
                if c.lower() != word.lower() and " " not in c and c.isalpha():
                    pool[c] = max(pool.get(c, 0), lemma.count())
        return sorted(pool.items(), key=lambda kv: kv[1], reverse=True)

    def _pick(synonyms, temperature, rng):
        n = len(synonyms)
        cut = (n // 3) if temperature < 0.3 else (2 * n // 3) if temperature < 0.7 else n
        cut = max(1, cut)
        words = [s[0] for s in synonyms[:cut]]
        return rng.choice(words)

    def _preserve_case(orig, repl):
        if orig.isupper(): return repl.upper()
        if orig[0].isupper(): return repl.capitalize()
        return repl.lower()

    def _tokenize(text):
        return re.findall(r"\w+|[^\w\s]|\s+", text, re.UNICODE)

    def _detokenize(tokens):
        out = ""
        for i, t in enumerate(tokens):
            if i > 0 and re.match(r"\w", t) and re.match(r"\w", tokens[i-1]):
                out += " "
            out += t
        return out

    def mutate_text(text, temperature=0.5, max_changes=None, seed=None):
        _ensure()
        rng    = random.Random(seed)
        tokens = _tokenize(text)
        prob   = 0.01 + temperature * 0.08
        cap    = max_changes or max(1, round(len(tokens) * prob))

        widx = [i for i, t in enumerate(tokens) if re.match(r"[A-Za-z]{4,}", t)]
        tagged = pos_tag([tokens[i] for i in widx])
        cands = [(widx[j], w, t) for j, (w, t) in enumerate(tagged)
                 if _POS_MAP.get(t[0])]
        rng.shuffle(cands)

        new_tokens = list(tokens)
        changes = []
        for idx, word, tag in cands:
            if len(changes) >= cap: break
            if rng.random() >= prob: continue
            syns = _synonyms_sorted(word, _POS_MAP[tag[0]])
            if not syns: continue
            repl = _preserve_case(word, _pick(syns, temperature, rng))
            new_tokens[idx] = repl
            changes.append({"original": word, "replacement": repl, "tag": tag})

        return _detokenize(new_tokens), changes

    def randomize_document(text, temperature=0.5, n_versions=1,
                           max_changes=None, base_seed=None):
        return [mutate_text(text, temperature, max_changes,
                            (base_seed + i) if base_seed is not None else None)
                for i in range(n_versions)]

    def generate_versions(input_file, output_dir="variants", count=10,
                          temperatures=(0.1, 0.3, 0.5, 0.7, 0.9)):
        text = Path(input_file).read_text(encoding="utf-8")
        out  = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            temp = random.choice(temperatures)
            mutated, log = mutate_text(text, temperature=temp)
            p = out / f"variant_{i+1:03d}_t{temp:.1f}.txt"
            p.write_text(mutated, encoding="utf-8")
            print(f"Created {p}  ({len(log)} substitutions)")


# ---------------------------------------------------------------------------
# Engine-backed implementation
# ---------------------------------------------------------------------------
else:
    def mutate_text(text, temperature=0.5, max_changes=None, seed=None,
                    profile="neutral", protected_terms=None):
        conservation = (ConservationConstraint(protected_terms.split(","))
                        if protected_terms else None)
        engine = PerturbationEngine(profile=profile, conservation=conservation)
        result = engine.mutate(text, temperature=temperature,
                               max_changes=max_changes, seed=seed)
        changes = [{"original": c.original, "replacement": c.replacement,
                    "tag": c.penn_tag} for c in result.changes]
        return result.text, changes

    def randomize_document(text, temperature=0.5, n_versions=1,
                           max_changes=None, base_seed=None, profile="neutral"):
        engine = PerturbationEngine(profile=profile)
        results = engine.generate_versions(text, n=n_versions,
                                           temperature=temperature,
                                           max_changes=max_changes,
                                           base_seed=base_seed)
        return [(r.text, [{"original": c.original, "replacement": c.replacement,
                           "tag": c.penn_tag} for c in r.changes])
                for r in results]

    def generate_versions(input_file, output_dir="variants", count=10,
                          temperatures=(0.1, 0.3, 0.5, 0.7, 0.9),
                          profile="neutral"):
        text   = Path(input_file).read_text(encoding="utf-8")
        out    = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        engine = PerturbationEngine(profile=profile)
        results = engine.generate_versions(
            text, n=count, temperatures=list(temperatures),
            base_seed=random.randint(0, 9999),
        )
        for i, r in enumerate(results, 1):
            p = out / f"variant_{i:03d}_t{r.temperature:.1f}_{r.profile}.txt"
            p.write_text(r.text, encoding="utf-8")
            print(f"Created {p}  ({len(r.changes)} substitutions)")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
def demo() -> None:
    sample = (
        "The scientist carefully examined the structure of the ancient building "
        "before publishing the report."
    )
    print("Original:\n ", sample, "\n")
    for temp in (0.1, 0.3, 0.5, 0.7, 0.9):
        modified, log = mutate_text(sample, temperature=temp, seed=42)
        print(f"t={temp}  ({len(log)} change(s)):")
        print(" ", modified)
        for e in log:
            print(f"    {e['original']!r} → {e['replacement']!r}  [{e['tag']}]")
        print()


# ---------------------------------------------------------------------------
# CLI (thin wrapper; full CLI is in docperturb_cli.py)
# ---------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser(description="Synonym randomizer (standalone / compat)")
    p.add_argument("input")
    p.add_argument("-n", "--versions", type=int, default=1)
    p.add_argument("-t", "--temperature", type=float, default=0.5)
    p.add_argument("-m", "--max-changes", type=int, default=None)
    p.add_argument("-o", "--output-dir", default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("-p", "--profile", default="neutral")
    p.add_argument("--protect", default=None)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    text = (Path(args.input).read_text(encoding="utf-8")
            if args.input != "-" else sys.stdin.read())
    if not text.strip():
        sys.exit("Empty input.")

    results = randomize_document(
        text,
        temperature  = args.temperature,
        n_versions   = args.versions,
        max_changes  = args.max_changes,
        base_seed    = args.seed,
        **({"profile": args.profile, "protected_terms": args.protect}
           if _ENGINE_AVAILABLE else {}),
    )

    out_dir = Path(args.output_dir) if args.output_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.input).stem if args.input != "-" else "document"

    for i, (modified, log) in enumerate(results, 1):
        if out_dir:
            p2 = out_dir / f"{stem}_v{i:03d}_t{args.temperature:.2f}.txt"
            p2.write_text(modified, encoding="utf-8")
            print(f"Written: {p2}  ({len(log)} substitutions)")
        else:
            print(f"\n{'='*60}\nVersion {i}  t={args.temperature:.2f}  "
                  f"changes={len(log)}\n{'='*60}")
            print(modified)
            if args.verbose:
                for e in log:
                    print(f"  {e['original']!r} → {e['replacement']!r}")


if __name__ == "__main__":
    main()
