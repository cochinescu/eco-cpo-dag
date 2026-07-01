"""Crypto primitives for the prototype.

Choices (kept deliberately simple and honest for a first cut):

* Hash: BLAKE2b-256 from the standard library, with explicit length framing so
  concatenations are unambiguous (a stand-in for the paper's BLAKE3).
* Commitment: a Pedersen commitment in a prime-order subgroup of Z_p* using the
  RFC 3526 MODP-2048 safe prime. This is a genuine additively-homomorphic
  Pedersen commitment; the paper specifies a Ristretto/curve group, which only
  changes concrete proof sizes and speed, not the algebra. Documented in
  RESULTS.md so no measurement over-claims a curve implementation.
* Signatures: Ed25519 via PyNaCl.

Randomness is threaded through an explicit ``random.Random`` so every run is
reproducible from a seed (the plan forbids wall-clock nondeterminism for logical
outputs).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from random import Random

import nacl.exceptions
import nacl.signing

# --- domain-separated hash ---------------------------------------------------


def hash_bytes(domain: str, *parts: bytes) -> bytes:
    """BLAKE2b-256 over ``domain`` and ``parts`` with 8-byte length framing so
    that different part boundaries never collide."""
    h = hashlib.blake2b(digest_size=32)

    def _absorb(b: bytes) -> None:
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)

    _absorb(domain.encode("utf-8"))
    for p in parts:
        _absorb(p)
    return h.digest()


def hash_int(domain: str, *parts: bytes) -> int:
    """Hash mapped to an integer (used for Fiat-Shamir challenges)."""
    return int.from_bytes(hash_bytes(domain, *parts), "big")


# --- Pedersen commitment in a prime-order group ------------------------------

# RFC 3526 MODP Group 14 (2048-bit). p is a safe prime, so q = (p-1)/2 is prime
# and the quadratic residues form the unique subgroup of order q.
_P_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF"
)


@dataclass(frozen=True)
class PrimeOrderGroup:
    p: int
    q: int
    g: int
    h: int


def _derive_group() -> PrimeOrderGroup:
    p = int(_P_HEX, 16)
    q = (p - 1) // 2
    # g = 4 = 2^2 is a quadratic residue != 1, hence generates the order-q group.
    g = 4
    # h: nothing-up-my-sleeve second generator with unknown log_g(h). Hash a
    # fixed seed to an integer and square it into the QR subgroup.
    seed = hash_int("pedersen-h", b"ECO/CPO-DAG generator h") % p
    h = pow(seed, 2, p)
    if h in (0, 1):  # astronomically unlikely; keep it total anyway
        h = pow(seed + 1, 2, p)
    return PrimeOrderGroup(p=p, q=q, g=g, h=h)


GROUP = _derive_group()


def commit(value: int, r: int) -> int:
    """Pedersen commitment g^value * h^r (mod p). Exponents are reduced mod q,
    so negative values (as in a homomorphic difference) are well defined."""
    v = value % GROUP.q
    rr = r % GROUP.q
    return (pow(GROUP.g, v, GROUP.p) * pow(GROUP.h, rr, GROUP.p)) % GROUP.p


def add_commitments(c1: int, c2: int) -> int:
    """Commitment to the sum of the two committed values."""
    return (c1 * c2) % GROUP.p


def sub_commitments(c1: int, c2: int) -> int:
    """Commitment to the difference of the two committed values."""
    return (c1 * pow(c2, -1, GROUP.p)) % GROUP.p


def random_scalar(rng: Random) -> int:
    """A scalar in [0, q) drawn from the supplied reproducible RNG."""
    return rng.randrange(GROUP.q)


# --- Ed25519 signatures ------------------------------------------------------


@dataclass(frozen=True)
class Keypair:
    signing: nacl.signing.SigningKey

    @classmethod
    def generate(cls, rng: Random) -> "Keypair":
        seed = bytes(rng.getrandbits(8) for _ in range(32))
        return cls(nacl.signing.SigningKey(seed))

    @property
    def public(self) -> bytes:
        return bytes(self.signing.verify_key)

    def sign(self, message: bytes) -> bytes:
        return self.signing.sign(message).signature


def verify(public: bytes, message: bytes, signature: bytes) -> bool:
    try:
        nacl.signing.VerifyKey(public).verify(message, signature)
        return True
    except nacl.exceptions.BadSignatureError:
        return False
