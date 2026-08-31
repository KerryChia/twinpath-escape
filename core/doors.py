"""Door system with pressure plate triggers and piston-style animations."""

import random

import pygame

from core.config.constants import DOOR_PLATE_ANIM_SPEED, P1_OUTLINE_LOCAL, P2_OUTLINE_LOCAL
from core.resource import resource_path
from core.utils import add_outline, group_tiles_by_x, link_plates_to_doors, load_spritesheet

DOOR_PRESSURE_PATH = resource_path("assets/adve/door_pressure_plate.png")
DOOR_PRESSURE_FRAME_SIZE = (8, 8)
DOOR_PRESSURE_FRAME_COUNT = 3
DOOR_OPEN_SPEED = 120.0  # pixels per second
DOOR_CLOSE_SPEED = 200.0


class DoorPressurePlate:
    """Pressure plate specifically for doors — only active while a player stands on it."""

    def __init__(self, rect: pygame.Rect, frames: list[pygame.Surface]) -> None:
        self.rect = rect
        self.frames = frames
        self.pressed = False
        self.frame_index = 0.0

    def update(self, dt: float, *player_rects: pygame.Rect) -> None:
        self.pressed = any(self.rect.colliderect(pr) for pr in player_rects)

        if self.pressed:
            self.frame_index = min(
                self.frame_index + dt * DOOR_PLATE_ANIM_SPEED,
                len(self.frames) - 1,
            )
        else:
            self.frame_index = max(self.frame_index - dt * DOOR_PLATE_ANIM_SPEED, 0.0)

    def draw(self, surface: pygame.Surface, camera_offset: tuple[int, int] = (0, 0)) -> None:
        ox, oy = camera_offset
        frame = self.frames[int(self.frame_index)]
        surface.blit(frame, (self.rect.x - ox, self.rect.y - oy))


class Door:
    """A door made of tiles that opens from the middle like pistons.

    Supports different behaviors via the `behavior` parameter:
    - "pressure": opens while linked pressure plate is pressed, closes when released
    - "toggle": toggles open/closed on pressure plate press (future)
    - "permanent": opens once and stays open (future)
    """

    def __init__(
        self,
        tiles: list[tuple[pygame.Rect, pygame.Surface]],
        behavior: str = "pressure",
    ) -> None:
        self.behavior = behavior

        tiles.sort(key=lambda t: t[0].y)
        self.tile_count = len(tiles)
        self.tiles = tiles
        self.original_positions = [pygame.Rect(r.x, r.y, r.w, r.h) for r, _ in tiles]

        mid = self.tile_count // 2
        self.top_indices = list(range(mid))
        self.bottom_indices = list(range(mid, self.tile_count))

        tile_h = tiles[0][0].height if tiles else 32
        self.max_displacement = tile_h * mid

        self.open_amount = 0.0  # 0 = closed, max_displacement = fully open
        self.target_open = False

    @property
    def is_open(self) -> bool:
        return self.open_amount >= self.max_displacement - 1

    @property
    def is_closed(self) -> bool:
        return self.open_amount <= 0

    def set_open(self, should_open: bool) -> None:
        self.target_open = should_open

    def update(self, dt: float) -> None:
        if self.target_open:
            self.open_amount = min(self.open_amount + DOOR_OPEN_SPEED * dt, self.max_displacement)
        else:
            self.open_amount = max(self.open_amount - DOOR_CLOSE_SPEED * dt, 0.0)

        displacement = int(self.open_amount)
        for i in self.top_indices:
            orig = self.original_positions[i]
            self.tiles[i][0].y = orig.y - displacement
        for i in self.bottom_indices:
            orig = self.original_positions[i]
            self.tiles[i][0].y = orig.y + displacement

    def collision_rects(self) -> list[pygame.Rect]:
        """Return collision rects only when door is not fully open."""
        if self.is_open:
            return []
        return [r for r, _ in self.tiles]

    def draw(self, surface: pygame.Surface, camera_offset: tuple[int, int] = (0, 0)) -> None:
        ox, oy = camera_offset
        for rect, img in self.tiles:
            surface.blit(img, (rect.x - ox, rect.y - oy))


