# ECO/CPO-DAG — Prototype & Measured Evaluation

This repository holds the reference implementation, measured evaluation, and
benchmark for the paper *"ECO/CPO-DAG: A Contradiction-Based Accountability
Layer for Adversarial Supply Chains"* (Sebastian Cochinescu, University of
Bucharest). See **Artifacts & citation** at the end for DOIs.

**Key framing:** this is a *single-machine simulation plus microbenchmarks*, not
a real multi-party deployment. No collaborators, adopters, or live supply chain
are needed. One person (with AI help) can build and run all of it on a laptop.

Every number produced here replaces a "model output (not measured)" claim in the
paper's §7–§8. Until then the paper's abstract must keep saying "no implementation
or empirical evaluation is claimed."

> **Implementation status:** all milestones (M1–M5) are complete; the measured numbers are folded into the paper's §8.4. Built and test-driven in the
> `ecodag/` package (Python lane). See **[BUILD.md](BUILD.md)** for setup, tests,
> the one-command reproduction, and the module map. Measured numbers land in
> `results/RESULTS.md`.

---

## 1. Scope — what to build (and what not to)

Build the smallest thing that produces credible measurements:

- ECO creation, signing, and commitment.
- A local-view DAG with causal `refs` and hybrid-logical-clock timestamps.
- The `Violates` predicates for the 5 constraint classes (Table 2 of the paper).
- CPO generation + public verification, in two modes:
  - **plaintext-opening** CPO (open both commitments, check the rule);
  - **ZK** CPO for the quantity constraint (range proof over the homomorphic
    difference — the one crypto-heavy path).
- The `Blame` resolver (self-equivocation, monotonic violation, else ⊥) — matches
  the revised §5.1.
- A **simulation harness**: N participants + h watchtowers as threads/async
  tasks, fed synthetic EPCIS 2.0 event traces with injected contradictions,
  each watchtower doing radius-limited, randomly-sampled **same-subject
  candidate-pair** walks over the `SubjectClaims` set (`refs`/radius only order
  the walk).

**Do NOT build:** a real P2P network, on-chain smart contracts, a consensus/
checkpoint BFT layer, a UI, or persistence beyond a file. Stub the network as
in-process message passing; stub checkpoints as periodic Merkle-root snapshots.

## 2. Tech choices (pick one lane, don't mix)

Recommended: **Rust** (best ZK/crypto library ecosystem and honest performance
numbers). Python is acceptable for a faster, rougher first cut.

| Concern | Rust choice | Python choice |
|---|---|---|
| Signatures | `ed25519-dalek` | `pynacl` |
| Pedersen commitment | `curve25519-dalek` (Ristretto) | `petlib` / manual on `cryptography` |
| ZK range proof (quantity) | `bulletproofs` crate | `pybulletproofs` / port |
| Groth16 (optional 2nd datapoint) | `arkworks` (`ark-groth16`) | `snarkjs` via node shim |
| Merkle | `rs_merkle` | `pymerkle` |
| Hashing / HLC | `blake3`, hand-rolled HLC | `blake3`, hand-rolled HLC |

Use **Bulletproofs** as the primary ZK backend (transparent setup — no trusted
ceremony, matches the caveat now in §6.2). Groth16 is an optional second column
in the proof-cost table if time allows.

## 3. Suggested layout

