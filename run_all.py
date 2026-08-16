"""Reproduce every claim episode #8 makes, from scratch.

    python run_all.py

Runs the checklist scan (six finite machines against the requirements) and the repair
attempt (an irrational turn bolted onto the best-behaved one), then checks the published
numbers against the fresh output. Exits non-zero if anything has drifted.

Needs numpy. Regenerating the figures additionally needs matplotlib. About a minute.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
fails = []


def check(name, got, want, tol=0.0):
    ok = (got == want) if tol == 0 else (got is not None and abs(got - want) <= tol)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}\n         got {got!r}, expected {want!r}")
    if not ok:
        fails.append(name)


def flag(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  (' + detail + ')' if detail else ''}")
    if not ok:
        fails.append(name)


print("1. the checklist scan - six finite machines ...\n")
subprocess.run([sys.executable, "checklist_scan.py"], cwd=HERE, check=True)
M = json.loads((HERE / "metrics_checklist.json").read_text(encoding="utf-8"))
R = json.loads((HERE / "checklist_reference.json").read_text(encoding="utf-8"))


def row(m, slug):
    return next(r for r in m["results"] if r["slug"] == slug)


SIX = ["modular_squaring", "lwe_shear", "primitive_root_multiplication",
       "lfsr_12", "mini_spn_8", "mini_spn_16"]

print("\n   every machine holds clean tones - and that is the trap:\n")
flag("all six pass the first requirement",
     all(s["R1"] == "PASS" for s in M["scorecard"]),
     f"{sum(s['R1'] == 'PASS' for s in M['scorecard'])} of 6")
flag("all six fail the never-repeat requirement, strictly",
     all(s["R2"] == "FAIL_STRICT" for s in M["scorecard"]),
     f"{sum(s['R2'] == 'FAIL_STRICT' for s in M['scorecard'])} of 6")
check("machines that passed every hard requirement", M["hard_requirement_passes"], 0)

print("\n   how long until it comes back around:\n")
for slug in SIX:
    got = row(M, slug)["spectral"]["max_cycle_length"]
    want = row(R, slug)["spectral"]["max_cycle_length"]
    check(f"{slug}: longest orbit", got, want)

spn = row(M, "mini_spn_16")["spectral"]
flag("the most cipher-like machine repeats inside its own state space",
     spn["max_cycle_length"] < spn["state_count"],
     f"{spn['max_cycle_length']:,} of {spn['state_count']:,} states")

print("\n2. the repair - an irrational turn bolted on ...\n")
subprocess.run([sys.executable, "repair_run.py"], cwd=HERE, check=True)
P = json.loads((HERE / "metrics_repair.json").read_text(encoding="utf-8"))
PR = json.loads((HERE / "repair_reference.json").read_text(encoding="utf-8"))
ref = {r["slug"]: r for r in PR["scorecard"]}

print("\n   the tones stop repeating - the repair works:\n")
for r in P["scorecard"]:
    flag(f"{r['slug']}: never-repeat requirement now passes", r["R2"] == "PASS")
    want = ref[r["slug"]]["spectral_alignment_residual"]
    got = r["spectral_alignment_residual"]
    flag(f"{r['slug']}: alignment residual reproduces",
         got <= max(want * 10, 1e-14), f"{got:.3e} vs {want:.3e}")

print("\n   ...and the gentle blur is gone:\n")
for r in P["scorecard"]:
    want = ref[r["slug"]]["alpha_fit"]
    check(f"{r['slug']}: blur exponent", round(r["alpha_fit"], 3), round(want, 3), 0.02)
    flag(f"{r['slug']}: blur is outside the target band 0.3-1.2",
         r["alpha_fit"] > 1.2, f"alpha={r['alpha_fit']:.3f}")
flag("no machine holds both at once",
     not any(r["R2"] == "PASS" and r["R3_R7"] == "PASS" for r in P["scorecard"]))

print("\n" + ("-" * 62))
if fails:
    print(f"{len(fails)} CHECK(S) FAILED: {', '.join(fails)}")
    sys.exit(1)
print("all checks reproduced")
