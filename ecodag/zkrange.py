"""Zero-knowledge range proof over a Pedersen commitment.

We prove ``commit(v, r)`` opens to ``v ∈ [0, 2^bits)`` without revealing v, via
bit decomposition:

* commit each bit b_i as C_i = g^{b_i} h^{r_i}, with the r_i chosen so that
  ∏ C_i^{2^i} = C (a public linear check, no extra proof needed);
* prove each C_i commits to 0 or 1 with a Chaum–Pedersen OR proof made
  non-interactive by Fiat–Shamir.

To prove a quantity violation ∑out > ∑in in zero knowledge we range-prove the
homomorphic difference: W = (C_out / C_in) · g^{-1} commits to out − in − 1,
which lies in [0, 2^bits) exactly when out > in.

This is deliberately the textbook Sigma construction, not Bulletproofs: it is a
real ZK proof and gives honest (larger) size/time numbers that RESULTS.md
reports alongside the published Bulletproofs asymptotics.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from . import crypto

_P = crypto.GROUP.p
_Q = crypto.GROUP.q
_G = crypto.GROUP.g
_H = crypto.GROUP.h
_ELEM_BYTES = (_P.bit_length() + 7) // 8


def _el(x: int) -> bytes:
    return x.to_bytes(_ELEM_BYTES, "big")


@dataclass(frozen=True)
class BitProof:
    A0: int
    A1: int
    e0: int
    e1: int
    z0: int
    z1: int


@dataclass(frozen=True)
class RangeProof:
    commitments: list[int]          # C_i per bit
    bit_proofs: list[BitProof]


# --- OR proof that a commitment opens to 0 or 1 ------------------------------

def _prove_bit(commitment: int, r: int, bit: int, rng: Random) -> BitProof:
    # Y0 = C (opens to 0 <=> C = h^r); Y1 = C·g^{-1} (opens to 1 <=> C·g^{-1} = h^r)
    Y = [commitment, (commitment * pow(_G, -1, _P)) % _P]
    true, false = bit, 1 - bit

    e_false = rng.randrange(_Q)
    z_false = rng.randrange(_Q)
    A_false = (pow(_H, z_false, _P) * pow(Y[false], (-e_false) % _Q, _P)) % _P

    k = rng.randrange(_Q)
    A_true = pow(_H, k, _P)

    A = [0, 0]
    A[true], A[false] = A_true, A_false
    e = crypto.hash_int("zk-or", _el(commitment), _el(A[0]), _el(A[1])) % _Q
    e_true = (e - e_false) % _Q
    z_true = (k + e_true * r) % _Q

    es = [0, 0]; es[true], es[false] = e_true, e_false
    zs = [0, 0]; zs[true], zs[false] = z_true, z_false
    return BitProof(A[0], A[1], es[0], es[1], zs[0], zs[1])


def _verify_bit(commitment: int, bp: BitProof) -> bool:
    Y0 = commitment
    Y1 = (commitment * pow(_G, -1, _P)) % _P
    e = crypto.hash_int("zk-or", _el(commitment), _el(bp.A0), _el(bp.A1)) % _Q
    if (bp.e0 + bp.e1) % _Q != e:
        return False
    if pow(_H, bp.z0, _P) != (bp.A0 * pow(Y0, bp.e0, _P)) % _P:
        return False
    if pow(_H, bp.z1, _P) != (bp.A1 * pow(Y1, bp.e1, _P)) % _P:
        return False
    return True


# --- range proof -------------------------------------------------------------

def prove_range(value: int, r: int, bits: int, rng: Random) -> RangeProof:
    if not 0 <= value < (1 << bits):
        raise ValueError(f"value {value} not in [0, 2^{bits})")

    # bit blindings r_i chosen so that Σ 2^i r_i ≡ r (mod q)
    r_bits = [rng.randrange(_Q) for _ in range(bits - 1)]
    partial = sum((r_bits[i] << i) for i in range(bits - 1)) % _Q
    inv_top = pow(pow(2, bits - 1, _Q), -1, _Q)
    r_bits.append(((r - partial) % _Q) * inv_top % _Q)

    commitments, bit_proofs = [], []
    for i in range(bits):
        b = (value >> i) & 1
        Ci = crypto.commit(b, r_bits[i])
        commitments.append(Ci)
        bit_proofs.append(_prove_bit(Ci, r_bits[i], b, rng))
    return RangeProof(commitments, bit_proofs)


def verify_range(commitment: int, proof: RangeProof, bits: int) -> bool:
    if len(proof.commitments) != bits or len(proof.bit_proofs) != bits:
        return False
    # linear check: ∏ C_i^{2^i} == C
    acc = 1
    for i, Ci in enumerate(proof.commitments):
        acc = (acc * pow(Ci, 1 << i, _P)) % _P
    if acc != commitment % _P:
        return False
    return all(_verify_bit(Ci, bp)
               for Ci, bp in zip(proof.commitments, proof.bit_proofs))


# --- quantity violation over the homomorphic difference ----------------------

def prove_quantity_violation(in_val: int, r_in: int, out_val: int, r_out: int,
                             bits: int, rng: Random) -> RangeProof:
    if out_val <= in_val:
        raise ValueError("no quantity violation: out does not exceed in")
    w = out_val - in_val - 1                 # >= 0 exactly when out > in
    r_w = (r_out - r_in) % _Q
    return prove_range(w, r_w, bits, rng)


def verify_quantity_violation(C_in: int, C_out: int, proof: RangeProof,
                              bits: int) -> bool:
    # W = (C_out / C_in) · g^{-1} commits to out - in - 1
    W = (crypto.sub_commitments(C_out, C_in) * pow(_G, -1, _P)) % _P
    return verify_range(W, proof, bits)


def proof_size_bytes(proof: RangeProof) -> int:
    """Serialised size: every group element and scalar as a fixed-width field
    element (the honest upper bound for this construction)."""
    per_bit = 6 * _ELEM_BYTES          # A0,A1,e0,e1,z0,z1
    return len(proof.commitments) * _ELEM_BYTES + len(proof.bit_proofs) * per_bit
