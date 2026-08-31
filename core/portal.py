import math
from enum import Enum, auto

import pygame

from core.config.constants import BG_COLOR
from core.resource import resource_path

SPRITESHEET_PATH = resource_path("assets/portal/holy_shield.png")
FRAME_SIZE = 64
FRAME_COUNT = 11
PORTAL_FPS = 10
HOLD_FRAME = 6  # 0-indexed frame 7
ENTER_RADIUS = 30
VIGNETTE_DURATION = 1.5
POST_CLOSE_WAIT = 0.8
CUTAWAY_FADE_IN = 0.4
CUTAWAY_HOLD = 1.2
CUTAWAY_FADE_OUT = 0.4


class PortalState(Enum):
    INACTIVE = auto()
    CUTAWAY_IN = auto()
    OPENING = auto()
    CUTAWAY_OUT = auto()
    IDLE = auto()
    CLOSING = auto()
    DISSIPATING = auto()
    WAITING = auto()
    VIGNETTE = auto()
    DONE = auto()


def _load_portal_frames(scale: float) -> list[pygame.Surface]:
    sheet = pygame.image.load(SPRITESHEET_PATH).convert_alpha()
    frames: list[pygame.Surface] = []
    scaled = int(FRAME_SIZE * scale)
    for i in range(FRAME_COUNT):
        frame = sheet.subsurface(pygame.Rect(i * FRAME_SIZE, 0, FRAME_SIZE, FRAME_SIZE))
        frames.append(pygame.transform.scale(frame, (scaled, scaled)))
    empty = pygame.Surface((scaled, scaled), pygame.SRCALPHA)
    frames.append(empty)
    return frames


