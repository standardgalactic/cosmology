#!/usr/bin/env python3
"""
semantic_budget.py
------------------
Core abstractions for document-space perturbation as a constrained
optimization problem over a semantic fiber bundle.

Concepts
--------
SemanticMetric      — profile-dependent metric tensor on embedding space
SemanticBudget      — multi-axis budget vector (lexical / syntactic / semantic)
BudgetTracker       — stateful tracker measuring drift and curvature along a
                      document trajectory D₀ → D₁ → D₂ → …
ConservationConstraint — holonomic constraint pinning protected concepts
TemperatureVector   — convenience wrapper converting scalar temp to budget vector

Dependencies
------------
  pip install sentence-transformers numpy torch
"""

from __future__ import annotations

import numpy as np
import torch
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Lazy-loaded embedding model (singleton)
# ---------------------------------------------------------------------------
_EMBED_MODEL = None
_EMBED_DIM   = 384   # all-MiniLM-L6-v2 output dimension

def get_embedding_model(model_name: str = "all-MiniLM-L6-v2"):
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _EMBED_MODEL = SentenceTransformer(model_name)
    return _EMBED_MODEL

def embed(text: str) -> np.ndarray:
    model = get_embedding_model()
    return model.encode(text, convert_to_numpy=True, normalize_embeddings=True)

