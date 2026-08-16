from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "output"
METRICS_PATH = HERE / "metrics_checklist.json"
SCORECARD_PATH = OUT_DIR / "scorecard.csv"

SBOX4 = np.array([12, 5, 6, 11, 9, 0, 10, 13, 3, 14, 15, 8, 4, 7, 1, 2], dtype=np.uint16)


@dataclass(frozen=True)
class Candidate:
    name: str
    slug: str
    size: int
    mapping: np.ndarray
    observable: Callable[[np.ndarray], np.ndarray]
    initial_distribution: tuple[np.ndarray, np.ndarray]
    observable_cardinality: int
    predicted: str
    one_way_basis: str
    stability_prior: str


def is_prime(value: int) -> bool:
    if value < 2:
        return False
    if value % 2 == 0:
        return value == 2
    divisor = 3
    while divisor * divisor <= value:
        if value % divisor == 0:
            return False
        divisor += 2
    return True


def factor_int(value: int) -> list[int]:
    factors = []
    divisor = 2
    remaining = value
    while divisor * divisor <= remaining:
        if remaining % divisor == 0:
            factors.append(divisor)
            while remaining % divisor == 0:
                remaining //= divisor
        divisor += 1 if divisor == 2 else 2
    if remaining > 1:
        factors.append(remaining)
    return factors


