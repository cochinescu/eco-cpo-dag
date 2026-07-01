"""Hybrid logical clock [kulkarni2014hlc].

Physical time is *injected* (an integer supplied by the caller / trace), never
read from the wall clock, so scripted runs are deterministic — matching the
plan's requirement that logical outputs be bit-for-bit reproducible.

A timestamp is the pair ``(logical, counter)`` compared lexicographically, which
gives the happened-before order the DAG's clock invariant relies on.
"""

from __future__ import annotations

Timestamp = tuple[int, int]


class HLC:
    def __init__(self) -> None:
        self._l = 0
        self._c = 0

    def now(self, physical: int) -> Timestamp:
        """Local event: advance the clock and return the new timestamp."""
        if physical > self._l:
            self._l, self._c = physical, 0
        else:
            self._c += 1
        return (self._l, self._c)

    def update(self, physical: int, other: Timestamp) -> Timestamp:
        """Receive event: merge a remote timestamp, then advance."""
        ol, oc = other
        new_l = max(self._l, ol, physical)
        if new_l == self._l == ol:
            new_c = max(self._c, oc) + 1
        elif new_l == self._l:
            new_c = self._c + 1
        elif new_l == ol:
            new_c = oc + 1
        else:
            new_c = 0
        self._l, self._c = new_l, new_c
        return (self._l, self._c)
