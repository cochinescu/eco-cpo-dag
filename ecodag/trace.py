"""Synthetic EPCIS-2.0-style trace generator with labelled injected
contradictions (ground truth).

The in-memory dataclasses here ARE the stable schema; ``trace_io.py`` (M4.5)
serialises them to a versioned JSON-LD-ish format + a sidecar labels file. Each
``TraceEvent`` refers to its causal parents by *event index* (the sim maps
indices to ECO ids at build time), which keeps the format protocol-independent.

Ground truth: every injected contradiction records the two event indices, its
class, whether it is adversarial, and its expected adjudication outcome
("slash" for determinate self-equivocation/monotonic blame, "bottom" for the
cross-party / existential cases that must resolve to ⊥).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random

from .constraints import ConstraintClass
from .eco import Claim

SCHEMA_VERSION = "1.0"

_LOCATIONS = ["urn:loc:EU", "urn:loc:NA", "urn:loc:APAC", "urn:loc:LATAM"]


@dataclass(frozen=True)
class TraceEvent:
    index: int
    issuer: int                    # participant id
    subj: str
    claim: Claim
    refs: tuple[int, ...] = ()     # causal parents, by event index


@dataclass(frozen=True)
class Contradiction:
    id: int
    kappa: ConstraintClass
    a_index: int
    b_index: int
    adversarial: bool
    expected: str                  # "slash" | "bottom"


@dataclass
class Trace:
    events: list[TraceEvent] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    n_participants: int = 1

    def add(self, issuer: int, subj: str, claim: Claim,
            refs: tuple[int, ...] = ()) -> int:
        idx = len(self.events)
        self.events.append(TraceEvent(idx, issuer, subj, claim, refs))
        return idx


# --- injection helpers -------------------------------------------------------
# Each returns the expected adjudication outcome so ground truth stays local to
# the code that constructs the conflict.

def _inject_spatial(t: Trace, subj: str, p: int, q: int, cross: bool, rng: Random):
    issuer_b = q if cross else p
    ta = t.add(p, subj, Claim(event_type="ObjectEvent", location="urn:loc:EU",
                              event_time=1000))
    tb = t.add(issuer_b, subj, Claim(event_type="ObjectEvent", location="urn:loc:NA",
                                     event_time=1000))
    return ta, tb, ("bottom" if cross else "slash")


def _inject_temporal(t: Trace, subj: str, p: int, q: int, cross: bool, rng: Random):
    issuer_b = q if cross else p
    ta = t.add(p, subj, Claim(event_type="ObjectEvent", event_time=2000))
    tb = t.add(issuer_b, subj, Claim(event_type="ObjectEvent", event_time=1000),
               refs=(ta,))  # causally after ta but earlier business time
    return ta, tb, ("bottom" if cross else "slash")


def _inject_quantity(t: Trace, subj: str, p: int, q: int, cross: bool, rng: Random):
    issuer_b = q if cross else p
    ta = t.add(p, subj, Claim(event_type="TransformationEvent", quantity_in=100))
    tb = t.add(issuer_b, subj, Claim(event_type="TransformationEvent",
                                     quantity_out=150))
    # cross-party mass-balance mismatch is the honest-receiver case -> ⊥.
    return ta, tb, ("bottom" if cross else "slash")


def _inject_quality(t: Trace, subj: str, p: int, q: int, cross: bool, rng: Random):
    if cross:
        # monotone improvement without authorization -> existential -> ⊥.
        ta = t.add(p, subj, Claim(event_type="ObjectEvent", disposition="damaged",
                                  event_time=1000))
        tb = t.add(p, subj, Claim(event_type="ObjectEvent", disposition="good",
                                  event_time=2000, authorized_transform=False),
                   refs=(ta,))
        return ta, tb, "bottom"
    # instantaneous impossibility, same issuer -> self-equivocation -> slash.
    ta = t.add(p, subj, Claim(event_type="ObjectEvent", disposition="good",
                              event_time=1000))
    tb = t.add(p, subj, Claim(event_type="ObjectEvent", disposition="damaged",
                              event_time=1000))
    return ta, tb, "slash"


def _inject_regulatory(t: Trace, subj: str, p: int, q: int, cross: bool, rng: Random):
    issuer_b = q if cross else p
    cert = f"cert:{subj}"
    ta = t.add(p, subj, Claim(event_type="TransactionEvent", certificate=cert,
                              cert_status="valid"))
    tb = t.add(issuer_b, subj, Claim(event_type="TransactionEvent", certificate=cert,
                                     cert_status="revoked"))
    return ta, tb, ("bottom" if cross else "slash")


_INJECTORS = {
    ConstraintClass.SPATIAL: _inject_spatial,
    ConstraintClass.TEMPORAL: _inject_temporal,
    ConstraintClass.QUANTITY: _inject_quantity,
    ConstraintClass.QUALITY: _inject_quality,
    ConstraintClass.REGULATORY: _inject_regulatory,
}

def _baseline_chain(t: Trace, subj: str, owner: int, n_events: int, rng: Random):
    """A consistent custody chain: monotone time, single location, good
    disposition. Produces no violations (keeps the false-positive rate at 0)."""
    prev: tuple[int, ...] = ()
    loc = rng.choice(_LOCATIONS)
    time = 0
    for _ in range(n_events):
        time += rng.randint(10, 50)
        idx = t.add(owner, subj, Claim(event_type="ObjectEvent", location=loc,
                                       event_time=time, disposition="good"),
                    refs=prev)
        prev = (idx,)


def generate_trace(n_participants: int, n_subjects: int,
                   base_events_per_subject: int, injection_rate: float,
                   seed: int, adaptive: bool = False) -> Trace:
    """Build a labelled trace. ``injection_rate`` is the per-subject probability
    of injecting one contradiction of a randomly chosen class.

    ``adaptive`` is a reserved hook for an adversary that places contradictions
    to exploit the radius/sampling limits (README §4). It is NOT implemented:
    passing ``adaptive=True`` raises so no run can silently imply the paper's
    Table 4 adaptive-evasion row was tested. Only random placement is built."""
    if adaptive:
        raise NotImplementedError(
            "adaptive adversary not implemented; only random injection is "
            "supported (README §4 — leave Table 4's adaptive-evasion row "
            "analytical)")
    rng = Random(seed)
    t = Trace(n_participants=n_participants)
    classes = list(ConstraintClass)
    cid = 0
    for s in range(n_subjects):
        subj = f"urn:lot:{s}"
        owner = rng.randrange(n_participants)
        _baseline_chain(t, subj, owner, base_events_per_subject, rng)
        if rng.random() < injection_rate:
            kappa = rng.choice(classes)
            other = (owner + 1 + rng.randrange(max(1, n_participants - 1))) % n_participants
            # Quantity is exercised in BOTH modes so the measured blame breakdown
            # covers the same-issuer conservation slash (Blame (ii), "monotonic":
            # one issuer's own input vs. its own later output, out>in) as well as
            # the cross-party honest-receiver mismatch (-> ⊥). Every other
            # adversarial class is a same-issuer self-equivocation.
            cross = (rng.random() < 0.5) if kappa is ConstraintClass.QUANTITY else False
            a, b, expected = _INJECTORS[kappa](t, subj, owner, other, cross, rng)
            t.contradictions.append(
                Contradiction(cid, kappa, a, b, adversarial=(expected == "slash"),
                              expected=expected))
            cid += 1
    return t


def single_contradiction_trace(kappa: ConstraintClass, cross_party: bool,
                               seed: int = 0) -> Trace:
    """A minimal trace with exactly one injected contradiction of class
    ``kappa`` — used for targeted property tests (e.g. the honest-receiver ⊥
    case)."""
    rng = Random(seed)
    t = Trace(n_participants=2)
    subj = "urn:lot:targeted"
    a, b, expected = _INJECTORS[kappa](t, subj, 0, 1, cross_party, rng)
    t.contradictions.append(
        Contradiction(0, kappa, a, b, adversarial=(expected == "slash"),
                      expected=expected))
    return t
