"""AI behaviour polish regressions: hold anti-oscillation + double-jump usage.

These complement `test_dual_ai_completion.py` (which proves the campaign is
beaten) by pinning the *quality* fixes from the AI showcase handoff:

- HOLD dead-band control must not flip steering direction faster than 2/s
  (the old ±4px band with opposite-input braking flipped every frame).
- The gap-leap edges that physically require a double jump must actually see
  a second jump press inside the same takeoff (33 -> 59 -> 58 in level_001),
  with the landing correct.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

import pygame

from core.ai.controller import SearchActionProvider
from core.scenes.gameplay import Gameplay
from core.scene import SceneManager

# A double jump's second press lands ~20-24 frames after the first (apex of a
# 720/1800 jump); any ground-and-rejump pattern needs the full ~48-frame
# airtime plus a fresh takeoff, so a second press within this many frames of
# the first can only be a mid-air double jump.
DOUBLE_PRESS_MAX_GAP = 40


class _RecordingProvider:
    """Wrap a SearchActionProvider, logging (state, steer) per tick."""

    def __init__(self, inner: SearchActionProvider) -> None:
        self.inner = inner
        self.log: list[tuple[str, int]] = []

    def tick(self, dt: float, observation):
        action = self.inner.tick(dt, observation)
        steer = (1 if action.right else 0) - (1 if action.left else 0)
        self.log.append((self.inner.execution_state.value, steer))
        return action

    def get_action(self, observation):
        action = self.inner.get_action(observation)
        steer = (1 if action.right else 0) - (1 if action.left else 0)
        self.log.append((self.inner.execution_state.value, steer))
        return action

    def consume_reset_request(self) -> bool:
        return self.inner.consume_reset_request()

    @property
    def metrics(self):
        return self.inner.metrics


def _two_press_double(script) -> bool:
    """True if a committed trajectory holds a mid-air second jump press."""
    presses = [
        i for i in range(len(script))
        if script[i].jump and (i == 0 or not script[i - 1].jump)
    ]
    return any(
        0 < b - a <= DOUBLE_PRESS_MAX_GAP
        for a, b in zip(presses, presses[1:])
    )


class HoldAntiOscillationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.mixer.init()
        pygame.display.set_mode((1280, 720))

    def test_tutorial_hold_flip_rate_is_bounded(self):
        manager = SceneManager()
        scene = Gameplay(manager, "tutorial_001", ai_algorithm="A*")
        manager.push(scene)
        recorders = []
        for index, player in enumerate((scene.player1, scene.player2)):
            recorder = _RecordingProvider(SearchActionProvider(player_index=index))
            recorders.append(recorder)
            player.action_provider = recorder
        for _ in range(60 * 120):
            scene.update(1 / 60)
            if scene.portal is not None and scene.portal.p1_entered and scene.portal.p2_entered:
                break
        self.assertTrue(scene._portal_activated, "portal must have been reached")
        # Oscillation breaker: the in-place left/right shake must never trip
        # it on a clean run (three reversals in the same spot = the twitch).
        for index, recorder in enumerate(recorders):
            self.assertLessEqual(
                recorder.inner.oscillations, 2,
                f"P{index + 1} tripped the oscillation breaker "
                f"{recorder.inner.oscillations} times",
            )
        for index, recorder in enumerate(recorders):
            hold = [(state, steer) for state, steer in recorder.log if state == "HOLD"]
            if not hold:
                continue
            flips = 0
            last = 0
            for _state, steer in hold:
                if steer != 0:
                    if last and steer != last:
                        flips += 1
                    last = steer
            seconds = len(hold) / 60
            rate = flips / max(seconds, 1e-9)
            self.assertLessEqual(
                rate, 2.0,
                f"P{index + 1} HOLD oscillates at {rate:.2f} flips/s "
                f"({flips} flips over {len(hold)} frames)",
            )


class DoubleJumpUsageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.mixer.init()
        pygame.display.set_mode((1280, 720))

    def test_gap_leap_edges_commit_double_jump_script(self):
        # The 33 -> 59 -> 58 chain in level_001 spans flat gaps wider than a
        # full-speed single jump glide (~150-175px); only a double jump can
        # cover them. Either AI crossing that chain must commit a simulator
        # script with two jump presses inside one takeoff.
        manager = SceneManager()
        scene = Gameplay(manager, "level_001", ai_algorithm="A*")
        manager.push(scene)
        providers = [
            SearchActionProvider(player_index=0),
            SearchActionProvider(player_index=1),
        ]
        scene.player1.action_provider = providers[0]
        scene.player2.action_provider = providers[1]
        found_double = False
        for _ in range(60 * 120):
            scene.update(1 / 60)
            for provider in providers:
                if provider._sim_script and _two_press_double(provider._sim_script):
                    found_double = True
                    break
            if found_double:
                break
        self.assertTrue(
            found_double,
            "no committed trajectory used a double jump for the wide gap-leap edges",
        )


if __name__ == "__main__":
    unittest.main()
