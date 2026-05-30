#!/usr/bin/env python3
"""
mutation_profiles.py
--------------------
MutationProfile definitions controlling which words are eligible for
substitution, how synonyms are selected, and how LLM backends are prompted.

A profile is not merely a synonym list.  It defines:
  • which Penn Treebank POS tags are eligible
  • minimum WordNet corpus frequency for candidates
  • maximum semantic drift (hard ceiling, profile-level)
  • preference for Latinate vs. Saxon vocabulary
  • an LLM system prompt for contextual synonym generation

The same perturbation engine runs unchanged across all profiles;
only the metric and profile parameters change.

Usage
-----
    from mutation_profiles import PROFILES, get_profile
    profile = get_profile("academic")
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# MutationProfile
# ---------------------------------------------------------------------------
@dataclass
class MutationProfile:
    name: str

    # Which Penn Treebank tags are candidates for substitution.
    # Conservative profiles restrict to adjectives/adverbs; aggressive ones
    # include nouns and verbs.
    eligible_pos: frozenset = field(default_factory=frozenset)

    # WordNet lemma.count() floor.  Low-frequency synonyms are excluded below
    # this threshold at all temperatures.
    min_freq_count: int = 1

    # Hard ceiling on cosine distance for any single substitution,
    # regardless of remaining budget.
    max_semantic_drift: float = 0.20

    # Vocabulary register preferences.
    # prefer_latinate → longer, Latinate words score higher (academic, legal)
    # prefer_saxon    → shorter, Germanic words score higher (journalistic)
    # Neither set     → neutral selection
    prefer_latinate: bool = False
    prefer_saxon:    bool = False

    # LLM system prompt injected when using OpenAI / Ollama backend.
    llm_system_prompt: str = (
        "You are a careful editor. Choose synonyms that preserve the original "
        "meaning and register as closely as possible."
    )

    # Whether verbs may be substituted.  False for legal/technical profiles
    # where verb changes risk altering meaning.
    allow_verb_substitution: bool = True

    def is_eligible(self, penn_tag: str) -> bool:
        return penn_tag in self.eligible_pos

    def apply_register_bias(self, synonyms_with_freqs: list[tuple[str, int]]) -> list[tuple[str, int]]:
        """
        Re-weight candidates according to Latinate / Saxon preference.

        Heuristic: words of Latin origin tend to be longer (≥ 8 chars) and
        often end in -tion, -ence, -ity, -ous, -ate, -ive.
        Saxon-origin words tend to be shorter and monosyllabic.

        This is a rough proxy — a proper implementation would use a
        morphological dictionary.
        """
        LATINATE_SUFFIXES = ("tion", "ence", "ity", "ous", "ate", "ive", "ment", "ance")
        SAXON_PREFERENCE_MAX_LEN = 6

        if not self.prefer_latinate and not self.prefer_saxon:
            return synonyms_with_freqs

        result = []
        for word, freq in synonyms_with_freqs:
            w = word.lower()
            is_latinate = len(word) >= 8 or w.endswith(LATINATE_SUFFIXES)
            is_saxon    = len(word) <= SAXON_PREFERENCE_MAX_LEN

            if self.prefer_latinate and is_latinate:
                result.append((word, freq * 3))
            elif self.prefer_saxon and is_saxon:
                result.append((word, freq * 3))
            else:
                result.append((word, freq))

        return result


# ---------------------------------------------------------------------------
# Profile definitions
# ---------------------------------------------------------------------------

# Penn Treebank tag sets
_ALL_CONTENT = frozenset({
    "NN", "NNS", "NNP", "NNPS",
    "VB", "VBD", "VBG", "VBN", "VBP", "VBZ",
    "JJ", "JJR", "JJS",
    "RB", "RBR", "RBS",
})
_NO_VERBS = frozenset({
    "NN", "NNS", "NNP", "NNPS",
    "JJ", "JJR", "JJS",
    "RB", "RBR", "RBS",
})
_ADJ_ADV_ONLY = frozenset({
    "JJ", "JJR", "JJS",
    "RB", "RBR", "RBS",
})
_VERBS_AND_ADJ = frozenset({
    "VB", "VBD", "VBG", "VBN", "VBP", "VBZ",
    "JJ", "JJR", "JJS",
    "RB", "RBR", "RBS",
})


PROFILES: dict[str, MutationProfile] = {

    # ------------------------------------------------------------------
    "academic": MutationProfile(
        name                  = "academic",
        eligible_pos          = _ALL_CONTENT,
        min_freq_count        = 2,
        max_semantic_drift    = 0.12,
        prefer_latinate       = True,
        prefer_saxon          = False,
        allow_verb_substitution = True,
        llm_system_prompt     = (
            "You are an academic writing assistant. "
            "Choose formal, precise synonyms appropriate for peer-reviewed "
            "scientific or humanities writing. "
            "Prefer Latinate vocabulary over Germanic equivalents. "
            "Maintain register consistency. "
            "Return only the synonym word, nothing else."
        ),
    ),

    # ------------------------------------------------------------------
    "journalistic": MutationProfile(
        name                  = "journalistic",
        eligible_pos          = _VERBS_AND_ADJ,
        min_freq_count        = 10,    # high-frequency only — no obscure words
        max_semantic_drift    = 0.08,
        prefer_latinate       = False,
        prefer_saxon          = True,
        allow_verb_substitution = True,
        llm_system_prompt     = (
            "You are a newspaper style editor. "
            "Choose clear, direct, short synonyms appropriate for AP-style journalism. "
            "Prefer Germanic vocabulary and short Anglo-Saxon words. "
            "Avoid jargon, Latinate constructions, and academic register. "
            "Return only the synonym word, nothing else."
        ),
    ),

    # ------------------------------------------------------------------
    "creative": MutationProfile(
        name                  = "creative",
        eligible_pos          = _ALL_CONTENT,
        min_freq_count        = 1,    # rare words are welcome
        max_semantic_drift    = 0.25,
        prefer_latinate       = False,
        prefer_saxon          = False,
        allow_verb_substitution = True,
        llm_system_prompt     = (
            "You are a literary editor working on fiction or creative non-fiction. "
            "Choose vivid, evocative synonyms that add texture and imagery. "
            "Unusual, archaic, or highly specific words are welcome. "
            "Prefer sensory and concrete language over abstract generalizations. "
            "Return only the synonym word, nothing else."
        ),
    ),

    # ------------------------------------------------------------------
    "legal": MutationProfile(
        name                  = "legal",
        eligible_pos          = _NO_VERBS,    # verb changes dangerous in legal text
        min_freq_count        = 5,
        max_semantic_drift    = 0.06,          # extremely tight drift tolerance
        prefer_latinate       = True,
        prefer_saxon          = False,
        allow_verb_substitution = False,
        llm_system_prompt     = (
            "You are a legal editor reviewing formal legal documents. "
            "Choose synonyms with IDENTICAL legal meaning. "
            "When in doubt, do not substitute — return the original word. "
            "Never introduce ambiguity. "
            "Only modify nouns, adjectives, and adverbs; never verbs. "
            "Return only the synonym word, nothing else."
        ),
    ),

    # ------------------------------------------------------------------
    "technical": MutationProfile(
        name                  = "technical",
        eligible_pos          = _ADJ_ADV_ONLY,  # safest: only modifiers
        min_freq_count        = 3,
        max_semantic_drift    = 0.07,
        prefer_latinate       = False,
        prefer_saxon          = False,
        allow_verb_substitution = False,
        llm_system_prompt     = (
            "You are a technical writing editor for engineering documentation. "
            "Choose synonyms that preserve precise technical meaning exactly. "
            "Never introduce ambiguity or alter quantitative implications. "
            "Only replace adjectives and adverbs; leave nouns and verbs unchanged. "
            "Return only the synonym word, nothing else."
        ),
    ),

    # ------------------------------------------------------------------
    "neutral": MutationProfile(
        name                  = "neutral",
        eligible_pos          = _ALL_CONTENT,
        min_freq_count        = 1,
        max_semantic_drift    = 0.20,
        prefer_latinate       = False,
        prefer_saxon          = False,
        allow_verb_substitution = True,
        llm_system_prompt     = (
            "You are a careful editor. "
            "Choose synonyms that preserve the original meaning and register. "
            "Return only the synonym word, nothing else."
        ),
    ),
}


def get_profile(name: str) -> MutationProfile:
    name = name.lower()
    if name not in PROFILES:
        available = ", ".join(PROFILES.keys())
        raise ValueError(f"Unknown profile '{name}'. Available: {available}")
    return PROFILES[name]


def list_profiles() -> list[str]:
    return list(PROFILES.keys())
