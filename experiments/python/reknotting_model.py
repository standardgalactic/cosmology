#!/usr/bin/env python3
"""Deterministic proof of concept for the three-gate reknotting criterion.

This is a reduced mode model, not an RSVP terminal-state calculation.  Stability,
accessibility, and nonlinear persistence are computed by separate functions and
are combined only by the final classifier.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable


@dataclass(frozen=True)
class Protocol:
    name: str
    dt: float = 0.02
    duration: float = 80.0
    points: int = 129
    domain_half_width: float = 8.0
    mode_mu: float = 4.0
    seed_amplitude: float = 1.0e-4
    cubic: float = 1.0
    quintic: float = 1.0
    localization_threshold: float = 0.20
    maximum_support_fraction: float = 0.45
    recursive_tolerance: float = 0.18
    coarse_graining_radii: tuple[int, ...] = (1, 2, 4, 6)
    persistence_duration: float = 10.0


@dataclass(frozen=True)
class Sample:
    time: float
    amplitude: float
    h: float
    mu: float
    cutoff: float
    accessibility_gap: float
    unstable: bool
    accessible: bool
    localized: bool
    recursively_persistent: bool
    distinction: float
    available_work: float
    balance_residual: float


@dataclass(frozen=True)
class Result:
    protocol: str
    route: str
    classification: str
    instability_crossing: float | None
    accessibility_crossing: float | None
    active_crossing: float | None
    persistence_crossing: float | None
    gate_i: bool
    gate_ii: bool
    gate_iii: bool
    reknotting: bool
    final_amplitude: float
    max_recursive_deviation: float


def route_a_protocol() -> tuple[Protocol, Callable[[float], float], Callable[[float], float]]:
    """Latent instability becomes accessible when the cutoff grows."""
    protocol = Protocol(name="route_a_accessibility_driven")
    h = lambda _t: -0.35
    cutoff = lambda t: 1.2 + 1.4 / (1.0 + math.exp(-(t - 12.0) / 1.5))
    return protocol, h, cutoff


def route_b_protocol() -> tuple[Protocol, Callable[[float], float], Callable[[float], float]]:
    """An accessible mode becomes unstable as the background changes."""
    protocol = Protocol(name="route_b_background_driven")
    h = lambda t: 0.35 - 0.70 / (1.0 + math.exp(-(t - 12.0) / 1.5))
    cutoff = lambda _t: 2.6
    return protocol, h, cutoff


def negative_protocol() -> tuple[Protocol, Callable[[float], float], Callable[[float], float]]:
    """Control: the mode is accessible but remains linearly stable."""
    protocol = Protocol(name="negative_stable_control")
    h = lambda _t: 0.35
    cutoff = lambda _t: 2.6
    return protocol, h, cutoff


def inaccessible_protocol() -> tuple[Protocol, Callable[[float], float], Callable[[float], float]]:
    """Control: a genuine instability remains outside the accessible band."""
    protocol = Protocol(name="negative_inaccessible_control")
    h = lambda _t: -0.35
    cutoff = lambda _t: 1.2
    return protocol, h, cutoff


def transient_protocol() -> tuple[Protocol, Callable[[float], float], Callable[[float], float]]:
    """Control: an active perturbation decays before the persistence duration."""
    protocol = Protocol(
        name="negative_transient_control",
        seed_amplitude=0.25,
        persistence_duration=20.0,
    )
    h = lambda t: -0.35 + 0.70 / (1.0 + math.exp(-(t - 4.0) / 0.5))
    cutoff = lambda _t: 2.6
    return protocol, h, cutoff


def mode_profile(amplitude: float, protocol: Protocol) -> list[float]:
    """A fixed localized defect template carried by the reduced mode."""
    dx = 2.0 * protocol.domain_half_width / (protocol.points - 1)
    return [
        amplitude / math.cosh(-protocol.domain_half_width + i * dx)
        for i in range(protocol.points)
    ]


def box_coarse_grain(values: list[float], radius: int) -> list[float]:
    result = []
    for i in range(len(values)):
        lo = max(0, i - radius)
        hi = min(len(values), i + radius + 1)
        result.append(sum(values[lo:hi]) / (hi - lo))
    return result


def invariant_class(values: list[float], protocol: Protocol) -> tuple[int, int, bool]:
    """Return sign, component count, and bounded-support classification."""
    peak = max((abs(value) for value in values), default=0.0)
    if peak < protocol.localization_threshold:
        return 0, 0, False
    sign = 1 if sum(values) > 0.0 else -1
    active = [abs(value) >= 0.5 * peak for value in values]
    components = sum(flag and (i == 0 or not active[i - 1]) for i, flag in enumerate(active))
    support_fraction = sum(active) / len(active)
    return sign, components, components == 1 and support_fraction <= protocol.maximum_support_fraction


def recursive_diagnostics(values: list[float], protocol: Protocol) -> tuple[bool, float]:
    """Test invariant preservation and profile deviation on fixed scales."""
    base_class = invariant_class(values, protocol)
    if not base_class[2]:
        return False, math.inf
    base_norm = math.sqrt(sum(value * value for value in values))
    worst = 0.0
    for radius in protocol.coarse_graining_radii:
        coarse = box_coarse_grain(values, radius)
        coarse_class = invariant_class(coarse, protocol)
        if coarse_class != base_class:
            return False, math.inf
        coarse_norm = math.sqrt(sum(value * value for value in coarse))
        if coarse_norm == 0.0:
            return False, math.inf
        deviation = math.sqrt(
            sum((a / base_norm - b / coarse_norm) ** 2 for a, b in zip(values, coarse))
        )
        worst = max(worst, deviation)
    return worst <= protocol.recursive_tolerance, worst


def distinction(values: list[float]) -> float:
    """RMS spatial distinction after removal of the homogeneous component."""
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def effective_potential(q: float, h: float, protocol: Protocol) -> float:
    return 0.5 * h * q**2 - 0.25 * protocol.cubic * q**4 + protocol.quintic * q**6 / 6.0


def available_work(q: float, h: float, protocol: Protocol) -> float:
    """Potential drop available under the instantaneous reduced gradient flow."""
    candidates = [0.0]
    discriminant = protocol.cubic**2 - 4.0 * protocol.quintic * h
    if discriminant >= 0.0:
        for sign in (-1.0, 1.0):
            q_squared = (protocol.cubic + sign * math.sqrt(discriminant)) / (
                2.0 * protocol.quintic
            )
            if q_squared > 0.0:
                root = math.sqrt(q_squared)
                candidates.extend((root, -root))
    minimum = min(effective_potential(candidate, h, protocol) for candidate in candidates)
    return max(0.0, effective_potential(q, h, protocol) - minimum)


def amplitude_derivative(q: float, h: float, protocol: Protocol) -> float:
    """Subcritical saturating normal form: qdot=-h*q+b*q^3-q^5."""
    return -h * q + protocol.cubic * q**3 - protocol.quintic * q**5


def rk4_step(q: float, h: float, protocol: Protocol) -> float:
    dt = protocol.dt
    f = lambda value: amplitude_derivative(value, h, protocol)
    k1 = f(q)
    k2 = f(q + 0.5 * dt * k1)
    k3 = f(q + 0.5 * dt * k2)
    k4 = f(q + dt * k3)
    return q + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0


def first_true_time(samples: Iterable[Sample], predicate: Callable[[Sample], bool]) -> float | None:
    for sample in samples:
        if predicate(sample):
            return sample.time
    return None


def classify_route(samples: list[Sample]) -> str:
    active = next((sample for sample in samples if sample.unstable and sample.accessible), None)
    if active is None:
        return "neither"
    previous = samples[max(0, samples.index(active) - 1)]
    if previous.unstable and not previous.accessible:
        return "accessibility-driven"
    if previous.accessible and not previous.unstable:
        return "background-driven"
    return "simultaneous-or-initial"


def classify_outcome(samples: list[Sample], persistence_crossing: float | None) -> str:
    """Apply Chapter 74's named classification using diagnostics only."""
    if persistence_crossing is not None:
        return "reknotting"
    if any(sample.unstable and sample.accessible for sample in samples):
        return "crossing without persistence"
    if any(sample.unstable for sample in samples):
        return "unstable but inaccessible"
    if any(sample.accessible for sample in samples):
        return "accessible but stable"
    return "stable"


