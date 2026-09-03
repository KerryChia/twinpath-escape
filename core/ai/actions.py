"""Shared, immutable input actions for human and computer-controlled players."""

from dataclasses import dataclass
from typing import Protocol, TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from core.ai.observation import Observation


@dataclass(frozen=True, slots=True)
class Action:
    left: bool = False
    right: bool = False
    jump: bool = False
    down: bool = False


class ActionProvider(Protocol):
    def get_action(self, observation: "Observation | None") -> Action: ...


class KeyboardActionProvider:
    """Translate one configured key set into an Action without touching physics."""

    def __init__(self, bindings: dict[str, str], key_map: dict[str, int]) -> None:
        self.keys = {name: key_map[value] for name, value in bindings.items()}

    def get_action(self, observation: "Observation | None" = None) -> Action:
        pressed = pygame.key.get_pressed()
        return Action(
            left=bool(pressed[self.keys["left"]]),
            right=bool(pressed[self.keys["right"]]),
            jump=bool(pressed[self.keys["jump"]]),
            down=bool(pressed[self.keys["down"]]),
        )


class StaticActionProvider:
    """Deterministic provider used by tests and headless simulations."""

    def __init__(self, action: Action = Action()) -> None:
        self.action = action

    def get_action(self, observation: "Observation | None" = None) -> Action:
        return self.action
