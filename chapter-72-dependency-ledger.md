# Chapter 72 Dependency Ledger

## Audit checkpoint for the cosmological recurrence and reknotting program

**Status:** Frozen checkpoint before the generic reknotting toy calculation  
**Date:** August 2026

## How We Got Here

This dependency structure emerged while developing Chapter 36 of the cosmology monograph. The initial physical intuition was that matter and other localized structure could be understood as capacity temporarily “tied up in knots,” with a primordial smooth state differentiating into particles, stars, galaxies, filaments, and voids before late-time smoothing eventually removes the accessible distinctions required for useful work. Trying to turn the proposed terminal “reknotting” of a smooth universe into an actual calculation exposed several dependencies on earlier RSVP formulations. In particular, the claim required real variational grounding for localized matter, a defensible persistence principle across localization and delocalization, and a precise meaning of recursive stability under TARTAN coarse-graining. This led to a two-stage corpus audit: Stage 1 reconciled the variational, dissipative, AKSZ, and gauge-gravity formulations as far as the existing work permits; Stage 2 examined TARTAN's behavior under cosmological dilation and tested its literal fixed-point definition. The result is the dependency structure recorded here. It should be treated as the frozen starting point for subsequent calculations rather than reconstructed from the exploratory discussion.

## 1. Persistence Postulate

The recurrence architecture requires a persistence hypothesis of the form

\[
\mathcal H_{\mathrm{fund}}(S_0)\simeq\mathcal H_{\mathrm{fund}}(S_*),
\]

where \(S_0\) denotes the primordial smooth regime and \(S_*\) the candidate terminal smooth regime.

This is **an explicit hypothesis, not an established theorem of RSVP**.

The minimal closed variational RSVP sector has ordinary on-shell conservation, but it does not contain all of the dissipative and constitutive physics used elsewhere in the cosmological model. The phenomenological lamphrodynamic sector contains entropy production, diffusion, nonlinear repair, and related effects, but no complete closed variational description of the degrees of freedom receiving the corresponding exchange has yet been established.

The logical hierarchy must therefore remain explicit:

\[
\text{local conservation}
\not\Rightarrow
\text{closure of effective field content}
\not\Rightarrow
\text{persistence over the full cosmological trajectory}.
\]

### RSVP Closure Problem

**Open problem.** Determine whether there exists a closed variational completion whose effective limit reproduces the dissipative lamphrodynamic equations while retaining all fundamental degrees of freedom.

This has the same logical form as the information question raised by black-hole evaporation: an apparently dissipative effective description cannot establish fundamental persistence unless the apparently lost distinctions are represented somewhere in the complete state space. The two problems are physically distinct, but recurrence depends on closure at both levels.

A Schwinger–Keldysh, reservoir-field, or comparable dissipative variational completion is outside the scope of the present cosmology monograph unless independently developed elsewhere.

## 2. Source Corrections Identified During Stage 1

These corrections are independent of the cosmological recurrence claim and should be filed against the relevant RSVP source documents.

First, the Chapter 5/Chapter 8 presentation of the AKSZ/minimal action contains a sign-convention discrepancy that must be corrected or explicitly reconciled.

Second, the Chapter 8 canonical stress tensor is not generically symmetric merely by virtue of being the displayed canonical tensor. Any symmetry claim requires an appropriate Hilbert definition, Belinfante-type improvement, or additional argument.

Third, the Volume II tensor \(\Theta_{\mu\nu}\) has not been established as separately conserved off shell. A possible exchange relation of the form

\[
\nabla^\mu\Theta_{\mu\nu}=8\pi G\,E_\nu
\]

remains a candidate reconciliation rather than a proved identity.

### Variational Traceability Principle

Every term appearing in a claimed field equation must have an identifiable variational ancestor in the displayed action, and every non-topological term in the displayed action must have a corresponding Euler–Lagrange consequence.

This principle should be stated explicitly as a methodological commitment in the monograph rather than used only as an audit device.

## 3. AKSZ and Gauge-Gravity/Palatini Relationship

Stage 1A produced a **conditional transport-sector embedding**, not a proof of full theory equivalence.

An augmented RSVP transport Lagrangian containing symmetric scalar advection,

