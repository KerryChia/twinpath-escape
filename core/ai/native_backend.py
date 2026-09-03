"""Strict ctypes bridge to the C++17 CSR search engine.

The graph adapter intentionally remains in Python: arbitrary hashable application nodes
are enumerated into dense integer IDs while the search loops and statistics live solely
in the native library. Failure to load or validate that library is fatal; there is no
production Python search fallback.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path
import math
import platform
import sys
from typing import Callable, Hashable, Iterable, Protocol, TypeVar

ABI_VERSION = 1
NodeT = TypeVar("NodeT", bound=Hashable)


class NativeBackendError(RuntimeError):
    """Raised when the required native search backend is absent or invalid."""


class SearchGraph(Protocol[NodeT]):
    def neighbors(self, node: NodeT, conditions: frozenset[str]) -> Iterable[tuple[NodeT, float]]: ...


class _CStats(ctypes.Structure):
    _fields_ = [
        ("expanded", ctypes.c_uint64),
        ("generated", ctypes.c_uint64),
        ("frontier_peak", ctypes.c_uint64),
        ("path_cost", ctypes.c_double),
    ]


class _CResult(ctypes.Structure):
    _fields_ = [
        ("found", ctypes.c_uint32),
        ("path_length", ctypes.c_uint32),
        ("stats", _CStats),
    ]


@dataclass(frozen=True, slots=True)
class NativeResult:
    path: tuple[NodeT, ...]
    found: bool
    expanded: int
    generated: int
    frontier_peak: int
    path_cost: float


def _platform_tag() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower().replace("amd64", "x86_64").replace("aarch64", "arm64")
    return f"{system}-{machine}"


def _library_name() -> str:
    if sys.platform == "win32":
        return "search_native.dll"
    if sys.platform == "darwin":
        return "libsearch_native.dylib"
    return "libsearch_native.so"


def library_candidates() -> tuple[Path, ...]:
    relative = Path("build") / "native" / _platform_tag() / _library_name()
    candidates: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root) / relative)
    candidates.append(Path(__file__).resolve().parents[2] / relative)
    return tuple(dict.fromkeys(candidates))


_LIB: ctypes.CDLL | None = None
_LOADED_PATH: Path | None = None


def _load() -> ctypes.CDLL:
    global _LIB, _LOADED_PATH
    if _LIB is not None:
        return _LIB
    existing = next((path for path in library_candidates() if path.is_file()), None)
    if existing is None:
        searched = "\n  ".join(str(path) for path in library_candidates())
        raise NativeBackendError(
            "Native search library is required but was not found. "
            "Run `python tools/build_native.py --ensure`. Searched:\n  " + searched
        )
    try:
        library = ctypes.CDLL(str(existing))
        library.tn_search_abi_version.argtypes = []
        library.tn_search_abi_version.restype = ctypes.c_uint32
        library.tn_search_backend_info.argtypes = []
        library.tn_search_backend_info.restype = ctypes.c_char_p
        library.tn_search_self_test.argtypes = []
        library.tn_search_self_test.restype = ctypes.c_int32
        library.tn_search_csr.argtypes = [
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint64,
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_uint32,
            ctypes.POINTER(_CResult),
        ]
        library.tn_search_csr.restype = ctypes.c_int32
    except (AttributeError, OSError) as exc:
        raise NativeBackendError(f"Cannot load native search library {existing}: {exc}") from exc
    actual_abi = int(library.tn_search_abi_version())
    if actual_abi != ABI_VERSION:
        raise NativeBackendError(
            f"Native search ABI mismatch: Python requires {ABI_VERSION}, library provides {actual_abi}"
        )
    if not library.tn_search_backend_info():
        raise NativeBackendError("Native search backend returned empty build information")
    if library.tn_search_self_test() != 1:
        raise NativeBackendError("Native search library self-test failed during loading")
    _LIB = library
    _LOADED_PATH = existing
    return library


def abi_version() -> int:
    return int(_load().tn_search_abi_version())


def backend_info() -> str:
    value = _load().tn_search_backend_info()
    if not value:
        raise NativeBackendError("Native search backend returned empty build information")
    return value.decode("utf-8", errors="strict")


def loaded_library_path() -> Path:
    _load()
    assert _LOADED_PATH is not None
    return _LOADED_PATH


def native_self_test() -> bool:
    library = _load()
    if library.tn_search_self_test() != 1:
        raise NativeBackendError("Native search library self-test failed")
    return True


def _serialize_graph(
    graph: SearchGraph[NodeT], start: NodeT, goal: NodeT, conditions: frozenset[str]
) -> tuple[list[NodeT], list[int], list[int], list[float], int]:
    nodes = [start]
    indices = {start: 0}
    if start == goal:
        return nodes, [0, 0], [], [], 0
    adjacency: list[list[tuple[int, float]]] = []
    cursor = 0
    while cursor < len(nodes):
        node = nodes[cursor]
        outgoing: list[tuple[int, float]] = []
        for item in graph.neighbors(node, conditions):
            try:
                neighbor, cost = item
            except (TypeError, ValueError) as exc:
                raise TypeError("graph.neighbors() must yield (hashable_node, numeric_cost) pairs") from exc
            try:
                neighbor_index = indices.get(neighbor)
            except TypeError as exc:
                raise TypeError(f"search graph node is not hashable: {neighbor!r}") from exc
            if neighbor_index is None and neighbor not in indices:
                neighbor_index = len(nodes)
                indices[neighbor] = neighbor_index
                nodes.append(neighbor)
            assert neighbor_index is not None
            numeric_cost = float(cost)
            if not math.isfinite(numeric_cost) or numeric_cost < 0:
                raise ValueError(f"search edge cost must be finite and non-negative: {numeric_cost!r}")
            outgoing.append((neighbor_index, numeric_cost))
        adjacency.append(outgoing)
        cursor += 1
    try:
        goal_index = indices.get(goal)
    except TypeError as exc:
        raise TypeError(f"search goal is not hashable: {goal!r}") from exc
    if goal_index is None and goal not in indices:
        goal_index = len(nodes)
        indices[goal] = goal_index
        nodes.append(goal)
        adjacency.append([])
    assert goal_index is not None

    offsets = [0]
    targets: list[int] = []
    costs: list[float] = []
    for outgoing in adjacency:
        for target, cost in outgoing:
            targets.append(target)
            costs.append(cost)
        offsets.append(len(targets))
    return nodes, offsets, targets, costs, goal_index


def run_search(
    algorithm: str,
    graph: SearchGraph[NodeT],
    start: NodeT,
    goal: NodeT,
    heuristic: Callable[[NodeT, NodeT], float] | None,
    conditions: frozenset[str],
) -> NativeResult[NodeT]:
    library = _load()
    algorithm_id = {"BFS": 1, "DFS": 2, "A*": 3}[algorithm]
    nodes, offsets, targets, costs, goal_index = _serialize_graph(graph, start, goal, conditions)
    heuristic_values = (
        [float(heuristic(node, goal)) for node in nodes]
        if algorithm == "A*" and heuristic is not None
        else [0.0] * len(nodes)
    )
    if any(not math.isfinite(value) or value < 0 for value in heuristic_values):
        raise ValueError("A* heuristic values must be finite and non-negative")

    offsets_array = (ctypes.c_uint64 * len(offsets))(*offsets)
    targets_array = (ctypes.c_uint32 * len(targets))(*targets)
    costs_array = (ctypes.c_double * len(costs))(*costs)
    heuristics_array = (ctypes.c_double * len(heuristic_values))(*heuristic_values)
    path_array = (ctypes.c_uint32 * len(nodes))()
    result = _CResult()
    status = int(
        library.tn_search_csr(
            algorithm_id,
            len(nodes),
            len(targets),
            offsets_array,
            targets_array,
            costs_array,
            heuristics_array,
            0,
            goal_index,
            path_array,
            len(nodes),
            ctypes.byref(result),
        )
    )
    if status != 0:
        raise NativeBackendError(f"Native search call failed with status {status}")
    path = tuple(nodes[path_array[index]] for index in range(result.path_length))
    return NativeResult(
        path=path,
        found=bool(result.found),
        expanded=int(result.stats.expanded),
        generated=int(result.stats.generated),
        frontier_peak=int(result.stats.frontier_peak),
        path_cost=float(result.stats.path_cost),
    )
