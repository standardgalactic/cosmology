# Python Experiments

Monte Carlo experiment that estimates \(\pi\) by sampling random points in a unit square.

## Run

```bash
cd experiments/python
python3 experiment.py --samples 100000 --seed 42
```

## Generic reknotting proof of concept

`reknotting_model.py` is a deterministic reduced-mode implementation of the
three-gate criterion in Chapters 72 and 74. It is deliberately not a model of
the terminal cosmological state `S_*`. Its purpose is to verify that dynamical
instability, recursive accessibility, and nonlinear persistence can be defined
independently and combined without tuning their definitions after a run.

The experiment pre-registers one accessibility-driven case, one
background-driven case, and three negative controls: stable but accessible,
unstable but inaccessible, and active but too transient to persist. It writes a JSON
classification summary and complete CSV histories:

```bash
cd experiments/python
python3 reknotting_model.py --output reknotting-output
python3 -m unittest -v test_reknotting_model.py
```

Route A begins with an unstable but inaccessible mode; the independently
evolving cutoff later admits it. Route B begins with an accessible stable mode;
the independently evolving background later changes the sign of its stability
diagnostic. Both must still produce a localized nonlinear state that preserves
its predeclared invariant class across the fixed coarse-graining interval for a
fixed duration. The controls isolate failure at each gate instead of treating
every negative result as the same kind of failure.

Each history also records the reduced potential's available relaxation work,
the gradient-flow balance residual, and a scale-dependent distinction spectrum.
The final outcome label is generated from the diagnostics alone using Chapter
74's named classes; filenames and expected outcomes are not inputs to the
classifier.

This experiment validates the logical architecture only. It does not resolve
the RSVP Closure Problem, derive the physical terminal background, establish a
physical TARTAN cutoff law, or elevate the Persistence Postulate to a theorem.
