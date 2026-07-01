"""In-process simulation harness.

N participants emit ECOs from a replayed trace; h watchtowers each hold a local
view and run rate-bounded, radius-ordered, **randomly-sampled same-subject
candidate-pair** detection. Each watchtower samples with an *independent* seed
derived from one master seed + observer index (the independence the Detectability
theorem needs; a shared/deterministic view would collapse the bound).

The harness logs ground truth so the blame-outcome breakdown, the false-positive
rate, and the "zero honest parties slashed" invariant can all be checked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random

from . import cpo as cpo_mod
from .blame import resolve_blame
from .constraints import ConstraintClass, violates
from .crypto import Keypair
from .dag import LocalView
from .eco import create_eco
from .hlc import HLC
from .trace import Trace

_CLASSES = list(ConstraintClass)


@dataclass
class SimResult:
    n_injected: int
    detected: set[int] = field(default_factory=set)
    outcomes: dict[int, str] = field(default_factory=dict)   # cid -> blame reason
    expected: dict[int, str] = field(default_factory=dict)   # cid -> "slash"|"bottom"
    cpo_count: int = 0
    false_positives: int = 0

    @property
    def coverage(self) -> float:
        if self.n_injected == 0:
            return 1.0
        return len(self.detected) / self.n_injected

    @property
    def slash_count(self) -> int:
        return sum(1 for c in self.detected if self.outcomes[c] != "bottom")

    @property
    def bottom_count(self) -> int:
        return sum(1 for c in self.detected if self.outcomes[c] == "bottom")

    @property
    def false_slashes(self) -> int:
        return sum(1 for c in self.detected
                   if self.outcomes[c] != "bottom" and self.expected[c] == "bottom")


def _build_ecos(trace: Trace, seed: int):
    """Materialise the trace into signed ECOs, resolving ref indices to ids."""
    key_rng = Random(seed ^ 0x5EED)
    commit_rng = Random(seed ^ 0xC0FFEE)
    participants = [Keypair.generate(key_rng) for _ in range(trace.n_participants)]
    clocks = [HLC() for _ in range(trace.n_participants)]

    ecos = []
    id_by_index: dict[int, str] = {}
    for ev in trace.events:
        refs = [id_by_index[i] for i in ev.refs]
        eco = create_eco(participants[ev.issuer], ev.claim, subj=ev.subj,
                         refs=refs, hlc=clocks[ev.issuer], rng=commit_rng,
                         physical=ev.index)
        id_by_index[ev.index] = eco.id
        ecos.append(eco)
    return ecos


def run_simulation(trace: Trace, n_watchtowers: int, sampling_fraction: float,
                   seed: int) -> SimResult:
    ecos = _build_ecos(trace, seed)
    index_by_id = {e.id: ev.index for e, ev in zip(ecos, trace.events)}

    # ground truth: unordered index pair -> contradiction
    pair_to_c = {frozenset((c.a_index, c.b_index)): c for c in trace.contradictions}
    result = SimResult(n_injected=len(trace.contradictions),
                       expected={c.id: c.expected for c in trace.contradictions})

    views = [LocalView() for _ in range(n_watchtowers)]
    rngs = [Random(seed * 100_003 + w) for w in range(n_watchtowers)]

    for eco in ecos:
        for w in range(n_watchtowers):
            view, rng = views[w], rngs[w]
            candidates = view.subject_claims(eco)
            sampled = [c for c in candidates if rng.random() < sampling_fraction]
            for old in sampled:
                for kappa in _CLASSES:
                    if not violates(eco, old, kappa, view):
                        continue
                    cpo = cpo_mod.make_cpo(eco, old, kappa,
                                           challenger=str(w).encode(), deposit=1)
                    if not cpo_mod.verify_cpo(cpo, view):
                        continue
                    result.cpo_count += 1
                    pair = frozenset((index_by_id[eco.id], index_by_id[old.id]))
                    contradiction = pair_to_c.get(pair)
                    if contradiction is None:
                        result.false_positives += 1
                        continue
                    br = resolve_blame(eco, old, kappa, view)
                    result.detected.add(contradiction.id)
                    # first detection sets the recorded outcome
                    result.outcomes.setdefault(contradiction.id, br.reason)
            view.append(eco)

    return result
