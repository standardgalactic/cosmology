#!/usr/bin/env python3
"""
perturbation_engine.py
----------------------
Document-space perturbation engine.

Treats document mutation as constrained optimization over a semantic fiber
bundle:

    maximize(variation)
    subject to:
        metric.distance(D₀, Dₙ)    ≤ budget.axis_budget
        metric.distance(Dₖ₋₁, Dₖ)  ≤ budget.max_step
        conservation.satisfied(D₀, Dₙ)

Each transformation (word swap, sentence flip, LLM paraphrase) is an operator
that consumes semantic budget.  The mutator proposes candidates and admits only
those that pass the FiberExplorer checks.

Multi-pass architecture
-----------------------
  Pass 1 — lexical      : word-level synonym substitution
  Pass 2 — syntactic    : active↔passive, clause reordering   (stub, extend as needed)
  Pass 3 — semantic     : LLM full-sentence paraphrase         (stub, extend as needed)

Each pass draws from its own budget axis (lexical / syntactic / semantic).

Public API
----------
  PerturbationEngine.mutate(text, ...)
  PerturbationEngine.generate_versions(text, n, ...)

Dependencies
------------
  pip install nltk
  sentence-transformers (optional, for drift filtering and budget tracking)
"""

from __future__ import annotations

import re
import random
import sys
from typing import Optional
from dataclasses import dataclass, field

from synonym_engine  import (
    ensure_nltk_data, choose_synonym, replacement_probability, penn_to_wn
)
from mutation_profiles import MutationProfile, get_profile, PROFILES
from semantic_budget   import (
    SemanticBudget, SemanticMetric, TemperatureVector,
    ConservationConstraint, FiberExplorer,
)

from nltk.tokenize import word_tokenize
from nltk           import pos_tag


# ---------------------------------------------------------------------------
# Case preservation
# ---------------------------------------------------------------------------
def _preserve_case(original: str, replacement: str) -> str:
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[0].isupper():
        return replacement.capitalize()
    return replacement.lower()


# ---------------------------------------------------------------------------
# Tokenise / detokenise
# ---------------------------------------------------------------------------
def _tokenize(text: str) -> list[str]:
    """Preserve whitespace and punctuation as separate tokens."""
    return re.findall(r"\w+|[^\w\s]|\s+", text, re.UNICODE)

def _detokenize(tokens: list[str]) -> str:
    out = ""
    for i, tok in enumerate(tokens):
        if i > 0 and re.match(r"\w", tok) and re.match(r"\w", tokens[i - 1]):
            out += " "
        out += tok
    return out


# ---------------------------------------------------------------------------
# Change record
# ---------------------------------------------------------------------------
@dataclass
class Change:
    token_idx:   int
    original:    str
    replacement: str
    penn_tag:    str
    step_drift:  float = 0.0
    total_drift: float = 0.0
    pass_name:   str   = "lexical"


# ---------------------------------------------------------------------------
# MutationResult
# ---------------------------------------------------------------------------
@dataclass
class MutationResult:
    text:        str
    changes:     list[Change]
    budget_used: float
    budget_max:  float
    seed:        int
    temperature: float
    profile:     str
    pass_summary: dict = field(default_factory=dict)

    @property
    def utilisation(self) -> float:
        return self.budget_used / (self.budget_max + 1e-10)


# ---------------------------------------------------------------------------
# Lexical pass
# ---------------------------------------------------------------------------
def _lexical_pass(
    text:         str,
    temperature:  float,
    profile:      MutationProfile,
    budget:       SemanticBudget,
    metric:       SemanticMetric,
    conservation: Optional[ConservationConstraint],
    max_changes:  Optional[int],
    rng:          random.Random,
) -> tuple[str, list[Change], float]:
    """
    Perform word-level synonym substitutions within the lexical budget.
    Returns (mutated_text, changes, budget_spent).
    """
    tokens = _tokenize(text)
    word_indices = [
        i for i, t in enumerate(tokens)
        if re.match(r"[A-Za-z]{4,}", t)
    ]
    if not word_indices:
        return text, [], 0.0

    words  = [tokens[i] for i in word_indices]
    tagged = pos_tag(words)

    # Build candidate list: (token_idx, word, tag)
    candidates = [
        (word_indices[j], word, tag)
        for j, (word, tag) in enumerate(tagged)
        if penn_to_wn(tag) and profile.is_eligible(tag)
    ]
    if not candidates:
        return text, [], 0.0

    # Shuffle for randomness; budget controls how many we accept
    rng.shuffle(candidates)

    # Auto max_changes
    prob = replacement_probability(temperature)
    cap  = max_changes if max_changes is not None else max(1, round(len(tokens) * prob))

    # Initialize fiber explorer for lexical axis
    explorer = FiberExplorer(
        original_text = text,
        budget        = budget,
        metric        = metric,
        conservation  = conservation,
        axis          = "lexical",
    )

    new_tokens  = list(tokens)
    changes: list[Change] = []
    current_text = text

    for tok_idx, word, tag in candidates:
        if len(changes) >= cap:
            break
        if rng.random() >= prob:
            continue

        # Find sentence context for LLM and conservation checks
        char_start = sum(len(t) for t in tokens[:tok_idx])
        context    = text[max(0, char_start - 80): char_start + 80]

        synonym = choose_synonym(
            word, tag, context, temperature, rng,
            profile=profile,
            conservation=conservation,
            original_sentence=text,
        )
        if synonym is None:
            continue

        replacement  = _preserve_case(word, synonym)
        candidate_text = _detokenize(
            new_tokens[:tok_idx] + [replacement] + new_tokens[tok_idx + 1:]
        )

        # Fiber admission check
        admitted, reason = explorer.admit(candidate_text)
        if not admitted:
            continue

        step_drift  = explorer.commit(candidate_text)
        total_drift = explorer.tracker.spent

        new_tokens[tok_idx] = replacement
        current_text = candidate_text
        changes.append(Change(
            token_idx   = tok_idx,
            original    = word,
            replacement = replacement,
            penn_tag    = tag,
            step_drift  = step_drift,
            total_drift = total_drift,
            pass_name   = "lexical",
        ))

    return _detokenize(new_tokens), changes, explorer.tracker.spent


