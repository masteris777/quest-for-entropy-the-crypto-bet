# Quest for Entropy #8 — The Crypto Bet

Companion code for the article *The Crypto Bet*.

Six small finite machines of the kind cryptography is built from, run against a list of
requirements written down in advance, plus one attempt to repair the failure by bolting an
irrational turn onto the best-behaved of them. This repo re-runs both from scratch and
checks every number the article quotes.

## Run it

```
pip install -r requirements.txt
python run_all.py
```

About a minute. It runs both experiments from scratch and checks the published numbers
against the fresh output. Exits non-zero if anything drifted.

To regenerate the figures as well:

```
python make_figures.py
```

## What is in here

| file | what it is |
|---|---|
| `checklist_scan.py` | the six machines against the requirements: orbit decomposition, spectra, blur |
| `skew_product.py` | the shared construction behind the repair attempt |
| `spectral_diagnostics.py` | does the repaired machine hold tones that never repeat? |
| `diffusion_diagnostics.py` | how fast does a small uncertainty spread? |
| `bounded_predictor.py` | a bounded observer's stress test: can a ridge model predict it? |
| `repair_run.py` | runs the three repair diagnostics and scores them |
| `make_figures.py` | the article's figures, drawn from the stored metrics |
| `run_all.py` | the reproduction gate |
| `checklist_reference.json`, `repair_reference.json` | the numbers as published |
| `assets/` | the figures and hero as published |

## Honesty notes

**Neither experiment is a clean failure.** Both came back partial. The repair genuinely
works on the half it was aimed at — the tones do stop repeating, to machine precision. What
fails is the combination: nothing here holds non-repeating tones *and* a gentle blur at the
same time.

**Six machines is six machines.** The toys are small on purpose — small enough to enumerate
every state and count every orbit exactly. That is the strength of the result and its limit
in the same breath. Nothing here says anything about the security of real cryptography;
these experiments measure spectra and spreading, and they break nothing.

**The closed-orbit argument is standard.** A finite reversible map is a permutation, its
orbits are cycles, and its eigenvalues are roots of unity. That is textbook algebra, not a
result of this repo. What this repo does is check whether the thing hoped for could survive it.

## Licence

Code MIT. Article text CC BY 4.0.
