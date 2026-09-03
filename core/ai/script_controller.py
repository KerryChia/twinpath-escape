"""Resolve explicit campaign scripts against typed runtime observations."""

from dataclasses import dataclass
import math

from core.ai.level_scripts import LEVEL_SCRIPTS, ScriptStep
from core.ai.observation import Observation, RectTuple


@dataclass(frozen=True, slots=True)
class ScriptDirective:
    step_index: int
    operation: str
    semantic_target: str | None
    goal_key: str
    node_id: str | None
    target_rect: RectTuple | None
    complete: bool = False

    @property
    def identity(self) -> tuple[int, str, str | None]:
        return self.step_index, self.operation, self.semantic_target


class LevelScriptController:
    def __init__(self, player_index: int) -> None:
        self.player_index = player_index
        self.level_id: str | None = None
        self.step_index = 0

    def _reset_level(self, level_id: str) -> None:
        if level_id != self.level_id:
            self.level_id = level_id
            self.step_index = 0

    def _predicate(self, predicate: str, observation: Observation) -> bool:
        if predicate == "portal_active":
            return observation.portal_active
        if predicate == "self_portal_entered":
            return observation.portal_entered[self.player_index]
        if predicate == "coop_open":
            return observation.coop_doors_open
        if predicate == "self_exit_entered":
            return observation.final_exit_entered[self.player_index]
        if predicate.startswith("latched:"):
            door_id = predicate.removeprefix("latched:")
            return any(door.door_id == door_id and door.latched for door in observation.doors)
        if predicate.startswith("right_of:"):
            door_id = predicate.removeprefix("right_of:")
            door = next((door for door in observation.doors if door.door_id == door_id), None)
            return bool(door and observation.players[self.player_index].rect[0] >= door.rect[0] + door.rect[2])
        return False

    @staticmethod
    def _center(rect: RectTuple) -> tuple[float, float]:
        return rect[0] + rect[2] / 2, rect[1] + rect[3] / 2

    def _resolve(self, target: str | None, observation: Observation) -> tuple[str | None, RectTuple | None]:
        if target is None:
            return None, None
        rect = None
        if target == "portal":
            rect = observation.portal_rect
        elif target.startswith("exit:player:"):
            index = int(target.rsplit(":", 1)[1])
            if observation.exits:
                rect = observation.exits[min(index, len(observation.exits) - 1)]
        elif target.endswith(":right") and (target.startswith("door:") or target.startswith("coop:")):
            door_id = target.removesuffix(":right")
            door = next((door for door in observation.doors if door.door_id == door_id), None)
            if door:
                rect = (door.rect[0] + door.rect[2] * 2, door.rect[1], max(8, door.rect[2]), door.rect[3])
        else:
            plate = next((plate for plate in observation.plates if plate.plate_id == target), None)
            rect = plate.rect if plate else None
        if rect is None or observation.graph is None:
            return None, rect
        center = self._center(rect)
        preferred_kind = "exit" if target == "portal" or target.startswith("exit:") else "plate" if "plate" in target or target.startswith(("ordinary:", "coop:player:")) else "door_side"
        candidates = [node for node in observation.graph.nodes.values() if node.kind == preferred_kind]
        if not candidates:
            candidates = list(observation.graph.nodes.values())
        node = min(candidates, key=lambda item: math.dist(item.position, center))
        return node.node_id, rect

    def directive(self, observation: Observation) -> ScriptDirective:
        self._reset_level(observation.level_id)
        scripts = LEVEL_SCRIPTS.get(observation.level_id)
        if not scripts:
            if observation.exits:
                index = min(self.player_index, len(observation.exits) - 1)
                rect = observation.exits[index]
                graph = observation.graph
                nodes = [node for node in graph.nodes.values() if node.kind == "exit"] if graph else []
                node = min(nodes, key=lambda item: math.dist(item.position, self._center(rect))).node_id if nodes else None
                return ScriptDirective(0, "enter", f"exit:player:{index}", "ai.goal.exit", node, rect)
            return ScriptDirective(0, "wait", None, "ai.goal.wait", None, None, True)
        steps = scripts[self.player_index]
        while self.step_index < len(steps) and self._predicate(steps[self.step_index].until, observation):
            self.step_index += 1
        if self.step_index >= len(steps):
            return ScriptDirective(self.step_index, "complete", None, "ai.goal.complete", None, None, True)
        step: ScriptStep = steps[self.step_index]
        node, rect = self._resolve(step.target, observation)
        return ScriptDirective(self.step_index, step.operation, step.target, step.goal_key, node, rect)