# ---------------------------------------------------------------------------
# Syntactic pass  (stub — extend with spacy dependency parsing)
# ---------------------------------------------------------------------------
def _syntactic_pass(
    text:        str,
    temperature: float,
    budget:      SemanticBudget,
    rng:         random.Random,
) -> tuple[str, list[Change], float]:
    """
    Sentence-level structural transformations.

    Currently implemented: sentence boundary shuffling within paragraphs
    at syntactic_temperature > 0.5.  A full implementation would use
    spaCy dependency parsing for active↔passive conversion and clause
    reordering while remaining semantically equivalent.

    Extend this function to add:
        - active ↔ passive voice  (requires spacy + rule-based transform)
        - clause reordering       (VP and NP subtree permutation)
        - appositive insertion    (adding clarifying noun phrases)
    """
    if temperature < 0.3 or budget.syntactic < 0.01:
        return text, [], 0.0

    # Minimal implementation: shuffle sentences within a paragraph
    # only at high syntactic temperature.
    if temperature < 0.6:
        return text, [], 0.0

    paragraphs = text.split("\n\n")
    new_paragraphs = []
    for para in paragraphs:
        sents = re.split(r"(?<=[.!?])\s+", para)
        if len(sents) > 2 and rng.random() < temperature * 0.3:
            # Shuffle middle sentences, keep first and last anchored
            middle = sents[1:-1]
            rng.shuffle(middle)
            sents = [sents[0]] + middle + [sents[-1]]
        new_paragraphs.append(" ".join(sents))
    return "\n\n".join(new_paragraphs), [], 0.0


# ---------------------------------------------------------------------------
# Semantic pass  (LLM paraphrase)
# ---------------------------------------------------------------------------
def _semantic_pass(
    text:        str,
    temperature: float,
    budget:      SemanticBudget,
    profile:     MutationProfile,
    rng:         random.Random,
) -> tuple[str, list[Change], float]:
    """
    Full sentence paraphrase using LLM backend.

    Each sentence is independently offered for paraphrase; accepted only if
    the semantic temperature is above threshold and LLM backend is configured.

    A future implementation should check embedding drift per sentence against
    the remaining semantic budget before committing.
    """
    import os
    backend = os.environ.get("SYNONYM_LLM_BACKEND", "")
    if not backend or temperature < 0.7 or budget.semantic < 0.01:
        return text, [], 0.0

    sentences  = re.split(r"(?<=[.!?])\s+", text)
    new_sents  = []
    spent      = 0.0

    for sent in sentences:
        if rng.random() > temperature * 0.3:
            new_sents.append(sent)
            continue

        paraphrase = _llm_paraphrase(sent, profile.llm_system_prompt, temperature)
        if paraphrase:
            new_sents.append(paraphrase)
        else:
            new_sents.append(sent)

    return " ".join(new_sents), [], spent


def _llm_paraphrase(sentence: str, system_prompt: str, temperature: float) -> Optional[str]:
    import os
    backend = os.environ.get("SYNONYM_LLM_BACKEND", "").lower()

    user_prompt = (
        f"Paraphrase this sentence, preserving its meaning exactly, "
        f"but using different wording. Return only the paraphrased sentence:\n\n"
        f"{sentence}"
    )

    try:
        if backend == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=os.environ["OPENAI_API_KEY"],
                            base_url=os.environ.get("OPENAI_BASE_URL"))
            resp = client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                max_tokens=200,
                temperature=temperature,
            )
            return resp.choices[0].message.content.strip()

        if backend == "ollama":
            import json, urllib.request
            host    = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
            payload = json.dumps({
                "model":  os.environ.get("OLLAMA_MODEL", "mistral"),
                "system": system_prompt,
                "prompt": user_prompt,
                "stream": False,
            }).encode()
            req = urllib.request.Request(
                f"{host}/api/generate", data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read()).get("response", "").strip()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# PerturbationEngine  — public API
