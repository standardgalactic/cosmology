# DocPerturb — Document-Space Perturbation Engine

Generates semantically constrained alternate versions of documents by treating
mutation as constrained optimization over a semantic fiber bundle.

## Conceptual framing

A document D₀ exists at a point m on the semantic identity manifold M under the
projection π : X → M where X is the space of all syntactically valid documents.
The fiber π⁻¹(m) is the equivalence class of all documents that "mean the same
thing." The perturbation engine explores this fiber subject to:

    maximize(variation)
    subject to:
        metric.distance(D₀, Dₙ)    ≤ budget.axis_budget   (total displacement)
        metric.distance(Dₖ₋₁, Dₖ)  ≤ budget.max_step      (curvature control)
        conservation.satisfied(D₀, Dₙ)                     (pinned concepts)

Temperature is a derived quantity — a scalar summary of the budget vector and
step-size constraint, convenient for interfaces but not fundamental.

## File map

```
semantic_budget.py       Core abstractions: SemanticMetric, SemanticBudget,
                         BudgetTracker, ConservationConstraint, FiberExplorer

mutation_profiles.py     MutationProfile definitions (academic, journalistic,
                         creative, legal, technical, neutral)

synonym_engine.py        Synonym retrieval: WordNet frequency-weighted selection
                         + optional LLM backend (OpenAI / Ollama)

perturbation_engine.py   Three-pass mutation engine (lexical / syntactic /
                         semantic), PerturbationEngine public API

docperturb_cli.py        Full-featured CLI with budget, profile, vector temp,
                         conservation constraints, JSON output

synonym_randomizer.py    Compatibility layer; standalone or engine-backed

synonym_randomizer_ui.jsx  React frontend with budget display, profile selector,
                            temperature vector editor, drift trajectory visualizer
```

## Installation

```bash
pip install nltk

# Recommended (for drift filtering and budget tracking):
pip install sentence-transformers

# Optional LLM backend:
pip install openai
```

NLTK data downloads automatically on first run.

## Quick start

```bash
# Standalone (no extra dependencies beyond nltk):
python synonym_randomizer.py input.txt

# Full engine, academic profile, protected terms:
python docperturb_cli.py input.txt \
    -p academic \
    --protect "RSVP,Friedmann,TARTAN" \
    -t 0.6 \
    -n 5 \
    -o variants/

# Multi-axis temperature vector:
python docperturb_cli.py input.txt \
    --tv-lexical 0.8 \
    --tv-syntactic 0.3 \
    --tv-semantic 0.1

# Sampled temperature pool (reference implementation style):
python docperturb_cli.py input.txt -n 20 -T 0.1,0.3,0.5,0.7,0.9 -o variants/

# LLM-assisted high-temperature (OpenAI-compatible):
SYNONYM_LLM_BACKEND=openai \
OPENAI_API_KEY=sk-... \
    python docperturb_cli.py input.txt -t 0.9 -p creative

# LLM-assisted (Ollama local):
SYNONYM_LLM_BACKEND=ollama \
OLLAMA_MODEL=mistral \
    python docperturb_cli.py input.txt -t 0.8 -p academic

# JSON output for downstream processing:
python docperturb_cli.py input.txt -n 3 --json | jq '.changes[] | .original + " → " + .replacement'

# Explicit budget override:
python docperturb_cli.py input.txt \
    --budget-lexical 0.03 \
    --budget-syntactic 0.06 \
    --budget-semantic 0.10 \
    --max-step 0.015
```

## Python API

