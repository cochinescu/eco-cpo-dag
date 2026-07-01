"""Temporal, quantity, quality, and regulatory predicates (M2).

Key correctness points from the README/paper:
* temporal orders by causal refs, not raw HLC — concurrent events are NOT a
  violation;
* quantity is the two-ECO mass-balance reading (∑out > ∑in);
* quality covers both the instantaneous self-equivocation and the
  monotone-improvement-without-authorization cases;
* regulatory is a compliance-assertion vs. revocation/expiry pairing.
"""

import random

from ecodag.constraints import ConstraintClass, violates
from ecodag.crypto import Keypair
from ecodag.dag import LocalView
from ecodag.eco import Claim, create_eco
from ecodag.hlc import HLC

KP = Keypair.generate(random.Random(21))
RNG = random.Random(21)


def _eco(subj, claim, refs=(), physical=1):
    return create_eco(KP, claim, subj=subj, refs=list(refs), hlc=HLC(),
                      rng=RNG, physical=physical)


# --- temporal ---------------------------------------------------------------

def test_temporal_violation_backward_time_on_causal_path():
    view = LocalView()
    anc = _eco("lot-1", Claim(event_type="ObjectEvent", event_time=200))
    view.append(anc)
    desc = _eco("lot-1", Claim(event_type="ObjectEvent", event_time=100),
                refs=[anc.id])  # causally after anc but timestamped earlier
    view.append(desc)
    assert violates(anc, desc, ConstraintClass.TEMPORAL, view)


def test_no_temporal_violation_forward_time():
    view = LocalView()
    anc = _eco("lot-1", Claim(event_type="ObjectEvent", event_time=100))
    view.append(anc)
    desc = _eco("lot-1", Claim(event_type="ObjectEvent", event_time=200),
                refs=[anc.id])
    view.append(desc)
    assert not violates(anc, desc, ConstraintClass.TEMPORAL, view)


def test_concurrent_events_are_not_a_temporal_violation():
    # No refs linking them -> happened-before-incomparable -> NOT a violation,
    # even though the timestamps are inverted (the false-slash trap).
    view = LocalView()
    a = _eco("lot-1", Claim(event_type="ObjectEvent", event_time=200))
    b = _eco("lot-1", Claim(event_type="ObjectEvent", event_time=100))
    view.append(a)
    view.append(b)
    assert not violates(a, b, ConstraintClass.TEMPORAL, view)


# --- quantity ---------------------------------------------------------------

def test_quantity_violation_output_exceeds_input():
    a = _eco("lot-1", Claim(event_type="TransformationEvent", quantity_in=100))
    b = _eco("lot-1", Claim(event_type="TransformationEvent", quantity_out=150))
    assert violates(a, b, ConstraintClass.QUANTITY, LocalView())


def test_no_quantity_violation_when_conserved():
    a = _eco("lot-1", Claim(event_type="TransformationEvent", quantity_in=100))
    b = _eco("lot-1", Claim(event_type="TransformationEvent", quantity_out=80))
    assert not violates(a, b, ConstraintClass.QUANTITY, LocalView())


# --- quality ----------------------------------------------------------------

def test_quality_instantaneous_impossibility():
    a = _eco("lot-1", Claim(event_type="ObjectEvent", disposition="good",
                            event_time=100))
    b = _eco("lot-1", Claim(event_type="ObjectEvent", disposition="damaged",
                            event_time=100))
    assert violates(a, b, ConstraintClass.QUALITY, LocalView())


def test_quality_monotone_improvement_without_authorization():
    view = LocalView()
    anc = _eco("lot-1", Claim(event_type="ObjectEvent", disposition="damaged",
                              event_time=100))
    view.append(anc)
    desc = _eco("lot-1", Claim(event_type="ObjectEvent", disposition="good",
                               event_time=200, authorized_transform=False),
                refs=[anc.id])
    view.append(desc)
    assert violates(anc, desc, ConstraintClass.QUALITY, view)


def test_no_quality_violation_with_authorized_transform():
    view = LocalView()
    anc = _eco("lot-1", Claim(event_type="ObjectEvent", disposition="damaged",
                              event_time=100))
    view.append(anc)
    desc = _eco("lot-1", Claim(event_type="ObjectEvent", disposition="good",
                               event_time=200, authorized_transform=True),
                refs=[anc.id])
    view.append(desc)
    assert not violates(anc, desc, ConstraintClass.QUALITY, view)


# --- regulatory -------------------------------------------------------------

def test_regulatory_violation_valid_assertion_vs_revocation():
    a = _eco("lot-1", Claim(event_type="TransactionEvent", certificate="C1",
                            cert_status="valid"))
    b = _eco("lot-1", Claim(event_type="TransactionEvent", certificate="C1",
                            cert_status="revoked"))
    assert violates(a, b, ConstraintClass.REGULATORY, LocalView())


def test_no_regulatory_violation_for_different_certificate():
    a = _eco("lot-1", Claim(event_type="TransactionEvent", certificate="C1",
                            cert_status="valid"))
    b = _eco("lot-1", Claim(event_type="TransactionEvent", certificate="C2",
                            cert_status="revoked"))
    assert not violates(a, b, ConstraintClass.REGULATORY, LocalView())
