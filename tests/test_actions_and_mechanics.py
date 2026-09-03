import dataclasses
from dataclasses import replace
import ast
import inspect
import os
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest
import pygame

from core.ai.actions import Action, KeyboardActionProvider, StaticActionProvider
from core.ai.controller import SearchActionProvider
from core.ai.graph import PlatformGraph, PlatformNode
from core.ai.observation import from_scene
from core.doors import DoorManager
from core.moving_platform import MovingPlatformManager
from core.player import Player
from core.scene import SceneManager
from core.scenes.gameplay import Gameplay


class ActionAndMechanicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init(); pygame.mixer.init(); pygame.display.set_mode((1280, 720))

    def test_action_is_immutable_and_player_uses_provider(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            Action().left = True
        provider = StaticActionProvider(Action(right=True))
        player = Player(10, 10, action_provider=provider)
        player.update(1 / 60, [], [], action=provider.get_action(None))
        self.assertGreater(player.acceleration.x, 0)
        self.assertEqual(player.last_action, Action(right=True))

    def test_ai_controller_has_no_coordinate_or_fake_event_control(self):
        root = Path(__file__).resolve().parents[1] / "core" / "ai"
        for path in root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("pygame.event", source)
            tree = ast.parse(source)
            for node in ast.walk(tree):
                targets = []
                if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Attribute):
                        self.assertNotIn(target.attr, {"pos", "rect", "velocity"}, path.name)
        self.assertIsInstance(SearchActionProvider().get_action(None), Action)

    def test_local_two_player_keyboard_regression(self):
        scene = Gameplay(SceneManager(), "tutorial_001")
        self.assertIsNone(scene.ai_provider)
        self.assertIsInstance(scene.player1.action_provider, KeyboardActionProvider)
        self.assertIsInstance(scene.player2.action_provider, KeyboardActionProvider)
        self.assertNotEqual(scene.player1.action_provider.keys, scene.player2.action_provider.keys)

    def test_real_keyboard_provider_action_reaches_physics(self):
        scene = Gameplay(SceneManager(), "tutorial_001")
        player = scene.player1
        pressed = [False] * 600
        pressed[player.action_provider.keys["right"]] = True
        with patch("pygame.key.get_pressed", return_value=pressed):
            action = player.action_provider.get_action(None)
        old_x = player.pos.x
        player.update(1 / 30, [], [], action=action)
        self.assertEqual(action, Action(right=True))
        self.assertGreater(player.pos.x, old_x)

    def test_stuck_controller_replans_without_oscillation(self):
        scene = Gameplay(SceneManager(), "level_002", ai_algorithm="A*")
        observation = from_scene(scene); provider = scene.ai_provider
        actions = [provider.tick(0.25, observation) for _ in range(12)]
        self.assertGreater(provider.replans, 0)
        self.assertEqual(set(provider.candidates), {"BFS", "DFS", "A*"})
        self.assertIn(provider.winner, {"BFS", "DFS", "A*", ""})
        self.assertTrue(all(isinstance(action, Action) for action in actions))
        self.assertFalse(any(action.left and action.right for action in actions))

    def test_observation_includes_floor_and_grounded_platform(self):
        scene = Gameplay(SceneManager(), "level_002")
        player = scene.player2
        floor = max(scene.map.collision_rects, key=lambda rect: rect.width)
        player.rect.midbottom = (floor.centerx, floor.top)
        player.pos.update(player.rect.topleft); player.on_ground = True
        observation = from_scene(scene)
        self.assertIn((floor.x, floor.y, floor.width, floor.height), observation.platforms)
        self.assertIsNotNone(observation.players[1].platform_id)

    def test_failed_search_retries_are_counted_bounded_and_request_reset(self):
        scene = Gameplay(SceneManager(), "level_002")
        observation = from_scene(scene)
        graph = PlatformGraph()
        graph.add_node(PlatformNode("start", (0, 0), "platform"))
        graph.add_node(PlatformNode("exit:0", (100, 0), "exit"))
        players = tuple(replace(player, platform_id="start") for player in observation.players)
        observation = replace(
            observation,
            level_id="test",
            graph=graph,
            players=players,
            exits=((100, 0, 10, 10),),
            portal_active=True,
            doors=(),
        )
        provider = SearchActionProvider()
        for _ in range(300):
            provider.tick(1 / 60, observation)
            if provider._reset_requested:
                break
        self.assertTrue(provider._reset_requested)
        provider.path = ("start", "exit:0")
        provider.path_index = 1
        provider.goal_node = "exit:0"
        self.assertTrue(provider.consume_reset_request())
        self.assertEqual(provider.path, ())
        self.assertEqual(provider.path_index, 0)
        self.assertIsNone(provider.goal_node)
        attempts = provider._plan_attempts
        provider.tick(1 / 60, observation)
        self.assertGreater(provider._plan_attempts, attempts)
        self.assertGreaterEqual(provider.replans, 5)
        self.assertLess(provider.replans, 30)

    def test_moving_platform_carries_rider(self):
        image = pygame.Surface((20, 10)); tile = (pygame.Rect(0, 100, 20, 10), image)
        manager = MovingPlatformManager([tile], [pygame.Rect(0, 100, 1, 1), pygame.Rect(50, 100, 1, 1)])
        rider = Player(0, 52, action_provider=StaticActionProvider())
        rider.rect.bottom = 100; rider.pos.y = rider.rect.y; rider.velocity.y = 0
        old_x = rider.pos.x; manager.update(0.2, [rider])
        self.assertGreater(rider.pos.x, old_x)

    def test_door_swept_close_stops_before_open_gap_player(self):
        image = pygame.Surface((20, 20))
        tiles = [(pygame.Rect(100, y, 20, 20), image) for y in (60, 80, 100, 120)]
        manager = DoorManager(tiles, [], 1.0)
        door = manager.doors[0]; door.open_amount = door.max_displacement; door.update(0.0)
        blocker = pygame.Rect(100, 85, 20, 30)
        self.assertFalse(any(rect.colliderect(blocker) for rect in door.collision_rects()))
        before = door.open_amount
        for _ in range(5):
            manager.update(0.1, blocker)
            self.assertFalse(any(rect.colliderect(blocker) for rect in door.collision_rects()))
        self.assertFalse(door.target_open)
        self.assertGreater(door.open_amount, 0)
        self.assertLess(door.open_amount, before)

    def test_long_fall_airtime_survives_landing_check(self):
        player = Player(0, 50, action_provider=StaticActionProvider())
        floor = pygame.Rect(-100, 100, 300, 20)
        player.rect.bottom = 99; player.pos.y = player.rect.y
        player.velocity.y = 120; player.was_airborne = True; player._airtime = 2.0
        player.update(1 / 30, [floor], [], action=Action())
        self.assertTrue(player.dead)


if __name__ == "__main__":
    unittest.main()
