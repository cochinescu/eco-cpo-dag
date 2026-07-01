"""Local-view DAG.

Each participant/watchtower holds a ``LocalView``: an append-only set of ECOs
indexed by subject. ``subject_claims`` returns *every* same-subject ECO held
(not only declared refs ancestors) — refs and the radius limit only order/bound
the detection walk, they are not the detection boundary (paper §4.3).
"""

from __future__ import annotations

from collections import defaultdict

from .eco import ECO


class LocalView:
    def __init__(self) -> None:
        self._by_id: dict[str, ECO] = {}
        self._by_subject: dict[str, list[str]] = defaultdict(list)

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, eco_id: str) -> bool:
        return eco_id in self._by_id

    def append(self, eco: ECO) -> None:
        if eco.id in self._by_id:
            return
        self._by_id[eco.id] = eco
        self._by_subject[eco.subj].append(eco.id)

    def get(self, eco_id: str) -> ECO | None:
        return self._by_id.get(eco_id)

    def all(self) -> list[ECO]:
        return list(self._by_id.values())

    def subject_claims(self, eco: ECO) -> list[ECO]:
        """All same-subject ECOs already in the view (excluding ``eco`` itself)."""
        return [
            self._by_id[i] for i in self._by_subject.get(eco.subj, ()) if i != eco.id
        ]

    def is_causal_ancestor(self, ancestor_id: str, descendant: ECO) -> bool:
        """True iff ``ancestor_id`` is reachable from ``descendant`` by following
        refs (i.e. ancestor -> ... -> descendant in happened-before)."""
        seen: set[str] = set()
        stack = list(descendant.refs)
        while stack:
            cur = stack.pop()
            if cur == ancestor_id:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            parent = self._by_id.get(cur)
            if parent is not None:
                stack.extend(parent.refs)
        return False
