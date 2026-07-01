"""Measurement functions for the four headline figures (+ the supplementary
scan-time figure) and the blame breakdown.

Everything here returns plain dicts/lists so ``scripts/reproduce.py`` can write
CSVs directly. Statistics: Wilson binomial CIs on measured proportions, and a
predicted-coverage *band* obtained by propagating p̂_min's CI through 1-(1-p)^h
(the plan requires error bars on both the measured points and the model curve).
"""

from __future__ import annotations

import math
import statistics
import time
from random import Random

from . import sim, zkrange
from .constraints import ConstraintClass, violates
from .cpo import make_cpo, verify_cpo
from .crypto import commit, random_scalar
from .dag import LocalView
from .trace import generate_trace, single_contradiction_trace

# --- statistics --------------------------------------------------------------


def percentile(data: list[float], q: float) -> float:
    """Linear-interpolation percentile (q in [0, 100]); used for timing bands."""
    if not data:
        return 0.0
    xs = sorted(data)
    if len(xs) == 1:
        return xs[0]
    pos = (q / 100) * (len(xs) - 1)
    lo = int(pos)
    frac = pos - lo
    if lo + 1 >= len(xs):
        return xs[-1]
    return xs[lo] + frac * (xs[lo + 1] - xs[lo])


def _band(data: list[float]) -> tuple[float, float]:
    """Central 95% percentile band (p2.5, p97.5)."""
    return percentile(data, 2.5), percentile(data, 97.5)


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    phat = successes / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def predict_coverage(p: float, h: int) -> float:
    return 1 - (1 - p) ** h


def predict_band(p_hat: float, p_ci: tuple[float, float], h: int):
    return (predict_coverage(p_hat, h),
            predict_coverage(p_ci[0], h),
            predict_coverage(p_ci[1], h))


# --- Measurement 1: plaintext CPO generate + verify time ---------------------


def measure_cpo_times(seed: int, iterations: int) -> list[dict]:
    rows = []
    for kappa in ConstraintClass:
        t = single_contradiction_trace(kappa, cross_party=False)
        ecos = sim._build_ecos(t, seed)
        c = t.contradictions[0]
        e1, e2 = ecos[c.a_index], ecos[c.b_index]
        view = LocalView()
        for e in ecos:
            view.append(e)
        assert violates(e1, e2, kappa, view), f"{kappa} pair should violate"

        gen, ver = [], []
        for _ in range(iterations):
            s = time.perf_counter()
            cpo = make_cpo(e1, e2, kappa, challenger=b"bench", deposit=1)
            gen.append((time.perf_counter() - s) * 1e6)
            s = time.perf_counter()
            verify_cpo(cpo, view)
            ver.append((time.perf_counter() - s) * 1e6)
        g_lo, g_hi = _band(gen)
        v_lo, v_hi = _band(ver)
        rows.append({
            "constraint": kappa.value,
            "generate_us_mean": statistics.mean(gen),
            "generate_us_median": statistics.median(gen),
            "generate_us_ci_low": g_lo,
            "generate_us_ci_high": g_hi,
            "verify_us_mean": statistics.mean(ver),
            "verify_us_median": statistics.median(ver),
            "verify_us_ci_low": v_lo,
            "verify_us_ci_high": v_hi,
            "iterations": iterations,
        })
    return rows


# --- Measurement 1b: steady-state watchtower scan time -----------------------


