"""Explicit game modes shared by every gameplay entry point.

`LOCAL` keeps both characters on the keyboard. `HUMAN_AI` gives the orange
character to the hybrid AI planner while the green one stays human-controlled.
`AI_SHOWCASE` is the presentation mode: both characters are AI-driven and a
showcase HUD narrates the run; gameplay logic is identical to HUMAN_AI's AI.
"""

from enum import Enum, auto


class GameMode(Enum):
    LOCAL = auto()
    HUMAN_AI = auto()
    AI_SHOWCASE = auto()