\[
\mathcal L_{\rm adv}
\supset
-\nu v_\mu v^\mu
+\lambda v^\mu\nabla_\mu\Phi
+\gamma v^\mu\nabla_\mu S,
\]

gives, upon variation with respect to the auxiliary transport field,

\[
2\nu v_\mu
=
\lambda\nabla_\mu\Phi+\gamma\nabla_\mu S
\]

up to the chosen metric/sign conventions. Thus the auxiliary-field limit reproduces the AKSZ-type transport law with effective ratios

\[
\beta=\frac{\lambda}{2\nu},
\qquad
\alpha=\frac{\gamma}{2\nu}.
\]

This explains the earlier rank-one degeneracy as an expected feature of eliminating an auxiliary field rather than, by itself, a pathology.

It does **not** establish equivalence of the complete AKSZ and gauge-gravity/Palatini theories. The cosmology monograph therefore uses the gauge-gravity/Palatini branch as its load-bearing covariant formulation, while the AKSZ BV/categorical machinery remains only partially connected.

## 4. TARTAN Scale Covariance

For bare spectral TARTAN coarse-graining, cosmological dilation and recursive projection are distinct operations but can be equivariant.

If

\[
(\mathcal D_\lambda X)(x)=X(x/\lambda),
\]

then Laplacian eigenvalues scale as

\[
\mu_k\mapsto\lambda^{-2}\mu_k.
\]

For a physical coarse-graining length \(\ell\), the appropriate relation is

\[
\boxed{
\mathcal R_{\lambda\ell}\mathcal D_\lambda
=
\mathcal D_\lambda\mathcal R_\ell.
}
\]

Thus cosmic expansion is not identified with smoothing or coarse-graining. Rather, TARTAN projection transforms consistently when its resolution scale is transformed with the cosmological dilation.

Under the standard assumption that entropy \(S\) transforms as a dimensionless scalar, the same scaling behavior is compatible with an entropy-weighted operator of the schematic form

\[
\widetilde\Delta=e^{-S}\Delta.
\]

However, the functional-analytic status and physical derivation of the entropy-weighted spectral construction remain incomplete and must not be treated as established merely because it is dilation-covariant.

**Status:** scale covariance/equivariance established for the bare spectral construction; entropy-weighted physical interpretation remains conditional.

## 5. Failure of the Literal TARTAN Fixed-Point Definition

Let

\[
X=\sum_k a_k\psi_k
\]

and let \(\mathcal R_N\) be successively coarser spectral projections. Literal recursive stability,

\[
\mathcal R_NX=X
\qquad\text{for every admissible }N,
\]

requires

\[
X\in\bigcap_N\operatorname{Ran}(\mathcal R_N).
\]

For ordinary nested spectral truncation this intersection reduces to the modes retained at every resolution. On a connected compact domain with the usual scalar Laplacian, this is generically the zero/constant eigenspace:

\[
\operatorname{Fix}_{\rm literal}
\simeq
\ker\Delta
=
\operatorname{span}\{1\},
\]

subject to boundary conditions and field-bundle zero modes.

The literal definition therefore cannot generically represent localized particles or defects as recursively stable objects.

**Status:** literal fixed-point definition fails for the intended matter interpretation.

## 6. Repaired Recursive Persistence

The replacement is not exact field equality under every projection but preservation of independently specified physical invariants.

For invariants \(\mathcal I_a\), define recursive persistence over an admissible interval \(I_X\) by

\[
\boxed{
\mathcal I_a[\mathcal R_\ell X]
=
\mathcal I_a[X]
\quad
\forall a,\;\ell\in I_X.
}
\]

Equivalently,

\[
[\mathcal R_\ell X]_{\mathcal A}
=
[X]_{\mathcal A}.
\]

Possible invariants include topological charge, genuine gauge charge, defect number, admissibility class, or other quantities independently justified for the sector.

The equivalence relation must be minimal. Arbitrary field redefinitions or arbitrary equivalences cannot be admitted merely to preserve a desired fixed point. Gauge transformations, dilations, and other transformations belong in the quotient only insofar as independently chosen observables establish their physical equivalence.

