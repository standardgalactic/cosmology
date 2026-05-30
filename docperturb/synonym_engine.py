#!/usr/bin/env python3
"""
synonym_engine.py
-----------------
Synonym retrieval combining WordNet (with frequency-weighted selection) and
optional LLM backends for contextual, high-temperature substitutions.

WordNet strategy
----------------
  • POS-aware lookup via Penn Treebank → WordNet mapping
  • Candidates sorted by corpus frequency (lemma.count())
  • Temperature controls both synset breadth and frequency-weight exponent:
      low temperature  → steep exponent, high-frequency synonyms dominate
      high temperature → flat exponent, rare synonyms become reachable
  • Profile register bias optionally re-weights Latinate vs. Saxon candidates

LLM strategy (optional)
------------------------
  Set SYNONYM_LLM_BACKEND = "openai" | "ollama"
  At temperature ≥ 0.5 the LLM is tried first; WordNet is the fallback.
  The LLM prompt is drawn from the active MutationProfile.

Dependencies
------------
  pip install nltk
  pip install openai          # optional, for OpenAI-compatible backend
"""

from __future__ import annotations

import os
import re
import random
from typing import Optional

# ---------------------------------------------------------------------------
# NLTK bootstrap
# ---------------------------------------------------------------------------
import nltk
from nltk.corpus import wordnet as wn
from nltk import pos_tag
from nltk.tokenize import word_tokenize

_NLTK_RESOURCES = [
    ("tokenizers", "punkt"),
    ("tokenizers", "punkt_tab"),
    ("taggers",    "averaged_perceptron_tagger"),
    ("taggers",    "averaged_perceptron_tagger_eng"),
    ("corpora",    "wordnet"),
    ("corpora",    "omw-1.4"),
]

def ensure_nltk_data() -> None:
    for category, name in _NLTK_RESOURCES:
        try:
            nltk.data.find(f"{category}/{name}")
        except LookupError:
            print(f"  Downloading NLTK resource: {name}")
            nltk.download(name, quiet=True)


# ---------------------------------------------------------------------------
# POS mapping  (Penn Treebank → WordNet)
# ---------------------------------------------------------------------------
_POS_MAP = {
    "J": wn.ADJ,
    "V": wn.VERB,
    "N": wn.NOUN,
    "R": wn.ADV,
}

def penn_to_wn(penn_tag: str) -> Optional[str]:
    return _POS_MAP.get(penn_tag[0]) if penn_tag else None


# ---------------------------------------------------------------------------
# Replacement probability  (from reference implementation)
# ---------------------------------------------------------------------------
def replacement_probability(temperature: float) -> float:
    """
    Per-token swap probability.
      t = 0.0  →  0.01
      t = 1.0  →  0.09
    Temperature primarily controls synonym *breadth* and selection weight;
    max_changes controls overall substitution volume.
    """
    return 0.01 + temperature * 0.08


# ---------------------------------------------------------------------------
# WordNet synonym retrieval with frequency weighting
# ---------------------------------------------------------------------------
def get_wordnet_synonyms(
    word: str,
    wn_pos: str,
    temperature: float,
    min_freq: int = 1,
) -> list[tuple[str, int]]:
    """
    Return (synonym, corpus_count) pairs from WordNet.

    Number of synsets searched scales with temperature:
      t = 0.1  →  closest synset only
      t = 1.0  →  all synsets for this word/POS

    Candidates are filtered by min_freq and deduplicated.
    Result is sorted by descending corpus count (most common first).
    """
    synsets = wn.synsets(word, pos=wn_pos)
    if not synsets:
        return []

    n_synsets = max(1, round(len(synsets) * max(temperature, 0.1)))
    pool: dict[str, int] = {}

    for synset in synsets[:n_synsets]:
        for lemma in synset.lemmas():
            candidate = lemma.name().replace("_", " ")
            if (
                candidate.lower() != word.lower()
                and " " not in candidate        # single-word only
                and candidate.isalpha()
                and lemma.count() >= min_freq
            ):
                pool[candidate] = max(pool.get(candidate, 0), lemma.count())

    return sorted(pool.items(), key=lambda kv: kv[1], reverse=True)


def frequency_weighted_choice(
    synonyms_with_counts: list[tuple[str, int]],
    temperature: float,
    rng: random.Random,
) -> str:
    """
    Sample from the synonym list using frequency-weighted probabilities.

    At low temperature the weight exponent is high, so high-frequency
    (common) synonyms dominate.  At high temperature the exponent approaches
    zero, flattening toward a uniform distribution and making rare synonyms
    reachable.

      exponent = 1.0 − (temperature × 0.85)
      t = 0.0  →  exponent = 1.00   (full frequency bias)
      t = 0.5  →  exponent = 0.575
      t = 1.0  →  exponent = 0.15   (near-uniform)

    Example at t = 0.1:
      researcher      (freq=42)  →  weight = 42^0.915  ≈  28
      investigator    (freq=12)  →  weight = 12^0.915  ≈   9
      natural philosopher (freq=1) →  weight =  1^0.915  ≈   1
    """
    if not synonyms_with_counts:
        raise ValueError("empty synonym list")

    exponent = 1.0 - (temperature * 0.85)
    words, counts = zip(*synonyms_with_counts)
    weights = [max(c, 1) ** exponent for c in counts]
    total = sum(weights)

    r = rng.random() * total
    cumulative = 0.0
    for word, w in zip(words, weights):
        cumulative += w
        if r <= cumulative:
            return word
    return words[-1]


