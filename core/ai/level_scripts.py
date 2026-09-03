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
        # Green (player 0): wait while Orange holds the front plate, cross
        # the open door, then take over the back plate so Orange can release
        # and follow; finally the springboard up to the ledge and the exits.
        (
            ScriptStep("wait", None, "ai.goal.wait_door", "door_open:door:0"),
            ScriptStep("cross", "door:0:right", "ai.goal.cross_door", "right_of:door:0"),
            ScriptStep("hold", "door_plate:door:0:back", "ai.goal.plate", "partner_right_of:door:0"),
            ScriptStep("jump", "ledge:mount", "ai.goal.jump_up", "on:ledge"),
            ScriptStep("enter", "exit:player:0", "ai.goal.exit", "self_exit_entered"),
        ),
        # Orange (player 1): hold the front plate until Green holds the back
        # plate, cross the still-open door, then follow Green up the
        # springboard, hop the fake door and reach the exits.
        (
            ScriptStep("hold", "door_plate:door:0:front", "ai.goal.plate", "pressed:door_plate:door:0:back"),
            ScriptStep("cross", "door:0:right", "ai.goal.cross_door", "right_of:door:0"),
            ScriptStep("jump", "ledge:mount", "ai.goal.jump_up", "on:ledge"),
            ScriptStep("enter", "exit:player:1", "ai.goal.exit", "self_exit_entered"),
        ),
    ),
}