A localized toy profile demonstrates that this construction avoids both extremes: ordinary spectral truncation changes the detailed field profile, so literal equality fails, while preservation of a nonzero topological invariant can distinguish a defect sector from the homogeneous \(Q=0\) sector.

**Status:** toy-model validation obtained; general construction remains open.

### Admissible Resolution Interval Problem

The interval \(I_X\) must eventually be determined independently rather than retrospectively defined as the range over which the desired invariant happens to survive.

A predictive construction may require independently specified bounds involving localization length, resolution, charge fidelity, admissibility conditions, and energy barriers between sectors.

This is an explicit prerequisite for Chapter 74 numerics.

## 7. Three-Gate Reknotting Criterion

The central result of the audit is that reknotting cannot be identified with instability alone.

\[
\boxed{
\text{Reknotting}
=
\text{dynamical instability}
\cap
\text{recursive accessibility}
\cap
\text{nonlinear persistence}.
}
\]

### Gate I: Dynamical Instability

Let \(h_\alpha(t)\) denote the relevant eigenvalue of the energy Hessian or dynamical stability operator around the smooth background.

The instability boundary is

\[
h_\alpha(t)=0.
\]

With the convention used here,

\[
h_\alpha(t)<0
\]

denotes a direction in which the smooth configuration has lost local energetic stability.

### Gate II: Recursive Accessibility

Let \(\mu_\alpha(t)\) denote the spectral quantity governing whether the corresponding structure lies within the TARTAN-resolved sector, with resolution cutoff \(\Lambda(t)\).

The accessibility boundary is

\[
\mu_\alpha(t)=\Lambda^2(t),
\]

and the mode is recursively accessible when

\[
\mu_\alpha(t)\leq\Lambda^2(t).
\]

The dynamical eigenvalue \(h_\alpha\) and resolution eigenvalue \(\mu_\alpha\) must not be identified merely because both may descend from related spectral operators.

### Gate III: Nonlinear Persistence

Entering the unstable and accessible region establishes only onset. The perturbation must subsequently evolve toward a genuine localized configuration,

\[
\delta X_\alpha\longrightarrow X_{\rm loc},
\]

with appropriate nonlinear stability conditions such as

\[
\delta E[X_{\rm loc}]=0,
\qquad
\delta^2E[X_{\rm loc}]>0
\]

modulo genuine zero modes, together with recursive invariant preservation,

\[
[\mathcal R_\ell X_{\rm loc}]_{\mathcal A}
=
[X_{\rm loc}]_{\mathcal A}
\qquad
\forall\ell\in I_{X_{\rm loc}}.
\]

A transient growing perturbation is therefore not sufficient evidence of reknotting.

## 8. Active-Reknotting Quadrant

The first two gates define four regimes:

| | \(h_\alpha>0\) | \(h_\alpha<0\) |
|---|---|---|
| \(\mu_\alpha>\Lambda^2\) | unresolved, stable | latent instability |
| \(\mu_\alpha\leq\Lambda^2\) | resolved, stable | **active reknotting candidate** |

The bottom-right cell is a candidate onset regime only. Gate III must still be satisfied.

A useful indicator is

\[
\mathcal K_\alpha(t)
=
\Theta[-h_\alpha(t)]
\Theta[\Lambda^2(t)-\mu_\alpha(t)]
\chi_{I_\alpha}(t),
\]

where \(\chi_{I_\alpha}\) records membership in the independently determined admissible domain.

Thus

\[
\mathcal K_\alpha=1
\]

means dynamically unstable, recursively accessible, and admissibly classified. It does not by itself prove nonlinear persistence.

## 9. Two Distinct Routes into Active Reknotting

The active quadrant can be entered by physically different mechanisms.

### Route A: Accessibility-Driven Onset

The instability already exists,

\[
h_\alpha<0,
\]

while the mode initially lies outside the accessible band. Evolution of the cutoff produces

\[
\mu_\alpha-\Lambda^2:
+\longrightarrow-.
\]

Thus

\[
\text{latent instability}
\longrightarrow
\text{active reknotting candidate}.
\]

This route requires a derived evolution law for \(\Lambda(t)\). Its interpretation is that a structural possibility already exists dynamically but becomes recursively accessible only later.

