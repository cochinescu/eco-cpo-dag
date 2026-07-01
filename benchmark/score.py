"""Language-agnostic scorer for the ECO/CPO-DAG contradiction benchmark (M4.5).

A detector — in ANY language — reads ``events.jsonld``, emits a JSON file of the
contradictions it found, and this script grades it against ``labels.json``.
Only the Python standard library is used, so the scorer is trivially portable.

Detector output format (JSON):

    {"detections": [{"a_index": <int>, "b_index": <int>, "kappa": "<class>"}, ...]}

``kappa`` is optional; if present it must match the label's class to count as a
hit. Pairs are unordered ({a,b} == {b,a}).

Usage:
    python score.py --labels v1.0/labels.json --detections my_output.json
"""

from __future__ import annotations

import argparse
import json


def _key(a, b, kappa=None):
    lo, hi = sorted((int(a), int(b)))
    return (lo, hi, kappa)


def score(labels: dict, detections: list) -> dict:
    truth = labels["contradictions"]
    truth_pairs = {_key(c["a_index"], c["b_index"]): c for c in truth}
    truth_keyed = {_key(c["a_index"], c["b_index"], c["kappa"]) for c in truth}

    tp = 0
    matched = set()
    for d in detections:
        pair = _key(d["a_index"], d["b_index"])
        kappa = d.get("kappa")
        hit = (_key(d["a_index"], d["b_index"], kappa) in truth_keyed
               if kappa is not None else pair in truth_pairs)
        if hit:
            tp += 1
            matched.add(pair)

    produced = len(detections)
    n_truth = len(truth)
    adv = [c for c in truth if c["adversarial"]]
    adv_found = sum(1 for c in adv if _key(c["a_index"], c["b_index"]) in matched)
    return {
        "n_events": labels.get("nEvents"),
        "n_contradictions": n_truth,
        "detections_submitted": produced,
        "true_positives": tp,
        "false_positives": produced - tp,
        "precision": round(tp / produced, 4) if produced else 0.0,
        "recall_coverage": round(len(matched) / n_truth, 4) if n_truth else 0.0,
        "adversarial_total": len(adv),
        "adversarial_found": adv_found,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--detections", required=True)
    args = ap.parse_args()
    with open(args.labels) as fh:
        labels = json.load(fh)
    with open(args.detections) as fh:
        det = json.load(fh)
    detections = det["detections"] if isinstance(det, dict) else det
    print(json.dumps(score(labels, detections), indent=2))


if __name__ == "__main__":
    main()
