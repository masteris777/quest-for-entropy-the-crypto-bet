from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from skew_product import CONFIGS, expected_eigenvalues, simulate_single


HERE = Path(__file__).resolve().parent
SPECTRAL_PATH = HERE / "spectral_metrics.json"


def delay_blocks(signal: np.ndarray, memory_depth: int) -> tuple[np.ndarray, np.ndarray]:
    blocks = np.lib.stride_tricks.sliding_window_view(signal, memory_depth)
    return blocks[:-1], blocks[1:]


def fit_shift(signal: np.ndarray, rank: int = 14, memory_depth: int = 80) -> tuple[np.ndarray, float, np.ndarray]:
    past, future = delay_blocks(signal, memory_depth)
    mean = np.mean(past, axis=0, keepdims=True)
    past_centered = past - mean
    future_centered = future - mean
    _u, singular_values, vt = np.linalg.svd(past_centered, full_matrices=False)
    numerical_rank = int(np.sum(singular_values > singular_values[0] * 1e-10))
    target_rank = min(rank, numerical_rank, memory_depth)
    basis = vt[:target_rank].T
    current = past_centered @ basis
    nxt = future_centered @ basis
    operator_t, *_ = np.linalg.lstsq(current, nxt, rcond=None)
    operator = operator_t.T
    residual = np.linalg.norm(nxt - current @ operator.T) / max(np.linalg.norm(nxt), 1e-12)
    return operator, float(residual), singular_values[:target_rank]


def spectral_alignment(eigenvalues: np.ndarray, expected: np.ndarray) -> float:
    usable = eigenvalues[np.abs(eigenvalues) > 1e-8]
    usable = usable / np.abs(usable)
    distances = []
    for value in expected:
        distances.append(float(np.min(np.abs(usable - value))))
    return float(np.mean(distances))


def rational_residual(phase_fraction: float, max_denominator: int = 32) -> float:
    best = 1.0
    for denominator in range(1, max_denominator + 1):
        numerator = round(phase_fraction * denominator)
        best = min(best, abs(phase_fraction - numerator / denominator))
    return float(best)


def matched_phase_fractions(eigenvalues: np.ndarray, expected: np.ndarray) -> np.ndarray:
    usable = eigenvalues[np.abs(eigenvalues) > 1e-8]
    usable = usable / np.abs(usable)
    matched = []
    for value in expected:
        nearest = usable[int(np.argmin(np.abs(usable - value)))]
        matched.append((np.angle(nearest) / (2.0 * np.pi)) % 1.0)
    return np.array(matched, dtype=float)


def cyclotomic_false_positive_score(phases: np.ndarray, tolerance: float = 1e-4) -> tuple[float, list[float]]:
    residuals = np.array([rational_residual(float(phase)) for phase in phases])
    false_positive_fraction = float(np.mean(residuals <= tolerance)) if len(residuals) else 1.0
    return false_positive_fraction, [float(value) for value in residuals]


def analyze_config(config) -> dict:
    trace = simulate_single(config, steps=16000)
    expected = expected_eigenvalues(trace["frequencies"])
    operator, residual, singular_values = fit_shift(trace["signal"])
    eigenvalues = np.linalg.eigvals(operator)
    radii = np.abs(eigenvalues)
    alignment = spectral_alignment(eigenvalues, expected)
    matched_phases = matched_phase_fractions(eigenvalues, expected)
    cyclotomic_false_positive, rational_residuals = cyclotomic_false_positive_score(matched_phases)
    noncyclo = 1.0 - cyclotomic_false_positive
    return {
        "name": config.name,
        "slug": config.slug,
        "prediction_residual": residual,
        "rank": int(operator.shape[0]),
        "mean_radius_error_from_unit": float(np.mean(np.abs(radii - 1.0))),
        "max_radius": float(np.max(radii)),
        "min_radius": float(np.min(radii)),
        "spectral_alignment_residual": alignment,
        "matched_phase_fractions": [float(value) for value in matched_phases],
        "rational_residuals_denominator_le_32": rational_residuals,
        "cyclotomic_false_positive_fraction_denominator_le_32": cyclotomic_false_positive,
        "noncyclotomic_fraction_denominator_le_32": noncyclo,
        "singular_values": [float(value) for value in singular_values[:10]],
        "R2_status": "PASS" if alignment < 0.08 and noncyclo >= 0.7 else "FAIL",
    }


def run() -> dict:
    rows = [analyze_config(config) for config in CONFIGS]
    metrics = {
        "diagnostic": "R2 Hankel/Koopman recovery on irrational skew-product observations",
        "rows": rows,
        "best_alignment": float(min(row["spectral_alignment_residual"] for row in rows)),
        "pass_count": int(sum(row["R2_status"] == "PASS" for row in rows)),
    }
    SPECTRAL_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))