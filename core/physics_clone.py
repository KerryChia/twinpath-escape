"""Headless Player state construction for deterministic physics rollouts."""

import pygame

from core.player import Player


def clone_observed_player(observation) -> Player:
    """Create an isolated Player clone from an immutable AI observation."""
    sim = Player.__new__(Player)
    sim.pos = pygame.math.Vector2(observation.position[0], observation.rect[1])
    sim.velocity = pygame.math.Vector2(observation.velocity[0], observation.velocity[1])
    sim.acceleration = pygame.math.Vector2()
    sim.on_ground = observation.on_ground
    sim.was_airborne = False
    sim.just_landed = False
    sim.in_water = observation.in_water
    sim.in_lava = False
    sim.on_stairs = observation.on_stairs
    sim.dropping_through = False
    sim.has_double_jump = observation.has_double_jump
    sim.dead = False
    sim._death_timer = 0.0
    sim._airtime = 0.0
    sim.state = "idle"
    sim.frame_index = 0.0
    sim.image = None
    sim.rect = pygame.Rect(
        int(sim.pos.x), int(sim.pos.y), observation.rect[2], observation.rect[3]
    )
    sim._squash_timer = 0.0
    sim._stretch_timer = 0.0
    sim.scale_x = 1.0
    sim.scale_y = 1.0
    idle = pygame.Surface((1, 1))
    sim.animations = {
        "idle": [idle],
        "walk": [idle],
        "jump": [idle],
        "die": [idle],
        "fall": [idle],
    }
    sim._animate = lambda dt: None
    return sim