class Portal:
    def __init__(self, screen_rect: pygame.Rect, map_scale: float) -> None:
        self.frames = _load_portal_frames(map_scale)
        self.frame_size = self.frames[0].get_width()

        self.x = screen_rect.centerx
        self.y = screen_rect.centery
        self.rect = pygame.Rect(
            self.x - self.frame_size // 2,
            self.y - self.frame_size // 2,
            self.frame_size,
            self.frame_size,
        )

        self.state = PortalState.INACTIVE
        self.frame_index = 0.0
        self.timer = 0.0

        self.p1_entered = False
        self.p2_entered = False

        self.cutaway_alpha = 0.0
        self.vignette_progress = 0.0

    def activate(self) -> None:
        if self.state == PortalState.INACTIVE:
            self.state = PortalState.CUTAWAY_IN
            self.timer = 0.0
            self.cutaway_alpha = 0.0
            self.frame_index = 0.0

    def _player_in_portal(self, player_rect: pygame.Rect) -> bool:
        dx = abs(player_rect.centerx - self.x)
        dy = abs(player_rect.centery - self.y)
        return dx < ENTER_RADIUS and dy < ENTER_RADIUS

    @property
    def in_cutaway(self) -> bool:
        return self.state in (PortalState.CUTAWAY_IN, PortalState.OPENING, PortalState.CUTAWAY_OUT)

    def update(self, dt: float, p1_rect: pygame.Rect, p2_rect: pygame.Rect) -> None:
        if self.state == PortalState.INACTIVE:
            return

        if self.state == PortalState.CUTAWAY_IN:
            self.timer += dt
            self.cutaway_alpha = min(self.timer / CUTAWAY_FADE_IN, 1.0)
            if self.timer >= CUTAWAY_FADE_IN:
                self.state = PortalState.OPENING
                self.timer = 0.0

        elif self.state == PortalState.OPENING:
            self.frame_index += dt * PORTAL_FPS
            if self.frame_index >= HOLD_FRAME:
                self.frame_index = HOLD_FRAME
                self.timer = 0.0
                self.state = PortalState.CUTAWAY_OUT

        elif self.state == PortalState.CUTAWAY_OUT:
            self.timer += dt
            self.cutaway_alpha = max(1.0 - self.timer / CUTAWAY_FADE_OUT, 0.0)
            if self.timer >= CUTAWAY_FADE_OUT:
                self.cutaway_alpha = 0.0
                self.state = PortalState.IDLE

        elif self.state == PortalState.IDLE:
            if not self.p1_entered and self._player_in_portal(p1_rect):
                self.p1_entered = True
            if not self.p2_entered and self._player_in_portal(p2_rect):
                self.p2_entered = True

            if self.p1_entered and self.p2_entered:
                self.state = PortalState.CLOSING
                self.frame_index = HOLD_FRAME

        elif self.state == PortalState.CLOSING:
            self.frame_index -= dt * PORTAL_FPS
            if self.frame_index <= 0:
                self.frame_index = 0
                self.state = PortalState.DISSIPATING

        elif self.state == PortalState.DISSIPATING:
            self.frame_index += dt * PORTAL_FPS
            total = FRAME_COUNT  # 11 + 1 empty = index 11
            if self.frame_index >= total:
                self.state = PortalState.WAITING
                self.timer = 0.0

        elif self.state == PortalState.WAITING:
            self.timer += dt
            if self.timer >= POST_CLOSE_WAIT:
                self.state = PortalState.VIGNETTE
                self.vignette_progress = 0.0

        elif self.state == PortalState.VIGNETTE:
            self.vignette_progress += dt / VIGNETTE_DURATION
            if self.vignette_progress >= 1.0:
                self.vignette_progress = 1.0
                self.state = PortalState.DONE

    def should_hide_player(self, player_index: int) -> bool:
        if player_index == 0:
            return self.p1_entered
        return player_index == 1 and self.p2_entered

    def draw(self, surface: pygame.Surface, camera_offset: tuple[int, int] = (0, 0)) -> None:
        if self.state == PortalState.INACTIVE or self.in_cutaway:
            return

        idx = min(int(self.frame_index), len(self.frames) - 1)
        ox, oy = camera_offset
        frame = self.frames[idx]
        draw_x = self.x - self.frame_size // 2 - ox
        draw_y = self.y - self.frame_size // 2 - oy
        surface.blit(frame, (draw_x, draw_y))

    def draw_cutaway(self, surface: pygame.Surface) -> None:
        if not self.in_cutaway or self.cutaway_alpha <= 0.01:
            return

        sw, sh = surface.get_size()
        idx = min(int(self.frame_index), len(self.frames) - 1)
        frame = self.frames[idx]

        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((*BG_COLOR, int(200 * self.cutaway_alpha)))

        big_size = min(sw, sh) // 2
        big_frame = pygame.transform.scale(frame, (big_size, big_size))
        fx = (sw - big_size) // 2
        fy = (sh - big_size) // 2
        overlay.blit(big_frame, (fx, fy))

        overlay.set_alpha(int(255 * self.cutaway_alpha))
        surface.blit(overlay, (0, 0))

    def draw_vignette(
        self, surface: pygame.Surface, camera_offset: tuple[int, int] = (0, 0)
    ) -> None:
        if self.state != PortalState.VIGNETTE and self.state != PortalState.DONE:
            return

        sw, sh = surface.get_size()
        ox, oy = camera_offset
        center_x = self.x - ox
        center_y = self.y - oy

        max_radius = int(math.hypot(sw, sh))
        radius = int(max_radius * (1.0 - self.vignette_progress))

        vignette = pygame.Surface((sw, sh), pygame.SRCALPHA)
        vignette.fill((*BG_COLOR, 255))
        if radius > 0:
            pygame.draw.circle(vignette, (0, 0, 0, 0), (center_x, center_y), radius)
        surface.blit(vignette, (0, 0))

    @property
    def is_done(self) -> bool:
        return self.state == PortalState.DONE

    @property
    def is_active(self) -> bool:
        return self.state not in (PortalState.INACTIVE, PortalState.DONE)
