"""Contradiction Proof Objects: the plaintext-opening path. A CPO verifies iff
both signatures check, both commitments open to the cited claims, and the cited
constraint is genuinely violated (paper §4.5)."""

import dataclasses
import random

from ecodag.constraints import ConstraintClass
from ecodag.cpo import CPO, Opening, make_cpo, verify_cpo
from ecodag.crypto import Keypair
from ecodag.dag import LocalView
from ecodag.eco import Claim, create_eco
from ecodag.hlc import HLC

KP = Keypair.generate(random.Random(11))
RNG = random.Random(11)


def _obj(subj, location, event_time):
    return create_eco(KP, Claim(event_type="ObjectEvent", location=location,
                                event_time=event_time),
                      subj=subj, refs=[], hlc=HLC(), rng=RNG, physical=1)


def test_valid_spatial_cpo_verifies():
    a = _obj("lot-1", "EU", 100)
    b = _obj("lot-1", "NA", 100)
    cpo = make_cpo(a, b, ConstraintClass.SPATIAL, challenger=b"chal", deposit=1)
    assert verify_cpo(cpo, LocalView())


def test_cpo_over_noncontradictory_pair_fails():
    a = _obj("lot-1", "EU", 100)
    b = _obj("lot-1", "EU", 100)  # same location -> no contradiction
    cpo = make_cpo(a, b, ConstraintClass.SPATIAL, challenger=b"chal", deposit=1)
    assert not verify_cpo(cpo, LocalView())


def test_verify_uses_opened_claim_not_the_in_memory_claim():
    # Spoof: two honest, non-contradictory ECOs (same location, same time). The
    # attacker swaps eco1's in-memory .claim to a violating value but leaves cm
    # (and a correct opening) bound to the real, non-violating claim. Verification
    # must judge the violation on the *opened* claim, so this must NOT verify.
    a = _obj("lot-1", "EU", 100)
    b = _obj("lot-1", "EU", 100)
    real_claim = a.claim
    fake_claim = Claim(event_type="ObjectEvent", location="NA", event_time=100)
    tampered_a = dataclasses.replace(a, claim=fake_claim)  # cm still commits "EU"
    # witness opens to the REAL claim, which does open correctly to a.cm
    witness = Opening(claim1=real_claim, r1=a.r, claim2=b.claim, r2=b.r)
    cpo = CPO(eco1=tampered_a, eco2=b, kappa=ConstraintClass.SPATIAL,
              witness=witness, challenger=b"x", deposit=1)
    assert not verify_cpo(cpo, LocalView())


def test_cpo_with_forged_opening_fails():
    a = _obj("lot-1", "EU", 100)
    b = _obj("lot-1", "NA", 100)
    cpo = make_cpo(a, b, ConstraintClass.SPATIAL, challenger=b"chal", deposit=1)
    # Replace the opening of eco1 with a mismatched claim.
    bad = cpo.witness.__class__(
        claim1=Claim(event_type="ObjectEvent", location="NA", event_time=100),
        r1=cpo.witness.r1, claim2=cpo.witness.claim2, r2=cpo.witness.r2,
    )
    tampered = cpo.__class__(eco1=cpo.eco1, eco2=cpo.eco2, kappa=cpo.kappa,
                             witness=bad, challenger=cpo.challenger, deposit=cpo.deposit)
    assert not verify_cpo(tampered, LocalView())