def measure_scan_times(seed: int, history_sizes: list[int],
                       iterations: int) -> list[dict]:
    """Time a watchtower's per-incoming-ECO Detect() scan — subject_claims +
    Violates over all same-subject candidates and all 5 classes at sampling
    fraction 1.0 — as the subject history grows. Reported in µs/ECO.

    Note on complexity: this is more than O(history x 5). The temporal and
    quality predicates call ``LocalView.is_causal_ancestor`` (a refs DFS), so on
    a long causal chain the per-scan cost is super-linear in history size (the
    measured growth is roughly quadratic). This is exactly why the radius limit
    and candidate-pair sampling exist — the benchmark quantifies the unbounded
    baseline the optimisation bounds."""
    from .crypto import Keypair
    from .eco import Claim, create_eco
    from .hlc import HLC

    rows = []
    for k in history_sizes:
        rng = Random(seed ^ (k * 2654435761))
        kp = Keypair.generate(rng)
        hlc = HLC()
        view = LocalView()
        subj = "urn:lot:scan"
        prev: tuple[str, ...] = ()
        for i in range(k):
            e = create_eco(kp, Claim(event_type="ObjectEvent", location="EU",
                                     event_time=i, disposition="good"),
                           subj=subj, refs=list(prev), hlc=hlc, rng=rng, physical=i)
            view.append(e)
            prev = (e.id,)
        incoming = create_eco(kp, Claim(event_type="ObjectEvent", location="EU",
                                        event_time=k, disposition="good"),
                              subj=subj, refs=list(prev), hlc=hlc, rng=rng,
                              physical=k)

        times = []
        for _ in range(iterations):
            s = time.perf_counter()
            for old in view.subject_claims(incoming):
                for kappa in ConstraintClass:
                    violates(incoming, old, kappa, view)
            times.append((time.perf_counter() - s) * 1e6)
        lo, hi = _band(times)
        rows.append({
            "history_size": k,
            "detect_us_mean": statistics.mean(times),
            "detect_us_median": statistics.median(times),
            "detect_us_ci_low": lo,
            "detect_us_ci_high": hi,
            "iterations": iterations,
        })
    return rows


# --- Measurement 2: ZK proof size + prove/verify time ------------------------


def measure_zk(seed: int, bit_widths: list[int], iterations: int) -> list[dict]:
    rng = Random(seed)
    rows = []
    for bits in bit_widths:
        prove_ms, verify_ms, sizes = [], [], []
        for _ in range(iterations):
            in_val, out_val = 100, 150
            r_in, r_out = random_scalar(rng), random_scalar(rng)
            C_in, C_out = commit(in_val, r_in), commit(out_val, r_out)
            s = time.perf_counter()
            proof = zkrange.prove_quantity_violation(in_val, r_in, out_val, r_out,
                                                     bits=bits, rng=rng)
            prove_ms.append((time.perf_counter() - s) * 1e3)
            s = time.perf_counter()
            ok = zkrange.verify_quantity_violation(C_in, C_out, proof, bits=bits)
            verify_ms.append((time.perf_counter() - s) * 1e3)
            assert ok
            sizes.append(zkrange.proof_size_bytes(proof))
        p_lo, p_hi = _band(prove_ms)
        v_lo, v_hi = _band(verify_ms)
        rows.append({
            "bits": bits,
            "proof_size_bytes": sizes[0],
            "prove_ms_mean": statistics.mean(prove_ms),
            "prove_ms_median": statistics.median(prove_ms),
            "prove_ms_ci_low": p_lo,
            "prove_ms_ci_high": p_hi,
            "verify_ms_mean": statistics.mean(verify_ms),
            "verify_ms_median": statistics.median(verify_ms),
            "verify_ms_ci_low": v_lo,
            "verify_ms_ci_high": v_hi,
            "iterations": iterations,
        })
    return rows


# --- Measurement 3: storage growth -------------------------------------------


def eco_public_size(eco) -> int:
    """Serialised size of the public ECO fields ⟨id, τ, refs, subj, cm⟩ + σ +
    issuer key (bytes)."""
    return (32                       # id (BLAKE2b-256)
            + 32                     # cm
            + 64                     # Ed25519 signature
            + 32                     # issuer public key
            + 16                     # HLC timestamp (2 x 8 bytes)
            + len(eco.subj.encode())
            + 32 * len(eco.refs))    # each ref id


def measure_storage(seed: int, trace_params: dict) -> dict:
    t = generate_trace(seed=seed, **trace_params)
    ecos = sim._build_ecos(t, seed)
    cum = 0
    growth = []
    refset_hist: dict[int, int] = {}
    total = 0
    for i, eco in enumerate(ecos, start=1):
        sz = eco_public_size(eco)
        cum += sz
        total += sz
        growth.append({"objects": i, "cumulative_bytes": cum})
        k = len(eco.refs)
        refset_hist[k] = refset_hist.get(k, 0) + 1
    return {
        "growth": growth,
        "bytes_per_object_mean": total / len(ecos),
        "refset_histogram": refset_hist,
        "n_objects": len(ecos),
    }


