"""Contradiction Proof Objects (plaintext-opening path).

A CPO binds two signed ECOs, the violated constraint class, and a witness. In
the plaintext path the witness is the two commitment openings; public
verification checks signatures, openings, and that the constraint really is
violated (paper §4.5). Blame resolution (§5.1) lives in ``blame.py`` (M2); a
CPO can verify as a true contradiction yet still resolve to ⊥ (no slash).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from . import constraints
from .constraints import ConstraintClass
from .dag import LocalView
from .eco import ECO, Claim


@dataclass(frozen=True)
class Opening:
    claim1: Claim
    r1: bytes
    claim2: Claim
    r2: bytes


@dataclass(frozen=True)
class CPO:
    eco1: ECO
    eco2: ECO
    kappa: ConstraintClass
    witness: Opening
    challenger: bytes
    deposit: int


def make_cpo(eco1: ECO, eco2: ECO, kappa: ConstraintClass, challenger: bytes,
             deposit: int) -> CPO:
    witness = Opening(eco1.claim, eco1.r, eco2.claim, eco2.r)
    return CPO(eco1=eco1, eco2=eco2, kappa=kappa, witness=witness,
               challenger=challenger, deposit=deposit)


def verify_cpo(cpo: CPO, view: LocalView) -> bool:
    # 1. both ECOs carry valid issuer signatures
    if not (cpo.eco1.verify_signature() and cpo.eco2.verify_signature()):
        return False
    # 2. the openings match the on-record commitments
    if not cpo.eco1.opens_to(cpo.witness.claim1, cpo.witness.r1):
        return False
    if not cpo.eco2.opens_to(cpo.witness.claim2, cpo.witness.r2):
        return False
    # 3. the cited constraint is genuinely violated — evaluated over the
    #    commitment-BOUND opened claims, never the free-floating in-memory
    #    eco.claim. id/refs/subj/tau are authenticated by the signature; only
    #    the payload lives behind the commitment, so we substitute the opened
    #    witness claim before checking the predicate.
    e1 = dataclasses.replace(cpo.eco1, claim=cpo.witness.claim1)
    e2 = dataclasses.replace(cpo.eco2, claim=cpo.witness.claim2)
    return constraints.violates(e1, e2, cpo.kappa, view)