class DoorManager:
    """Manages doors and their linked pressure plates."""

    def __init__(
        self,
        door_tiles: list[tuple[pygame.Rect, pygame.Surface]],
        plate_rects: list[pygame.Rect],
        scale: float,
    ) -> None:
        self.plate_frames = load_spritesheet(
            DOOR_PRESSURE_PATH, DOOR_PRESSURE_FRAME_SIZE, DOOR_PRESSURE_FRAME_COUNT, scale
        )
        self.plates = [DoorPressurePlate(r, self.plate_frames) for r in plate_rects]
        self.doors = [Door(tiles) for tiles in group_tiles_by_x(door_tiles)]
        self.stuck_triggered = False
        self._player_crossed: dict[int, bool] = {}
        self.plate_door_map = link_plates_to_doors(self.plates, self.doors)

    def update(self, dt: float, *player_rects: pygame.Rect) -> None:
        for plate in self.plates:
            plate.update(dt, *player_rects)

        for door in self.doors:
            door.set_open(False)

        for pi, plate in enumerate(self.plates):
            if plate.pressed:
                di = self.plate_door_map.get(pi, 0)
                if di < len(self.doors):
                    self.doors[di].set_open(True)

        for di, door in enumerate(self.doors):
            door.update(dt)

            if len(player_rects) < 2 or self.stuck_triggered:
                continue

            door_x = door.original_positions[0].centerx
            p1_left = player_rects[0].centerx < door_x
            p2_left = player_rects[1].centerx < door_x
            players_separated = p1_left != p2_left

            # Track if players crossed through while door was open
            if door.is_open and players_separated:
                self._player_crossed[di] = True

            # If door closed and players are separated after having crossed
            if not door.is_open and self._player_crossed.get(di, False) and players_separated:
                self.stuck_triggered = True
                self._play_stuck()

    def collision_rects(self) -> list[pygame.Rect]:
        rects = []
        for door in self.doors:
            rects.extend(door.collision_rects())
        return rects

    def _play_stuck(self) -> None:
        from core.config.game_settings import settings

        path = resource_path("assets/audio/cues/stuck.wav")
        if not path.exists():
            return
        pygame.mixer.music.set_volume(settings.music_volume * 0.15)
        sound = pygame.mixer.Sound(path)
        sound.set_volume(settings.sfx_volume)
        sound.play()

    def draw(self, surface: pygame.Surface, camera_offset: tuple[int, int] = (0, 0)) -> None:
        for plate in self.plates:
            plate.draw(surface, camera_offset)
        for door in self.doors:
            door.draw(surface, camera_offset)


class CoopPressurePlate:
    """Pressure plate assigned to a specific player by color."""

    def __init__(self, rect: pygame.Rect, frames: list[pygame.Surface], player_index: int) -> None:
        self.rect = rect
        self.player_index = player_index
        self.pressed = False
        self.frame_index = 0.0
        self._glow_time = 0.0

        color = P1_OUTLINE_LOCAL if player_index == 0 else P2_OUTLINE_LOCAL
        self.glow_color = color
        self.frames = [add_outline(f, color) for f in frames]

    def update(self, dt: float, player_rects: list[pygame.Rect]) -> None:
        self._glow_time += dt
        if self.player_index < len(player_rects):
            self.pressed = self.rect.colliderect(player_rects[self.player_index])
        else:
            self.pressed = False

        if self.pressed:
            self.frame_index = min(
                self.frame_index + dt * DOOR_PLATE_ANIM_SPEED, len(self.frames) - 1
            )
        else:
            self.frame_index = max(self.frame_index - dt * DOOR_PLATE_ANIM_SPEED, 0.0)

    def draw(self, surface: pygame.Surface, camera_offset: tuple[int, int] = (0, 0)) -> None:
        ox, oy = camera_offset
        frame = self.frames[int(self.frame_index)]
        x, y = self.rect.x - ox - 1, self.rect.y - oy - 1  # offset for outline padding
        surface.blit(frame, (x, y))


class CoopDoorManager:
    """Door that requires both players on color-assigned plates. Stays open permanently."""

    def __init__(
        self,
        door_tiles: list[tuple[pygame.Rect, pygame.Surface]],
        plate_rects: list[pygame.Rect],
        scale: float,
    ) -> None:
        plate_frames = load_spritesheet(
            DOOR_PRESSURE_PATH, DOOR_PRESSURE_FRAME_SIZE, DOOR_PRESSURE_FRAME_COUNT, scale
        )

        self.plates: list[CoopPressurePlate] = []
        indices = list(range(len(plate_rects)))
        random.shuffle(indices)
        for i, rect in enumerate(plate_rects):
            self.plates.append(CoopPressurePlate(rect, plate_frames, i % 2))

        self.doors = [Door(tiles, behavior="permanent") for tiles in group_tiles_by_x(door_tiles)]
        self._opened = False
        self.plate_door_map = link_plates_to_doors(self.plates, self.doors)

    def update(self, dt: float, player_rects: list[pygame.Rect]) -> None:
        for plate in self.plates:
            plate.update(dt, player_rects)

        if not self._opened:
            all_pressed = all(plate.pressed for plate in self.plates) if self.plates else False
            if all_pressed:
                self._opened = True
                from core.audio import play_ui

                play_ui("success")

        for door in self.doors:
            door.set_open(self._opened)
            door.update(dt)

    def collision_rects(self) -> list[pygame.Rect]:
        rects = []
        for door in self.doors:
            rects.extend(door.collision_rects())
        return rects

    def draw(self, surface: pygame.Surface, camera_offset: tuple[int, int] = (0, 0)) -> None:
        for plate in self.plates:
            plate.draw(surface, camera_offset)
        for door in self.doors:
            door.draw(surface, camera_offset)
