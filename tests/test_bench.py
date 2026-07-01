"""Statistical helpers behind the headline detection figure: Wilson binomial
confidence intervals and the predicted-coverage band derived from an
independently-measured p̂_min (raised to the h-th power, so its uncertainty is
propagated as a band, not a line)."""

import math

import pytest

from ecodag import bench


def test_wilson_ci_brackets_the_point_estimate():
    low, high = bench.wilson_ci(successes=50, n=100)
    assert low < 0.5 < high
    assert 0.0 <= low <= high <= 1.0


def test_wilson_ci_is_tighter_with_more_samples():
    narrow = bench.wilson_ci(500, 1000)
    wide = bench.wilson_ci(5, 10)
    assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])


def test_wilson_ci_handles_degenerate_counts():
    assert bench.wilson_ci(0, 0) == (0.0, 1.0)
    lo, hi = bench.wilson_ci(10, 10)
    assert hi == 1.0 or hi > lo  # all-success stays well-defined


def test_predicted_coverage_matches_closed_form():
    # 1 - (1 - p)^h
    assert math.isclose(bench.predict_coverage(0.5, 1), 0.5)
    assert math.isclose(bench.predict_coverage(0.5, 2), 0.75)
    assert math.isclose(bench.predict_coverage(0.5, 3), 0.875)


def test_percentile_is_monotone_and_bracketing():
    data = list(range(1, 101))  # 1..100
    lo = bench.percentile(data, 2.5)
    hi = bench.percentile(data, 97.5)
    assert data[0] <= lo < hi <= data[-1]
    assert bench.percentile(data, 50) == pytest.approx(50, abs=1.5)


def test_predicted_band_widens_with_h_and_brackets_center():
    center, lo, hi = bench.predict_band(p_hat=0.5, p_ci=(0.4, 0.6), h=4)
    assert lo <= center <= hi
    assert math.isclose(center, bench.predict_coverage(0.5, 4))
    # band comes from propagating the p CI through the h-th power
    assert math.isclose(lo, bench.predict_coverage(0.4, 4))
    assert math.isclose(hi, bench.predict_coverage(0.6, 4))