def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """1 − cosine_similarity.  Range [0, 2]; identical → 0."""
    return float(1.0 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


# ---------------------------------------------------------------------------
# SemanticMetric  — profile-dependent metric tensor
# ---------------------------------------------------------------------------
@dataclass
class SemanticMetric:
    """
    Distance on embedding space defined by a positive semi-definite matrix M:

        d(a, b) = sqrt((a − b)ᵀ M (a − b))

    The identity matrix recovers standard Euclidean distance.
    Learned or hand-specified M encodes a profile's notion of semantic proximity.

    Profiles differ not just in which words they choose but in which *directions*
    of meaning-change are cheap vs. expensive.  An academic metric amplifies
    distance along the formality axis; a literary metric amplifies distance along
    the affect axis.  The same perturbation engine works unchanged — only the
    metric changes.
    """
    name: str
    matrix: np.ndarray          # (dim, dim) PSD matrix
    protected_axes: list[np.ndarray] = field(default_factory=list)

    def distance(self, emb_a: np.ndarray, emb_b: np.ndarray) -> float:
        delta = emb_a - emb_b
        return float(np.sqrt(np.maximum(0.0, delta @ self.matrix @ delta)))

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------
    @classmethod
    def identity(cls, name: str = "neutral", dim: int = _EMBED_DIM) -> "SemanticMetric":
        return cls(name=name, matrix=np.eye(dim))

    @classmethod
    def from_axis_weights(
        cls,
        axes: list[np.ndarray],
        weights: list[float],
        name: str,
        dim: int = _EMBED_DIM,
    ) -> "SemanticMetric":
        """
        Amplify distance along embedding directions derived from labeled corpora.
        weight > 1  →  movements along that axis are "expensive"
        weight < 1  →  movements along that axis are "cheap"

        Axes can be learned by:
          axis = mean(embed(formal_docs)) − mean(embed(informal_docs))
          axis /= np.linalg.norm(axis)
        """
        M = np.eye(dim)
        for ax, w in zip(axes, weights):
            ax = np.asarray(ax, dtype=float)
            ax = ax / (np.linalg.norm(ax) + 1e-10)
            M += (w - 1.0) * np.outer(ax, ax)
        return cls(name=name, matrix=M, protected_axes=axes)

    @classmethod
    def from_contrastive_pairs(
        cls,
        pairs: list[tuple[str, str]],
        amplify: float = 3.0,
        name: str = "contrastive",
        dim: int = _EMBED_DIM,
    ) -> "SemanticMetric":
        """
        Learn axes from (register_a, register_b) text pairs.
        Each pair contributes one axis along the direction register_a − register_b.
        """
        axes, weights = [], []
        for a_text, b_text in pairs:
            a_emb = embed(a_text)
            b_emb = embed(b_text)
            axis  = a_emb - b_emb
            norm  = np.linalg.norm(axis)
            if norm > 1e-6:
                axes.append(axis / norm)
                weights.append(amplify)
        return cls.from_axis_weights(axes, weights, name=name, dim=dim)


# ---------------------------------------------------------------------------
# Pre-built profile metrics  (identity baselines; replace axes with learned ones)
# ---------------------------------------------------------------------------
def academic_metric(dim: int = _EMBED_DIM) -> SemanticMetric:
    """
    Placeholder — amplify formality axis if learned embeddings are available.
    Falls back to identity; replace axis with:
        mean(embed(formal_corpora)) − mean(embed(casual_corpora)), normalised.
    """
    return SemanticMetric.identity(name="academic", dim=dim)

def literary_metric(dim: int = _EMBED_DIM) -> SemanticMetric:
    return SemanticMetric.identity(name="literary", dim=dim)

def journalistic_metric(dim: int = _EMBED_DIM) -> SemanticMetric:
    return SemanticMetric.identity(name="journalistic", dim=dim)

def legal_metric(dim: int = _EMBED_DIM) -> SemanticMetric:
    return SemanticMetric.identity(name="legal", dim=dim)

def technical_metric(dim: int = _EMBED_DIM) -> SemanticMetric:
    return SemanticMetric.identity(name="technical", dim=dim)


# ---------------------------------------------------------------------------
# SemanticBudget  — multi-axis budget vector
# ---------------------------------------------------------------------------
@dataclass
class SemanticBudget:
    """
    Three-axis budget controlling independent transformation passes.

    lexical   : word-level synonym swaps          Δ ≈ 0.002 per swap
    syntactic : sentence restructuring             Δ ≈ 0.010 per operation
    semantic  : full clause / sentence paraphrase  Δ ≈ 0.025 per operation

    Total budget is not simply the sum; the three passes interact because each
    consumes part of the total semantic distance from the original.

    Operator cost estimates (empirical, all-MiniLM-L6-v2, cosine distance):
        word swap (common synonym)      0.001–0.004
        word swap (rare synonym)        0.004–0.012
        active ↔ passive               0.008–0.015
        clause reordering              0.010–0.020
        sentence paraphrase (LLM)      0.015–0.040
    """
    lexical:   float = 0.05
    syntactic: float = 0.08
    semantic:  float = 0.12
    max_step:  float = 0.025   # curvature control: largest single mutation allowed

    @classmethod
    def from_scalar(cls, t: float) -> "SemanticBudget":
        """Backward-compatible scalar → budget vector conversion."""
        return cls(
            lexical   = t * 0.10,
            syntactic = t * 0.15,
            semantic  = t * 0.20,
            max_step  = 0.005 + t * 0.045,
        )

    @property
    def total(self) -> float:
        return self.lexical + self.syntactic + self.semantic


# ---------------------------------------------------------------------------
# TemperatureVector  — multi-axis temperature for multi-pass mutation
# ---------------------------------------------------------------------------
@dataclass
class TemperatureVector:
    """
    Each axis controls one transformation pass independently.

    lexical_temperature   — synonym selection breadth (0 = shortest, 1 = widest pool)
    syntactic_temperature — probability of sentence-level restructuring
    semantic_temperature  — aggressiveness of LLM paraphrase when invoked

    From a scalar temperature:
        lexical   = t
        syntactic = t × 0.4   (structural changes are rarer)
        semantic  = t × 0.2   (full paraphrase is expensive, used sparingly)
    """
    lexical:   float = 0.5
    syntactic: float = 0.2
    semantic:  float = 0.1

    @classmethod
    def from_scalar(cls, t: float) -> "TemperatureVector":
        return cls(
            lexical   = t,
            syntactic = t * 0.4,
            semantic  = t * 0.2,
        )

    def to_budget(self) -> SemanticBudget:
        return SemanticBudget.from_scalar(
            (self.lexical + self.syntactic + self.semantic) / 3
        )


# ---------------------------------------------------------------------------
# BudgetTracker  — trajectory-aware drift and curvature accounting
# ---------------------------------------------------------------------------
class BudgetTracker:
    """
    Tracks the document trajectory D₀ → D₁ → D₂ → … in embedding space,
    enforcing both total-budget and max-step-size constraints.

    Total budget  : distance(D₀, Dₙ) ≤ budget.total
    Curvature     : distance(Dₙ₋₁, Dₙ) ≤ budget.max_step

    Additionally tracks the convex hull of visited embeddings (approximated
    as the set of already-visited points) to discourage oscillatory trajectories
    that consume budget without exploring new regions of the fiber.
    """

    def __init__(
        self,
        original_text: str,
        budget: SemanticBudget,
        metric: SemanticMetric,
        axis: str = "lexical",   # which budget axis this tracker draws from
    ):
        self.budget      = budget
        self.metric      = metric
        self.axis        = axis
        self.origin_emb  = embed(original_text)
        self.current_emb = self.origin_emb.copy()
        self.spent       = 0.0
        self.step_count  = 0
        self.history: list[np.ndarray] = [self.origin_emb.copy()]

    # ------------------------------------------------------------------
    # Budget axis limit
    # ------------------------------------------------------------------
    @property
    def axis_budget(self) -> float:
        return getattr(self.budget, self.axis)

    @property
    def remaining(self) -> float:
        return max(0.0, self.axis_budget - self.spent)

    # ------------------------------------------------------------------
    # Prospective checks (non-mutating)
    # ------------------------------------------------------------------
    def would_exceed_total(self, candidate_text: str) -> bool:
        cand_emb = embed(candidate_text)
        drift = self.metric.distance(self.origin_emb, cand_emb)
        return drift > self.axis_budget

    def would_exceed_step(self, candidate_text: str) -> bool:
        cand_emb = embed(candidate_text)
        step = self.metric.distance(self.current_emb, cand_emb)
        return step > self.budget.max_step

    def is_in_explored_region(self, candidate_text: str, tolerance: float = 0.005) -> bool:
        """
        Returns True if the candidate lands very close to an already-visited
        point — indicating an oscillatory / unproductive mutation.
        """
        cand_emb = embed(candidate_text)
        for visited in self.history:
            if cosine_distance(cand_emb, visited) < tolerance:
                return True
        return False

    def admit(self, candidate_text: str) -> tuple[bool, str]:
        """
        Full admission check.  Returns (admitted, reason).
        Reason is non-empty only on rejection.
        """
        cand_emb = embed(candidate_text)
        total_drift = self.metric.distance(self.origin_emb, cand_emb)
        step_drift  = self.metric.distance(self.current_emb, cand_emb)

        if total_drift > self.axis_budget:
            return False, f"total drift {total_drift:.4f} exceeds budget {self.axis_budget:.4f}"
        if step_drift > self.budget.max_step:
            return False, f"step size {step_drift:.4f} exceeds max_step {self.budget.max_step:.4f}"
        return True, ""

    # ------------------------------------------------------------------
    # Commit a mutation (mutating)
    # ------------------------------------------------------------------
    def commit(self, new_text: str) -> float:
        """
        Commit a mutation that has already passed admit().
        Returns the step drift consumed.
        """
        new_emb    = embed(new_text)
        step_drift = self.metric.distance(self.current_emb, new_emb)
        total_drift = self.metric.distance(self.origin_emb, new_emb)

        self.spent       = total_drift   # track absolute from origin, not cumulative
        self.current_emb = new_emb
        self.step_count += 1
        self.history.append(new_emb.copy())
        return step_drift

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def summary(self) -> dict:
        return {
            "axis":         self.axis,
            "budget":       self.axis_budget,
            "spent":        self.spent,
            "remaining":    self.remaining,
            "steps":        self.step_count,
            "max_step":     self.budget.max_step,
            "utilisation":  self.spent / (self.axis_budget + 1e-10),
        }


# ---------------------------------------------------------------------------
# ConservationConstraint  — holonomic constraint on protected concepts
# ---------------------------------------------------------------------------
class ConservationConstraint:
    """
    Pins protected concepts in the document.

    Every mutation must satisfy:

        |proj(protected_axis, original) − proj(protected_axis, candidate)| < ε

    regardless of remaining budget.  This prevents high-temperature runs from
    accidentally mutating the document's core argument, framework names, or
    technical claims.

    Protected concepts can be specified as:
      • raw strings  (embedded on construction)
      • pre-computed embedding vectors

    For framework-heavy documents (RSVP, TARTAN, CLIO, etc.) pass the framework
    names and key theoretical claims as protected phrases.
    """

    def __init__(
        self,
        protected_phrases: list[str] = (),
        protected_embeddings: list[np.ndarray] = (),
        epsilon: float = 0.05,
    ):
        self.epsilon = epsilon
        self.axes: list[np.ndarray] = list(protected_embeddings)
        for phrase in protected_phrases:
            emb = embed(phrase)
            emb = emb / (np.linalg.norm(emb) + 1e-10)
            self.axes.append(emb)

    def _project(self, text_emb: np.ndarray, axis: np.ndarray) -> float:
        """Scalar projection of document embedding onto protected axis."""
        return float(np.dot(text_emb, axis))

    def satisfied(
        self,
        original_text: str,
        candidate_text: str,
        original_emb: Optional[np.ndarray] = None,
    ) -> tuple[bool, list[float]]:
        """
        Returns (satisfied, list_of_violations).
        violations is a list of |Δprojection| values, one per protected axis.
        Empty violations list means all constraints satisfied.
        """
        orig_emb = original_emb if original_emb is not None else embed(original_text)
        cand_emb = embed(candidate_text)

        violations = []
        for axis in self.axes:
            orig_proj = self._project(orig_emb, axis)
            cand_proj = self._project(cand_emb, axis)
            delta = abs(orig_proj - cand_proj)
            if delta > self.epsilon:
                violations.append(delta)

        return len(violations) == 0, violations

    def add_phrase(self, phrase: str) -> None:
        emb = embed(phrase)
        emb = emb / (np.linalg.norm(emb) + 1e-10)
        self.axes.append(emb)


# ---------------------------------------------------------------------------
# FiberExplorer  — unified interface combining tracker + conservation
# ---------------------------------------------------------------------------
class FiberExplorer:
    """
    Explores the semantic fiber π⁻¹(m) of a document.

    Two documents are considered equivalent (in the same fiber) if they project
    to approximately the same semantic representation under the given metric.
    The budget parameterises how far within the fiber a mutation is allowed to go.

    Usage
    -----
    explorer = FiberExplorer(
        original_text    = text,
        budget           = SemanticBudget.from_scalar(0.7),
        metric           = academic_metric(),
        conservation     = ConservationConstraint(["RSVP", "central thesis"], epsilon=0.05),
    )

    # Test a candidate mutation
    ok, reason = explorer.admit(candidate_text)

    # Commit if admitted
    if ok:
        explorer.commit(candidate_text)
    """

    def __init__(
        self,
        original_text: str,
        budget: SemanticBudget,
        metric: SemanticMetric,
        conservation: Optional[ConservationConstraint] = None,
        axis: str = "lexical",
    ):
        self.tracker      = BudgetTracker(original_text, budget, metric, axis)
        self.conservation = conservation
        self.original_emb = self.tracker.origin_emb.copy()

    def admit(self, candidate_text: str) -> tuple[bool, str]:
        ok, reason = self.tracker.admit(candidate_text)
        if not ok:
            return False, reason

        if self.conservation is not None:
            cons_ok, violations = self.conservation.satisfied(
                "", candidate_text, original_emb=self.original_emb
            )
            if not cons_ok:
                return False, f"conservation violated: max Δ={max(violations):.4f}"

        return True, ""

    def commit(self, new_text: str) -> float:
        return self.tracker.commit(new_text)

    def summary(self) -> dict:
        return self.tracker.summary()
