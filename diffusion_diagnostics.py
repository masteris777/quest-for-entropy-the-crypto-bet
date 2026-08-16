from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from skew_product import CONFIGS, simulate_ensemble


HERE = Path(__file__).resolve().parent
DIFFUSION_PATH = HERE / "diffusion_metrics.json"


def fit_alpha(variances: list[float]) -> tuple[float, float]:
    values = np.array(variances, dtype=float)
    excess = np.maximum(values - values[0], 1e-12)
    max_value = float(np.max(values))
    k = np.arange(1, len(values), dtype=float)
    usable = (excess[1:] > 1e-8) & (values[1:] < max(values[0] + 1e-6, 0.85 * max_value))
    if np.sum(usable) < 6:
        return 0.0, 0.0
    log_k = np.log(k[usable])
    log_v = np.log(excess[1:][usable])
    alpha, intercept = np.polyfit(log_k, log_v, 1)
    predicted = alpha * log_k + intercept
    ss_res = float(np.sum((log_v - predicted) ** 2))
    ss_tot = float(np.sum((log_v - np.mean(log_v)) ** 2))
    fit_r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return float(alpha), float(fit_r2)


def classify(alpha: float, variances: list[float]) -> tuple[str, int | None]:
    values = np.array(variances, dtype=float)
    max_value = float(np.max(values))
    saturation_step = None
    for index, value in enumerate(values):
        if max_value > 0 and value >= 0.8 * max_value:
            saturation_step = index
            break
    if saturation_step is not None and saturation_step <= 3:
        return "avalanche", saturation_step
    if 0.3 <= alpha <= 1.2:
        return "polynomial_gentle", saturation_step
    if 1.2 < alpha <= 2.1:
        return "ballistic_polynomial", saturation_step
    if alpha <= 0.1:
        return "rigid_or_bounded", saturation_step
    return "unclassified", saturation_step


def analyze_config(config) -> dict:
    data = simulate_ensemble(config)
    alpha, fit_r2 = fit_alpha(data["variance_by_k"])
    classification, saturation_step = classify(alpha, data["variance_by_k"])
    return {
        "name": config.name,
        "slug": config.slug,
        "variance_by_k": data["variance_by_k"],
        "entropy_by_k": data["entropy_by_k"],
        "support_span_by_k": data["support_span_by_k"],
        "alpha_fit": alpha,
        "alpha_fit_r2": fit_r2,
        "saturation_step_80pct": saturation_step,
        "classification": classification,
        "R3_R7_status": "PASS" if classification == "polynomial_gentle" else "FAIL",
    }


def run() -> dict:
    rows = [analyze_config(config) for config in CONFIGS]
    metrics = {
        "diagnostic": "R3/R7 local packet blur under irrational LWE/KAM skew products",
        "rows": rows,
        "pass_count": int(sum(row["R3_R7_status"] == "PASS" for row in rows)),
    }
    DIFFUSION_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))