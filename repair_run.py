from __future__ import annotations

import json
from pathlib import Path

from bounded_predictor import run as run_predictor
from diffusion_diagnostics import run as run_diffusion
from spectral_diagnostics import run as run_spectral


HERE = Path(__file__).resolve().parent
METRICS_PATH = HERE / "metrics_repair.json"


def by_slug(metrics: dict) -> dict:
    return {row["slug"]: row for row in metrics["rows"]}


def main() -> dict:
    spectral = run_spectral()
    diffusion = run_diffusion()
    predictor = run_predictor()
    spectral_rows = by_slug(spectral)
    diffusion_rows = by_slug(diffusion)
    predictor_rows = by_slug(predictor)
    scorecard = []
    for slug, spectral_row in spectral_rows.items():
        diffusion_row = diffusion_rows[slug]
        predictor_row = predictor_rows[slug]
        r2 = spectral_row["R2_status"]
        r3 = diffusion_row["R3_R7_status"]
        r6 = predictor_row["R6_bounded_predictor_status"]
        if r2 == "PASS" and r3 == "PASS" and r6 != "FAIL_PREDICTABLE":
            verdict = "PASS" if r6 == "SURVIVES_THIS_TEST" else "PARTIAL_R2_R3_R6_SHORT_ONLY"
        elif r2 == "PASS" and r3 == "PASS":
            verdict = "PARTIAL_R2_R3_ONLY"
        elif r2 == "PASS" or r3 == "PASS":
            verdict = "PARTIAL_SINGLE_PILLAR"
        else:
            verdict = "FAIL"
        scorecard.append(
            {
                "name": spectral_row["name"],
                "slug": slug,
                "R2": r2,
                "R3_R7": r3,
                "R6": r6,
                "spectral_alignment_residual": spectral_row["spectral_alignment_residual"],
                "noncyclotomic_fraction_denominator_le_32": spectral_row["noncyclotomic_fraction_denominator_le_32"],
                "alpha_fit": diffusion_row["alpha_fit"],
                "diffusion_classification": diffusion_row["classification"],
                "long_horizon_predictor_advantage": predictor_row["rows"][-1]["advantage_over_best_baseline"],
                "verdict": verdict,
            }
        )
    r2_r3 = [row for row in scorecard if row["R2"] == "PASS" and row["R3_R7"] == "PASS"]
    full = [row for row in scorecard if row["verdict"] == "PASS"]
    if full:
        verdict = "PASS"
    elif r2_r3:
        verdict = "PARTIAL"
    elif any(row["R2"] == "PASS" or row["R3_R7"] == "PASS" for row in scorecard):
        verdict = "PARTIAL_SINGLE_PILLAR"
    else:
        verdict = "FAIL"
    metrics = {
        "verdict": verdict,
        "both_pillars_held": bool(r2_r3),
        "verdict_note": "A follow-up was to run only if both pillars held at once. The predictor stage is a bounded-observer stress test, not a cryptographic proof.",
        "spectral_metrics_file": "spectral_metrics.json",
        "diffusion_metrics_file": "diffusion_metrics.json",
        "predictor_metrics_file": "predictor_metrics.json",
        "scorecard": scorecard,
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"verdict: {verdict}")
    for row in scorecard:
        print(
            f"{row['name']}: {row['verdict']} | R2={row['R2']} | R3={row['R3_R7']} | "
            f"R6={row['R6']} | alpha={row['alpha_fit']:.3f} | align={row['spectral_alignment_residual']:.3e}"
        )
    return metrics


if __name__ == "__main__":
    main()