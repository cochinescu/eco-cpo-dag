"""Versioned, protocol-independent serialisation of a Trace (M4.5).

Serialises a :class:`~ecodag.trace.Trace` to an EPCIS-2.0-style JSON-LD event
list plus a sidecar ground-truth labels file. This is the *stable benchmark
format*: a detector in any language reads the events, emits the contradictions
it finds, and ``benchmark/score.py`` grades them against ``labels.json``.

Events reference their causal parents by **event index** (stable across the
file), never by an internal ECO id, so the format is decoupled from this
implementation's crypto. Round-trips via :func:`load_jsonld`.
"""

from __future__ import annotations

from dataclasses import asdict

from .eco import Claim
from .trace import SCHEMA_VERSION, Trace, TraceEvent

_CONTEXT = [
    "https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld",
    {"ecodag": "urn:ecodag:vocab:"},
]


def _event_to_jsonld(ev: TraceEvent) -> dict:
    c = ev.claim
    obj = {
        "@type": c.event_type,
        "eventID": f"urn:ecodag:event:{ev.index}",
        "ecodag:index": ev.index,
        "ecodag:issuer": ev.issuer,
        "ecodag:subject": ev.subj,
        "ecodag:refs": list(ev.refs),
        # the constraint-relevant payload, verbatim, so a detector has exactly
        # what the paper's Violates predicates read (Table 2 mapping)
        "ecodag:claim": {k: v for k, v in asdict(c).items() if v is not None},
    }
    if c.event_time is not None:
        obj["eventTime"] = c.event_time
    if c.location is not None:
        obj["bizLocation"] = {"id": c.location}
    return obj


def to_jsonld(trace: Trace, meta: dict | None = None) -> dict:
    return {
        "@context": _CONTEXT,
        "schemaVersion": SCHEMA_VERSION,
        "ecodag:generator": meta or {},
        "ecodag:nParticipants": trace.n_participants,
        "epcisBody": {"eventList": [_event_to_jsonld(e) for e in trace.events]},
    }


def to_labels(trace: Trace) -> dict:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "nEvents": len(trace.events),
        "contradictions": [
            {
                "id": c.id,
                "kappa": c.kappa.value,
                "a_index": c.a_index,
                "b_index": c.b_index,
                "adversarial": c.adversarial,
                "expected": c.expected,
            }
            for c in trace.contradictions
        ],
    }


def load_jsonld(doc: dict) -> Trace:
    """Reconstruct a Trace (events only; labels are a separate file)."""
    events = doc["epcisBody"]["eventList"]
    n_participants = doc.get("ecodag:nParticipants")
    if n_participants is None:
        n_participants = max((e["ecodag:issuer"] for e in events), default=-1) + 1
    t = Trace(n_participants=n_participants)
    for ev in sorted(events, key=lambda e: e["ecodag:index"]):
        claim = Claim(**ev["ecodag:claim"])
        t.add(ev["ecodag:issuer"], ev["ecodag:subject"], claim,
              tuple(ev["ecodag:refs"]))
    return t
