"""Build the frozen, versioned ECO/CPO-DAG contradiction benchmark (M4.5).

Deterministic from a fixed seed, so the artifact is reproducible and citable.
Emits, under ``benchmark/v1.0/``:

  events.jsonld  — EPCIS-2.0-style event list (the detector's *input*)
  labels.json    — ground-truth contradictions (the scorer's *answer key*)
  MANIFEST.json  — schema/version, seed, generator params, sha256 of the above

Run:  python benchmark/build_benchmark.py
"""

from __future__ import annotations

import hashlib
import json
import os

from ecodag import trace_io
from ecodag.trace import generate_trace

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "v1.0")
SEED = 0
PARAMS = dict(n_participants=8, n_subjects=500, base_events_per_subject=6,
              injection_rate=0.5, seed=SEED)


def _sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _dump(obj, path: str) -> None:
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    trace = generate_trace(**PARAMS)
    ev_path = os.path.join(OUT, "events.jsonld")
    lb_path = os.path.join(OUT, "labels.json")
    _dump(trace_io.to_jsonld(trace, meta={"seed": SEED, "params": PARAMS}), ev_path)
    _dump(trace_io.to_labels(trace), lb_path)

    slash = sum(1 for c in trace.contradictions if c.expected == "slash")
    manifest = {
        "schemaVersion": trace_io.SCHEMA_VERSION,
        "benchmarkVersion": "1.0",
        "seed": SEED,
        "params": PARAMS,
        "nEvents": len(trace.events),
        "nContradictions": len(trace.contradictions),
        "nSlashExpected": slash,
        "nBottomExpected": len(trace.contradictions) - slash,
        "sha256": {"events.jsonld": _sha256(ev_path),
                   "labels.json": _sha256(lb_path)},
    }
    _dump(manifest, os.path.join(OUT, "MANIFEST.json"))
    print(f"wrote benchmark v1.0: {len(trace.events)} events, "
          f"{len(trace.contradictions)} contradictions ({slash} slash / "
          f"{len(trace.contradictions) - slash} bottom) -> {OUT}")


if __name__ == "__main__":
    main()
