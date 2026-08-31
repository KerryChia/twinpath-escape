"""AI-controlled players for the main menu background."""

import random

import pygame
import pytmx
from pytmx.util_pygame import load_pygame

from core.config.constants import (
    PLAYER_ACCELERATION,
    PLAYER_JUMP_FORCE,
    STRETCH_DURATION,
)
from core.player import Player
from core.resource import resource_path

MENU_MAP_PATH = resource_path("assets/tiled/menu.tmx")


SKIP_RENDER = {"Path", "SpawnA", "SpawnB"}


class MenuBackground:
    """Loads menu.tmx — renders Bg+Floor visible, Path as invisible collision."""

    def __init__(self, screen_size: tuple[int, int]) -> None:
        self.tmx = load_pygame(str(MENU_MAP_PATH))
        tw, th = self.tmx.tilewidth, self.tmx.tileheight
        self.pixel_size = (self.tmx.width * tw, self.tmx.height * th)
        self._native_rects: list[pygame.Rect] = []
        self._native_spawns: dict[str, tuple[float, float]] = {}
        self.collision_rects: list[pygame.Rect] = []
        self.scale = 1.0
        self.offset = (0, 0)
        self._surface = self._pre_render()
        self._scaled_surface = self._surface
        self._extract_collision()
        self._extract_spawns()
        self.rescale(screen_size)

    def _pre_render(self) -> pygame.Surface:
        surface = pygame.Surface(self.pixel_size, pygame.SRCALPHA)
        tw, th = self.tmx.tilewidth, self.tmx.tileheight
        for layer in self.tmx.layers:
            if not isinstance(layer, pytmx.TiledTileLayer):
                continue
            if layer.name in SKIP_RENDER or not layer.visible:
                continue
            for x, y, image in layer.tiles():
                surface.blit(image, (x * tw, y * th))
        return surface

    def _extract_collision(self) -> None:
        tw, th = self.tmx.tilewidth, self.tmx.tileheight
        path_layer = floor_layer = None
        for layer in self.tmx.layers:
            if not isinstance(layer, pytmx.TiledTileLayer):
                continue
            if layer.name == "Path":
                path_layer = layer
            elif layer.name == "Floor":
                floor_layer = layer

        source = path_layer or floor_layer
        if not source:
            return
        for x, y, gid in source:
            if gid:
                self._native_rects.append(pygame.Rect(x * tw, y * th, tw, th))

    def _extract_spawns(self) -> None:
        tw, th = self.tmx.tilewidth, self.tmx.tileheight
        for layer in self.tmx.layers:
            if not isinstance(layer, pytmx.TiledTileLayer):
                continue
            if layer.name not in ("SpawnA", "SpawnB"):
                continue
            for x, y, gid in layer:
                if gid:
                    self._native_spawns[layer.name] = (
                        x * tw + tw / 2,
                        y * th + th / 2,
                    )
                    break

    def get_spawn(self, player: str) -> tuple[float, float] | None:
        """Return scaled spawn position for SpawnA/SpawnB."""
        native = self._native_spawns.get(f"Spawn{player.upper()}")
        if not native:
            return None
        ox, oy = self.offset
        return (native[0] * self.scale + ox, native[1] * self.scale + oy)

    def rescale(self, screen_size: tuple[int, int]) -> None:
        sw, sh = screen_size
        pw, ph = self.pixel_size
        self.scale = min(sw / pw, sh / ph)
        scaled_w = int(pw * self.scale)
        scaled_h = int(ph * self.scale)
        self.offset = ((sw - scaled_w) // 2, (sh - scaled_h) // 2)
        self._scaled_surface = pygame.transform.scale(self._surface, (scaled_w, scaled_h))
        ox, oy = self.offset
        s = self.scale
        self.collision_rects = [
            pygame.Rect(int(r.x * s) + ox, int(r.y * s) + oy, int(r.w * s), int(r.h * s))
            for r in self._native_rects
        ]

    def get_bounds(self) -> pygame.Rect:
        pw, ph = self.pixel_size
        return pygame.Rect(
            self.offset[0], self.offset[1], int(pw * self.scale), int(ph * self.scale)
        )

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self._scaled_surface, self.offset)


class AIPlayer(Player):
    """Player controlled by simple AI for menu background decoration."""

    def __init__(
        self,
        x: float,
        y: float,
        outline_color: tuple[int, int, int],
        character: str,
    ) -> None:
        super().__init__(x, y, outline_color=outline_color, character=character, name="")
        self._dir = random.choice([-1, 1])
        self._move_timer = random.uniform(2.0, 4.0)
        self._jump_timer = random.uniform(1.0, 3.0)
        self._idle_timer = 0.0
        self._want_jump = False
        self._stuck_frames = 0

    def handle_input(self) -> None:
        """Replace keyboard input with AI decisions."""
        self.acceleration.x = 0
        self.dropping_through = False

        if self._idle_timer > 0:
            return

        self.acceleration.x = PLAYER_ACCELERATION * self._dir
        self.facing_right = self._dir > 0

        if self._want_jump:
            if self.on_ground:
                self.velocity.y = PLAYER_JUMP_FORCE
                self.on_ground = False
                self.has_double_jump = True
                self._stretch_timer = STRETCH_DURATION
                self._squash_timer = 0.0
            elif self.has_double_jump and self._near_apex():
                self.velocity.y = PLAYER_JUMP_FORCE
                self.has_double_jump = False
                self._stretch_timer = STRETCH_DURATION
                self._squash_timer = 0.0
            self._want_jump = False

    def update_ai(self, dt: float, map_bounds: pygame.Rect) -> None:
        """Tick AI state machine before Player.update is called."""
        if self._idle_timer > 0:
            self._idle_timer -= dt
            if self._idle_timer <= 0:
                self._dir = random.choice([-1, 1])
                self._move_timer = random.uniform(2.0, 4.0)
            return

        self._move_timer -= dt
        if self._move_timer <= 0:
            if random.random() < 0.25:
                self._idle_timer = random.uniform(0.5, 1.5)
            else:
                self._dir *= -1
                self._move_timer = random.uniform(2.0, 4.0)

        self._jump_timer -= dt
        if self._jump_timer <= 0 and self.on_ground:
            self._want_jump = True
            self._jump_timer = random.uniform(1.5, 3.5)

        # Reverse if stuck against a wall
        if abs(self.velocity.x) < 1.0 and self.acceleration.x != 0:
            self._stuck_frames += 1
            if self._stuck_frames > 5:
                self._dir *= -1
                self._stuck_frames = 0
        else:
            self._stuck_frames = 0

        # Reverse at map edges
        margin = 40
        if self.rect.left <= map_bounds.left + margin:
            self._dir = 1
        elif self.rect.right >= map_bounds.right - margin:
            self._dir = -1
