import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import heapq
import unittest
import pygame

from core.ai.graph import PlatformGraphExtractor
from core.ai.search import astar
from core.ai.observation import from_scene
from core.map_loader import TMXMap
from core.scene import SceneManager
from core.scenes.gameplay import Gameplay
from core.resource import resource_path


class PlatformGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init(); pygame.display.set_mode((1280, 720))
        cls.map = TMXMap(resource_path("assets/tiled/level_002.tmx"))
        cls.graph = PlatformGraphExtractor(cls.map).extract()

    def test_extracts_runtime_semantic_nodes_and_edges(self):
        kinds = {node.kind for node in self.graph.nodes.values()}
        self.assertTrue({"platform", "stairs", "plate", "door_side", "dock", "exit"} <= kinds)
        self.assertGreater(sum(map(len, self.graph.adjacency.values())), 0)
        self.assertEqual(len([n for n in self.graph.nodes.values() if n.kind == "exit"]), 2)

    def test_closed_and_open_conditional_doors(self):
        for base in ("door:0", "door:1", "coop:0"):
            left, right = f"{base}:left", f"{base}:right"
            self.assertNotIn(right, dict(self.graph.neighbors(left)))
            self.assertIn(right, dict(self.graph.neighbors(left, frozenset({f"open:{base}"}))))

    def test_no_direct_edges_cross_doors_or_lava(self):
        for edges in self.graph.adjacency.values():
            for edge in edges:
                a = self.graph.nodes[edge.source].position; b = self.graph.nodes[edge.target].position
                if edge.movement != "door":
                    self.assertFalse(any(rect.clipline(a, b) for rect in self.map.door_rects + self.map.second_door_rects))
                self.assertFalse(PlatformGraphExtractor._line_hits_hazard(a, b, self.map.lava_rects))

    def test_production_astar_matches_independent_dijkstra(self):
        conditions = frozenset({
            "open:door:0", "open:door:1", "open:coop:0",
            "ride:0:a>b", "ride:0:b>a",
        })

        def dijkstra_cost(start, goal):
            queue = [(0.0, start)]; best = {start: 0.0}
            while queue:
                cost, node = heapq.heappop(queue)
                if node == goal:
                    return cost
                if cost != best[node]:
                    continue
                for neighbor, edge_cost in self.graph.neighbors(node, conditions):
                    candidate = cost + edge_cost
                    if candidate < best.get(neighbor, float("inf")):
                        best[neighbor] = candidate
                        heapq.heappush(queue, (candidate, neighbor))
            return float("inf")

        separated = next(
            (a, b) for a in self.graph.nodes for b in self.graph.nodes
            if self.graph.nodes[a].position != self.graph.nodes[b].position
        )
        self.assertGreater(self.graph.heuristic(*separated), 0.0)
        for start in self.graph.nodes:
            for goal in self.graph.nodes:
                expected = dijkstra_cost(start, goal)
                result = astar(self.graph, start, goal, self.graph.heuristic, conditions)
                self.assertEqual(result.found, expected < float("inf"), (start, goal))
                if result.found:
                    self.assertAlmostEqual(result.stats.path_cost, expected, places=7)

    def test_moving_platform_availability_and_runtime_cost(self):
        ride_edges = [edge for edges in self.graph.adjacency.values() for edge in edges if edge.movement == "ride"]
        self.assertEqual(len(ride_edges), 2)
        a, b = "dock:0:a", "dock:0:b"
        self.assertNotIn(b, dict(self.graph.neighbors(a)))
        unavailable = self.graph.update_moving_platform(0, 0.5, 1)
        self.assertNotIn(b, dict(self.graph.neighbors(a, unavailable)))
        at_dock = self.graph.update_moving_platform(0, 0.0, 1)
        initial_cost = dict(self.graph.neighbors(a, at_dock))[b]
        departing = self.graph.update_moving_platform(0, 0.1, 1)
        departing_cost = dict(self.graph.neighbors(a, departing))[b]
        self.assertLess(departing_cost, initial_cost)
        wrong_direction = self.graph.update_moving_platform(0, 0.0, -1)
        self.assertNotIn(b, dict(self.graph.neighbors(a, wrong_direction)))

    def test_scene_observation_tracks_real_moving_platform_state(self):
        scene = Gameplay(SceneManager(), "level_002")
        platform = scene.moving_platforms.platforms[0]
        platform.progress = 0.0; platform.direction = 1
        boarding = from_scene(scene)
        self.assertIn("ride:0:a>b", boarding.graph_conditions)
        scene.moving_platforms.update(platform.distance / 60.0 * 0.5, scene.players)
        travelling = from_scene(scene)
        self.assertNotIn("ride:0:a>b", travelling.graph_conditions)
        platform.progress = 1.0; platform.direction = -1
        returning = from_scene(scene)
        self.assertIn("ride:0:b>a", returning.graph_conditions)


if __name__ == "__main__":
    unittest.main()
