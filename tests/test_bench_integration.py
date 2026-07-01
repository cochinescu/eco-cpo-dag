"""Integration checks for the M4 measurement pipeline (fast paths only — ZK
timing is exercised separately)."""

from ecodag import bench

PARAMS = dict(n_participants=4, n_subjects=40, base_events_per_subject=4,
              injection_rate=0.6)
SEEDS = [0, 1, 2, 3]


def test_pmin_estimate_is_near_the_sampling_fraction():
    est = bench.estimate_pmin(0.5, SEEDS, PARAMS)
    assert 0.3 < est["p_hat"] < 0.7
    assert est["n"] > 0


def test_coverage_is_monotone_nondecreasing_in_h():
    rows = bench.measure_coverage_vs_h(0.5, [1, 2, 4, 8], SEEDS, PARAMS)
    covs = [r["coverage"] for r in rows]
    assert covs == sorted(covs)
    assert covs[-1] > covs[0]


def test_blame_breakdown_has_no_false_slashes():
    bd = bench.measure_blame_breakdown(7, PARAMS)
    assert bd["false_slashes"] == 0
    assert bd["n_detected"] > 0


def test_zero_injection_control_is_clean():
    ctrl = bench.zero_injection_control(7, PARAMS)
    assert ctrl["cpos"] == 0
    assert ctrl["false_positives"] == 0


def test_storage_reports_bytes_and_refset_distribution():
    st = bench.measure_storage(7, PARAMS)
    assert st["bytes_per_object_mean"] > 0
    assert sum(st["refset_histogram"].values()) == st["n_objects"]


def test_scan_time_grows_with_subject_history():
    rows = bench.measure_scan_times(0, history_sizes=[1, 10, 40], iterations=50)
    assert [r["history_size"] for r in rows] == [1, 10, 40]
    # steady-state scan cost is non-trivially larger for a bigger history
    assert rows[-1]["detect_us_median"] > rows[0]["detect_us_median"]
    assert rows[-1]["detect_us_ci_high"] >= rows[-1]["detect_us_ci_low"]


def test_blame_breakdown_reports_precision():
    bd = bench.measure_blame_breakdown(7, PARAMS)
    assert bd["produced_cpos"] >= bd["n_detected"]
    assert bd["true_positive_cpos"] == bd["produced_cpos"] - bd["false_positives"]
    assert 0.0 <= bd["precision"] <= 1.0
    # baseline chains are consistent -> no false positives -> precision 1.0
    assert bd["precision"] == 1.0


def test_cpo_timing_rows_include_confidence_band_on_both_sides():
    rows = bench.measure_cpo_times(0, iterations=200)
    r = rows[0]
    assert r["generate_us_ci_low"] <= r["generate_us_median"] <= r["generate_us_ci_high"]
    assert r["verify_us_ci_low"] <= r["verify_us_median"] <= r["verify_us_ci_high"]


def test_zk_timing_rows_include_confidence_band_on_both_sides():
    rows = bench.measure_zk(0, bit_widths=[16], iterations=2)
    r = rows[0]
    assert r["prove_ms_ci_low"] <= r["prove_ms_median"] <= r["prove_ms_ci_high"]
    assert r["verify_ms_ci_low"] <= r["verify_ms_median"] <= r["verify_ms_ci_high"]


def test_adaptive_trace_mode_is_explicitly_unimplemented():
    import pytest
    from ecodag import trace
    with pytest.raises(NotImplementedError):
        trace.generate_trace(n_participants=3, n_subjects=5,
                             base_events_per_subject=3, injection_rate=0.5,
                             seed=0, adaptive=True)
