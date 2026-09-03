"""Public search façade backed exclusively by the native C++17 engine."""

from dataclasses import dataclass
from typing import Callable, Hashable, Iterable, Protocol, TypeVar

from core.ai.native_backend import (
    ABI_VERSION,
    backend_info,
    loaded_library_path,
    native_self_test as _native_self_test,
    run_search,
)

NodeT = TypeVar("NodeT", bound=Hashable)


class SearchGraph(Protocol[NodeT]):
    def neighbors(self, node: NodeT, conditions: frozenset[str]) -> Iterable[tuple[NodeT, float]]: ...


@dataclass(frozen=True, slots=True)
class SearchStats:
    expanded: int = 0
    generated: int = 0
    frontier_peak: int = 0
    path_cost: float = 0.0


@dataclass(frozen=True, slots=True)
class SearchResult:
    path: tuple[NodeT, ...]
    found: bool
    stats: SearchStats


def _native(
    algorithm: str,
    graph: SearchGraph[NodeT],
    start: NodeT,
    goal: NodeT,
    heuristic: Callable[[NodeT, NodeT], float] | None,
    conditions: frozenset[str],
) -> SearchResult:
    result = run_search(algorithm, graph, start, goal, heuristic, conditions)
    return SearchResult(
        result.path,
        result.found,
        SearchStats(result.expanded, result.generated, result.frontier_peak, result.path_cost),
    )


def native_backend_info() -> dict[str, object]:
    """Return the identity of the required native backend currently in use."""
    return {
        "abi": ABI_VERSION,
        "backend": backend_info(),
        "library": str(loaded_library_path()),
    }


def native_self_test() -> bool:
    """Execute the C++ library's built-in known-answer validation."""
    return _native_self_test()


def bfs(
    graph: SearchGraph[NodeT],
    start: NodeT,
    goal: NodeT,
    conditions: frozenset[str] = frozenset(),
) -> SearchResult:
    return _native("BFS", graph, start, goal, None, conditions)


def dfs(
    graph: SearchGraph[NodeT],
    start: NodeT,
    goal: NodeT,
    conditions: frozenset[str] = frozenset(),
) -> SearchResult:
    return _native("DFS", graph, start, goal, None, conditions)


def astar(
    graph: SearchGraph[NodeT],
    start: NodeT,
    goal: NodeT,
    heuristic: Callable[[NodeT, NodeT], float],
    conditions: frozenset[str] = frozenset(),
) -> SearchResult:
    return _native("A*", graph, start, goal, heuristic, conditions)


def search(
    algorithm: str,
    graph: SearchGraph[NodeT],
    start: NodeT,
    goal: NodeT,
    heuristic: Callable[[NodeT, NodeT], float] | None = None,
    conditions: frozenset[str] = frozenset(),
) -> SearchResult:
    name = algorithm.upper()
    if name == "BFS":
        return bfs(graph, start, goal, conditions)
    if name == "DFS":
        return dfs(graph, start, goal, conditions)
    if name in {"A*", "ASTAR"}:
        return _native("A*", graph, start, goal, heuristic or (lambda _a, _b: 0.0), conditions)
    raise ValueError(f"Unknown search algorithm: {algorithm}")