# ---------------------------------------------------------------------------
class PerturbationEngine:
    """
    Main entry point for document-space perturbation.

    Parameters
    ----------
    profile      : "academic" | "journalistic" | "creative" | "legal" |
                   "technical" | "neutral" | MutationProfile instance
    budget       : SemanticBudget | None  (constructed from temperature if None)
    metric       : SemanticMetric | None  (identity if None)
    conservation : ConservationConstraint | None
    """

    def __init__(
        self,
        profile:      str | MutationProfile = "neutral",
        budget:       Optional[SemanticBudget] = None,
        metric:       Optional[SemanticMetric] = None,
        conservation: Optional[ConservationConstraint] = None,
    ):
        ensure_nltk_data()

        self.profile = (
            get_profile(profile) if isinstance(profile, str) else profile
        )
        self._budget_override      = budget
        self._metric_override      = metric
        self.conservation          = conservation

    def _resolve_budget(self, temperature: float) -> SemanticBudget:
        return self._budget_override or SemanticBudget.from_scalar(temperature)

    def _resolve_metric(self) -> SemanticMetric:
        if self._metric_override:
            return self._metric_override
        from semantic_budget import academic_metric, literary_metric, SemanticMetric
        metric_map = {
            "academic":     academic_metric,
            "creative":     literary_metric,
        }
        factory = metric_map.get(self.profile.name)
        return factory() if factory else SemanticMetric.identity(self.profile.name)

    # ------------------------------------------------------------------
    def mutate(
        self,
        text:         str,
        temperature:  float = 0.5,
        temp_vector:  Optional[TemperatureVector] = None,
        max_changes:  Optional[int] = None,
        seed:         Optional[int] = None,
    ) -> MutationResult:
        """
        Produce one mutated version of *text*.

        If *temp_vector* is supplied it overrides *temperature* for each pass
        independently, enabling multi-axis control:
            lexical_temperature   = controls word swap breadth
            syntactic_temperature = controls structural restructuring
            semantic_temperature  = controls LLM paraphrase aggressiveness
        """
        if not 0.0 <= temperature <= 1.0:
            raise ValueError("temperature must be in [0.0, 1.0]")

        rng    = random.Random(seed if seed is not None else random.randint(0, 2**31))
        actual_seed = seed if seed is not None else rng.randint(0, 2**31)

        tv     = temp_vector or TemperatureVector.from_scalar(temperature)
        budget = self._resolve_budget(temperature)
        metric = self._resolve_metric()

        # Pass 1: lexical
        text1, lex_changes, lex_spent = _lexical_pass(
            text, tv.lexical, self.profile, budget, metric,
            self.conservation, max_changes, rng,
        )

        # Pass 2: syntactic
        text2, syn_changes, syn_spent = _syntactic_pass(
            text1, tv.syntactic, budget, rng,
        )

        # Pass 3: semantic (LLM paraphrase, high-temp only)
        text3, sem_changes, sem_spent = _semantic_pass(
            text2, tv.semantic, budget, self.profile, rng,
        )

        all_changes = lex_changes + syn_changes + sem_changes

        return MutationResult(
            text        = text3,
            changes     = all_changes,
            budget_used = lex_spent + syn_spent + sem_spent,
            budget_max  = budget.total,
            seed        = actual_seed,
            temperature = temperature,
            profile     = self.profile.name,
            pass_summary = {
                "lexical":   {"changes": len(lex_changes), "spent": lex_spent},
                "syntactic": {"changes": len(syn_changes), "spent": syn_spent},
                "semantic":  {"changes": len(sem_changes), "spent": sem_spent},
            },
        )

    # ------------------------------------------------------------------
    def generate_versions(
        self,
        text:         str,
        n:            int = 5,
        temperature:  float = 0.5,
        temperatures: Optional[list[float]] = None,
        temp_vector:  Optional[TemperatureVector] = None,
        max_changes:  Optional[int] = None,
        base_seed:    Optional[int] = None,
    ) -> list[MutationResult]:
        """
        Generate *n* variants.  If *temperatures* is supplied, each variant
        draws a temperature from the list (cycling if n > len(temperatures)).
        """
        results = []
        for i in range(n):
            if temperatures:
                temp = temperatures[i % len(temperatures)]
            else:
                temp = temperature
            seed = (base_seed + i) if base_seed is not None else None
            results.append(
                self.mutate(text, temperature=temp, temp_vector=temp_vector,
                            max_changes=max_changes, seed=seed)
            )
        return results
