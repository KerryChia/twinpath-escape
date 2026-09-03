from collections import deque
from dataclasses import dataclass
import heapq
from itertools import count
from pathlib import Path
import unittest

from core.ai.graph import PlatformEdge, PlatformGraph, PlatformNode
from core.ai.native_backend import (
    ABI_VERSION,
    abi_version,
    backend_info,
    loaded_library_path,
    native_self_test,
)
from core.ai.search import SearchStats, astar, bfs, dfs, native_backend_info, search


class MappingGraph:
    def __init__(self, adjacency):
        self.adjacency = adjacency
        self.conditions_seen = []

    def neighbors(self, node, conditions):
        self.conditions_seen.append((node, conditions))
        return self.adjacency.get(node, ())


class SearchTests(unittest.TestCase):
    def graph(self, edges):
        graph = PlatformGraph()
        names = {name for edge in edges for name in edge[:2]}
        for i, name in enumerate(sorted(names)):
            graph.add_node(PlatformNode(name, (i * 10, 0)))
        for source, target, cost, *condition in edges:
            graph.add_edge(PlatformEdge(source, target, "walk", 1, cost, condition[0] if condition else None))
        return graph

    def test_native_backend_is_authentic_and_validated(self):
        self.assertEqual(abi_version(), ABI_VERSION)
        self.assertTrue(native_self_test())
        info = native_backend_info()
        self.assertEqual(info["abi"], ABI_VERSION)
        self.assertIn("csr-c++17", info["backend"])
        self.assertIn("csr-c++17", backend_info())
        library = loaded_library_path()
        self.assertTrue(library.is_file())
        self.assertIn(str(Path("build") / "native"), str(library))
        source = (Path(__file__).parents[1] / "core" / "ai" / "search.py").read_text(encoding="utf-8")
        self.assertNotIn("heapq", source)
        self.assertNotIn("deque", source)
        self.assertIn("run_search", source)

    def test_bfs_finds_fewest_edges(self):
        graph = self.graph([("s", "a", 5), ("a", "g", 5), ("s", "b", 1), ("b", "c", 1), ("c", "g", 1)])
        self.assertEqual(bfs(graph, "s", "g").path, ("s", "a", "g"))

    def test_dfs_legal_path_and_no_solution(self):
        graph = self.graph([("s", "a", 1), ("a", "s", 1), ("a", "g", 1), ("x", "y", 1)])
        result = dfs(graph, "s", "g")
        self.assertTrue(result.found)
        self.assertTrue(all(graph.edge(a, b) for a, b in zip(result.path, result.path[1:])))
        self.assertFalse(dfs(graph, "s", "y").found)

    def test_astar_finds_lowest_double_cost(self):
        graph = MappingGraph({
            "s": [("a", 8.125), ("b", 2.25)],
            "a": [("g", 1.5)],
            "b": [("c", 2.125)],
            "c": [("g", 2.0625)],
        })
        result = astar(graph, "s", "g", lambda node, _goal: {"s": 0.5, "a": 0.25, "b": 0.125, "c": 0.0, "g": 0.0}[node])
        self.assertEqual(result.path, ("s", "b", "c", "g"))
        self.assertEqual(result.stats.path_cost, 6.4375)

    def test_exact_paths_and_stats_match_legacy_semantics(self):
        graph = MappingGraph({
            "s": [("a", 1.25), ("b", 0.5)],
            "a": [("g", 2.5)],
            "b": [("c", 0.25)],
            "c": [("g", 0.125)],
        })
        self.assertEqual(
            bfs(graph, "s", "g"),
            self._reference("BFS", graph.adjacency, "s", "g"),
        )
        self.assertEqual(
            dfs(graph, "s", "g"),
            self._reference("DFS", graph.adjacency, "s", "g"),
        )
        heuristic = lambda _node, _goal: 0.0
        self.assertEqual(
            astar(graph, "s", "g", heuristic),
            self._reference("A*", graph.adjacency, "s", "g", heuristic),
        )

    def test_arbitrary_hashable_nodes_order_conditions_and_dispatcher(self):
        @dataclass(frozen=True)
        class Token:
            name: str

        start = ("start", 1)
        first = frozenset({"first", 2})
        second = Token("second")
        goal = (Token("goal"), frozenset({3}))
        graph = MappingGraph({start: [(first, 1.5), (second, 1.0)], first: [(goal, 2.0)], second: [(goal, 9.0)]})
        conditions = frozenset({"open:gate", "ride:0:a>b"})
        result = search("bfs", graph, start, goal, conditions=conditions)
        self.assertEqual(result.path, (start, first, goal))
        self.assertTrue(graph.conditions_seen)
        self.assertTrue(all(seen == conditions for _node, seen in graph.conditions_seen))
        self.assertEqual(search("astar", graph, start, goal).path, (start, first, goal))
        self.assertEqual(search("A*", graph, start, goal).path, (start, first, goal))
        with self.assertRaisesRegex(ValueError, "Unknown search algorithm"):
            search("greedy", graph, start, goal)

    def test_invalid_numeric_domain_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite and non-negative"):
            bfs(MappingGraph({"s": [("g", float("nan"))]}), "s", "g")
        with self.assertRaisesRegex(ValueError, "finite and non-negative"):
            dfs(MappingGraph({"s": [("g", -1.0)]}), "s", "g")
        with self.assertRaisesRegex(ValueError, "heuristic values"):
            astar(MappingGraph({"s": [("g", 1.0)]}), "s", "g", lambda _a, _b: float("inf"))

    def test_edge_cases_cycles_dynamic_block_and_stats_reset(self):
        graph = self.graph([("s", "s", 1), ("s", "g", 1, "open:gate"), ("s", "a", 1), ("a", "s", 1)])
        for searcher in (bfs, dfs):
            self.assertEqual(searcher(graph, "s", "s").path, ("s",))
            self.assertFalse(searcher(graph, "s", "g").found)
            self.assertTrue(searcher(graph, "s", "g", frozenset({"open:gate"})).found)
        self.assertFalse(astar(graph, "s", "g", lambda _a, _b: 0).found)
        opened = astar(graph, "s", "g", lambda _a, _b: 0, frozenset({"open:gate"}))
        self.assertTrue(opened.found)
        self.assertEqual(bfs(graph, "s", "s").stats, SearchStats(frontier_peak=1))
        self.assertGreaterEqual(opened.stats.generated, 1)

    @staticmethod
    def _reference(algorithm, adjacency, start, goal, heuristic=lambda _a, _b: 0.0):
        if start == goal:
            from core.ai.search import SearchResult
            return SearchResult((start,), True, SearchStats(frontier_peak=1))
        parent = {start: None}; costs = {start: 0.0}; stats = [0, 0, 1]

        def finish(node):
            from core.ai.search import SearchResult
            path = []
            while node is not None:
                path.append(node); node = parent[node]
            path.reverse()
            return SearchResult(tuple(path), True, SearchStats(*stats, costs[path[-1]]))

        if algorithm in {"BFS", "DFS"}:
            frontier = deque([start]) if algorithm == "BFS" else [start]
            while frontier:
                current = frontier.popleft() if algorithm == "BFS" else frontier.pop(); stats[0] += 1
                values = adjacency.get(current, ())
                for neighbor, cost in (values if algorithm == "BFS" else reversed(values)):
                    if neighbor in parent:
                        continue
                    parent[neighbor] = current; costs[neighbor] = costs[current] + cost; stats[1] += 1
                    if neighbor == goal:
                        return finish(goal)
                    frontier.append(neighbor); stats[2] = max(stats[2], len(frontier))
        else:
            serial = count(); frontier = [(heuristic(start, goal), next(serial), start)]; closed = set()
            while frontier:
                _priority, _, current = heapq.heappop(frontier)
                if current in closed:
                    continue
                closed.add(current); stats[0] += 1
                if current == goal:
                    return finish(goal)
                for neighbor, edge_cost in adjacency.get(current, ()):
                    candidate = costs[current] + edge_cost
                    if candidate >= costs.get(neighbor, float("inf")):
                        continue
                    parent[neighbor] = current; costs[neighbor] = candidate; stats[1] += 1
                    heapq.heappush(frontier, (candidate + heuristic(neighbor, goal), next(serial), neighbor))
                    stats[2] = max(stats[2], len(frontier))
        from core.ai.search import SearchResult
        return SearchResult((), False, SearchStats(*stats))


if __name__ == "__main__":
    unittest.main()