def primitive_root(prime: int) -> int:
    factors = factor_int(prime - 1)
    for candidate in range(2, prime):
        if all(pow(candidate, (prime - 1) // factor, prime) != 1 for factor in factors):
            return candidate
    raise ValueError(f"No primitive root found for {prime}")


def gaussian_distribution(size: int, center: int, width: float, radius: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    if radius is None:
        radius = max(4, int(math.ceil(4.0 * width)))
    offsets = np.arange(-radius, radius + 1)
    states = (center + offsets) % size
    weights = np.exp(-0.5 * (offsets / width) ** 2)
    weights = weights / np.sum(weights)
    unique_weights: dict[int, float] = defaultdict(float)
    for state, weight in zip(states, weights):
        unique_weights[int(state)] += float(weight)
    unique_states = np.array(sorted(unique_weights), dtype=np.int64)
    unique_probs = np.array([unique_weights[int(state)] for state in unique_states], dtype=float)
    unique_probs /= np.sum(unique_probs)
    return unique_states, unique_probs


def hamming_ball_distribution(center: int, bits: int, radius: int = 1) -> tuple[np.ndarray, np.ndarray]:
    states = {center}
    bit_positions = range(bits)
    if radius >= 1:
        for bit in bit_positions:
            states.add(center ^ (1 << bit))
    if radius >= 2:
        for first in bit_positions:
            for second in range(first + 1, bits):
                states.add(center ^ (1 << first) ^ (1 << second))
    ordered = np.array(sorted(states), dtype=np.int64)
    weights = np.ones(len(ordered), dtype=float) / len(ordered)
    return ordered, weights


def modular_squaring_candidate() -> Candidate:
    p, q = 83, 107
    modulus = p * q
    residues = sorted({(x * x) % modulus for x in range(1, modulus) if math.gcd(x, modulus) == 1})
    index_of = {residue: index for index, residue in enumerate(residues)}
    mapping = np.array([index_of[(residue * residue) % modulus] for residue in residues], dtype=np.int64)
    states, weights = gaussian_distribution(len(residues), center=len(residues) // 5, width=8.0)
    return Candidate(
        name="Modular squaring on QR_N",
        slug="modular_squaring",
        size=len(residues),
        mapping=mapping,
        observable=lambda state: state.astype(np.int64),
        initial_distribution=(states, weights),
        observable_cardinality=len(residues),
        predicted="top candidate; R2/R3 unknown but plausible",
        one_way_basis="factoring / quadratic residuosity (finite toy only)",
        stability_prior="medium: algebraic structure survives parameter choice, not arbitrary noise",
    )


def lwe_shear_candidate() -> Candidate:
    q = 97
    mapping = np.empty(q * q, dtype=np.int64)
    for x in range(q):
        for y in range(q):
            index = x * q + y
            next_x = (x + y + 3) % q
            next_y = (y + 1) % q
            mapping[index] = next_x * q + next_y
    center = (q // 2) * q + q // 3
    offsets = []
    weights = []
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            x = (q // 2 + dx) % q
            y = (q // 3 + dy) % q
            offsets.append(x * q + y)
            weights.append(math.exp(-0.5 * (dx * dx + dy * dy) / 2.0**2))
    states = np.array(offsets, dtype=np.int64)
    probs = np.array(weights, dtype=float)
    probs /= np.sum(probs)
    return Candidate(
        name="LWE-style affine lattice shear",
        slug="lwe_shear",
        size=q * q,
        mapping=mapping,
        observable=lambda state: (state // q).astype(np.int64),
        initial_distribution=(states, probs),
        observable_cardinality=q,
        predicted="top candidate for gentle polynomial blur; R2 unknown",
        one_way_basis="LWE-inspired only; no reduction for this toy shear",
        stability_prior="medium-high for bounded affine perturbations before modular wrap",
    )


def primitive_root_candidate() -> Candidate:
    prime = 4099 if is_prime(4099) else 4093
    root = primitive_root(prime)
    size = prime - 1
    powers = []
    value = 1
    for _index in range(size):
        powers.append(value)
        value = (value * root) % prime
    log_index = {value: index for index, value in enumerate(powers)}
    mapping = np.array([(index + 1) % size for index in range(size)], dtype=np.int64)
    states, weights = gaussian_distribution(size, center=size // 3, width=7.0)
    return Candidate(
        name="Primitive-root multiplication",
        slug="primitive_root_multiplication",
        size=size,
        mapping=mapping,
        observable=lambda state: state.astype(np.int64),
        initial_distribution=(states, weights),
        observable_cardinality=size,
        predicted="rigid rotation baseline; expected R3 fail",
        one_way_basis="discrete-log flavour, but iteration is transparent in log coordinates",
        stability_prior="high as algebraic rotation; too rigid for blur",
    )


def parity(value: int) -> int:
    return value.bit_count() & 1


def lfsr_candidate(bits: int = 12) -> Candidate:
    mask = (1 << bits) - 1
    tap_mask = (1 << 0) | (1 << 3) | (1 << 5) | (1 << 11)
    states = np.arange(1, mask + 1, dtype=np.int64)
    index_of = {int(state): index for index, state in enumerate(states)}
    mapping_values = []
    for state in states:
        feedback = parity(int(state) & tap_mask)
        next_state = (int(state) >> 1) | (feedback << (bits - 1))
        mapping_values.append(index_of[next_state])
    center_state = 0b101001011011
    local_states, weights = hamming_ball_distribution(index_of[center_state], bits, radius=1)
    return Candidate(
        name="LFSR 12-bit",
        slug="lfsr_12",
        size=len(states),
        mapping=np.array(mapping_values, dtype=np.int64),
        observable=lambda state: (states[state] & 0xFF).astype(np.int64),
        initial_distribution=(local_states, weights),
        observable_cardinality=256,
        predicted="predicted R2 fail: cyclotomic linear recurrence",
        one_way_basis="weak / linear, not a standard one-way candidate",
        stability_prior="low: linear recurrence changes under tap perturbation",
    )


def bit_permutation(value: int, bits: int) -> int:
    result = 0
    modulus = bits - 1
    multiplier = 3 if bits == 8 else 5
    for bit in range(bits):
        target = bits - 1 if bit == bits - 1 else (multiplier * bit) % modulus
        if value & (1 << bit):
            result |= 1 << target
    return result


def feistel_round_function(value: int, half_bits: int, round_constant: int) -> int:
    mask = (1 << half_bits) - 1
    mixed = (value + round_constant) & mask
    result = 0
    for nibble in range(max(1, half_bits // 4)):
        result |= int(SBOX4[(mixed >> (4 * nibble)) & 0xF]) << (4 * nibble)
    rotated = ((result << 1) | (result >> max(1, half_bits - 1))) & mask
    return (rotated ^ ((mixed * 0x9) & mask) ^ (round_constant & mask)) & mask


def aes_like_mapping(bits: int, rounds: int) -> np.ndarray:
    size = 1 << bits
    mapping = np.empty(size, dtype=np.int64)
    constants = [0x3, 0xC, 0x6, 0x9, 0xF, 0x5, 0xA, 0x7]
    if bits == 16:
        constants = [0x3A, 0xC5, 0x69, 0x96, 0xF0, 0x0F, 0xA7, 0x5D]
    half_bits = bits // 2
    mask = (1 << half_bits) - 1
    for state in range(size):
        left = state >> half_bits
        right = state & mask
        for round_index in range(rounds):
            new_left = right
            new_right = left ^ feistel_round_function(right, half_bits, constants[round_index])
            left, right = new_left & mask, new_right & mask
        mapping[state] = (left << half_bits) | right
    return mapping


def spn_candidate(bits: int, rounds: int) -> Candidate:
    size = 1 << bits
    center = 0xA7 if bits == 8 else 0xA73D
    local_states, weights = hamming_ball_distribution(center, bits, radius=1)
    return Candidate(
        name=f"Mini-SPN {bits}-bit ({rounds} rounds)",
        slug=f"mini_spn_{bits}",
        size=size,
        mapping=aes_like_mapping(bits, rounds),
        observable=lambda state: (state & 0xFF).astype(np.int64),
        initial_distribution=(local_states, weights),
        observable_cardinality=256,
        predicted="predicted R3 fail: avalanche control group",
        one_way_basis="toy AES-like assumption only; not standard at this size",
        stability_prior="low: avalanche profile changes under round-function perturbation",
    )


def cycle_lengths(mapping: np.ndarray) -> list[int]:
    visited = np.zeros(len(mapping), dtype=bool)
    lengths = []
    for start in range(len(mapping)):
        if visited[start]:
            continue
        current = start
        length = 0
        while not visited[current]:
            visited[current] = True
            current = int(mapping[current])
            length += 1
        lengths.append(length)
    return lengths


def spectral_metrics(lengths: list[int]) -> dict:
    total = sum(lengths)
    max_cycle = max(lengths)
    lcm_cap = 1
    for length in sorted(lengths, reverse=True)[:32]:
        lcm_cap = math.lcm(lcm_cap, length)
        if lcm_cap > 10**18:
            break
    phases = []
    for length in lengths:
        if len(phases) > 20000:
            break
        phases.extend((2.0 * math.pi * np.arange(length) / length).tolist())
    phase_array = np.array(phases, dtype=float)
    unique_lengths = len(set(lengths))
    return {
        "cycle_count": len(lengths),
        "state_count": total,
        "max_cycle_length": max_cycle,
        "max_cycle_fraction": max_cycle / total,
        "unique_cycle_lengths": unique_lengths,
        "lcm_cap_first_32_cycles": lcm_cap,
        "sampled_phase_count": int(len(phase_array)),
        "phase_sample": phase_array,
        "strict_r2_status": "FAIL_FINITE_CYCLOTOMIC",
        "r2_proxy_score": float(min(1.0, math.log1p(max_cycle) / math.log1p(total)) * min(1.0, unique_lengths / 8.0)),
    }


def observable_distribution(values: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    buckets: dict[int, float] = defaultdict(float)
    for value, weight in zip(values, weights):
        buckets[int(value)] += float(weight)
    ordered = np.array(sorted(buckets), dtype=np.int64)
    probs = np.array([buckets[int(value)] for value in ordered], dtype=float)
    probs /= np.sum(probs)
    return ordered, probs


def entropy(probs: np.ndarray) -> float:
    positive = probs[probs > 0]
    return float(-np.sum(positive * np.log(positive)))


def variance(values: np.ndarray, probs: np.ndarray) -> float:
    mean = float(np.sum(values * probs))
    return float(np.sum(((values - mean) ** 2) * probs))


def diffusion_metrics(candidate: Candidate, steps: int = 80) -> dict:
    states, weights = candidate.initial_distribution
    variances = []
    entropies = []
    support_sizes = []
    spans = []
    for _step in range(steps + 1):
        obs_values = candidate.observable(states)
        values, probs = observable_distribution(obs_values, weights)
        variances.append(variance(values.astype(float), probs))
        entropies.append(entropy(probs))
        support_sizes.append(int(len(values)))
        spans.append(float(np.max(values) - np.min(values)) if len(values) else 0.0)
        states = candidate.mapping[states]

    variance_array = np.array(variances, dtype=float)
    entropy_array = np.array(entropies, dtype=float)
    span_array = np.array(spans, dtype=float)
    excess = np.maximum(variance_array - variance_array[0], 1e-12)
    max_variance = float(np.max(variance_array))
    observable_uniform_variance = ((candidate.observable_cardinality**2) - 1.0) / 12.0
    relative_max_variance = max_variance / max(observable_uniform_variance, 1.0)
    relative_span = float(np.max(span_array) / max(candidate.observable_cardinality - 1, 1))
    saturation_step = None
    for index, value in enumerate(variance_array):
        if max_variance > 0 and value >= 0.8 * max_variance:
            saturation_step = index
            break

    fit_indices = np.arange(1, steps + 1)
    usable = (excess[1:] > 1e-9) & (variance_array[1:] < max(0.9 * max_variance, variance_array[0] + 1e-6))
    if np.sum(usable) >= 5:
        log_k = np.log(fit_indices[usable])
        log_v = np.log(excess[1:][usable])
        alpha, intercept = np.polyfit(log_k, log_v, 1)
        predicted = alpha * log_k + intercept
        ss_res = float(np.sum((log_v - predicted) ** 2))
        ss_tot = float(np.sum((log_v - np.mean(log_v)) ** 2))
        fit_r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    else:
        alpha = 0.0
        fit_r2 = 0.0

    if relative_span < 0.03 and np.max(excess) < 1e-6:
        classification = "rigid"
    elif saturation_step is not None and saturation_step <= 3 and relative_span > 0.25:
        classification = "avalanche"
    elif alpha > 2.2 and fit_r2 > 0.8:
        classification = "exponential_or_superballistic"
    elif 0.25 <= alpha <= 2.2 and relative_span > 0.05:
        classification = "polynomial"
    elif 0.0 < alpha < 0.25 or relative_span <= 0.05:
        classification = "logarithmic_or_rigid"
    else:
        classification = "unclassified"

    return {
        "steps": steps,
        "variance_by_k": [float(value) for value in variance_array],
        "entropy_by_k": [float(value) for value in entropy_array],
        "support_size_by_k": support_sizes,
        "span_by_k": [float(value) for value in span_array],
        "alpha_fit": float(alpha),
        "alpha_fit_r2": float(fit_r2),
        "max_variance": max_variance,
        "relative_max_variance": float(relative_max_variance),
        "relative_span": relative_span,
        "saturation_step_80pct_observed": saturation_step,
        "classification": classification,
    }


def score_candidate(candidate: Candidate, spec: dict, diff: dict) -> dict:
    r1 = "PASS" if spec["state_count"] == candidate.size else "FAIL"
    r2 = "FAIL_STRICT" if spec["strict_r2_status"] == "FAIL_FINITE_CYCLOTOMIC" else "PASS"
    r3 = "PASS" if diff["classification"] == "polynomial" else "FAIL"
    r4 = "PASS" if candidate.observable_cardinality > 8 and max(diff["support_size_by_k"]) > 1 else "PARTIAL"
    r5 = "NOT_TESTED_R2_REQUIRED"
    r6 = "PASS_TOY" if "factoring" in candidate.one_way_basis or "LWE" in candidate.one_way_basis else "FAIL_OR_WEAK"
    if diff["classification"] == "polynomial" and 0.0 < diff["alpha_fit"] <= 2.0:
        r7 = "PASS"
    elif diff["classification"] in {"avalanche", "rigid", "logarithmic_or_rigid"}:
        r7 = "FAIL"
    else:
        r7 = "PARTIAL"
    r8 = "PARTIAL" if candidate.stability_prior.startswith("medium") else ("PASS" if candidate.stability_prior.startswith("high") else "FAIL")
    hard_pass = all(value == "PASS" for value in [r1, r3, r4]) and r2 == "PASS"
    if hard_pass:
        verdict = "PASS"
    elif r3 == "PASS" and r2 == "FAIL_STRICT":
        verdict = "PARTIAL_DIFFUSIVE_BUT_CYCLOTOMIC"
    elif r2 == "FAIL_STRICT":
        verdict = "FAIL_R2_STRICT"
    else:
        verdict = "FAIL"
    return {
        "primitive": candidate.name,
        "slug": candidate.slug,
        "R1": r1,
        "R2": r2,
        "R3": r3,
        "R4": r4,
        "R5": r5,
        "R6": r6,
        "R7": r7,
        "R8": r8,
        "verdict": verdict,
        "prediction": candidate.predicted,
    }


def plot_spectrum(candidate: Candidate, spec: dict) -> None:
    phases = spec["phase_sample"]
    if len(phases) == 0:
        return
    sample = phases[: min(len(phases), 6000)]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].scatter(np.cos(sample), np.sin(sample), s=3, alpha=0.35)
    axes[0].set_aspect("equal")
    axes[0].set_title(f"{candidate.name}: eigenphases")
    axes[0].set_xlabel("Re")
    axes[0].set_ylabel("Im")
    axes[1].hist(sample, bins=64, color="#3B82F6", alpha=0.8)
    axes[1].set_title("phase histogram")
    axes[1].set_xlabel("theta")
    axes[1].set_ylabel("count")
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"spectrum_{candidate.slug}.png", dpi=160)
    plt.close(fig)


def plot_diffusion(candidate: Candidate, diff: dict) -> None:
    k = np.arange(diff["steps"] + 1)
    variance_values = np.array(diff["variance_by_k"], dtype=float)
    entropy_values = np.array(diff["entropy_by_k"], dtype=float)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(k, variance_values, marker="o", markersize=2)
    axes[0].set_title(f"{candidate.name}: V_k")
    axes[0].set_xlabel("k")
    axes[0].set_ylabel("observable variance")
    axes[0].set_xscale("symlog", linthresh=1)
    axes[0].set_yscale("symlog", linthresh=1e-6)
    axes[1].plot(k, entropy_values, marker="o", markersize=2, color="#059669")
    axes[1].set_title("observable entropy")
    axes[1].set_xlabel("k")
    axes[1].set_ylabel("S_k")
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"diffusion_{candidate.slug}.png", dpi=160)
    plt.close(fig)


def json_ready(value):
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items() if key != "phase_sample"}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def write_scorecard(rows: list[dict]) -> None:
    with SCORECARD_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["primitive", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "verdict", "prediction"])
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in writer.fieldnames})


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = [
        modular_squaring_candidate(),
        lwe_shear_candidate(),
        primitive_root_candidate(),
        lfsr_candidate(),
        spn_candidate(bits=8, rounds=4),
        spn_candidate(bits=16, rounds=5),
    ]
    results = []
    scorecard = []
    for candidate in candidates:
        lengths = cycle_lengths(candidate.mapping)
        spec = spectral_metrics(lengths)
        diff = diffusion_metrics(candidate)
        score = score_candidate(candidate, spec, diff)
        plot_spectrum(candidate, spec)
        plot_diffusion(candidate, diff)
        scorecard.append(score)
        results.append(
            {
                "name": candidate.name,
                "slug": candidate.slug,
                "size": candidate.size,
                "predicted": candidate.predicted,
                "one_way_basis": candidate.one_way_basis,
                "stability_prior": candidate.stability_prior,
                "spectral": json_ready(spec),
                "diffusion": diff,
                "score": score,
            }
        )

    write_scorecard(scorecard)
    hard_passes = [row for row in scorecard if row["verdict"] == "PASS"]
    r3_passes = [row for row in scorecard if row["R3"] == "PASS"]
    verdict = "PASS" if hard_passes else ("PARTIAL" if r3_passes else "FAIL")
    metrics = {
        "verdict": verdict,
        "verdict_note": "Strict finite-state spectra are cyclotomic, so R2 fails exactly for every tested finite primitive. Diffusion still separates promising algebraic/shear candidates from avalanche controls.",
        "candidate_count": len(candidates),
        "hard_requirement_passes": len(hard_passes),
        "r3_polynomial_passes": len(r3_passes),
        "results": results,
        "scorecard": scorecard,
        "output_dir": str(OUT_DIR.relative_to(HERE)),
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"verdict: {verdict}")
    print(f"Hard requirement passes: {len(hard_passes)}")
    print(f"R3 polynomial passes: {len(r3_passes)}")
    for row in scorecard:
        print(f"{row['primitive']}: {row['verdict']} | R3={row['R3']} | R2={row['R2']}")


if __name__ == "__main__":
    main()