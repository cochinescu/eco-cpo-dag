"""Hybrid logical clock: deterministic (physical time is injected, never read
from the wall clock), monotone, and mergeable on receive."""

from ecodag.hlc import HLC


def test_local_ticks_are_strictly_increasing():
    c = HLC()
    t1 = c.now(physical=10)
    t2 = c.now(physical=10)  # same physical time -> counter advances
    t3 = c.now(physical=11)  # physical advances -> counter resets, still greater
    assert t1 < t2 < t3


def test_counter_resets_when_physical_advances():
    c = HLC()
    c.now(physical=5)
    c.now(physical=5)
    t = c.now(physical=6)
    assert t == (6, 0)


def test_update_on_receive_takes_the_max_and_advances():
    a = HLC()
    b = HLC()
    ta = a.now(physical=20)          # (20, 0)
    tb = b.now(physical=3)           # (3, 0), b's clock is behind
    merged = b.update(physical=3, other=ta)
    assert merged > ta               # strictly ahead of the received stamp
    assert merged > tb
