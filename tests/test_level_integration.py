import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest
import pygame

from core.ai.controller import SearchActionProvider
from core.ai.search import search
from core.config.levels import LEVELS
from core.scenes.base_gameplay import FinaleState
from core.scenes.gameplay import Gameplay
from core.scenes.main_menu import MainMenu
from core.scene import SceneManager


class LevelIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init(); pygame.mixer.init(); pygame.display.set_mode((1280, 720))

    def test_all_levels_load_with_two_spawns(self):
        self.assertEqual(set(LEVELS), {"tutorial_001", "level_001", "level_002"})
        for level_id in LEVELS:
            scene = Gameplay(SceneManager(), level_id)
            self.assertIsNotNone(scene.map.get_spawn("A") if level_id == "level_002" else (scene.spawn_x, scene.spawn_y))
            self.assertIsNotNone(scene.map.get_spawn("B") if level_id == "level_002" else (scene.spawn_b_x, scene.spawn_b_y))
            self.assertEqual(len(scene.players), 2)

    def test_finale_integrity_and_trigger_references(self):
        scene = Gameplay(SceneManager(), "level_002", ai_algorithm="A*")
        self.assertEqual(len(scene.final_exit_rects), 2)
        specs = scene.map.mechanism_specs
        self.assertEqual({spec["controls"] for spec in specs}, {"door:0", "door:1"})
        self.assertEqual({spec["required_player"] for spec in specs}, {1, 2})
        self.assertTrue(all(spec["mode"] == "latch" for spec in specs))
        self.assertEqual(len(scene.door_manager.doors), 2)
        self.assertEqual(len(scene.coop_doors.plates), 2)

    def test_all_algorithms_validate_cooperative_route(self):
        scene = Gameplay(SceneManager(), "level_002")
        graph = scene.platform_graph
        stages = [
            ("plate:0", "plate:1", frozenset({"open:door:0"})),
            ("plate:1", "plate:3", frozenset({"open:door:0", "open:door:1"})),
            ("plate:3", "exit:1", frozenset({"open:door:0", "open:door:1", "open:coop:0"})),
        ]
        for algorithm in ("BFS", "DFS", "A*"):
            for start, goal, conditions in stages:
                result = search(algorithm, graph, start, goal, graph.heuristic, conditions)
                self.assertTrue(result.found, (algorithm, start, goal))
                self.assertTrue(all(graph.edge(a, b) for a, b in zip(result.path, result.path[1:])))

    def test_all_algorithms_complete_finale_through_real_physics(self):
        # Hybrid planner runs BFS, DFS and A* every plan; `prefer` only hints the
        # winner so each algorithm can be proven individually executable. The AI
        # drives player 2; player 1 is the local human. Search provider runs both
        # players through real physics independently.
        for prefer in ("BFS", "DFS", "A*"):
            manager = SceneManager(); scene = Gameplay(manager, "level_002", ai_algorithm="A*")
            manager.push(scene)
            scene.player1.action_provider = SearchActionProvider(prefer=prefer, player_index=0)
            scene.player2.action_provider = SearchActionProvider(prefer=prefer, player_index=1)
            frames = 0
            for frame in range(60 * 60):
                if scene.finale_state != FinaleState.PLAYING:
                    frames = frame
                    break
                scene.update(1 / 60)
            self.assertLess(frames, 60 * 60 - 1, prefer)
            self.assertTrue(scene.coop_doors._opened, prefer)
            self.assertEqual(scene.final_exit_entered, [True, True], prefer)
            self.assertEqual(scene.finale_state, FinaleState.SUCCESS, prefer)
            self.assertEqual(set(scene.player2.action_provider.candidates), {"BFS", "DFS", "A*"}, prefer)

            scene.update(0.5)
            surface = pygame.Surface((1280, 720))
            surface.fill((0, 0, 0))
            scene.draw(surface)
            self.assertNotEqual(surface.get_at((640, 360))[:3], (0, 0, 0), prefer)

    def test_full_ending_state_returns_to_main_menu(self):
        manager = SceneManager(); scene = Gameplay(manager, "level_002", ai_algorithm="A*")
        manager.push(scene)
        scene.player1.action_provider = SearchActionProvider(player_index=0)
        for _ in range(60 * 60):
            scene.update(1 / 60)
            if scene.finale_state != FinaleState.PLAYING:
                break
        self.assertEqual(scene.finale_state, FinaleState.SUCCESS)
        for _ in range(60 * 40):
            if isinstance(manager.current, MainMenu):
                break
            scene._update_shared(1 / 60)
        self.assertIsInstance(manager.current, MainMenu)

    def test_finale_checkpoint_and_latch_survive_respawn_and_resize(self):
        scene = Gameplay(SceneManager(), "level_002")
        scene.door_manager._latched = {0, 1}
        for door in scene.door_manager.doors:
            door.open_amount = door.max_displacement
        player = scene.player1
        player.on_ground = True; player.in_water = False; player.in_lava = False
        player.pos.x = scene.checkpoints[0][0] + 300; player.rect.x = int(player.pos.x)
        scene._update_checkpoint(0, player)
        checkpoint = scene.checkpoints[0]
        scene._respawn_player(0, player)
        self.assertEqual(tuple(player.pos), checkpoint)

        player.pos.y = scene.map.offset[1] + scene.map.scaled_size[1] + 300
        player.rect.y = int(player.pos.y)
        scene._update_player(0, player, 1 / 60)
        self.assertEqual(tuple(player.pos), checkpoint)

        player.dead = True
        player._death_timer = 1.49
        scene._update_player(0, player, 1 / 30)
        self.assertFalse(player.dead)
        self.assertEqual(tuple(player.pos), checkpoint)

        self.assertEqual(scene.door_manager._latched, {0, 1})
        scene.on_resize(1920, 1080)
        self.assertEqual(scene.door_manager._latched, {0, 1})
        self.assertTrue(all(door.open_amount > 0 for door in scene.door_manager.doors))


if __name__ == "__main__":
    unittest.main()
