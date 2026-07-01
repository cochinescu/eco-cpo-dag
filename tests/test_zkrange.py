"""Zero-knowledge range proof over a Pedersen commitment, and its use to prove
a quantity violation (∑out > ∑in) on the homomorphic difference without
revealing the amounts (paper §6.1/§6.2).

The construction is a bit-decomposition Sigma OR-proof with Fiat-Shamir — a
genuine ZK range proof (larger/slower than Bulletproofs, but honest and
measurable). RESULTS.md notes the comparison.
"""

import random

import pytest

from ecodag import crypto, zkrange


def test_range_proof_roundtrip():
    rng = random.Random(1)
    r = crypto.random_scalar(rng)
    value = 12345
    C = crypto.commit(value, r)
    proof = zkrange.prove_range(value, r, bits=16, rng=rng)
    assert zkrange.verify_range(C, proof, bits=16)


def test_range_proof_rejects_wrong_commitment():
    rng = random.Random(2)
    r = crypto.random_scalar(rng)
    proof = zkrange.prove_range(1000, r, bits=16, rng=rng)
    other = crypto.commit(1001, r)  # commitment to a different value
    assert not zkrange.verify_range(other, proof, bits=16)


def test_range_proof_refuses_out_of_range_value():
    rng = random.Random(3)
    r = crypto.random_scalar(rng)
    with pytest.raises(ValueError):
        zkrange.prove_range(2 ** 16, r, bits=16, rng=rng)  # == 2^16, not < 2^16


def test_quantity_violation_proof_verifies_when_out_exceeds_in():
    rng = random.Random(4)
    r_in, r_out = crypto.random_scalar(rng), crypto.random_scalar(rng)
    in_val, out_val = 100, 150
    C_in, C_out = crypto.commit(in_val, r_in), crypto.commit(out_val, r_out)
    proof = zkrange.prove_quantity_violation(in_val, r_in, out_val, r_out,
                                             bits=16, rng=rng)
    assert zkrange.verify_quantity_violation(C_in, C_out, proof, bits=16)


def test_cannot_prove_violation_when_quantity_is_conserved():
    rng = random.Random(5)
    r_in, r_out = crypto.random_scalar(rng), crypto.random_scalar(rng)
    with pytest.raises(ValueError):
        zkrange.prove_quantity_violation(100, r_in, 80, r_out, bits=16, rng=rng)


def test_proof_size_is_reported():
    rng = random.Random(6)
    r = crypto.random_scalar(rng)
    proof = zkrange.prove_range(500, r, bits=16, rng=rng)
    assert zkrange.proof_size_bytes(proof) > 0
