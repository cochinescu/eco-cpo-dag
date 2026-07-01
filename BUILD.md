# Building & running the prototype

This is the **implementation** of the plan in [`README.md`](README.md): a
single-machine Python simulation + microbenchmarks of the ECO/CPO-DAG
accountability layer. It is a first cut in the "Python lane" the plan permits;
everything is test-driven and reproducible from a seed.

## Setup

```bash
cd prototype
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"    # pynacl, pytest, matplotlib
```

## Run the tests

```bash
.venv/bin/python -m pytest -q
```

## Reproduce every measurement + figure (one command)

```bash
.venv/bin/python scripts/reproduce.py --seed 0            # full (~3 min, ZK-bound)
.venv/bin/python scripts/reproduce.py --seed 0 --quick    # fast smoke run
```

Outputs land in `results/`: the CSVs, the four headline figures
(`fig1..fig4_*.png`) plus the supplementary `fig1b_scan.png` (scan time vs.
subject-history size), the blame-outcome breakdown, `run_meta.json`, and a
generated `RESULTS.md`. Re-render figures alone with
`.venv/bin/python scripts/plot.py`.

## Module map (`ecodag/`)

| module | role | plan ref |
|---|---|---|
| `crypto.py` | BLAKE2b hash, prime-order Pedersen commitment, Ed25519 | §2 |
| `hlc.py` | hybrid logical clock (injected physical time → deterministic) | §3 |
| `eco.py` | Event Claim Object + `create_eco` (Algorithm 1) | §3 |
| `dag.py` | local-view DAG, `SubjectClaims`, causal-ancestor walk | §3, §4.3 |
| `constraints.py` | the 5 `Violates` predicates (Table 2 mapping) | §4.4 |
| `blame.py` | Blame resolver (self-equiv / monotonic / ⊥ carve-outs) | §5.1 |
| `cpo.py` | plaintext CPO make + verify | §4.5 |
| `zkrange.py` | ZK range proof over the homomorphic difference (quantity) | §6.1/§6.2 |
| `trace.py` | synthetic EPCIS traces + labelled injected contradictions | §4 |
| `trace_io.py` | versioned JSON-LD export + labels sidecar (M4.5 benchmark format) | §4 |
| `sim.py` | N participants + h watchtowers, sampled detection, instrumentation | §5 harness |
| `bench.py` | 4 measurements + scan throughput + Wilson CIs + timing bands + predicted band | §5 eval |

The standalone benchmark artifact lives in `benchmark/` (frozen `v1.0/` set,
`score.py`, `reference_detector.py`, `build_benchmark.py`, README, LICENSE).

CPO verification binds the violation check to the **commitment-opened** claim
(the witness), not the free-floating in-memory `eco.claim`, so a spoofed
plaintext field cannot forge a contradiction (`cpo.verify_cpo`).

## Milestone status vs. the plan

- **M1–M4: done.** All 5 constraints, Blame with the §4.4/§5.1 carve-outs, the
  sim harness with independent-seed candidate-pair sampling, the ZK quantity
  path, and the four headline figures (+ supplementary Fig 1b) + blame breakdown
  are implemented and tested.
  Measurement 1 also reports **watchtower scan throughput** (Detect() µs/ECO vs.
  subject-history size, `scan_times.csv`), timing rows carry a **95% percentile
  band**, and the evaluation reports **precision** and the zero-injection
  **CPOs/honest-event** rate. The trace injects quantity contradictions in
  **both** modes, so the blame breakdown exercises the conservation (quantity)
  slash branch alongside self-equivocation and the honest-receiver ⊥ case.
- **Adaptive-adversary trace mode: not implemented.** `generate_trace(...,
  adaptive=True)` raises `NotImplementedError` so no run can silently imply the
  paper's Table 4 adaptive-evasion row was tested (README §4).
- **M4.5 (standalone benchmark artifact): done.** `benchmark/` ships a frozen,
  seeded `v1.0/` set (`events.jsonld` + `labels.json` + `MANIFEST.json` with
  SHA-256s: 3480 events, 240 labelled contradictions), a standard-library-only
  `score.py` that grades any language's detector, a label-free
  `reference_detector.py` worked example (precision/recall 1.0 at full coverage),
  `build_benchmark.py`, a README, and a CC BY 4.0 LICENSE. Minting the Zenodo DOI
  and pasting it into the paper + benchmark README is the only manual step left.
- **M5 (fold numbers back into the paper): not done here** — deliberately. The
  paper is out of scope for this implementation; `RESULTS.md` holds the measured
  numbers ready to be cited when M5 happens.

## Honesty caveats (also in generated `RESULTS.md`)

- Pedersen/ZK run over a **2048-bit MODP integer group**, not the paper's
  Ristretto curve, so ZK **size/time are a conservative upper bound** — a
  Bulletproofs/curve build would be far smaller and faster. The detection,
  blame, storage, and coverage results are unaffected by this choice.
- Hashing is **BLAKE2b** (stdlib) standing in for BLAKE3.
- All traces are **synthetic**; the generator parameters are recorded in
  `RESULTS.md`/`run_meta.json`. Securing a real/public EPCIS trace (plan §4)
  remains the biggest external-validity lever.
- Logical outputs (coverage, blame counts, storage) are bit-for-bit
  reproducible from the seed; the ZK/CPO **timing** rows are wall-clock and are
  reported as mean/median (they will not match across machines).