# ---------------------------------------------------------------------------
# LLM backend
# ---------------------------------------------------------------------------
def llm_synonym(
    word: str,
    context_sentence: str,
    temperature: float,
    system_prompt: str,
) -> Optional[str]:
    """
    Ask a local or remote LLM for a contextually appropriate synonym.
    Returns None if the backend is unavailable or returns nothing useful.

    Environment variables
    ---------------------
    SYNONYM_LLM_BACKEND   "openai" | "ollama"
    OPENAI_API_KEY        required for openai backend
    OPENAI_BASE_URL       optional (e.g. for local vllm/lm-studio endpoints)
    OPENAI_MODEL          default: gpt-4o-mini
    OLLAMA_MODEL          default: mistral
    OLLAMA_HOST           default: http://localhost:11434
    """
    backend = os.environ.get("SYNONYM_LLM_BACKEND", "").lower()
    if not backend:
        return None

    user_prompt = (
        f'Give me ONE single-word synonym for "{word}" as used in this sentence:\n'
        f'"{context_sentence}"\n'
        f'Reply with only the synonym. No punctuation, no explanation.'
    )

    try:
        if backend == "openai":
            from openai import OpenAI
            client = OpenAI(
                api_key=os.environ["OPENAI_API_KEY"],
                base_url=os.environ.get("OPENAI_BASE_URL"),
            )
            resp = client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                max_tokens=10,
                temperature=temperature,
            )
            raw = resp.choices[0].message.content.strip().split()[0]
            return raw if raw.isalpha() and raw.lower() != word.lower() else None

        if backend == "ollama":
            import json, urllib.request
            host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
            payload = json.dumps({
                "model":  os.environ.get("OLLAMA_MODEL", "mistral"),
                "system": system_prompt,
                "prompt": user_prompt,
                "stream": False,
            }).encode()
            req = urllib.request.Request(
                f"{host}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                result = json.loads(r.read())
            raw = result.get("response", "").strip().split()[0]
            return raw if raw.isalpha() and raw.lower() != word.lower() else None

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Unified synonym chooser
# ---------------------------------------------------------------------------
def choose_synonym(
    word: str,
    penn_tag: str,
    context_sentence: str,
    temperature: float,
    rng: random.Random,
    profile=None,               # MutationProfile | None
    conservation=None,          # ConservationConstraint | None
    original_sentence: str = "",
) -> Optional[str]:
    """
    Choose a replacement for *word* respecting temperature, profile, and
    optional conservation constraints.

    Strategy
    --------
    t < 0.5   WordNet only, frequency-weighted conservative selection
    t ≥ 0.5   Try LLM first (contextual, profile-prompted); fall back to WordNet

    If a ConservationConstraint is provided, candidates that violate it are
    discarded before selection.
    """
    wn_pos = penn_to_wn(penn_tag)
    if wn_pos is None:
        return None

    # Profile gates
    if profile is not None:
        if not profile.is_eligible(penn_tag):
            return None
        if penn_tag.startswith("V") and not profile.allow_verb_substitution:
            return None
        min_freq = profile.min_freq_count
        llm_prompt = profile.llm_system_prompt
    else:
        min_freq = 1
        llm_prompt = "Return only the synonym word, nothing else."

    # High-temperature: try LLM first
    if temperature >= 0.5:
        llm_result = llm_synonym(word, context_sentence, temperature, llm_prompt)
        if llm_result:
            if _passes_conservation(llm_result, word, context_sentence,
                                    original_sentence, conservation):
                return llm_result

    # WordNet fallback
    synonyms = get_wordnet_synonyms(word, wn_pos, temperature, min_freq=min_freq)
    if not synonyms:
        return None

    # Apply profile register bias (Latinate / Saxon preference)
    if profile is not None:
        synonyms = profile.apply_register_bias(synonyms)
    if not synonyms:
        return None

    # Apply profile max_semantic_drift filter if embeddings available
    if profile is not None and profile.max_semantic_drift < 1.0:
        synonyms = _filter_by_drift(word, context_sentence, synonyms,
                                     profile.max_semantic_drift)
    if not synonyms:
        return None

    # Frequency-weighted selection
    return frequency_weighted_choice(synonyms, temperature, rng)


def _passes_conservation(
    candidate: str,
    original_word: str,
    context_sentence: str,
    original_sentence: str,
    conservation,
) -> bool:
    if conservation is None:
        return True
    candidate_sentence = re.sub(
        rf"\b{re.escape(original_word)}\b",
        candidate,
        context_sentence,
        count=1,
        flags=re.IGNORECASE,
    )
    ok, _ = conservation.satisfied(original_sentence or context_sentence,
                                   candidate_sentence)
    return ok


def _filter_by_drift(
    word: str,
    context_sentence: str,
    synonyms: list[tuple[str, int]],
    max_drift: float,
) -> list[tuple[str, int]]:
    """
    Remove synonyms whose substitution into context_sentence exceeds max_drift
    from the original sentence.  Requires sentence_transformers.
    """
    try:
        from semantic_budget import embed, cosine_distance
    except ImportError:
        return synonyms   # graceful degradation if embeddings unavailable

    orig_emb = embed(context_sentence)
    filtered = []
    for candidate, freq in synonyms:
        modified = re.sub(
            rf"\b{re.escape(word)}\b",
            candidate, context_sentence,
            count=1, flags=re.IGNORECASE,
        )
        cand_emb = embed(modified)
        if cosine_distance(orig_emb, cand_emb) <= max_drift:
            filtered.append((candidate, freq))
    return filtered