```
prototype/
  README.md            <- this file
  Cargo.toml           (or pyproject.toml)
  src/
    eco.rs             ECO struct, CreateECO (Algorithm 1)
    dag.rs             local-view DAG, refs, HLC, SubjectClaims (all same-subject ECOs; refs/radius only order the walk)
    constraints.rs     Violates predicates for the 5 classes
                       (temporal monotonicity MUST order by causal `refs`, not
                       raw HLC/wall-clock — happened-before-incomparable
                       (concurrent) events are NOT a violation; comparing HLC
                       values naively false-positives on concurrency → false slash.
                       QUANTITY: the CPO binds exactly TWO ECOs and Detect is
                       pairwise, but ∑outputs > ∑inputs is n-ary — so commit to a
                       scalar *aggregate* per ECO and range-prove cm₁ − cm₂ (the
                       two-ECO reading; matches §6.1). Decide and document this
                       before M3. REGULATORY: the paper (§4.4) now settles this
                       as a two-ECO contradiction — a compliance assertion vs. a
                       revocation/expiry record for the cited certificate.
                       Implement that pairing; a *lone* missing certificate is a
                       single-claim validity check outside the pairwise-CPO shape,
                       so keep it out of scope or flag it separately.
                       QUALITY: only a *self-equivocation on condition* (two of one
                       issuer's own condition claims that are jointly impossible)
                       is slashable and closed over the pair. A monotone
                       'improvement without an intervening authorized
                       transformation/certification' is existential over a
                       possibly-partial view — a watchtower missing the authorizing
                       event would false-slash an honest issuer — so the Blame
                       resolver MUST route it to ⊥, never slash (mirrors the
                       §4.4/§5.1 carve-out). Aligned in M2.)
    cpo.rs             MakeCPO, verify (plaintext + ZK quantity), Blame
    sim.rs             N participants + h watchtowers, trace replay, injection
    trace.rs           synthetic EPCIS 2.0 trace generator / loader
                       (DESIGN THE OUTPUT AS A STABLE, VERSIONED, PROTOCOL-
                       INDEPENDENT FORMAT NOW — EPCIS 2.0 JSON-LD events + a
                       sidecar ground-truth labels file. Cheap up front, costly to
                       retrofit; this is what makes the M4.5 benchmark artifact a
                       repackaging job, not a rewrite.)
  benches/             microbenchmarks (criterion or pytest-benchmark)
  data/                sample EPCIS traces (generated + any public sample)
  results/             raw CSVs + generated figures
  scripts/plot.py      turns results/*.csv into the figures (4 headline + supplementary Fig 1b)
```

## 4. EPCIS traces

- Generate synthetic GS1 EPCIS 2.0 events (ObjectEvent, AggregationEvent,
  TransformationEvent, TransactionEvent) for a set of lots/items with realistic
  branching custody chains.