# --- Measurement 4: detection coverage ---------------------------------------


def _pooled(trace_params: dict, trial_seeds: list[int], h: int,
            fraction: float) -> tuple[int, int]:
    successes = n = 0
    for s in trial_seeds:
        t = generate_trace(seed=s, **trace_params)
        res = sim.run_simulation(t, n_watchtowers=h, sampling_fraction=fraction,
                                 seed=s)
        successes += len(res.detected)
        n += res.n_injected
    return successes, n


def estimate_pmin(fraction: float, trial_seeds: list[int],
                  trace_params: dict) -> dict:
    """Single-observer, single-draw coverage — the empirical p̂_min the model
    curve is built from (measured independently of the multi-observer runs)."""
    successes, n = _pooled(trace_params, trial_seeds, h=1, fraction=fraction)
    return {"p_hat": successes / n, "ci": wilson_ci(successes, n),
            "successes": successes, "n": n, "fraction": fraction}


def measure_coverage_vs_h(fraction: float, h_values: list[int],
                          trial_seeds: list[int], trace_params: dict) -> list[dict]:
    rows = []
    for h in h_values:
        successes, n = _pooled(trace_params, trial_seeds, h=h, fraction=fraction)
        lo, hi = wilson_ci(successes, n)
        rows.append({"h": h, "coverage": successes / n, "ci_low": lo,
                     "ci_high": hi, "successes": successes, "n": n})
    return rows


def measure_coverage_vs_fraction(fractions: list[float], h: int,
                                 trial_seeds: list[int],
                                 trace_params: dict) -> list[dict]:
    rows = []
    for f in fractions:
        successes, n = _pooled(trace_params, trial_seeds, h=h, fraction=f)
        lo, hi = wilson_ci(successes, n)
        rows.append({"fraction": f, "coverage": successes / n, "ci_low": lo,
                     "ci_high": hi, "successes": successes, "n": n})
    return rows


# --- Measurement 5: blame-outcome breakdown + controls -----------------------


def measure_blame_breakdown(seed: int, trace_params: dict) -> dict:
    t = generate_trace(seed=seed, **trace_params)
    res = sim.run_simulation(t, n_watchtowers=4, sampling_fraction=1.0, seed=seed)
    reasons = {"self_equivocation": 0, "monotonic": 0, "bottom": 0}
    by_class = {}
    for c in t.contradictions:
        if c.id in res.detected:
            reasons[res.outcomes[c.id]] += 1
            by_class.setdefault(c.kappa.value, {"slash": 0, "bottom": 0})
            bucket = "bottom" if res.outcomes[c.id] == "bottom" else "slash"
            by_class[c.kappa.value][bucket] += 1
    produced = res.cpo_count
    true_positive = produced - res.false_positives
    precision = (true_positive / produced) if produced else 1.0
    return {
        "self_equivocation": reasons["self_equivocation"],
        "monotonic": reasons["monotonic"],
        "bottom": reasons["bottom"],
        "slash_total": reasons["self_equivocation"] + reasons["monotonic"],
        "false_slashes": res.false_slashes,
        "false_positives": res.false_positives,
        "produced_cpos": produced,
        "true_positive_cpos": true_positive,
        "precision": precision,
        "n_injected": res.n_injected,
        "n_detected": len(res.detected),
        "by_class": by_class,
    }


def zero_injection_control(seed: int, trace_params: dict) -> dict:
    params = dict(trace_params)
    params["injection_rate"] = 0.0
    t = generate_trace(seed=seed, **params)
    res = sim.run_simulation(t, n_watchtowers=4, sampling_fraction=1.0, seed=seed)
    n_events = len(t.events)
    return {"cpos": res.cpo_count, "false_positives": res.false_positives,
            "n_events": n_events,
            "cpos_per_honest_event": res.cpo_count / n_events if n_events else 0.0}
