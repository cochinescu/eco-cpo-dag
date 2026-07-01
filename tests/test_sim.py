"""Simulation harness + trace generator.

Pins the measurement-critical invariants:
* full sampling detects every injected contradiction;
* zero-injection produces zero CPOs (false-positive control);
* an honest party is never slashed (No-false-accusation), including the
  cross-party quantity case that must resolve to ⊥;
* more watchtowers never lowers coverage.
"""

from ecodag.constraints import ConstraintClass
from ecodag import sim, trace


def test_full_sampling_detects_all_injected_contradictions():
    t = trace.generate_trace(n_participants=4, n_subjects=30,
                             base_events_per_subject=4, injection_rate=0.5,
                             seed=1)
    assert t.contradictions, "generator should inject some contradictions"
    result = sim.run_simulation(t, n_watchtowers=3, sampling_fraction=1.0, seed=1)
    assert result.coverage == 1.0


def test_zero_injection_produces_no_cpos():
    t = trace.generate_trace(n_participants=4, n_subjects=30,
                             base_events_per_subject=4, injection_rate=0.0,
                             seed=2)
    assert t.contradictions == []
    result = sim.run_simulation(t, n_watchtowers=3, sampling_fraction=1.0, seed=2)
    assert result.cpo_count == 0
    assert result.false_positives == 0


def test_no_honest_party_is_ever_slashed():
    t = trace.generate_trace(n_participants=5, n_subjects=50,
                             base_events_per_subject=5, injection_rate=0.6,
                             seed=3)
    result = sim.run_simulation(t, n_watchtowers=4, sampling_fraction=1.0, seed=3)
    assert result.false_slashes == 0


def test_cross_party_quantity_resolves_to_bottom_never_slash():
    # Targeted honest-receiver case: sender under-reports, honest receiver
    # reports the true larger reading. Must resolve to ⊥, never slash.
    t = trace.single_contradiction_trace(ConstraintClass.QUANTITY, cross_party=True)
    result = sim.run_simulation(t, n_watchtowers=2, sampling_fraction=1.0, seed=4)
    assert result.coverage == 1.0            # it IS detected as a contradiction
    assert result.slash_count == 0           # but nobody is slashed
    assert result.bottom_count >= 1


def test_self_equivocation_is_slashed():
    t = trace.single_contradiction_trace(ConstraintClass.SPATIAL, cross_party=False)
    result = sim.run_simulation(t, n_watchtowers=2, sampling_fraction=1.0, seed=5)
    assert result.slash_count >= 1
    assert result.false_slashes == 0


def test_more_watchtowers_never_lowers_coverage():
    t = trace.generate_trace(n_participants=4, n_subjects=60,
                             base_events_per_subject=6, injection_rate=0.5,
                             seed=6)
    low = sim.run_simulation(t, n_watchtowers=1, sampling_fraction=0.3, seed=6)
    high = sim.run_simulation(t, n_watchtowers=8, sampling_fraction=0.3, seed=6)
    assert high.coverage >= low.coverage