def simulate(
    protocol: Protocol,
    h_function: Callable[[float], float],
    cutoff_function: Callable[[float], float],
) -> tuple[Result, list[Sample]]:
    q = protocol.seed_amplitude
    samples: list[Sample] = []
    worst_finite_deviation = 0.0
    previous_energy: float | None = None
    previous_h: float | None = None
    previous_qdot: float | None = None
    steps = round(protocol.duration / protocol.dt)
    for step in range(steps + 1):
        time = step * protocol.dt
        h = h_function(time)
        cutoff = cutoff_function(time)
        gap = protocol.mode_mu - cutoff * cutoff
        profile = mode_profile(q, protocol)
        recursive, deviation = recursive_diagnostics(profile, protocol)
        if math.isfinite(deviation):
            worst_finite_deviation = max(worst_finite_deviation, deviation)
        localized = invariant_class(profile, protocol)[2]
        energy = effective_potential(q, h, protocol)
        qdot = amplitude_derivative(q, h, protocol)
        balance_residual = 0.0
        if previous_energy is not None and previous_h is not None and previous_qdot is not None:
            energy_rate = (energy - previous_energy) / protocol.dt
            external_rate = 0.25 * (q * q + samples[-1].amplitude ** 2) * (
                h - previous_h
            ) / protocol.dt
            dissipation_rate = 0.5 * (qdot * qdot + previous_qdot * previous_qdot)
            balance_residual = energy_rate - external_rate + dissipation_rate
        samples.append(
            Sample(
                time=time,
                amplitude=q,
                h=h,
                mu=protocol.mode_mu,
                cutoff=cutoff,
                accessibility_gap=gap,
                unstable=h < 0.0,
                accessible=gap <= 0.0,
                localized=localized,
                recursively_persistent=recursive,
                distinction=distinction(profile),
                available_work=available_work(q, h, protocol),
                balance_residual=balance_residual,
            )
        )
        previous_energy = energy
        previous_h = h
        previous_qdot = qdot
        q = rk4_step(q, h, protocol)

    route = classify_route(samples)
    instability_crossing = first_true_time(samples, lambda sample: sample.unstable)
    accessibility_crossing = first_true_time(samples, lambda sample: sample.accessible)
    active_crossing = first_true_time(samples, lambda sample: sample.unstable and sample.accessible)

    required_samples = math.ceil(protocol.persistence_duration / protocol.dt)
    persistence_crossing = None
    streak = 0
    for sample in samples:
        if sample.unstable and sample.accessible and sample.recursively_persistent:
            streak += 1
            if streak >= required_samples:
                persistence_crossing = sample.time - (required_samples - 1) * protocol.dt
                break
        else:
            streak = 0

    result = Result(
        protocol=protocol.name,
        route=route,
        classification=classify_outcome(samples, persistence_crossing),
        instability_crossing=instability_crossing,
        accessibility_crossing=accessibility_crossing,
        active_crossing=active_crossing,
        persistence_crossing=persistence_crossing,
        gate_i=instability_crossing is not None,
        gate_ii=accessibility_crossing is not None,
        gate_iii=persistence_crossing is not None,
        reknotting=persistence_crossing is not None,
        final_amplitude=samples[-1].amplitude,
        max_recursive_deviation=worst_finite_deviation,
    )
    return result, samples


