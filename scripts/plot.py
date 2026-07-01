#!/usr/bin/env python3
"""Render the figures from results/*.csv — four headline figures (Fig 1–4) plus
the supplementary Fig 1b (scan time vs. subject-history size).

    python scripts/plot.py [--results ../results]

Figure 4 is the headline: measured coverage points with Wilson 95% CIs overlaid
on the predicted 1-(1-p̂_min)^h band (not a bare line — the band propagates
p̂_min's own uncertainty).
"""

from __future__ import annotations

import argparse
import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def fig_cpo_times(results, out):
    rows = _read(os.path.join(results, "cpo_times.csv"))
    classes = [r["constraint"] for r in rows]
    gen = [float(r["generate_us_median"]) for r in rows]
    ver = [float(r["verify_us_median"]) for r in rows]
    x = range(len(classes))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([i - 0.2 for i in x], gen, width=0.4, label="generate")
    ax.bar([i + 0.2 for i in x], ver, width=0.4, label="verify")
    ax.set_yscale("log")
    ax.set_xticks(list(x))
    ax.set_xticklabels(classes, rotation=20)
    ax.set_ylabel("time (µs, median, log scale)")
    ax.set_title("Fig 1. Plaintext CPO generate/verify time by constraint class")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig1_cpo_times.png"), dpi=130)
    plt.close(fig)


def fig_scan(results, out):
    rows = _read(os.path.join(results, "scan_times.csv"))
    k = [int(r["history_size"]) for r in rows]
    med = [float(r["detect_us_median"]) for r in rows]
    lo = [max(0.0, float(r["detect_us_median"]) - float(r["detect_us_ci_low"]))
          for r in rows]
    hi = [max(0.0, float(r["detect_us_ci_high"]) - float(r["detect_us_median"]))
          for r in rows]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.errorbar(k, med, yerr=[lo, hi], fmt="o-", color="tab:orange", capsize=3,
                label="measured (median, 95% band)")
    # quadratic reference through the last point, to show the super-linear trend
    if k and k[-1] > 0:
        ref = [med[-1] * (x / k[-1]) ** 2 for x in k]
        ax.plot(k, ref, "--", color="gray", alpha=0.7, label="∝ history²")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("subject-history size (same-subject claims)")
    ax.set_ylabel("Detect() scan time (µs, log)")
    ax.set_title("Fig 1b. Watchtower scan time vs. subject-history size")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig1b_scan.png"), dpi=130)
    plt.close(fig)


def fig_zk(results, out):
    rows = _read(os.path.join(results, "zk_proofs.csv"))
    bits = [r["bits"] for r in rows]
    size_kb = [float(r["proof_size_bytes"]) / 1024 for r in rows]
    prove = [float(r["prove_ms_median"]) for r in rows]
    verify = [float(r["verify_ms_median"]) for r in rows]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
    a1.bar(bits, size_kb, color="tab:purple")
    a1.set_xlabel("range bits"); a1.set_ylabel("proof size (KB)")
    a1.set_title("ZK proof size")
    x = range(len(bits))
    a2.bar([i - 0.2 for i in x], prove, width=0.4, label="prove")
    a2.bar([i + 0.2 for i in x], verify, width=0.4, label="verify")
    a2.set_xticks(list(x)); a2.set_xticklabels(bits)
    a2.set_xlabel("range bits"); a2.set_ylabel("time (ms, median)")
    a2.set_title("ZK prove/verify time"); a2.legend()
    fig.suptitle("Fig 2. ZK quantity range proof (2048-bit MODP; conservative upper bound)")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig2_zk.png"), dpi=130)
    plt.close(fig)


def fig_storage(results, out):
    rows = _read(os.path.join(results, "storage_growth.csv"))
    objs = [int(r["objects"]) for r in rows]
    mb = [float(r["cumulative_bytes"]) / 1e6 for r in rows]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(objs, mb, color="tab:green")
    per_obj = rows[-1]["cumulative_bytes"] and (
        float(rows[-1]["cumulative_bytes"]) / int(rows[-1]["objects"]))
    ax.set_xlabel("objects in local view")
    ax.set_ylabel("cumulative size (MB)")
    ax.set_title(f"Fig 3. Storage growth (~{per_obj:.0f} B/object; "
                 f"paper estimate 256 B)")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig3_storage.png"), dpi=130)
    plt.close(fig)


def fig_detection(results, out):
    h_rows = _read(os.path.join(results, "coverage_vs_h.csv"))
    f_rows = _read(os.path.join(results, "coverage_vs_fraction.csv"))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.5))

    # left: coverage vs h, measured CI points over predicted band
    h = [int(r["h"]) for r in h_rows]
    cov = [float(r["coverage"]) for r in h_rows]
    # matplotlib requires non-negative error-bar distances; the Wilson interval
    # can sit fully below a point estimate of 1.0, so clamp at 0.
    lo = [max(0.0, float(r["coverage"]) - float(r["ci_low"])) for r in h_rows]
    hi = [max(0.0, float(r["ci_high"]) - float(r["coverage"])) for r in h_rows]
    pred = [float(r["predicted"]) for r in h_rows]
    plo = [float(r["predicted_low"]) for r in h_rows]
    phi = [float(r["predicted_high"]) for r in h_rows]
    a1.fill_between(h, plo, phi, alpha=0.25, color="tab:blue",
                    label="model band 1-(1-p̂_min)^h")
    a1.plot(h, pred, "--", color="tab:blue", label="model center")
    a1.errorbar(h, cov, yerr=[lo, hi], fmt="o", color="black", capsize=3,
                label="measured (95% CI)")
    a1.set_xlabel("honest watchtowers h")
    a1.set_ylabel("detection coverage")
    a1.set_title("Measured vs. model (f=0.5)")
    a1.set_ylim(0, 1.02); a1.legend(fontsize=8)

    # right: coverage vs sampling fraction
    fr = [float(r["fraction"]) for r in f_rows]
    fcov = [float(r["coverage"]) for r in f_rows]
    flo = [max(0.0, float(r["coverage"]) - float(r["ci_low"])) for r in f_rows]
    fhi = [max(0.0, float(r["ci_high"]) - float(r["coverage"])) for r in f_rows]
    a2.errorbar(fr, fcov, yerr=[flo, fhi], fmt="s-", color="tab:red", capsize=3)
    a2.set_xlabel("candidate-pair sampling fraction")
    a2.set_ylabel("detection coverage")
    a2.set_title("Coverage vs. sampling fraction (h=4)")
    a2.set_ylim(0, 1.02)

    fig.suptitle("Fig 4. Detection coverage — measured points vs. Theorem-1 model")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig4_detection.png"), dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--results", default=os.path.join(os.path.dirname(here), "results"))
    args = ap.parse_args()
    r = args.results
    fig_cpo_times(r, r)
    fig_scan(r, r)
    fig_zk(r, r)
    fig_storage(r, r)
    fig_detection(r, r)
    print(f"figures written -> {r}")


if __name__ == "__main__":
    main()
