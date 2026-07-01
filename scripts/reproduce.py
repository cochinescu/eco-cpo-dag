#!/usr/bin/env python3
"""Reproduce every measurement from a single seed and write CSVs + RESULTS.md.

    python scripts/reproduce.py --seed 0            # full run (~2 min)
    python scripts/reproduce.py --seed 0 --quick    # smaller/faster

Then render figures with ``python scripts/plot.py``.

Determinism: logical outputs (coverage, blame counts, storage) are bit-for-bit
reproducible from the seed; the ZK timing rows are wall-clock measurements and
are reported as mean/median (they will not match across machines).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ecodag import bench  # noqa: E402


def _write_csv(path: str, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None, help="output dir (default: ../results)")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--no-plot", action="store_true",
                    help="skip figure rendering (CSVs only)")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    out = args.out or os.path.join(os.path.dirname(here), "results")
    os.makedirs(out, exist_ok=True)
    seed = args.seed

    # Parameters (recorded in RESULTS.md so synthetic numbers are reproducible).
    if args.quick:
        zk_bits, zk_iters = [16], 3
        cov_params = dict(n_participants=6, n_subjects=60,
                          base_events_per_subject=5, injection_rate=0.6)
        trials = list(range(4))
        storage_params = dict(n_participants=6, n_subjects=100,
                              base_events_per_subject=6, injection_rate=0.2)
        h_values = [1, 2, 4, 8]
    else:
        zk_bits, zk_iters = [16, 32], 10
        cov_params = dict(n_participants=6, n_subjects=120,
                          base_events_per_subject=5, injection_rate=0.6)
        trials = list(range(10))
        storage_params = dict(n_participants=6, n_subjects=400,
                              base_events_per_subject=6, injection_rate=0.2)
        h_values = [1, 2, 3, 4, 6, 8]
    fraction = 0.5
    fractions = [0.1, 0.25, 0.5, 0.75, 1.0]
    cov_h = 4

    print("[1/6] CPO generate/verify times + watchtower scan throughput ...")
    cpo_rows = bench.measure_cpo_times(seed, iterations=(200 if args.quick else 2000))
    _write_csv(os.path.join(out, "cpo_times.csv"), cpo_rows, list(cpo_rows[0]))
    scan_sizes = [1, 5, 10, 25, 50] if args.quick else [1, 5, 10, 25, 50, 100]
    scan_rows = bench.measure_scan_times(seed, scan_sizes,
                                         iterations=(200 if args.quick else 300))
    _write_csv(os.path.join(out, "scan_times.csv"), scan_rows, list(scan_rows[0]))

    print(f"[2/6] ZK proofs (bits={zk_bits}, iters={zk_iters}) ... (slow)")
    zk_rows = bench.measure_zk(seed, zk_bits, zk_iters)
    _write_csv(os.path.join(out, "zk_proofs.csv"), zk_rows, list(zk_rows[0]))

    print("[3/6] Storage growth ...")
    storage = bench.measure_storage(seed, storage_params)
    _write_csv(os.path.join(out, "storage_growth.csv"), storage["growth"],
               ["objects", "cumulative_bytes"])
    _write_csv(os.path.join(out, "storage_refset.csv"),
               [{"refset_size": k, "count": v}
                for k, v in sorted(storage["refset_histogram"].items())],
               ["refset_size", "count"])

    print("[4/6] Detection: p_hat + coverage vs h + coverage vs fraction ...")
    pmin = bench.estimate_pmin(fraction, trials, cov_params)
    cov_h_rows = bench.measure_coverage_vs_h(fraction, h_values, trials, cov_params)
    for r in cov_h_rows:
        c, lo, hi = bench.predict_band(pmin["p_hat"], pmin["ci"], r["h"])
        r["predicted"], r["predicted_low"], r["predicted_high"] = c, lo, hi
    _write_csv(os.path.join(out, "coverage_vs_h.csv"), cov_h_rows,
               ["h", "coverage", "ci_low", "ci_high", "successes", "n",
                "predicted", "predicted_low", "predicted_high"])
    cov_f_rows = bench.measure_coverage_vs_fraction(fractions, cov_h, trials, cov_params)
    _write_csv(os.path.join(out, "coverage_vs_fraction.csv"), cov_f_rows,
               ["fraction", "coverage", "ci_low", "ci_high", "successes", "n"])

    print("[5/6] Blame breakdown + zero-injection control ...")
    breakdown = bench.measure_blame_breakdown(seed, cov_params)
    breakdown_rows = [
        {"metric": k, "value": breakdown[k]}
        for k in ("self_equivocation", "monotonic", "bottom", "slash_total",
                  "false_slashes", "false_positives", "produced_cpos",
                  "true_positive_cpos", "n_injected", "n_detected")
    ]
    breakdown_rows.append({"metric": "precision", "value": f"{breakdown['precision']:.4f}"})
    _write_csv(os.path.join(out, "blame_breakdown.csv"), breakdown_rows,
               ["metric", "value"])
    control = bench.zero_injection_control(seed, cov_params)

    print("[6/6] Writing RESULTS.md ...")
    meta = {
        "seed": seed, "quick": args.quick,
        "coverage_params": cov_params, "storage_params": storage_params,
        "trials": len(trials), "sampling_fraction": fraction,
        "pmin": pmin, "control": control, "breakdown": breakdown,
        "bytes_per_object_mean": storage["bytes_per_object_mean"],
        "n_storage_objects": storage["n_objects"],
    }
    with open(os.path.join(out, "run_meta.json"), "w") as f:
        json.dump(meta, f, indent=2, default=str)
    _write_results_md(os.path.join(out, "RESULTS.md"), meta, cpo_rows, zk_rows,
                      cov_h_rows, scan_rows)

    if not args.no_plot:
        try:
            import plot  # same scripts/ dir
            plot.fig_cpo_times(out, out)
            plot.fig_scan(out, out)
            plot.fig_zk(out, out)
            plot.fig_storage(out, out)
            plot.fig_detection(out, out)
            print("figures rendered")
        except Exception as e:  # matplotlib optional; CSVs already written
            print(f"(plot skipped: {e})")
    print(f"done -> {out}")


def _write_results_md(path, meta, cpo_rows, zk_rows, cov_h_rows, scan_rows) -> None:
    p = meta["pmin"]
    b = meta["breakdown"]
    ctrl = meta["control"]
    lines = [
        "# Measured Results (generated by scripts/reproduce.py)",
        "",
        f"Seed: `{meta['seed']}`  ·  quick={meta['quick']}  ·  "
        f"trials={meta['trials']}  ·  sampling fraction f={meta['sampling_fraction']}",
        "",
        "> **Honesty notes.** The Pedersen commitment / ZK range proof use a "
        "2048-bit MODP (RFC 3526) integer group, not the paper's Ristretto curve. "
        "The ZK size/time numbers are therefore a **conservative upper bound**: a "
        "Bulletproofs/curve implementation would be far smaller and faster. "
        "Hashing is BLAKE2b (stdlib) standing in for BLAKE3. All traces are "
        "**synthetic** with the parameters recorded below.",
        "",
        "## 1. Plaintext CPO generate + verify (µs, by constraint class)",
        "",
        "Median with central 95% band [p2.5, p97.5] over the sample.",
        "",
        "| class | generate (median µs, [95% band]) | verify (median µs, [95% band]) |",
        "|---|---|---|",
    ]
    for r in cpo_rows:
        lines.append(
            f"| {r['constraint']} | {r['generate_us_median']:.1f} "
            f"[{r['generate_us_ci_low']:.1f}, {r['generate_us_ci_high']:.1f}] | "
            f"{r['verify_us_median']:.1f} "
            f"[{r['verify_us_ci_low']:.1f}, {r['verify_us_ci_high']:.1f}] |")
    lines += [
        "",
        "## 1b. Watchtower scan throughput (Detect() µs per incoming ECO)",
        "",
        "Steady-state cost of scanning a new ECO against the same-subject history "
        "(all 5 classes, sampling fraction 1.0), vs. history size. The temporal "
        "and quality predicates walk causal ancestry (a refs DFS), so on a long "
        "chain this grows **super-linearly** (≈ quadratic) in history size — which "
        "is precisely the unbounded baseline the radius limit / candidate-pair "
        "sampling exist to bound.",
        "",
        "| subject-history size | scan (median µs) | [95% band] |",
        "|---|---|---|",
    ]
    for r in scan_rows:
        lines.append(
            f"| {r['history_size']} | {r['detect_us_median']:.1f} | "
            f"[{r['detect_us_ci_low']:.1f}, {r['detect_us_ci_high']:.1f}] |")
    lines += [
        "",
        "## 2. ZK quantity range proof (naive Sigma; conservative upper bound)",
        "",
        "| bits | proof size (bytes) | prove (median ms, [95% band]) | verify (median ms, [95% band]) |",
        "|---|---|---|---|",
    ]
    for r in zk_rows:
        lines.append(
            f"| {r['bits']} | {r['proof_size_bytes']} | "
            f"{r['prove_ms_median']:.1f} "
            f"[{r['prove_ms_ci_low']:.1f}, {r['prove_ms_ci_high']:.1f}] | "
            f"{r['verify_ms_median']:.1f} "
            f"[{r['verify_ms_ci_low']:.1f}, {r['verify_ms_ci_high']:.1f}] |")
    lines += [
        "",
        "## 3. Storage growth",
        "",
        f"- Measured **{meta['bytes_per_object_mean']:.1f} bytes/object** over "
        f"{meta['n_storage_objects']} objects "
        f"(paper estimate: ≈256 B/object).",
        f"- Storage trace params: `{meta['storage_params']}`.",
        f"- The actual ref-set-size distribution is in `storage_refset.csv` "
        f"(the 256 B/object figure depends on it).",
        "",
        "## 4. Detection coverage (the headline: measured vs. model)",
        "",
        f"- **p̂_min** (single-observer, single-draw, f={p['fraction']}) = "
        f"**{p['p_hat']:.3f}**  (Wilson 95% CI "
        f"[{p['ci'][0]:.3f}, {p['ci'][1]:.3f}], n={p['n']}).",
        f"- Model: coverage = 1 − (1 − p̂_min)^h, with the band from p̂_min's CI.",
        "- Agreement criterion: the predicted band overlaps the measured Wilson CI "
        "at every h. Measured vs. predicted per h:",
        "",
        "| h | measured (95% CI) | predicted band |",
        "|---|---|---|",
    ]
    agree = True
    for r in cov_h_rows:
        overlap = not (r["ci_high"] < r["predicted_low"] or r["ci_low"] > r["predicted_high"])
        agree = agree and overlap
        lines.append(
            f"| {r['h']} | {r['coverage']:.3f} "
            f"[{r['ci_low']:.3f}, {r['ci_high']:.3f}] | "
            f"{r['predicted']:.3f} [{r['predicted_low']:.3f}, "
            f"{r['predicted_high']:.3f}] |")
    lines += [
        "",
        f"**Model/measurement agreement: {'YES' if agree else 'NO'}** "
        f"(band overlaps CI at every h).",
        "",
        f"- Coverage params: `{meta['coverage_params']}`.",
        "",
        "## 5. Blame-outcome breakdown + controls",
        "",
        f"- self-equivocation slashes: **{b['self_equivocation']}**; "
        f"monotonic slashes: **{b['monotonic']}**; ⊥ (adjudication): **{b['bottom']}**.",
        f"- **false slashes (honest party slashed): {b['false_slashes']}** "
        f"(target: 0).",
        f"- **precision** = true-positive CPOs / produced CPOs = "
        f"{b['true_positive_cpos']}/{b['produced_cpos']} = "
        f"**{b['precision']:.3f}** (false positives: {b['false_positives']}).",
        f"- **zero-injection control**: {ctrl['cpos']} CPOs over "
        f"{ctrl['n_events']} honest events = "
        f"**{ctrl['cpos_per_honest_event']:.4f} CPOs/honest event** (target: 0).",
        "",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