### Route B: Background-Driven Onset

The mode is already accessible,

\[
\mu_\alpha\leq\Lambda^2,
\]

while evolution of the cosmological background drives

\[
h_\alpha:
+\longrightarrow-.
\]

Thus

\[
\text{resolved stable}
\longrightarrow
\text{active reknotting candidate}.
\]

This route requires the time dependence of the background stability operator and corresponds more directly to the claim that terminal smoothness itself becomes unstable.

A near-simultaneous crossing is possible but must be explained dynamically rather than assumed.

## 10. TARTAN's Role After the Audit

TARTAN should **not** be described as causing reknotting.

The dynamical field theory determines whether a structural instability exists. TARTAN determines whether the resulting distinction belongs to a recursively accessible and persistent multiscale sector.

Accordingly,

\[
\text{dynamics}
\longrightarrow
\text{differentiation},
\]

while

\[
\text{TARTAN}
\longrightarrow
\text{multiscale persistence/accessibility test}.
\]

This separation prevents the renormalization machinery from being overloaded with dynamical claims it does not itself establish.

## 11. Recursive Attractor Conjecture

The original Recursive Attractor Conjecture remains open.

The cosmology monograph should use only the narrowed version suggested by this audit: determine whether nontrivial invariant sectors exist that remain recursively persistent over independently determined resolution intervals and whether cosmological evolution can create, destroy, or change the accessibility of those sectors.

The space of stable sectors should therefore be treated as potentially background-dependent,

\[
\mathfrak S
=
\mathfrak S[X_0(t),S(t),g(t),\ldots],
\]

rather than assumed fixed for all cosmological epochs.

## 12. Immediate Falsifiable Question for Chapter 36

The onset question is

\[
\boxed{
\exists\,\alpha,t_c:
\quad
h_\alpha(t_c)<0,
\qquad
\mu_\alpha(t_c)\leq\Lambda^2(t_c),
\qquad
t_c\in I_\alpha?
}
\]

If no such \((\alpha,t_c)\) exists along the relevant trajectory, the proposed reknotting mechanism fails at Gates I–II.

If such a pair exists, the nonlinear equations must then be evolved to determine whether Gate III succeeds.

Failure at Gate III means that the theory permits unstable accessible perturbations but not persistent reknotting.

## 13. Next Calculation: Generic Proof of Concept

The next calculation should **not** begin with the full candidate terminal state \(S_*\).

First use a generic smooth homogeneous RSVP background and a potential already capable of nonlinear localization. Derive independently:

\[
h_\alpha(t),
\qquad
\mu_\alpha(t),
\qquad
\Lambda(t),
\qquad
I_\alpha.
\]

Do not tune the definitions after observing the crossing.

Determine whether the trajectory realizes Route A, Route B, both, or neither. Only if it enters the active quadrant should the nonlinear equations be integrated to test Gate III.

This establishes an epistemic ladder:

\[
\boxed{
\text{generic proof of concept}
\longrightarrow
\text{terminal-state }S_*\text{ calculation}
\longrightarrow
\text{cosmological recurrence claim}.
}
\]

The two principal negative outcomes must remain distinct.

If the generic model fails, the proposed reknotting formalism itself requires revision.

If the generic model succeeds but the physically motivated \(S_*\) calculation fails, the formalism remains viable while the cosmological recurrence proposal fails.

## 14. Frozen Status

At this checkpoint:

**Persistence:** explicit postulate; RSVP Closure Problem open.

**Variational audit:** source-level discrepancies identified; transport-sector AKSZ embedding conditionally constructed; full AKSZ ↔ gauge-gravity equivalence unproved.

**TARTAN dilation:** equivariance established for bare spectral truncation.

**Literal TARTAN fixed points:** falsified for the intended localized-sector interpretation.

**Invariant-sector repair:** survives the toy stress test but lacks a general independently derived \(I_X\).

**Reknotting:** reduced to three gates with two distinct onset pathways.

**Recursive Attractor Conjecture:** open in a narrowed, testable form.

**Next step:** generic proof-of-concept calculation before any claim about the actual terminal cosmological state.

This ledger is the starting state for the next calculation. Later work should update individual statuses rather than silently replacing the definitions established here.
