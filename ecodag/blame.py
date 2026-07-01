"""Blame resolver (paper §5.1).

Slashing fires only on *determinate blame* attributable from the pair alone:
self-equivocation (one issuer signed both conflicting ECOs) or an attributable
monotonic violation (same issuer's own chain). Every cross-party contradiction
resolves to ⊥, so an honest party is never slashed (No-false-accusation, §7).

Quality carve-out (§4.4): a monotone improvement routes to ⊥ even for a single
issuer — a partial-view watchtower may be missing the authorizing event — so
only an *instantaneous* self-equivocation on condition is slashable.
"""

from __future__ import annotations

from dataclasses import dataclass

from .constraints import ConstraintClass
from .dag import LocalView
from .eco import ECO


@dataclass(frozen=True)
class BlameResult:
    blamed: bytes | None                 # issuer public key, or None for ⊥
    reason: str                          # "self_equivocation" | "monotonic" | "bottom"


_BOTTOM = BlameResult(None, "bottom")


def _instantaneous_condition_conflict(e1: ECO, e2: ECO) -> bool:
    c1, c2 = e1.claim, e2.claim
    return (c1.disposition is not None and c2.disposition is not None
            and c1.event_time is not None and c1.event_time == c2.event_time
            and c1.disposition != c2.disposition)


def resolve_blame(e1: ECO, e2: ECO, kappa: ConstraintClass,
                  view: LocalView) -> BlameResult:
    if kappa is ConstraintClass.QUALITY:
        # Only the instantaneous impossibility is attributable; everything else
        # (monotone improvement) is existential over a partial view -> ⊥.
        if e1.issuer == e2.issuer and _instantaneous_condition_conflict(e1, e2):
            return BlameResult(e1.issuer, "self_equivocation")
        return _BOTTOM

    if e1.issuer == e2.issuer:
        reason = "monotonic" if kappa is ConstraintClass.QUANTITY else "self_equivocation"
        return BlameResult(e1.issuer, reason)

    # Cross-party: no attribution from the pair alone -> ⊥ (honest receiver safe).
    return _BOTTOM
