from __future__ import annotations

from dataclasses import dataclass

import numpy as np


OMEGA = 2.0 * np.pi * np.array([(np.sqrt(5.0) - 1.0) / 2.0, np.sqrt(2.0) - 1.0])


@dataclass(frozen=True)
class SkewProductConfig:
    name: str
    slug: str
    perturbation: float
    noise_gain: float
    shear_gain: float
    observation_bandwidth: int = 5
    seed: int = 51


CONFIGS = [
    SkewProductConfig("Pure irrational shear control", "pure_irrational_shear", 0.0, 0.0, 0.42),
    SkewProductConfig("LWE-like deterministic shear", "lwe_deterministic_shear", 0.0, 1.15, 0.32),
    SkewProductConfig("KAM-perturbed shear", "kam_perturbed_shear", 0.035, 0.72, 0.34),
]


def frequency_lattice(bandwidth: int) -> np.ndarray:
    vectors: list[tuple[int, int]] = []
    radius = 1
    while len(vectors) < bandwidth:
        candidates = []
        for k1 in range(-radius, radius + 1):
            for k2 in range(-radius, radius + 1):
                if k1 == 0 and k2 == 0:
                    continue
                if np.gcd(abs(k1), abs(k2)) != 1:
                    continue
                if k1 < 0 or (k1 == 0 and k2 < 0):
                    continue
                norm = np.hypot(k1, k2)
                if norm <= radius:
                    candidates.append((norm, k1, k2))
        candidates.sort()
        for _norm, k1, k2 in candidates:
            vector = (k1, k2)
            if vector not in vectors:
                vectors.append(vector)
                if len(vectors) == bandwidth:
                    return np.array(vectors, dtype=float)
        radius += 1
    return np.array(vectors, dtype=float)


def deterministic_phase_error(theta: np.ndarray, config: SkewProductConfig) -> np.ndarray:
    smooth = np.sin(theta[:, 0]) + 0.55 * np.sin(theta[:, 1]) + 0.35 * np.sin(theta[:, 0] - theta[:, 1])
    quantized = np.tanh(1.8 * smooth)
    return config.noise_gain * quantized


def advance_theta(theta: np.ndarray, config: SkewProductConfig) -> np.ndarray:
    if config.perturbation == 0.0:
        return (theta + OMEGA) % (2.0 * np.pi)
    perturb = config.perturbation * np.column_stack((np.sin(theta[:, 1]), -np.sin(theta[:, 0])))
    return (theta + OMEGA + perturb) % (2.0 * np.pi)


def simulate_ensemble(config: SkewProductConfig, steps: int = 160, ensemble_size: int = 4096) -> dict:
    rng = np.random.default_rng(config.seed)
    theta = rng.uniform(0.0, 2.0 * np.pi, size=(ensemble_size, 2))
    position = rng.normal(0.0, 0.35, size=ensemble_size)
    velocity = rng.normal(0.0, 0.18, size=ensemble_size)
    variances = []
    entropies = []
    support_spans = []
    for _step in range(steps + 1):
        variances.append(float(np.var(position)))
        hist, _edges = np.histogram(position, bins=96, density=False)
        probs = hist[hist > 0] / max(np.sum(hist), 1)
        entropies.append(float(-np.sum(probs * np.log(probs))))
        support_spans.append(float(np.percentile(position, 95) - np.percentile(position, 5)))
        error = deterministic_phase_error(theta, config)
        velocity = 0.985 * velocity + 0.12 * error
        position = position + config.shear_gain * velocity + 0.08 * error
        theta = advance_theta(theta, config)
    return {
        "variance_by_k": variances,
        "entropy_by_k": entropies,
        "support_span_by_k": support_spans,
    }


def simulate_single(config: SkewProductConfig, steps: int = 12000) -> dict:
    rng = np.random.default_rng(config.seed + 100)
    theta = rng.uniform(0.0, 2.0 * np.pi, size=(1, 2))
    position = np.array([0.0])
    velocity = np.array([0.12])
    lattice = frequency_lattice(config.observation_bandwidth)
    amplitudes = 1.0 / np.sqrt(np.arange(1, len(lattice) + 1, dtype=float))
    amplitudes /= np.linalg.norm(amplitudes)
    phases = rng.uniform(0.0, 2.0 * np.pi, size=len(lattice))
    signal = np.zeros(steps, dtype=float)
    position_trace = np.zeros(steps, dtype=float)
    theta_trace = np.zeros((steps, 2), dtype=float)
    for step in range(steps):
        theta_trace[step] = theta[0]
        carrier = 0.0
        for amplitude, vector, phase in zip(amplitudes, lattice, phases):
            carrier += amplitude * np.cos(float(vector @ theta[0]) + phase)
        signal[step] = carrier + 0.025 * np.tanh(position[0] / 8.0)
        position_trace[step] = position[0]
        error = deterministic_phase_error(theta, config)
        velocity = 0.985 * velocity + 0.12 * error
        position = position + config.shear_gain * velocity + 0.08 * error
        theta = advance_theta(theta, config)
    signal -= np.mean(signal)
    signal /= max(np.std(signal), 1e-12)
    return {
        "signal": signal,
        "position": position_trace,
        "theta": theta_trace,
        "frequencies": lattice,
        "amplitudes": amplitudes,
    }


def expected_eigenvalues(frequencies: np.ndarray) -> np.ndarray:
    phases = frequencies @ OMEGA
    return np.concatenate((np.exp(1j * phases), np.exp(-1j * phases)))