"""Domain constraint predicates (paper Table 2 / §4.4).

``violates(e1, e2, kappa, view)`` is True iff the ordered/unordered pair of ECOs
jointly violates constraint class ``kappa``. Only spatial is implemented in M1;
the remaining four land in M2.
"""

from __future__ import annotations

import enum

from .dag import LocalView
from .eco import ECO


class ConstraintClass(enum.Enum):
    SPATIAL = "spatial"
    TEMPORAL = "temporal"
    QUANTITY = "quantity"
    QUALITY = "quality"
    REGULATORY = "regulatory"


# Quality/condition lattice: a higher value is a "better" state. Quality is
# monotone non-increasing without an authorized transformation.
_DISPOSITION_ORDER = {"damaged": 0, "suspect": 1, "good": 2}


def _spatial(e1: ECO, e2: ECO, view: LocalView) -> bool:
    """Two locations for one subject at one time (ObjectEvent)."""
    c1, c2 = e1.claim, e2.claim
    if None in (c1.location, c2.location, c1.event_time, c2.event_time):
        return False
    return c1.event_time == c2.event_time and c1.location != c2.location


def _temporal(e1: ECO, e2: ECO, view: LocalView) -> bool:
    """Non-monotone business time along a *causal* path. Ordering is by refs,
    never raw HLC/wall-clock: concurrent (happened-before-incomparable) events
    are not a violation (avoids false-slashing legitimate concurrency)."""
    c1, c2 = e1.claim, e2.claim
    if c1.event_time is None or c2.event_time is None:
        return False
    if view.is_causal_ancestor(e1.id, e2):        # e1 -> e2
        return c2.event_time < c1.event_time
    if view.is_causal_ancestor(e2.id, e1):        # e2 -> e1
        return c1.event_time < c2.event_time
    return False                                   # concurrent: no violation


def _quantity(e1: ECO, e2: ECO, view: LocalView) -> bool:
    """Mass balance ∑out > ∑in (TransformationEvent), two-ECO scalar-aggregate
    reading: one ECO's committed input aggregate vs. the other's output."""
    for a, b in ((e1, e2), (e2, e1)):
        if a.claim.quantity_in is not None and b.claim.quantity_out is not None:
            if b.claim.quantity_out > a.claim.quantity_in:
                return True
    return False


def _quality(e1: ECO, e2: ECO, view: LocalView) -> bool:
    """Condition contradiction, two sub-cases (README §4.4):
    (i) instantaneous impossibility — same subject, same time, two different
        dispositions (no transform can occur at a single instant);
    (ii) monotone improvement without an authorized transform along a causal
        path. Blame routes (ii) — and cross-party (i) — to ⊥."""
    c1, c2 = e1.claim, e2.claim
    if c1.disposition is None or c2.disposition is None:
        return False
    if (c1.event_time is not None and c1.event_time == c2.event_time
            and c1.disposition != c2.disposition):
        return True
    o = _DISPOSITION_ORDER
    if c1.disposition in o and c2.disposition in o:
        if view.is_causal_ancestor(e1.id, e2):
            anc, desc = c1, c2
        elif view.is_causal_ancestor(e2.id, e1):
            anc, desc = c2, c1
        else:
            return False
        return o[desc.disposition] > o[anc.disposition] and not desc.authorized_transform
    return False


def _regulatory(e1: ECO, e2: ECO, view: LocalView) -> bool:
    """A compliance assertion ("valid") for a certificate paired with a
    revocation/expiry record for the same certificate (TransactionEvent)."""
    for a, b in ((e1, e2), (e2, e1)):
        if (a.claim.certificate is not None
                and a.claim.cert_status == "valid"
                and b.claim.certificate == a.claim.certificate
                and b.claim.cert_status in ("revoked", "expired")):
            return True
    return False


_PREDICATES = {
    ConstraintClass.SPATIAL: _spatial,
    ConstraintClass.TEMPORAL: _temporal,
    ConstraintClass.QUANTITY: _quantity,
    ConstraintClass.QUALITY: _quality,
    ConstraintClass.REGULATORY: _regulatory,
}


def violates(e1: ECO, e2: ECO, kappa: ConstraintClass, view: LocalView) -> bool:
    return _PREDICATES[kappa](e1, e2, view)
