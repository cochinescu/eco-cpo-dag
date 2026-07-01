"""Reference detector over the benchmark (M4.5 worked example).

Reads ``events.jsonld``, runs ecodag's Violates predicates over every
same-subject pair at **full coverage** (no sampling, and — crucially — without
ever looking at ``labels.json``), and writes a ``detections.json`` in the format
``score.py`` grades. It is the "oracle" upper bound a sampled watchtower
approaches; running it then scoring it demonstrates the benchmark end-to-end.

Run:
    python benchmark/reference_detector.py --events v1.0/events.jsonld --out detections.json
    python benchmark/score.py --labels v1.0/labels.json --detections detections.json
"""

from __future__ import annotations

import argparse
import json

from ecodag import trace_io
from ecodag.constraints import ConstraintClass, violates
from ecodag.dag import LocalView
from ecodag.sim import _build_ecos


def detect(doc: dict, seed: int = 0) -> list[dict]:
    trace = trace_io.load_jsonld(doc)
    ecos = _build_ecos(trace, seed)
    index_by_id = {e.id: ev.index for e, ev in zip(ecos, trace.events)}
    view = LocalView()
    out: list[dict] = []
    for eco in ecos:
        for old in view.subject_claims(eco):
            for kappa in ConstraintClass:
                if violates(eco, old, kappa, view):
                    out.append({
                        "a_index": index_by_id[eco.id],
                        "b_index": index_by_id[old.id],
                        "kappa": kappa.value,
                    })
        view.append(eco)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    with open(args.events) as fh:
        doc = json.load(fh)
    detections = detect(doc)
    with open(args.out, "w") as fh:
        json.dump({"detections": detections}, fh, indent=2)
    print(f"wrote {len(detections)} detections -> {args.out}")


if __name__ == "__main__":
    main()
