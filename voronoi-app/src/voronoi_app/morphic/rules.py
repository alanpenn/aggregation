"""
Generative rules and the engine that runs them.

Every rule implements the same interface, which keeps four concerns apart:

* eligibility   : ``eligible(state)``  -> which cells MAY be occupied next
* weighting     : ``weights(state, candidates)`` -> relative selection weights
                  (None = uniform). Independent of eligibility.
* transition    : the engine occupies the selected cell (``state.occupy``)
* termination   : ``termination(state)`` -> reason string or None

Modes
-----
Mode 0 ``random``   : minimum setup. Any unoccupied cell is eligible.
Mode 1 ``adjacent`` : operational reading of the 3rd operation. One seed
                      cell, then only unoccupied cells sharing a boundary
                      with the aggregate are eligible. Uniform selection.
Mode 2 ``enclosing``: OPERATIONAL APPROXIMATION of the 4th operation (a
                      surrounding relation). The 1976 paper does not give a
                      unique local algorithm, so this is a testable hypothesis,
                      not a reconstruction. A designated open target is
                      surrounded by an adjacent aggregate whose growth is
                      biased towards raising the enclosure score.

Enclosure score (see ``morphology.enclosure_score``): fraction of the target's
boundary length shared with occupied cells. The gain of a candidate is
the length it shares with the target divided by the target perimeter.
Weight = (1 - s) + s * gain / max_gain, with s = ``strength`` in [0, 1]
(s = 0 is uniform adjacent aggregation). When no candidate has positive gain
all candidates are weighted equally, so the aggregate can walk around.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from . import morphology as mo
from .carrier import Carrier

TERMINATION_TARGET_REACHED = "occupied_target_reached"
TERMINATION_NO_CANDIDATES = "no_eligible_candidates"
TERMINATION_ENCLOSED = "target_enclosed"


@dataclass
class State:
    carrier: Carrier
    occupied: List[int] = field(default_factory=list)  # in order of occupation
    target: frozenset = frozenset()
    max_occupied: int = 60

    @property
    def occupied_set(self) -> frozenset:
        return frozenset(self.occupied)

    def occupy(self, cell: int) -> None:
        if cell in self.occupied_set:
            raise ValueError(f"Cell {cell} already occupied")
        if cell in self.target:
            raise ValueError(f"Cell {cell} belongs to the protected target")
        self.occupied.append(cell)


class GenerativeRule(ABC):
    name: str = ""
    mode: int = -1
    description: str = ""

    def prepare(self, state: State) -> None:
        """Set up any rule-specific starting condition (e.g. the target)."""

    @abstractmethod
    def eligible(self, state: State) -> List[int]:
        ...

    def weights(self, state: State, candidates: Sequence[int]) -> Optional[List[float]]:
        return None

    def termination(self, state: State) -> Optional[str]:
        if len(state.occupied) >= state.max_occupied:
            return TERMINATION_TARGET_REACHED
        return None

    def config(self) -> Dict[str, Any]:
        return {"mode": self.mode, "name": self.name}


class RandomOccupation(GenerativeRule):
    name = "random"
    mode = 0
    description = "Minimum setup: occupy a uniformly random unoccupied cell; no adjacency requirement."

    def eligible(self, state: State) -> List[int]:
        occupied = state.occupied_set
        return [c for c in state.carrier.cells if c not in occupied]


class AdjacentAggregation(GenerativeRule):
    name = "adjacent"
    mode = 1
    description = (
        "3-syntax hypothesis: start from one random seed cell; each step occupies a "
        "uniformly random unoccupied cell sharing a boundary with the aggregate."
    )

    def eligible(self, state: State) -> List[int]:
        if not state.occupied:
            return [c for c in state.carrier.cells if c not in state.target]
        return [c for c in mo.candidate_cells(state.carrier, state.occupied) if c not in state.target]


class EnclosingAggregation(GenerativeRule):
    name = "enclosing"
    mode = 2
    description = (
        "Operational approximation of the 4-syntax (NOT a reconstruction): an adjacent "
        "aggregate grown around a protected open target, preferring cells that raise "
        "the target's enclosure score."
    )

    def __init__(self, strength: float = 1.0, target_size: int = 1, after_enclosure: str = "stop"):
        if not 0.0 <= strength <= 1.0:
            raise ValueError("strength must be in [0, 1]")
        if target_size < 1:
            raise ValueError("target_size must be >= 1")
        if after_enclosure not in ("stop", "continue"):
            raise ValueError("after_enclosure must be 'stop' or 'continue'")
        self.strength = strength
        self.target_size = target_size
        self.after_enclosure = after_enclosure

    def config(self) -> Dict[str, Any]:
        return {
            **super().config(),
            "strength": self.strength,
            "target_size": self.target_size,
            "after_enclosure": self.after_enclosure,
        }

    def prepare(self, state: State) -> None:
        state.target = choose_target(state.carrier, self.target_size)

    def eligible(self, state: State) -> List[int]:
        carrier = state.carrier
        if not state.occupied:
            # Starting condition: the seed is a neighbour of the target.
            ring = {n for t in state.target for n in carrier.adjacency[t]} - state.target
            return sorted(ring)
        return [c for c in mo.candidate_cells(carrier, state.occupied) if c not in state.target]

    def _gain(self, state: State, cell: int) -> float:
        perimeter = state.carrier.perimeter(state.target)
        shared = sum(
            length for neighbour, length in state.carrier.adjacency[cell].items()
            if neighbour in state.target
        )
        return shared / perimeter if perimeter else 0.0

    def weights(self, state: State, candidates: Sequence[int]) -> Optional[List[float]]:
        if not state.occupied:
            return None
        gains = [self._gain(state, c) for c in candidates]
        top = max(gains, default=0.0)
        if top <= 0:
            return None
        return [(1 - self.strength) + self.strength * g / top for g in gains]

    def termination(self, state: State) -> Optional[str]:
        if self.after_enclosure == "stop" and state.occupied and mo.is_target_enclosed(
            state.carrier, state.occupied, state.target
        ):
            return TERMINATION_ENCLOSED
        return super().termination(state)


def choose_target(carrier: Carrier, size: int) -> frozenset:
    """Deterministic interior target: the cell nearest the carrier centre plus
    its nearest neighbours (grown by adjacency) up to ``size`` cells."""
    min_x, min_y, max_x, max_y = carrier.extent
    cx, cy = (min_x + max_x) / 2, (min_y + max_y) / 2
    boundary = carrier.boundary_cells

    def distance(cell: int) -> float:
        x, y = carrier.centroid(cell)
        return (x - cx) ** 2 + (y - cy) ** 2

    interior = [c for c in carrier.cells if c not in boundary]
    if not interior:
        raise ValueError("Carrier has no interior cell to use as a target")
    first = min(interior, key=distance)
    target = [first]
    while len(target) < size:
        frontier = {
            n for t in target for n in carrier.adjacency[t]
            if n not in target and n not in boundary
        }
        if not frontier:
            raise ValueError(f"Cannot grow an interior target of size {size}")
        target.append(min(sorted(frontier), key=distance))
    return frozenset(target)


@dataclass
class Transformation:
    step: int
    rule: str
    cell: int
    n_candidates: int
    n_occupied: int
    delta_occupied_components: int
    delta_enclosed_components: int
    delta_graph_cycles: int
    enclosure_score: Optional[float]
    delta_enclosure_score: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class RunResult:
    rule: Dict[str, Any]
    seed: int
    occupied: List[int]
    target: frozenset
    transformations: List[Transformation]
    termination: str

    def occupied_at(self, step: int) -> List[int]:
        """Occupied cells after ``step`` transformations (for replay)."""
        return self.occupied[:step]


def _summary(carrier: Carrier, occupied: Sequence[int], target: frozenset):
    return (
        len(mo.occupied_components(carrier, occupied)),
        len(mo.enclosed_open_components(carrier, occupied)),
        mo.graph_cycle_count(carrier, occupied),
        mo.enclosure_score(carrier, occupied, target) if target else None,
    )


def run_rule(
    rule: GenerativeRule,
    carrier: Carrier,
    max_occupied: int = 60,
    seed: int = 40,
) -> RunResult:
    """Run ``rule`` from an empty carrier with a reproducible random stream."""
    if max_occupied > len(carrier.cells):
        raise ValueError("max_occupied exceeds the number of cells")
    rng = np.random.default_rng(seed)
    state = State(carrier=carrier, max_occupied=max_occupied)
    rule.prepare(state)

    transformations: List[Transformation] = []
    previous = _summary(carrier, state.occupied, state.target)
    reason = rule.termination(state)
    while reason is None:
        candidates = rule.eligible(state)
        if not candidates:
            reason = TERMINATION_NO_CANDIDATES
            break
        weights = rule.weights(state, candidates)
        if weights is None:
            probabilities = None
        else:
            total = float(sum(weights))
            probabilities = [w / total for w in weights] if total > 0 else None
        cell = int(candidates[rng.choice(len(candidates), p=probabilities)])
        state.occupy(cell)

        current = _summary(carrier, state.occupied, state.target)
        transformations.append(Transformation(
            step=len(state.occupied),
            rule=rule.name,
            cell=cell,
            n_candidates=len(candidates),
            n_occupied=len(state.occupied),
            delta_occupied_components=current[0] - previous[0],
            delta_enclosed_components=current[1] - previous[1],
            delta_graph_cycles=current[2] - previous[2],
            enclosure_score=current[3],
            delta_enclosure_score=None if current[3] is None else current[3] - previous[3],
        ))
        previous = current
        reason = rule.termination(state)

    return RunResult(
        rule=rule.config(),
        seed=seed,
        occupied=list(state.occupied),
        target=state.target,
        transformations=transformations,
        termination=reason,
    )


def make_rule(mode: str, **params) -> GenerativeRule:
    if mode == "random":
        return RandomOccupation()
    if mode == "adjacent":
        return AdjacentAggregation()
    if mode == "enclosing":
        return EnclosingAggregation(**params)
    raise ValueError(f"Unknown mode '{mode}'")
