"""Constraint predicates. M1 covers spatial; the other four are added in M2."""

import random

from ecodag.constraints import ConstraintClass, violates
from ecodag.crypto import Keypair
from ecodag.dag import LocalView
from ecodag.eco import Claim, create_eco
from ecodag.hlc import HLC

RNG = random.Random(7)
KP = Keypair.generate(random.Random(7))


def _eco(subj, claim, refs=(), physical=1, hlc=None):
    return create_eco(KP, claim, subj=subj, refs=list(refs),
                      hlc=hlc or HLC(), rng=RNG, physical=physical)


def _obj(subj, location, event_time, refs=()):
    return _eco(subj, Claim(event_type="ObjectEvent", location=location,
                            event_time=event_time), refs=refs)


def test_spatial_violation_two_locations_same_time():
    a = _obj("lot-1", "EU", event_time=100)
    b = _obj("lot-1", "NA", event_time=100)
    assert violates(a, b, ConstraintClass.SPATIAL, LocalView())


def test_no_spatial_violation_when_times_differ():
    # Different times = legitimate movement between locations, not a contradiction.
    a = _obj("lot-1", "EU", event_time=100)
    b = _obj("lot-1", "NA", event_time=200)
    assert not violates(a, b, ConstraintClass.SPATIAL, LocalView())


def test_no_spatial_violation_when_location_matches():
    a = _obj("lot-1", "EU", event_time=100)
    b = _obj("lot-1", "EU", event_time=100)
    assert not violates(a, b, ConstraintClass.SPATIAL, LocalView())