```python
from perturbation_engine import PerturbationEngine
from semantic_budget import (
    SemanticBudget, SemanticMetric, TemperatureVector, ConservationConstraint
)

# Basic usage
engine = PerturbationEngine(profile="academic")
result = engine.mutate(text, temperature=0.6)
print(result.text)
print(f"{len(result.changes)} substitutions, {result.utilisation*100:.0f}% budget used")

# Multi-axis temperature vector
from semantic_budget import TemperatureVector
tv = TemperatureVector(lexical=0.8, syntactic=0.3, semantic=0.1)
result = engine.mutate(text, temp_vector=tv)

# Conservation constraint (pins protected concepts)
conservation = ConservationConstraint(
    protected_phrases=["RSVP", "Friedmann equation", "central thesis"],
    epsilon=0.05,
)
engine = PerturbationEngine(profile="academic", conservation=conservation)

# Explicit budget
budget = SemanticBudget(lexical=0.03, syntactic=0.06, semantic=0.10, max_step=0.015)
engine = PerturbationEngine(profile="creative", budget=budget)

# Batch generation
results = engine.generate_versions(
    text,
    n=10,
    temperatures=[0.1, 0.3, 0.5, 0.7, 0.9],   # sampled per version
    base_seed=42,
)

# Custom metric (profile-dependent distance)
from semantic_budget import SemanticMetric
metric = SemanticMetric.from_contrastive_pairs(
    pairs=[("formal academic prose", "casual spoken language")],
    amplify=4.0,
    name="formality_amplified",
)
engine = PerturbationEngine(profile="academic", metric=metric)
```

## Temperature guide

| Temperature | Label       | Strategy                                   | Budget (lexical) |
|-------------|-------------|-------------------------------------------|------------------|
| 0.0         | Frozen      | No substitutions                          | 0.000            |
| 0.25        | Subtle      | Shortest synonyms, steep frequency bias   | 0.025            |
| 0.50        | Moderate    | Mid pool, moderate frequency bias         | 0.050            |
| 0.75        | Aggressive  | Wide pool, LLM-first if configured        | 0.075            |
| 1.0         | Maximum     | Full breadth, near-uniform sampling       | 0.100            |

## Profile comparison

| Profile      | Eligible POS     | Max drift | Register preference | Verb substitution |
|--------------|-----------------|-----------|--------------------|--------------------|
| neutral      | all content     | 0.20      | none               | yes                |
| academic     | all content     | 0.12      | Latinate           | yes                |
| journalistic | verbs + adj/adv | 0.08      | Saxon/short        | yes                |
| creative     | all content     | 0.25      | none (vivid)       | yes                |
| legal        | nouns + adj/adv | 0.06      | Latinate           | NO                 |
| technical    | adj/adv only    | 0.07      | none               | NO                 |

## LLM environment variables

| Variable              | Default               | Description                       |
|-----------------------|-----------------------|-----------------------------------|
| SYNONYM_LLM_BACKEND   | (empty = WordNet only)| "openai" or "ollama"              |
| OPENAI_API_KEY        | required for openai   | API key                           |
| OPENAI_BASE_URL       | api.openai.com        | Override for local endpoints      |
| OPENAI_MODEL          | gpt-4o-mini           | Model name                        |
| OLLAMA_HOST           | http://localhost:11434| Ollama server URL                 |
| OLLAMA_MODEL          | mistral               | Ollama model name                 |

## Applications

**Deduplication testing** — Generate a family of documents at calibrated distances
from the original. A test suite covering the full budget range reveals where a
deduplication system's decision boundary falls and characterizes its geometry.

**RAG robustness evaluation** — Perturb queries and source documents independently;
measure retrieval stability across the fiber. Low-temperature perturbations should
not change retrieval rank; high-temperature perturbations reveal the system's
semantic sensitivity.

**Synthetic training data** — Generate labeled pairs (original, perturbation) at
known semantic distances. The budget parameterizes the label: documents within
budget X are "equivalent," documents beyond it are "different."

**Plagiarism detection evaluation** — Systematic exploration of the fiber near a
document provides calibrated ground-truth for detector sensitivity analysis.

**Style transfer evaluation** — Profile-specific metrics define different notions
of register distance, enabling measurement of how far a style-transfer system has
moved along the intended stylistic axis vs. unintended semantic drift.
