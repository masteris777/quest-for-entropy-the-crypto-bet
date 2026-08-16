from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from skew_product import CONFIGS, simulate_single


HERE = Path(__file__).resolve().parent
PREDICTOR_PATH = HERE / "predictor_metrics.json"


def lag_matrix(series: np.ndarray, lag: int, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows = []
    targets = []
    persistence = []
    for index in range(lag, len(series) - horizon):
        rows.append(series[index - lag : index])
        targets.append(series[index + horizon])
        persistence.append(series[index - 1])
    return np.array(rows), np.array(targets), np.array(persistence)


def ridge_predict(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, ridge: float = 1e-5) -> np.ndarray:
    design = np.column_stack((train_x, np.ones(len(train_x))))
    test_design = np.column_stack((test_x, np.ones(len(test_x))))
    gram = design.T @ design + ridge * np.eye(design.shape[1])
    weights = np.linalg.solve(gram, design.T @ train_y)
    return test_design @ weights


def rmse(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.sqrt(np.mean((left - right) ** 2)))


def analyze_config(config) -> dict:
    trace = simulate_single(config, steps=18000)
    target = trace["position"]
    target = (target - np.mean(target)) / max(np.std(target), 1e-12)
    rows = []
    for horizon in [1, 5, 20, 80]:
        features, labels, persistence = lag_matrix(target, lag=48, horizon=horizon)
        split = int(0.55 * len(features))
        predictions = ridge_predict(features[:split], labels[:split], features[split:])
        model_rmse = rmse(predictions, labels[split:])
        persistence_rmse = rmse(persistence[split:], labels[split:])
        mean_rmse = rmse(np.full_like(labels[split:], np.mean(labels[:split])), labels[split:])
        baseline = min(persistence_rmse, mean_rmse)
        advantage = 1.0 - model_rmse / max(baseline, 1e-12)
        rows.append(
            {
                "horizon": horizon,
                "model_rmse": model_rmse,
                "best_baseline_rmse": baseline,
                "advantage_over_best_baseline": float(advantage),
            }
        )
    long_advantage = rows[-1]["advantage_over_best_baseline"]
    short_advantage = rows[0]["advantage_over_best_baseline"]
    if long_advantage > 0.25:
        status = "FAIL_PREDICTABLE"
    elif short_advantage > 0.10 and long_advantage <= 0.25:
        status = "PARTIAL_SHORT_ONLY"
    else:
        status = "SURVIVES_THIS_TEST"
    return {
        "name": config.name,
        "slug": config.slug,
        "observer_class": "rank-limited lag-48 ridge predictor from scalar position observations; no hidden phase or model parameters",
        "rows": rows,
        "R6_bounded_predictor_status": status,
    }


def run() -> dict:
    rows = [analyze_config(config) for config in CONFIGS]
    metrics = {
        "diagnostic": "R6 bounded pointwise predictor stress test",
        "rows": rows,
        "survival_count": int(sum(row["R6_bounded_predictor_status"] != "FAIL_PREDICTABLE" for row in rows)),
    }
    PREDICTOR_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))