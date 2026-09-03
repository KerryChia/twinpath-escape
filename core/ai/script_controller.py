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
        if predicate.startswith("pressed:"):
            plate_id = predicate.removeprefix("pressed:")
            plate = next((p for p in observation.plates if p.plate_id == plate_id), None)
            return bool(plate and plate.pressed)
        if predicate.startswith("partner_right_of:"):
            door_id = predicate.removeprefix("partner_right_of:")
            door = next((door for door in observation.doors if door.door_id == door_id), None)
            partner = observation.players[1 - self.player_index]
            return bool(door and partner.rect[0] >= door.rect[0] + door.rect[2])
        if predicate.startswith("door_open:"):
            tail = predicate.removeprefix("door_open:")
            # Real-time open state: true only while something keeps the door
            # held open (a hold-mode plate currently pressed). The ":off"
            # variant inverts it — the relay choreography uses it to detect
            # that the partner released the shared door.
            off = tail.endswith(":off")
            door_id = tail.removesuffix(":off") if off else tail
            opened = any(door.door_id == door_id and door.open for door in observation.doors)
            return (not opened) if off else opened
        if predicate == "on:ledge":
            # True once this player stands on the finale ledge (any platform
            # node above the ground line on level_002).
            me = observation.players[self.player_index]
            platforms = [
                node for node in observation.graph.nodes.values()
                if node.kind == "platform" and node.rect[1] < 500
            ] if observation.graph is not None else []
            return any(
                me.rect[0] < node.rect[0] + node.rect[2]
                and me.rect[0] + me.rect[2] > node.rect[0]
                and abs(node.rect[1] - (me.rect[1] + me.rect[3])) <= 12
                for node in platforms
            )
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
        elif target == "ledge:mount":
            # Resolve to the nearest platform ABOVE the player that lies
            # beyond the relay door — the finale-ledge side. Candidates left
            # of the door (the small ledge under the door column) are traps:
            # their jump arc clips the closed door body, and the AI would
            # bounce under it forever. From the ground the nearest such
            # platform is the springboard; from the springboard it is the
            # ledge itself, so the climb happens in natural hops.
            me = observation.players[self.player_index]
            feet = me.rect[1] + me.rect[3]
            door = next(
                (d for d in observation.doors if d.door_id == "door:0"), None
            )
            door_right = (door.rect[0] + door.rect[2]) if door else 0
            above = [
                node.rect for node in observation.graph.nodes.values()
                if node.kind == "platform" and node.rect[1] < feet - 60
                and node.rect[0] >= door_right - 20
            ] if observation.graph is not None else []
            if above:
                rect = min(above, key=lambda r: abs(r[0] + r[2] / 2 - me.position[0]))
        else:
            plate = next((plate for plate in observation.plates if plate.plate_id == target), None)
            rect = plate.rect if plate else None
        if rect is None or observation.graph is None:
            return None, rect
        center = self._center(rect)
        if target == "ledge:mount":
            # The springboard jump takes off from the ground below and lands
            # on the ledge's lip: pick the nearest platform node to the lip.
            node = min(
                (node for node in observation.graph.nodes.values() if node.kind == "platform"),
                key=lambda item: math.dist(item.position, center),
            ).node_id
            return node, rect
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
