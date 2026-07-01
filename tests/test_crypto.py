"""Tests for the crypto primitives: domain-separated hash, Pedersen
commitment (additively homomorphic), and Ed25519 signatures."""

import random

import pytest

from ecodag import crypto


# --- domain-separated hash ---------------------------------------------------

def test_hash_is_32_bytes():
    assert len(crypto.hash_bytes("dsep", b"payload")) == 32


def test_hash_is_deterministic():
    a = crypto.hash_bytes("eco", b"a", b"b")
    b = crypto.hash_bytes("eco", b"a", b"b")
    assert a == b


def test_hash_domain_separation_changes_output():
    same_parts = (b"a", b"b")
    assert crypto.hash_bytes("eco", *same_parts) != crypto.hash_bytes("cpo", *same_parts)


def test_hash_part_boundaries_are_unambiguous():
    # ("ab","c") must not collide with ("a","bc") — length framing required.
    assert crypto.hash_bytes("d", b"ab", b"c") != crypto.hash_bytes("d", b"a", b"bc")


# --- Pedersen commitment -----------------------------------------------------

def test_commit_is_deterministic_in_value_and_randomness():
    assert crypto.commit(5, 7) == crypto.commit(5, 7)


def test_commit_hides_value_changes():
    assert crypto.commit(5, 7) != crypto.commit(6, 7)


def test_commitment_is_additively_homomorphic():
    # commit(v1,r1) * commit(v2,r2) == commit(v1+v2, r1+r2)   (mod p)
    v1, r1, v2, r2 = 11, 123, 29, 456
    lhs = crypto.add_commitments(crypto.commit(v1, r1), crypto.commit(v2, r2))
    rhs = crypto.commit(v1 + v2, r1 + r2)
    assert lhs == rhs


def test_commitment_difference_is_homomorphic():
    # A quantity CPO range-proves the difference commitment; the group op must
    # let us form commit(v1-v2, r1-r2) from the two commitments.
    v1, r1, v2, r2 = 100, 900, 40, 300
    diff = crypto.sub_commitments(crypto.commit(v1, r1), crypto.commit(v2, r2))
    assert diff == crypto.commit(v1 - v2, r1 - r2)


def test_random_scalar_in_range_and_varies():
    rng = random.Random(1)
    xs = {crypto.random_scalar(rng) for _ in range(50)}
    assert len(xs) == 50  # no collisions from a decent range
    assert all(0 <= x < crypto.GROUP.q for x in xs)


# --- Ed25519 signatures ------------------------------------------------------

def test_sign_verify_roundtrip():
    kp = crypto.Keypair.generate(random.Random(2))
    sig = kp.sign(b"message")
    assert crypto.verify(kp.public, b"message", sig)


def test_verify_rejects_tampered_message():
    kp = crypto.Keypair.generate(random.Random(3))
    sig = kp.sign(b"message")
    assert not crypto.verify(kp.public, b"tampered", sig)


def test_verify_rejects_wrong_key():
    kp1 = crypto.Keypair.generate(random.Random(4))
    kp2 = crypto.Keypair.generate(random.Random(5))
    sig = kp1.sign(b"message")
    assert not crypto.verify(kp2.public, b"message", sig)
