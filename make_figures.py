"""The article's figures. Light theme, to sit on a white page.

    python make_figures.py

Reads the two experiments' stored metrics; nothing is retyped, so the figures
cannot drift from the runs. Writes into this folder.
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

HERE = Path(__file__).resolve().parent
M50 = json.loads((HERE / "metrics_checklist.json").read_text(encoding="utf-8"))
M51 = json.loads((HERE / "metrics_repair.json").read_text(encoding="utf-8"))

BG, INK, MUTED = "#faf8f4", "#1a1a1a", "#8a8580"
RED, GREEN, AMBER, BLUE = "#c1362f", "#2e7d4f", "#c98a1b", "#2f5fa8"

plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK,
                     "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK})

SHORT = {
    "Modular squaring on QR_N": "modular squaring",
    "LWE-style affine lattice shear": "LWE-style lattice shear",
    "Primitive-root multiplication": "primitive-root multiply",
    "LFSR 12-bit": "LFSR, 12-bit",
    "Mini-SPN 8-bit (4 rounds)": "mini-SPN, 8-bit",
    "Mini-SPN 16-bit (5 rounds)": "mini-SPN, 16-bit",
}
COLS = ["R1", "R2", "R3", "R4", "R6", "R7"]
WHAT = {"R1": "pure point\nspectrum", "R2": "never\nrepeats", "R3": "gentle\nblur",
        "R4": "invertible", "R6": "hard to\npredict", "R7": "bounded\ntransport"}


def face(v):
    if v is None:
        return "#e8e4de", MUTED, "-"
    if v.startswith("PASS"):
        return "#dceadf", GREEN, "PASS" if v == "PASS" else v.replace("PASS_", "").lower()
    if v.startswith("FAIL"):
        return "#f5dcd9", RED, "FAIL"
    return "#f7ecd6", AMBER, "part"


def hero():
    rows = M50["scorecard"]
    nr, nc = len(rows), len(COLS)
    fig, ax = plt.subplots(figsize=(12.6, 6.4), facecolor=BG)
    ax.set_facecolor(BG)

    for j, c in enumerate(COLS):
        ax.text(j + 0.5, nr + 0.62, c, ha="center", va="bottom", fontsize=15, color=INK, weight="bold")
        ax.text(j + 0.5, nr + 0.16, WHAT[c], ha="center", va="bottom", fontsize=9.5, color=MUTED)

    for i, r in enumerate(rows):
        y = nr - 1 - i
        ax.text(-0.22, y + 0.5, SHORT.get(r["primitive"], r["primitive"]),
                ha="right", va="center", fontsize=12.5, color=INK)
        for j, c in enumerate(COLS):
            bg, fg, lab = face(r.get(c))
            ax.add_patch(Rectangle((j + 0.06, y + 0.08), 0.88, 0.84, facecolor=bg,
                                   edgecolor="none", zorder=2))
            ax.text(j + 0.5, y + 0.5, lab, ha="center", va="center",
                    fontsize=10.5, color=fg, weight="bold", zorder=3)

    # the wall: R2 is the column where every single one dies
    j2 = COLS.index("R2")
    ax.add_patch(Rectangle((j2 - 0.01, 0.02), 1.02, nr - 0.04, fill=False,
                           edgecolor=RED, lw=2.6, zorder=5))
    # callout sits BELOW its own column - anywhere inside the grid it lands on a neighbouring cell
    ax.annotate("every one of them,\nfor the same reason",
                xy=(j2 + 0.5, -0.04), xytext=(j2 + 0.5, -0.62),
                fontsize=12.5, color=RED, ha="center", va="top",
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.8))

    ax.set_xlim(-3.35, nc + 0.25)
    ax.set_ylim(-2.35, nr + 1.45)
    ax.axis("off")
    ax.text(-3.3, nr + 1.02, "Six things that are deterministic, unpredictable, and never repeat.",
            fontsize=16.5, color=INK, ha="left")
    ax.text(-3.3, -1.62,
            "A finite machine is a permutation, so its spectrum is automatically pure point (R1) — and "
            "for exactly the same reason\nevery eigenvalue is a root of unity, so it can never be "
            "non-repeating (R2). Passing the first test is what makes the second impossible.",
            fontsize=11, color=MUTED, ha="left", va="top")
    fig.tight_layout()
    fig.savefig(HERE / "hero_the_wall.png", dpi=170, facecolor=BG)
    plt.close(fig)
    print("hero_the_wall.png")


def cycles():
    rows = M50["results"]
    names = [SHORT.get(r["name"], r["name"]) for r in rows]
    cyc = [r["spectral"]["max_cycle_length"] for r in rows]
    size = [r["size"] for r in rows]
    y = np.arange(len(rows))[::-1]

    fig, ax = plt.subplots(figsize=(11.2, 5.2), facecolor=BG)
    ax.set_facecolor(BG)
    ax.barh(y + 0.18, size, height=0.34, color="#dfe6f0", edgecolor=BLUE, lw=1.1,
            label="states in the whole machine")
    ax.barh(y - 0.18, cyc, height=0.34, color="#f0d7d4", edgecolor=RED, lw=1.1,
            label="longest orbit before it repeats")
    for yy, c in zip(y, cyc):
        ax.text(c * 1.12, yy - 0.18, f"{c:,}", va="center", fontsize=10.5, color=RED)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=11.5)
    ax.set_xscale("log")
    ax.set_xlabel("states  (log scale)")
    ax.set_xlim(50, 8e5)
    # legend below the axes: inside the plot it lands on the 16-bit bars and their label
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2,
              frameon=False, fontsize=10.5)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_title("“Never repeats in any horizon you could live to see”", fontsize=14, color=INK, loc="left")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(HERE / "cycles.png", dpi=170, facecolor=BG)
    plt.close(fig)
    print("cycles.png")


def blanket():
    sc = M51["scorecard"]
    names = [s["name"].replace(" shear", "\nshear") for s in sc]
    res = [s["spectral_alignment_residual"] for s in sc]
    al = [s["alpha_fit"] for s in sc]
    x = np.arange(len(sc))

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.9), facecolor=BG)
    a = axes[0]
    a.set_facecolor(BG)
    a.bar(x, res, color="#dceadf", edgecolor=GREEN, lw=1.3, width=0.55)
    a.set_yscale("log")
    a.set_ylabel("spectral alignment residual")
    a.set_title("Fix the spectrum:  it works", fontsize=13.5, color=GREEN, loc="left")
    for xi, r in zip(x, res):
        a.text(xi, r * 1.6, f"{r:.0e}", ha="center", fontsize=10, color=GREEN)
    a.set_ylim(1e-16, 1e-5)

    b = axes[1]
    b.set_facecolor(BG)
    b.axhspan(0.3, 1.2, color="#dceadf", zorder=1)
    # band label lives in the left margin; anywhere over the bars it collides with one of them
    b.set_xlim(-1.25, len(sc) - 0.55)
    b.text(-1.18, 0.75, "the target band\n0.3 – 1.2", ha="left", va="center",
           fontsize=10.5, color=GREEN, zorder=4)
    b.bar(x, al, color="#f0d7d4", edgecolor=RED, lw=1.3, width=0.55, zorder=3)
    for xi, v in zip(x, al):
        b.text(xi, v + 0.06, f"{v:.3f}", ha="center", fontsize=10.5, color=RED, zorder=4)
    b.set_ylabel("blur exponent  α")
    b.set_ylim(0, 1.85)
    b.set_title("…and the blur goes ballistic", fontsize=13.5, color=RED, loc="left")

    for ax_ in axes:
        ax_.set_xticks(x)
        ax_.set_xticklabels(names, fontsize=10.5)
        for s in ("top", "right"):
            ax_.spines[s].set_visible(False)
    fig.suptitle("The blanket is too short", fontsize=16, color=INK, x=0.012, ha="left", y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(HERE / "blanket.png", dpi=170, facecolor=BG)
    plt.close(fig)
    print("blanket.png")


if __name__ == "__main__":
    hero()
    cycles()
    blanket()
