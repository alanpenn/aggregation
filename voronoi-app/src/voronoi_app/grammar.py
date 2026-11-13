"""Deterministic graph-rewriting primitives for morphic spatial grammars."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Tuple

from .core import Representation


@dataclass(frozen=True)
class MorphicRule:
    """Replace a node symbol with a small attributed graph.

    External edges incident to the matched node are reattached to the
    replacement node selected by ``attachment_index``.
    """

    name: str
    match_symbol: str
    replacement_symbols: Tuple[str, ...]
    replacement_edges: Tuple[Tuple[int, int], ...] = ()
    attachment_index: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.replacement_symbols, str):
            raise ValueError("replacement_symbols must be a sequence of symbols")
        object.__setattr__(self, "replacement_symbols", tuple(self.replacement_symbols))
        object.__setattr__(
            self,
            "replacement_edges",
            tuple(tuple(edge) for edge in self.replacement_edges),
        )
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("rule name must not be empty")
        if not isinstance(self.match_symbol, str) or not self.match_symbol:
            raise ValueError("match_symbol must not be empty")
        if not self.replacement_symbols:
            raise ValueError("a rule must produce at least one symbol")
        if any(not isinstance(symbol, str) or not symbol for symbol in self.replacement_symbols):
            raise ValueError("replacement symbols must not be empty")
        if (
            not isinstance(self.attachment_index, int)
            or isinstance(self.attachment_index, bool)
            or not 0 <= self.attachment_index < len(self.replacement_symbols)
        ):
            raise ValueError("attachment_index must identify a replacement symbol")
        for edge in self.replacement_edges:
            if len(edge) != 2:
                raise ValueError("replacement edges must contain two node indices")
            left, right = edge
            if any(not isinstance(index, int) or isinstance(index, bool) for index in edge):
                raise ValueError("replacement edge endpoints must be integer indices")
            if (
                not 0 <= left < len(self.replacement_symbols)
                or not 0 <= right < len(self.replacement_symbols)
            ):
                raise ValueError("replacement edge endpoint is outside the replacement graph")
            if left == right:
                raise ValueError("replacement graph cannot contain self-edges")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "match_symbol": self.match_symbol,
            "replacement_symbols": list(self.replacement_symbols),
            "replacement_edges": [list(edge) for edge in self.replacement_edges],
            "attachment_index": self.attachment_index,
        }


@dataclass
class GrammarStep:
    """The rule applications performed in one synchronous generation."""

    iteration: int
    matches: List[Tuple[int, str]]
    generated_nodes: Dict[int, List[int]] = field(default_factory=dict)


@dataclass
class GrammarResult:
    """Final graph and trace returned by grammar evaluation."""

    initial: Representation
    final: Representation
    trace: List[GrammarStep]
    converged: bool


class MorphicGrammar:
    """Apply ordered graph-production rules to a spatial representation.

    Each generation matches only the nodes that existed at its start. When
    multiple rules match a node, the first rule in ``rules`` takes precedence.
    """

    def __init__(self, rules: Sequence[MorphicRule]):
        self.rules = tuple(rules)
        names = [rule.name for rule in self.rules]
        if len(names) != len(set(names)):
            raise ValueError("grammar rule names must be unique")

    def to_dict(self) -> Dict[str, Any]:
        return {"rules": [rule.to_dict() for rule in self.rules]}

    def evaluate(
        self,
        initial: Representation,
        max_iterations: int = 10,
    ) -> GrammarResult:
        if not isinstance(max_iterations, int) or isinstance(max_iterations, bool):
            raise ValueError("max_iterations must be an integer")
        if max_iterations < 0:
            raise ValueError("max_iterations must be non-negative")
        self._validate_representation(initial)

        current = initial
        trace = []
        for iteration in range(1, max_iterations + 1):
            applications = self._matching_rules(current)
            if not applications:
                break
            current, step = self._rewrite_generation(current, applications, iteration)
            trace.append(step)

        converged = not self._matching_rules(current)
        return GrammarResult(
            initial=initial,
            final=current,
            trace=trace,
            converged=converged,
        )

    def _matching_rules(self, representation: Representation) -> Dict[int, MorphicRule]:
        matches = {}
        for node in representation.nodes:
            symbol = representation.node_attributes.get(node, {}).get("symbol")
            for rule in self.rules:
                if symbol == rule.match_symbol:
                    matches[node] = rule
                    break
        return matches

    def _rewrite_generation(
        self,
        representation: Representation,
        matches: Dict[int, MorphicRule],
        iteration: int,
    ) -> Tuple[Representation, GrammarStep]:
        next_node_id = max(representation.nodes, default=-1) + 1
        replacements: Dict[int, List[int]] = {}
        attributes: Dict[int, Dict[str, Any]] = {}
        node_order: List[int] = []
        rewritten_edges = set()
        generated_nodes: Dict[int, List[int]] = {}

        for node in representation.nodes:
            rule = matches.get(node)
            if rule is None:
                replacements[node] = [node]
                node_order.append(node)
                if node in representation.node_attributes:
                    attributes[node] = dict(representation.node_attributes[node])
                continue

            generated = list(range(next_node_id, next_node_id + len(rule.replacement_symbols)))
            next_node_id += len(generated)
            replacements[node] = generated
            generated_nodes[node] = generated
            parent_attributes = representation.node_attributes.get(node, {})
            for generated_id, symbol in zip(generated, rule.replacement_symbols):
                child_attributes = dict(parent_attributes)
                child_attributes.update({
                    "symbol": symbol,
                    "grammar_parent": node,
                    "grammar_rule": rule.name,
                    "grammar_generation": iteration,
                })
                attributes[generated_id] = child_attributes
                node_order.append(generated_id)

            for left, right in rule.replacement_edges:
                rewritten_edges.add((generated[left], generated[right]))

        attachment_nodes = {
            node: replacements[node][matches[node].attachment_index]
            if node in matches else node
            for node in representation.nodes
        }
        for left, right in representation.edges:
            new_edge = (attachment_nodes[left], attachment_nodes[right])
            if new_edge[0] != new_edge[1]:
                rewritten_edges.add(new_edge)

        rewritten = Representation(
            name=representation.name,
            nodes=node_order,
            edges=sorted({
                (left, right) if left < right else (right, left)
                for left, right in rewritten_edges
            }),
            node_attributes=attributes,
            metadata={
                **representation.metadata,
                "grammar_generation": iteration,
            },
        )
        step = GrammarStep(
            iteration=iteration,
            matches=[(node, matches[node].name) for node in representation.nodes if node in matches],
            generated_nodes=generated_nodes,
        )
        return rewritten, step

    @staticmethod
    def _validate_representation(representation: Representation) -> None:
        if any(not isinstance(node, int) or isinstance(node, bool) for node in representation.nodes):
            raise ValueError("representation node identifiers must be integers")
        if len(representation.nodes) != len(set(representation.nodes)):
            raise ValueError("representation node identifiers must be unique")
        node_ids = set(representation.nodes)
        for left, right in representation.edges:
            if left not in node_ids or right not in node_ids:
                raise ValueError("representation edges must reference existing nodes")
