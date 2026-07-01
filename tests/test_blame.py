"""Blame resolver (§5.1). Slashing fires only on determinate blame:
self-equivocation or attributable monotonic violation. Everything cross-party
resolves to ⊥ so an honest party is never slashed (No-false-accusation).

The quality carve-out (README §4.4): monotone improvement routes to ⊥ even for a
single issuer, because a partial-view watchtower may be missing the authorizing
event; only an instantaneous self-equivocation on condition is slashable.
"""

import random

from ecodag.blame import resolve_blame
from ecodag.constraints import ConstraintClass
from ecodag.crypto import Keypair
from ecodag.dag import LocalView
from ecodag.eco import Claim, create_eco
from ecodag.hlc import HLC

ISSUER_A = Keypair.generate(random.Random(31))
ISSUER_B = Keypair.generate(random.Random(32))
RNG = random.Random(31)


def _eco(kp, subj, claim, refs=()):
    return create_eco(kp, claim, subj=subj, refs=list(refs), hlc=HLC(),
                      rng=RNG, physical=1)


def test_spatial_self_equivocation_is_slashed():
    a = _eco(ISSUER_A, "lot-1", Claim(event_type="ObjectEvent", location="EU",
                                      event_time=100))
    b = _eco(ISSUER_A, "lot-1", Claim(event_type="ObjectEvent", location="NA",
                                      event_time=100))
    result = resolve_blame(a, b, ConstraintClass.SPATIAL, LocalView())
    assert result.blamed == ISSUER_A.public
    assert result.reason == "self_equivocation"


def test_spatial_cross_party_resolves_to_bottom():
    a = _eco(ISSUER_A, "lot-1", Claim(event_type="ObjectEvent", location="EU",
                                      event_time=100))
    b = _eco(ISSUER_B, "lot-1", Claim(event_type="ObjectEvent", location="NA",
                                      event_time=100))
    result = resolve_blame(a, b, ConstraintClass.SPATIAL, LocalView())
    assert result.blamed is None
    assert result.reason == "bottom"


def test_quantity_same_issuer_is_monotonic_blame():
    a = _eco(ISSUER_A, "lot-1", Claim(event_type="TransformationEvent",
                                      quantity_in=100))
    b = _eco(ISSUER_A, "lot-1", Claim(event_type="TransformationEvent",
                                      quantity_out=150))
    result = resolve_blame(a, b, ConstraintClass.QUANTITY, LocalView())
    assert result.blamed == ISSUER_A.public
    assert result.reason == "monotonic"


def test_quantity_cross_party_honest_receiver_never_slashed():
    # Sender under-reports input; honest receiver reports true larger reading.
    sender = _eco(ISSUER_A, "lot-1", Claim(event_type="TransformationEvent",
                                           quantity_in=100))
    receiver = _eco(ISSUER_B, "lot-1", Claim(event_type="TransformationEvent",
                                             quantity_out=150))
    result = resolve_blame(sender, receiver, ConstraintClass.QUANTITY, LocalView())
    assert result.blamed is None
    assert result.reason == "bottom"


def test_quality_instantaneous_self_equivocation_is_slashed():
    a = _eco(ISSUER_A, "lot-1", Claim(event_type="ObjectEvent",
                                      disposition="good", event_time=100))
    b = _eco(ISSUER_A, "lot-1", Claim(event_type="ObjectEvent",
                                      disposition="damaged", event_time=100))
    result = resolve_blame(a, b, ConstraintClass.QUALITY, LocalView())
    assert result.blamed == ISSUER_A.public
    assert result.reason == "self_equivocation"


def test_quality_monotone_improvement_resolves_to_bottom_even_same_issuer():
    view = LocalView()
    anc = _eco(ISSUER_A, "lot-1", Claim(event_type="ObjectEvent",
                                        disposition="damaged", event_time=100))
    view.append(anc)
    desc = _eco(ISSUER_A, "lot-1", Claim(event_type="ObjectEvent",
                                         disposition="good", event_time=200),
                refs=[anc.id])
    view.append(desc)
    result = resolve_blame(anc, desc, ConstraintClass.QUALITY, view)
    assert result.blamed is None
    assert result.reason == "bottom"
