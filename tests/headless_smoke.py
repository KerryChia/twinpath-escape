"""Deterministic source-runtime smoke test; writes no screenshots or desktop data."""

import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from core.ai.controller import SearchActionProvider
from core.config.game_settings import settings
from core.scene import SceneManager
from core.scenes.ai_setup import AISetup
from core.scenes.base_gameplay import FinaleState
from core.scenes.gameplay import Gameplay
from core.scenes.main_menu import MainMenu


def checksum(surface: pygame.Surface) -> int:
    return sum(pygame.image.tobytes(surface, "RGB")[::997]) % 1_000_003


def run() -> dict:
    pygame.init(); pygame.mixer.init(); pygame.display.set_mode((1280, 720))
    report = {"menu": {}, "algorithms": {}}
    menu_manager = SceneManager(); menu = MainMenu(menu_manager); menu_manager.push(menu)
    setup = AISetup(menu_manager)
    for size in ((800, 600), (1280, 720), (1920, 1080)):
        menu.on_resize(*size); surface = pygame.Surface(size); menu.draw(surface)
        setup.on_resize(*size); setup.draw(surface)
        report["menu"][f"{size[0]}x{size[1]}"] = checksum(surface)

    # Hybrid main run: both players are search-driven (player 1 frozen as the
    # "human" observer is not viable because the co-op door needs two distinct
    # players on their own plates). Drive both with the fused planner so the AI
    # proves it understands the full cooperative sequence autonomously.
    manager = SceneManager(); scene = Gameplay(manager, "level_002", ai_algorithm="A*")
    manager.push(scene)
    scene.player1.action_provider = SearchActionProvider(player_index=0)
    scene.player2.action_provider = SearchActionProvider(player_index=1)
    frames = 0
    frame_limit = 60 * 60
    while frames < frame_limit and scene.finale_state == FinaleState.PLAYING:
        scene.update(1 / 60); frames += 1
    if scene.finale_state != FinaleState.SUCCESS:
        raise RuntimeError("Hybrid AI did not reach the explicit success page")
    scene.update(0.5)
    renders = {}
    for size in ((800, 600), (1280, 720), (1920, 1080)):
        scene.on_resize(*size); surface = pygame.Surface(size); scene.draw(surface)
        renders[f"{size[0]}x{size[1]}"] = checksum(surface)
    report["hybrid"] = {
        "frames_to_success": frames,
        "success_page": scene.finale_state == FinaleState.SUCCESS,
        "both_exits": list(scene.final_exit_entered),
        "winner": scene.player2.action_provider.winner,
        "candidates": list(scene.player2.action_provider.candidates),
        "replans": scene.player2.action_provider.replans,
        "renders": renders,
    }

    # Benchmark each plan preference: hybrid is still run, but the winner is forced.
    report["algorithms"] = {}
    for algorithm in ("BFS", "DFS", "A*"):
        manager = SceneManager(); scene = Gameplay(manager, "level_002", ai_algorithm="A*")
        manager.push(scene)
        scene.player1.action_provider = SearchActionProvider(prefer=algorithm, player_index=0)
        scene.player2.action_provider = SearchActionProvider(prefer=algorithm, player_index=1)
        frames = 0
        while frames < frame_limit and scene.finale_state == FinaleState.PLAYING:
            scene.update(1 / 60); frames += 1
        if scene.finale_state == FinaleState.PLAYING:
            raise RuntimeError(f"{algorithm} did not complete the physical finale smoke")
        report["algorithms"][algorithm] = {
            "frames_to_ending": frames,
            "winner": scene.player2.action_provider.winner,
            "candidates": list(scene.player2.action_provider.candidates),
            "both_exits": list(scene.final_exit_entered),
            "replans": scene.player2.action_provider.replans,
        }
    pygame.quit()
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