- **Pin the event-type mapping to the paper's Table 2 before freezing the trace
  format** (this decides the versioned schema, so it is cheap now and costly to
  retrofit): quantity contradictions are carried by **TransformationEvent**
  `inputQuantityList`/`outputQuantityList` (the mass-balance ∑out > ∑in as one
  issuer's input claim vs. its own later output claim) — **not** AggregationEvent,
  which is reversible containment. Quality/condition contradictions are carried
  by an **ObjectEvent `disposition` and/or `sensorElementList`** channel (a
  cold-chain excursion is a `sensorElementList` temperature reading), so the
  generator must emit a sensor/condition field or `constraints.rs`'s quality
  predicate has nothing to read and the quality/cold-chain blame rows can't be
  exercised. Emit quality contradictions in **both** directions so the §4.4
  carve-out is tested: (i) a *jointly-impossible* self-equivocation pair (one
  issuer's two mutually-inconsistent condition claims → slashable), and (ii) an
  *authorized-improvement* pair where an intervening authorized
  transformation/certification is present (→ must resolve to ⊥, never slash).
- **Secure at least one public/real EPCIS 2.0 trace** (e.g. a GS1 sample
  document) and run storage + coverage on it. This is elevated from "if
  available" to a target: single-synthetic-generator numbers have weak external
  validity, and a real-structure run is the most valuable external-validity extension after the
  measured-vs-model overlay. If no real trace can be obtained, say so explicitly
  in `RESULTS.md` and label every number synthetic.
- Provide a knob to **inject each contradiction class** at a controllable rate so
  detection can be measured against ground truth.
- Provide **two injection modes**: (a) *random* placement (the baseline), and
  (b) an *adaptive adversary* that places contradictions to exploit the radius
  limit / sampling fraction (far-apart events, low-traffic subjects). The paper's
  Table 4 claims "adaptive evasion — sometimes — more watchtowers"; only mode (b)
  substantiates that row. If you build only mode (a), **scope the eval as
  non-adaptive and leave Table 4's adaptive-evasion row analytical** — do not let
  a random-injection result imply the adaptive claim was tested.

## 5. The evaluation — 4 core measurements → 4 figures (+ 1 breakdown)

Keep the headline set to these four; each replaces a specific analytical claim in
the paper. Measurement 5 is a cheap instrumentation output, not a figure.

1. **Watchtower throughput & CPO generate/verify time** (plaintext path).
   Replaces: the "we do not report … times" hedge in §6.2. Report the steady-state
   scan time to run `Detect` per incoming ECO — but note `Detect` is
   O(|same-subject claims| × 5 constraints), so it grows with a subject's history
   depth. **Do not report a single "µs/ECO" headline**; plot scan time *vs.
   subject-history size* (or fix and state the history depth), or the
   high-throughput claim won't generalize. Also report mean/median CPO generate +
   verify time over ≥1k pairs, by constraint class.
2. **ZK proof size + prove/verify time** (quantity range proof; Groth16 second
   column if built). Replaces: the "published asymptotics only" hedge in §6.2 —
   **for the quantity range proof only.** Scope guard: this does NOT measure the
   *fully ZK CPO* of §6.2 ("I know openings of cm₁,cm₂ under valid signatures such
   that κ is violated"), which verifies signatures inside the circuit and is far
   harder. That claim stays analytical; do not let M5 imply it was measured.
3. **Storage growth.** Measure bytes/object and cumulative local-view size vs.
   time; compare to the ~256 B/object and ~1 GB/yr estimate in §8. Replaces: the
   first-principles storage estimate. The 256 B/object figure is dominated by the
   bounded `refs` set size and branching factor, so **log the actual ref-set-size
   distribution** rather than trusting the assumption — the paper says these
   reference-count assumptions are stated so they can be recomputed, so recompute
   them. Prefer a real/public EPCIS trace if one is loaded (§4); otherwise run on
   synthetic traces and **record the branching/ref-set parameters** in `results/`
   so the number is reproducible and honestly labelled as synthetic. (This
   supersedes any "on a real trace" wording — a real trace is preferred, not
   required.)
4. **Detection coverage vs. watchtowers h** (and vs. same-subject candidate-pair
   sampling fraction). Plot *measured* coverage points on the same axes as the Theorem 1
   curve `1 − (1 − p_min)^h`. Replaces: the model-only Figure 4. This
   measured-vs-model overlay is the strongest single figure — it validates (or
   honestly bounds) the paper's central detection claim.

   **Do this the non-circular way, or the figure proves nothing.** The theorem
   is valid only under the independence the paper claims in §7 — independence
   from *randomized same-subject candidate-pair sampling*, where h counts the
   observers that hold **both** ECOs of a pair and draw independent samples (the
   paper's current phrasing; the older "distinct local views" wording was
   superseded). Concretely: each watchtower must draw its candidate-pair sample
   with an **independent seed**, never a shared/deterministic view — otherwise
   the bound collapses to a single Bernoulli trial. And `p_min` for the model curve must
   come from an *independent* measurement, not be fit to the aggregate data:
   1. Measure single-observer, single-draw coverage → this is the empirical
      `p̂_min` (per the paper's definition of `p_min`).
   2. *Predict* `1 − (1 − p̂_min)^h` from that number alone.
   3. Separately measure multi-observer aggregate coverage as h grows.
   4. Overlay measured (step 3) on predicted (step 2). Agreement validates the
      model; a gap is an honest, publishable bound.

   **Put error bars on both, or "agreement" is not defensible.** A reviewer will
   reject a bare line-through-points. Required: (i) fix N — the number of
   *independent* injected contradictions behind each (h, fraction) data point —
   and state it; (ii) report a **Wilson (binomial) confidence interval** on every
   measured coverage point, since coverage is a proportion over N trials; (iii)
   `p̂_min` is itself an estimate with sampling error, and the prediction raises it
   to the h-th power, so **propagate that error — the predicted curve is a band,
   not a line**; (iv) state the agreement criterion up front (e.g. "predicted band
   overlaps the measured CI at every h"). Without (i)–(iv) the headline figure
   is not publishable.

   The two sweeps (over h, and over candidate-pair sampling fraction) are two
   separate runs, but they form the two panels of the single Figure 4 replacement
   — so the headline count stays at **four figures**. The zero-injection
   false-positive rate below is a number reported in `results/RESULTS.md`, not a
   fifth figure. If the adaptive-adversary mode (§4) is built, its coverage run is
   an *additional* figure (random vs. adaptive placement on the same axes), not
   one of the core four.

   **Precision, not just recall.** Coverage above is recall (true positives).
   Also run a **zero-injection control**: replay a fully honest trace with no
   injected contradictions and confirm **zero CPOs are produced**. Report the
   false-positive rate alongside coverage. This is cheap and directly hardens the
   "zero honest parties slashed" claim below — a contradiction-detection protocol
   is only credible if it does not manufacture contradictions.

5. **Blame-outcome breakdown** (instrumentation, not a headline figure). For
   every detected contradiction, record which bucket it lands in: (a) valid CPO
   (contradiction verified), (b) determinate-blame CPO that triggers slashing —
   split by self-equivocation vs. attributable monotonic violation, (c)
   ⊥-blame CPO routed to off-chain adjudication. (For the quality class only
   self-equivocation-on-condition slashes and lands in (b); a quality
   improvement-without-authorization must appear in (c) ⊥, never (b).) Report the counts and the
   ratio of automatic-slash to ⊥. Purpose: shows empirically how much of the
   protocol's action is determinate (slashing) vs. ambiguous (adjudication) —
   directly substantiates the §5.1 blame rule and the Table 5 scenarios, and
   surfaces the honest-receiver cross-party case (must land in ⊥, never slash).

Determinism (two regimes, don't conflate them):
- **Logical outputs** (coverage, blame counts, CPO validity) must be
  bit-for-bit reproducible: fix and record all seeds/timestamps in `results/`.
  Note the tension with Measurement 4 — the per-watchtower sampling seeds must be
  *distinct* across observers (for independence) yet *recorded* (for
  reproducibility). Derive them deterministically from one master seed + observer
  index.
- **Timing microbenchmarks** (Measurements 1–2) are inherently wall-clock
  variable and need many iterations; they are NOT bit-reproducible and won't
  match across machines. Report mean/median + a confidence interval over runs,
  not a single "deterministic" number.

The harness must log ground-truth (which injected contradictions were
adversarial) so the breakdown can be checked for false slashes — the target is
**zero** honest parties slashed. Do not rely on random injection alone to prove
this: add a **targeted test that explicitly constructs the honest-receiver
cross-party monotone-mismatch case** and asserts it lands in ⊥ (never slash).
Add the **quality analogue** too: an issuer that legitimately records a
condition improvement *with* an intervening authorized transformation, where a
watchtower's partial view is missing that authorizing event — assert it lands
in ⊥, never slash (the §4.4 quality carve-out).
Random traces may hit that case rarely or never; the property must be tested
directly.

## 6. Milestones (rough, solo + AI)

1. **M1 — core objects + one constraint end-to-end.** CreateECO, DAG append,
   spatial `Violates`, plaintext CPO + verify. Prove the loop works.
2. **M2 — all 5 constraints + Blame + sim harness.** N participants, h
   watchtowers, trace replay, contradiction injection, ground-truth coverage.
3. **M3 — ZK quantity path.** Bulletproofs range proof over committed difference.
4. **M4 — benchmarks + figures.** Produce the 4 headline figures (plus the
   supplementary Fig 1b scan-time plot) and their CSVs; write a short
   `results/RESULTS.md`.
4.5. **M4.5 — package the EPCIS contradiction benchmark as a standalone,
   independently citable artifact.** Datasets/benchmarks are reused far
   more than one-off systems, and you already build ~90% of it in `trace.rs` +
   injection + ground-truth labels — this is repackaging, not new research.
   Do it **after M4** (once traces + injection are stable), never before; do not
   let it delay the paper. Deliverables:
   - **Frozen, versioned trace sets** (v1.0, seeded) — EPCIS 2.0 JSON-LD events +
     a sidecar labels file (which events are the injected contradiction, its
     class, and adversarial-vs-honest ground truth). Format decoupled from the
     protocol internals (see §3 `trace.rs` note).
   - **A language-agnostic scorer** — a small script that takes any detector's
     output and computes precision/recall/coverage vs. the labels, so people who
     never touch this repo's Rust can benchmark their own detector.
   - **README + license + its own Zenodo DOI**, referenced *from* the paper.
   Positioning discipline: call it *a* reproducible benchmark with stated
   generative assumptions, not *the* standard; include at least one real/public
   EPCIS trace (§4) to blunt "synthetic is unrealistic." Do **not** split it into
   a separate paper yet — release as a sub-artifact cited within the main paper;
   spin off only if it gains traction.
5. **M5 — fold back into paper.** Replace §7–§8 model numbers with measured ones;
   update the abstract (drop "no implementation … is claimed"); add a
   reproducibility paragraph pointing at this folder + a Zenodo DOI.
   - **Don't over-claim in the abstract.** The prototype measures a *single-machine
     simulation* — CPO gen/verify, the quantity range proof, storage, and
     detection coverage. It does NOT measure the fully-ZK CPO, a multi-party
     network, or (unless mode (b) is built) the adaptive adversary. Replace the
     dropped line with a precise scope sentence, pre-written here to reuse
     verbatim: *"We implement a single-machine reference of the protocol and
     report measured CPO generation/verification cost, quantity range-proof size
     and time, storage growth, and detection coverage against the Theorem 1 model;
     the fully zero-knowledge CPO, multi-party propagation, and adaptive-adversary
     evasion remain analytical."*
   - **Sampling terminology is already aligned.** Both the paper (§7–§8) and this
     prototype use "same-subject candidate-pair sampling" (the watchtower draw over
     the `SubjectClaims` set). Keep them in sync if you ever rename either.

   **Framing a model/measurement gap (decide before you see the numbers).** If
   the measured `p̂_min` is low, the honest coverage curve (Measurement 4) may sit
   well below the illustrative `p_min` values in the current Figure 4, and the
   storage number may diverge from the ~1 GB/yr estimate. Per this plan's own
   philosophy an honest gap is publishable — but pre-commit to the framing so M5
   is not tempted to cherry-pick: (a) keep the analytical curve and overlay the
   measured points on the *same* axes, labelling which is model vs. measured;
   (b) report `p̂_min` as an empirical input, not a tuned knob; (c) if coverage is
   lower than the illustration, present it as "coverage is whatever the chosen
   (p_min, h, t) yield" (already the §7 stance) and, if needed, show that raising
   h or the sampling fraction recovers it — do not silently swap in a rosier
   `p_min`. A gap that is explained is a stronger result than an unexamined match.

## 7. Done criteria

- `results/` contains the 4 headline figures (Fig 1–4) + the supplementary
  Fig 1b, their measurement CSVs, and the blame-outcome breakdown CSV — all
  regenerable from a single command with a fixed seed. (The current
  implementation emits 5 figures and 9 CSVs; "4 headline" refers to the four
  measured claims that replace §7–§8's model numbers.)
- The breakdown shows **zero** honest parties slashed (no false slash); every
  cross-party monotone mismatch lands in ⊥ — verified both by the seeded run and
  by the explicit targeted test (§5).
- The **zero-injection control run produces zero CPOs**, and a false-positive
  rate is reported alongside detection coverage.
- Numbers are plausible and, where the paper made an estimate (256 B/object,
  ~1 GB/yr, Theorem 1 coverage), the measured value is reported alongside the
  estimate — agreement or honest discrepancy, either is publishable.
- Repo builds clean; a `scripts/` one-liner reproduces every figure.
- **(M4.5)** The benchmark artifact ships: frozen versioned EPCIS 2.0 traces +
  ground-truth labels + a language-agnostic scorer + its own Zenodo DOI, and a
  third party can score an external detector against it without touching this
  repo's Rust.

## 8. Artifacts & citation

- **Code (this repository):** archived on Zenodo — concept DOI
  [10.5281/zenodo.21114383](https://doi.org/10.5281/zenodo.21114383)
  (always resolves to the latest version).
- **EPCIS contradiction benchmark:** independently citable dataset —
  [10.5281/zenodo.21114601](https://doi.org/10.5281/zenodo.21114601)
  (see [`benchmark/`](benchmark/) for format and scorer).
- **Paper preprint:** arXiv (cs.CR), ID to be added on announcement.

If you use the code or the benchmark, please cite the paper and the
corresponding DOI above.
