"""Event Claim Objects: CreateECO (Algorithm 1), signature binding, and the
hiding/binding payload commitment used by the plaintext-opening path."""

import random

from ecodag.crypto import Keypair
from ecodag.eco import Claim, create_eco, recompute_id
from ecodag.hlc import HLC


def _issuer():
    return Keypair.generate(random.Random(42))


def test_create_eco_populates_all_fields():
    eco = create_eco(
        _issuer(), Claim(event_type="ObjectEvent", location="EU"),
        subj="lot-1", refs=[], hlc=HLC(), rng=random.Random(1), physical=1,
    )
    assert eco.subj == "lot-1"
    assert eco.tau == (1, 0)
    assert eco.refs == ()
    assert eco.id and eco.cm and eco.sig


def test_signature_verifies():
    eco = create_eco(
        _issuer(), Claim(event_type="ObjectEvent", location="EU"),
        subj="lot-1", refs=[], hlc=HLC(), rng=random.Random(1), physical=1,
    )
    assert eco.verify_signature()


def test_tampering_with_the_claim_breaks_the_id():
    kp = _issuer()
    eco = create_eco(
        kp, Claim(event_type="ObjectEvent", location="EU"),
        subj="lot-1", refs=[], hlc=HLC(), rng=random.Random(1), physical=1,
    )
    # The id commits to cm, which commits to the claim; a different claim's
    # commitment must not match the recorded id.
    forged_cm = b"\x00" * 32
    assert recompute_id(forged_cm, eco.tau, eco.refs, eco.subj) != eco.id


def test_commitment_opens_to_the_claim():
    eco = create_eco(
        _issuer(), Claim(event_type="ObjectEvent", location="EU"),
        subj="lot-1", refs=[], hlc=HLC(), rng=random.Random(1), physical=1,
    )
    assert eco.opens_to(eco.claim, eco.r)
    assert not eco.opens_to(Claim(event_type="ObjectEvent", location="NA"), eco.r)


def test_refs_are_recorded_in_order():
    eco = create_eco(
        _issuer(), Claim(event_type="ObjectEvent", location="EU"),
        subj="lot-1", refs=["a", "b"], hlc=HLC(), rng=random.Random(1), physical=2,
    )
    assert eco.refs == ("a", "b")