def write_outputs(output: Path, results: list[Result], histories: dict[str, list[Sample]]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(
        json.dumps([asdict(result) for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    for name, samples in histories.items():
        with (output / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=asdict(samples[0]).keys())
            writer.writeheader()
            writer.writerows(asdict(sample) for sample in samples)
        with (output / f"{name}_distinction.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=("time", "radius", "distinction"))
            writer.writeheader()
            for sample in samples:
                profile = mode_profile(sample.amplitude, Protocol(name=name))
                for radius in (0, *Protocol(name=name).coarse_graining_radii):
                    coarse = profile if radius == 0 else box_coarse_grain(profile, radius)
                    writer.writerow(
                        {
                            "time": sample.time,
                            "radius": radius,
                            "distinction": distinction(coarse),
                        }
                    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("reknotting-output"))
    args = parser.parse_args()
    cases = (
        route_a_protocol(),
        route_b_protocol(),
        negative_protocol(),
        inaccessible_protocol(),
        transient_protocol(),
    )
    results: list[Result] = []
    histories: dict[str, list[Sample]] = {}
    for protocol, h_function, cutoff_function in cases:
        result, samples = simulate(protocol, h_function, cutoff_function)
        results.append(result)
        histories[protocol.name] = samples
        print(json.dumps(asdict(result), sort_keys=True))
    write_outputs(args.output, results, histories)


if __name__ == "__main__":
    main()
