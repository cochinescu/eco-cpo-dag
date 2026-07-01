"""M4.5 benchmark: serialisation round-trip, scorer, and reference detector."""

import importlib.util
import os

from ecodag import trace_io
from ecodag.trace import generate_trace

_BENCH = os.path.join(os.path.dirname(__file__), "..", "benchmark")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_BENCH, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


score = _load("score")
reference_detector = _load("reference_detector")


def _trace():
    return generate_trace(n_participants=5, n_subjects=60,
                          base_events_per_subject=5, injection_rate=0.6, seed=1)


def test_jsonld_roundtrip_preserves_events():
    t = _trace()
    doc = trace_io.to_jsonld(t, meta={"seed": 1})
    back = trace_io.load_jsonld(doc)
    assert back.n_participants == t.n_participants
    assert len(back.events) == len(t.events)
    for a, b in zip(t.events, back.events):
        assert (a.index, a.issuer, a.subj, a.refs) == (b.index, b.issuer, b.subj, b.refs)
        assert a.claim == b.claim


def test_labels_shape():
    t = _trace()
    labels = trace_io.to_labels(t)
    assert labels["nEvents"] == len(t.events)
    assert len(labels["contradictions"]) == len(t.contradictions)
    for c in labels["contradictions"]:
        assert c["expected"] in ("slash", "bottom")
        assert set(c) >= {"id", "kappa", "a_index", "b_index", "adversarial", "expected"}


def test_scorer_perfect_and_false_positive():
    t = _trace()
    labels = trace_io.to_labels(t)
    perfect = [{"a_index": c["a_index"], "b_index": c["b_index"], "kappa": c["kappa"]}
               for c in labels["contradictions"]]
    r = score.score(labels, perfect)
    assert r["precision"] == 1.0 and r["recall_coverage"] == 1.0

    # a bogus pair is a false positive; unordered matching still holds
    bogus = perfect + [{"a_index": 999999, "b_index": 1000000, "kappa": "spatial"}]
    r2 = score.score(labels, bogus)
    assert r2["false_positives"] == 1 and r2["precision"] < 1.0
    assert r2["recall_coverage"] == 1.0

    r3 = score.score(labels, [])
    assert r3["recall_coverage"] == 0.0


def test_reference_detector_hits_full_coverage():
    t = _trace()
    doc = trace_io.to_jsonld(t)
    detections = reference_detector.detect(doc)
    labels = trace_io.to_labels(t)
    r = score.score(labels, detections)
    # the oracle detector at full coverage finds every injected contradiction
    # and manufactures none (baseline chains are consistent)
    assert r["recall_coverage"] == 1.0
    assert r["precision"] == 1.0
