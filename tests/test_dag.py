"""Local-view DAG: append, and SubjectClaims — all same-subject ECOs in the
local view (refs/radius only order the walk, they are not the detection
boundary; see paper §4.3)."""

import random

from ecodag.crypto import Keypair
from ecodag.dag import LocalView
from ecodag.eco import Claim, create_eco
from ecodag.hlc import HLC


def _make(subj, loc, kp, hlc, rng, physical, refs=()):
    return create_eco(kp, Claim(event_type="ObjectEvent", location=loc),
                      subj=subj, refs=list(refs), hlc=hlc, rng=rng, physical=physical)


def test_subject_claims_returns_same_subject_only():
    kp, hlc, rng = Keypair.generate(random.Random(0)), HLC(), random.Random(0)
    view = LocalView()
    a = _make("lot-1", "EU", kp, hlc, rng, 1)
    b = _make("lot-2", "NA", kp, hlc, rng, 2)
    view.append(a)
    view.append(b)
    new = _make("lot-1", "NA", kp, hlc, rng, 3)
    same = view.subject_claims(new)
    assert [e.id for e in same] == [a.id]


def test_subject_claims_ignores_declared_refs():
    # Two same-subject ECOs are comparable even when refs does NOT link them
    # (omitting a parent to fork a subject must not evade detection).
    kp, hlc, rng = Keypair.generate(random.Random(0)), HLC(), random.Random(0)
    view = LocalView()
    a = _make("lot-1", "EU", kp, hlc, rng, 1)
    view.append(a)
    unlinked = _make("lot-1", "NA", kp, hlc, rng, 2, refs=[])  # no ref to a
    assert a.id in [e.id for e in view.subject_claims(unlinked)]


def test_causal_ancestor_follows_refs():
    kp, hlc, rng = Keypair.generate(random.Random(0)), HLC(), random.Random(0)
    view = LocalView()
    a = _make("lot-1", "EU", kp, hlc, rng, 1)
    view.append(a)
    b = _make("lot-1", "EU", kp, hlc, rng, 2, refs=[a.id])
    view.append(b)
    assert view.is_causal_ancestor(a.id, b, )      # a -> b
    assert not view.is_causal_ancestor(b.id, a)    # not b -> a
