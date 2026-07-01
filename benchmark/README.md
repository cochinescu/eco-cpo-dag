# ECO/CPO-DAG Contradiction Benchmark

A frozen, versioned, seed-reproducible set of synthetic **GS1 EPCIS 2.0-style**
supply-chain events with **labelled injected contradictions**, for benchmarking
*contradiction detectors* independently of the reference implementation in this
repository. It accompanies the paper *ECO/CPO-DAG: A Contradiction-Based
Accountability Layer for Adversarial Supply Chains* (§8.4) but is released as a
standalone, citable artifact: a detector written in **any language** can be
scored against it without touching this repo's Python.

## Contents (`v1.0/`)

| file | role |
|---|---|
| `events.jsonld` | the detector's **input** — an EPCIS-2.0-style JSON-LD event list |
| `labels.json` | the **answer key** — ground-truth contradictions (do not read this in your detector) |
| `MANIFEST.json` | schema version, seed, generator params, and SHA-256 of the two files above |

`v1.0` is **3480 events over 500 subjects with 240 labelled contradictions**
(211 determinate-slash, 29 honest/⊥), spanning all five constraint classes
(spatial, temporal, quantity, quality, regulatory). It is deterministic from
`seed = 0`.

## Format

**Event** (`events.jsonld` → `epcisBody.eventList[]`):

```json
{
  "@type": "TransformationEvent",
  "eventID": "urn:ecodag:event:42",
  "ecodag:index": 42,
  "ecodag:issuer": 3,
  "ecodag:subject": "urn:lot:17",
  "ecodag:refs": [40],
  "ecodag:claim": { "event_type": "TransformationEvent", "quantity_out": 150 }
}
```

Events reference causal parents by **`ecodag:index`** (stable within the file),
not by any internal id, so the format is protocol-independent. `ecodag:claim`
carries exactly the fields the paper's `Violates` predicates read (Table 2).

**Label** (`labels.json` → `contradictions[]`):

```json
{ "id": 7, "kappa": "quantity", "a_index": 40, "b_index": 42,
  "adversarial": true, "expected": "slash" }
```

`expected` is `"slash"` (determinate blame — same-issuer self-equivocation or a
conservation violation) or `"bottom"` (cross-party / existential cases that must
resolve to ⊥, e.g. the honest-receiver mass-balance mismatch).

## Scoring your detector

Your detector reads `events.jsonld` and writes detections as JSON:

```json
{ "detections": [ { "a_index": 40, "b_index": 42, "kappa": "quantity" } ] }
```

`kappa` is optional; if present it must match the label's class. Pairs are
unordered. Then:

```bash
python score.py --labels v1.0/labels.json --detections your_output.json
```

which reports precision, recall/coverage, and how many of the adversarial
(slash-expected) contradictions were found. `score.py` is standard-library-only.

A worked example using this repo's predicates as an oracle detector:

```bash
python reference_detector.py --events v1.0/events.jsonld --out detections.json
python score.py --labels v1.0/labels.json --detections detections.json
# -> precision 1.0, recall_coverage 1.0 (the full-coverage upper bound)
```

## Reproducing / extending

```bash
python build_benchmark.py    # regenerates v1.0/ deterministically from seed 0
```

The SHA-256 digests in `MANIFEST.json` pin the released files. To propose a new
version, bump the params/seed and the `benchmarkVersion`, and keep old versions
frozen.

## Scope & honesty

- Traces are **synthetic**; the generator parameters are recorded in
  `MANIFEST.json`. Securing a real/public EPCIS 2.0 trace remains the biggest
  external-validity lever and is future work.
- The benchmark grades **detection** (finding the contradicting pair). Blame
  (slash vs. ⊥) is a separate, deterministic function of the pair given in the
  paper's §5.1; the `expected` field lets a scorer that also models blame check
  it, but the default scorer grades detection only.
- Only random contradiction placement is included; an adaptive adversary is
  future work (kept out so no result overstates evasion resistance).

## License

The data and code in this directory are released under **CC BY 4.0**
(`LICENSE`). Attribution: cite the paper and this benchmark's DOI.

## Citation

> S. Cochinescu. *ECO/CPO-DAG Contradiction Benchmark v1.0.* Zenodo, 2026.
> <https://doi.org/10.5281/zenodo.21114601>. Accompanies *ECO/CPO-DAG: A
> Contradiction-Based Accountability Layer for Adversarial Supply Chains.*

The benchmark has its own Zenodo DOI (`10.5281/zenodo.21114601`), separate from
the code repository's concept DOI (`10.5281/zenodo.21114383`), so it is independently
citable.
