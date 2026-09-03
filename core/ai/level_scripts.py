"""Explicit semantic cooperation scripts for the shipped campaign.

Scripts describe roles, world predicates and semantic targets.  They never
contain coordinates or input recordings; routes to resolved targets are still
searched by the native BFS/DFS/A* backend.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScriptStep:
    operation: str
    target: str | None
    goal_key: str
    until: str


LEVEL_SCRIPTS: dict[str, tuple[tuple[ScriptStep, ...], tuple[ScriptStep, ...]]] = {
    "tutorial_001": (
        (
            ScriptStep("hold", "ordinary:left", "ai.goal.plate_left", "portal_active"),
            ScriptStep("enter", "portal", "ai.goal.portal", "self_portal_entered"),
        ),
        (
            ScriptStep("hold", "ordinary:right", "ai.goal.plate_right", "portal_active"),
            ScriptStep("enter", "portal", "ai.goal.portal", "self_portal_entered"),
        ),
    ),
    "level_001": (
        (
            ScriptStep("hold", "ordinary:left", "ai.goal.plate_left", "portal_active"),
            ScriptStep("enter", "portal", "ai.goal.portal", "self_portal_entered"),
        ),
        (
            ScriptStep("hold", "ordinary:right", "ai.goal.plate_right", "portal_active"),
            ScriptStep("enter", "portal", "ai.goal.portal", "self_portal_entered"),
        ),
    ),
    "level_002": (
        (
            ScriptStep("wait", None, "ai.goal.wait_door", "latched:door:0"),
            ScriptStep("cross", "door:0:right", "ai.goal.cross_door", "right_of:door:0"),
            ScriptStep("latch", "door_plate:door:1", "ai.goal.latch", "latched:door:1"),
            ScriptStep("cross", "door:1:right", "ai.goal.cross_door", "right_of:door:1"),
            ScriptStep("hold", "coop:player:0", "ai.goal.coop_plate", "coop_open"),
            ScriptStep("cross", "coop:0:right", "ai.goal.cross_coop", "right_of:coop:0"),
            ScriptStep("enter", "exit:player:0", "ai.goal.exit", "self_exit_entered"),
        ),
        (
            ScriptStep("latch", "door_plate:door:0", "ai.goal.latch", "latched:door:0"),
            ScriptStep("cross", "door:0:right", "ai.goal.cross_door", "right_of:door:0"),
            ScriptStep("wait", None, "ai.goal.wait_door", "latched:door:1"),
            ScriptStep("cross", "door:1:right", "ai.goal.cross_door", "right_of:door:1"),
            ScriptStep("hold", "coop:player:1", "ai.goal.coop_plate", "coop_open"),
            ScriptStep("cross", "coop:0:right", "ai.goal.cross_coop", "right_of:coop:0"),
            ScriptStep("enter", "exit:player:1", "ai.goal.exit", "self_exit_entered"),
        ),
    ),
}
