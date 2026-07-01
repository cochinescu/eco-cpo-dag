"""Event Claim Objects (ECOs) and CreateECO (Algorithm 1).

A ``Claim`` carries the EPCIS-2.0-derived fields the constraint predicates read
(see ``constraints.py`` and README §4 for the Table-2 mapping). The public ECO
commits to the claim; the plaintext-opening path reveals ``(claim, r)`` and
checks the commitment. Randomness is threaded through an explicit RNG for
reproducibility.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from random import Random

from . import crypto
from .hlc import HLC, Timestamp

_ID_DOMAIN = "eco-id"
_PAYLOAD_DOMAIN = "eco-payload"


@dataclass(frozen=True)
class Claim:
    """EPCIS-derived claim payload. Fields default to None so a claim only
    populates what its event type needs (Table 2 mapping)."""

    event_type: str
    # spatial / temporal
    location: str | None = None
    event_time: int | None = None          # business time (distinct from HLC tau)
    # quantity conservation (TransformationEvent mass balance)
    quantity_in: int | None = None
    quantity_out: int | None = None
    # quality / condition (ObjectEvent disposition + sensor reading)
    disposition: str | None = None
    condition_value: int | None = None
    authorized_transform: bool = False     # intervening authorized transform/cert
    # regulatory (TransactionEvent certificate vs revocation/expiry record)
    certificate: str | None = None
    cert_status: str | None = None         # "valid" | "revoked" | "expired"

    def canonical(self) -> bytes:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()


def _refs_bytes(refs: tuple[str, ...]) -> bytes:
    return crypto.hash_bytes("refs", *(r.encode() for r in refs))


def _tau_bytes(tau: Timestamp) -> bytes:
    return tau[0].to_bytes(8, "big") + tau[1].to_bytes(8, "big")


def recompute_id(cm: bytes, tau: Timestamp, refs: tuple[str, ...], subj: str) -> str:
    return crypto.hash_bytes(
        _ID_DOMAIN, cm, _tau_bytes(tau), _refs_bytes(refs), subj.encode()
    ).hex()


def commit_payload(claim: Claim, r: bytes) -> bytes:
    return crypto.hash_bytes(_PAYLOAD_DOMAIN, claim.canonical(), r)


@dataclass(frozen=True)
class ECO:
    id: str
    subj: str
    issuer: bytes
    tau: Timestamp
    refs: tuple[str, ...]
    cm: bytes
    sig: bytes
    claim: Claim
    r: bytes  # opening randomness (issuer secret; revealed by a plaintext CPO)

    def verify_signature(self) -> bool:
        if recompute_id(self.cm, self.tau, self.refs, self.subj) != self.id:
            return False
        return crypto.verify(self.issuer, bytes.fromhex(self.id), self.sig)

    def opens_to(self, claim: Claim, r: bytes) -> bool:
        return commit_payload(claim, r) == self.cm


def create_eco(
    issuer: crypto.Keypair,
    claim: Claim,
    subj: str,
    refs: list[str],
    hlc: HLC,
    rng: Random,
    physical: int,
) -> ECO:
    """Algorithm 1: commit, timestamp, link, sign."""
    r = bytes(rng.getrandbits(8) for _ in range(32))
    cm = commit_payload(claim, r)
    tau = hlc.now(physical)
    refs_t = tuple(refs)
    eco_id = recompute_id(cm, tau, refs_t, subj)
    sig = issuer.sign(bytes.fromhex(eco_id))
    return ECO(
        id=eco_id, subj=subj, issuer=issuer.public, tau=tau, refs=refs_t,
        cm=cm, sig=sig, claim=claim, r=r,
    )
