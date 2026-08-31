import math
import random

import pygame

from core.config.constants import SPLIT_MERGE_THRESHOLD, SPLIT_THRESHOLD
from core.config.game_settings import settings
from core.utils import lerp


class Camera:
    def __init__(self) -> None:
        self.pos = pygame.math.Vector2(0, 0)
        self.target = pygame.math.Vector2(0, 0)
        self.smoothing = 8.0

        self._shake_intensity = 0.0
        self._shake_duration = 0.0
        self._shake_timer = 0.0
        self._shake_offset = pygame.math.Vector2(0, 0)

    @property
    def offset(self) -> tuple[int, int]:
        return (
            int(self.pos.x + self._shake_offset.x),
            int(self.pos.y + self._shake_offset.y),
        )

    def follow_point(self, cx: float, cy: float, view_w: int, view_h: int) -> None:
        self.target.x = cx - view_w / 2
        self.target.y = cy - view_h / 2

    def follow_rect(self, rect: pygame.Rect, view_w: int, view_h: int) -> None:
        self.follow_point(rect.centerx, rect.centery, view_w, view_h)

    def shake(self, intensity: float = 6.0, duration: float = 0.15) -> None:
        self._shake_intensity = intensity
        self._shake_duration = duration
        self._shake_timer = duration

    def clamp(self, map_rect: pygame.Rect, view_w: int, view_h: int) -> None:
        self.pos.x = max(map_rect.left, min(self.pos.x, map_rect.right - view_w))
        self.pos.y = max(map_rect.top, min(self.pos.y, map_rect.bottom - view_h))

    def update(self, dt: float) -> None:
        self.pos.x += (self.target.x - self.pos.x) * self.smoothing * dt
        self.pos.y += (self.target.y - self.pos.y) * self.smoothing * dt

        if self._shake_timer > 0:
            self._shake_timer -= dt
            t = self._shake_timer / self._shake_duration
            magnitude = self._shake_intensity * t
            self._shake_offset.x = random.uniform(-magnitude, magnitude)
            self._shake_offset.y = random.uniform(-magnitude, magnitude)
        else:
            self._shake_offset.x = 0
            self._shake_offset.y = 0


class SplitScreen:
    TRANSITION_SPEED = 4.0
    DIVIDER_WIDTH = 3
    DIVIDER_COLOR = (180, 185, 195)

    def __init__(self) -> None:
        self.cam1 = Camera()
        self.cam2 = Camera()
        self.shared_cam = Camera()

        self.split_amount = 0.0
        self.split_angle = 0.0
        self._target_split = 0.0

        # Cached surfaces — allocated once, reused every frame
        self._surf1: pygame.Surface | None = None
        self._surf2: pygame.Surface | None = None
        self._mask: pygame.Surface | None = None
        self._composite: pygame.Surface | None = None
        self._cached_size: tuple[int, int] = (0, 0)

    def update(
        self,
        dt: float,
        rect1: pygame.Rect,
        rect2: pygame.Rect,
    ) -> None:
        sw, sh = settings.screen_size

        dx = rect2.centerx - rect1.centerx
        dy = rect2.centery - rect1.centery
        distance = math.hypot(dx, dy)

        if distance > SPLIT_THRESHOLD:
            self._target_split = 1.0
        elif distance < SPLIT_MERGE_THRESHOLD:
            self._target_split = 0.0

        self.split_amount = lerp(
            self.split_amount,
            self._target_split,
            self.TRANSITION_SPEED * dt,
        )
        if self.split_amount < 0.01:
            self.split_amount = 0.0
        if self.split_amount > 0.99:
            self.split_amount = 1.0

        if distance > 1.0:
            target_angle = math.atan2(dy, dx) + math.pi / 2
            diff = target_angle - self.split_angle
            while diff > math.pi:
                diff -= 2 * math.pi
            while diff < -math.pi:
                diff += 2 * math.pi
            self.split_angle += diff * min(self.TRANSITION_SPEED * dt, 1.0)

        mid_x = (rect1.centerx + rect2.centerx) / 2
        mid_y = (rect1.centery + rect2.centery) / 2

        self.shared_cam.follow_point(mid_x, mid_y, sw, sh)
        self.shared_cam.update(dt)

        if distance > 1.0:
            dir_x = dx / distance
            dir_y = dy / distance
        else:
            dir_x, dir_y = 0.0, 0.0

        shift = (sw / 4) * self.split_amount
        self.cam1.follow_point(
            rect1.centerx + dir_x * shift,
            rect1.centery + dir_y * shift,
            sw,
            sh,
        )
        self.cam2.follow_point(
            rect2.centerx - dir_x * shift,
            rect2.centery - dir_y * shift,
            sw,
            sh,
        )
        self.cam1.update(dt)
        self.cam2.update(dt)

    def _get_surfaces(
        self, sw: int, sh: int
    ) -> tuple[pygame.Surface, pygame.Surface, pygame.Surface, pygame.Surface]:
        if self._cached_size != (sw, sh):
            self._surf1 = pygame.Surface((sw, sh))
            self._surf2 = pygame.Surface((sw, sh))
            self._mask = pygame.Surface((sw, sh), pygame.SRCALPHA)
            self._composite = pygame.Surface((sw, sh), pygame.SRCALPHA)
            self._cached_size = (sw, sh)
        return self._surf1, self._surf2, self._mask, self._composite

    def shake_all(self, intensity: float = 4.0, duration: float = 0.12) -> None:
        self.shared_cam.shake(intensity, duration)
        self.cam1.shake(intensity, duration)
        self.cam2.shake(intensity, duration)

    def _blended_offset(self, cam: Camera) -> tuple[int, int]:
        t = self.split_amount
        ox = lerp(self.shared_cam.pos.x, cam.pos.x, t)
        oy = lerp(self.shared_cam.pos.y, cam.pos.y, t)

        sx = self.shared_cam._shake_offset.x
        sy = self.shared_cam._shake_offset.y
        cx = cam._shake_offset.x
        cy = cam._shake_offset.y

        return (int(ox + lerp(sx, cx, t)), int(oy + lerp(sy, cy, t)))

    def _build_half_polygon(
        self,
        sw: int,
        sh: int,
        side: float,
    ) -> list[tuple[float, float]]:
        cx, cy = sw / 2, sh / 2
        extent = math.hypot(sw, sh) * 2

        sl_dx = math.cos(self.split_angle)
        sl_dy = math.sin(self.split_angle)

        norm_x = -sl_dy * side
        norm_y = sl_dx * side

        p1 = (cx - sl_dx * extent, cy - sl_dy * extent)
        p2 = (cx + sl_dx * extent, cy + sl_dy * extent)

        p3 = (p2[0] + norm_x * extent, p2[1] + norm_y * extent)
        p4 = (p1[0] + norm_x * extent, p1[1] + norm_y * extent)

        return [p1, p2, p3, p4]

    def _determine_p1_side(self, rect1: pygame.Rect, rect2: pygame.Rect) -> float:
        mid_x = (rect1.centerx + rect2.centerx) / 2
        mid_y = (rect1.centery + rect2.centery) / 2

        sl_dx = math.cos(self.split_angle)
        sl_dy = math.sin(self.split_angle)

        p1_rel_x = rect1.centerx - mid_x
        p1_rel_y = rect1.centery - mid_y

        cross = sl_dx * p1_rel_y - sl_dy * p1_rel_x
        return 1.0 if cross >= 0 else -1.0

    def render(
        self,
        screen: pygame.Surface,
        draw_fn: callable,
        rect1: pygame.Rect,
        rect2: pygame.Rect,
        hud_fn: object = None,
    ) -> None:
        sw, sh = settings.screen_size

        if self.split_amount == 0.0:
            draw_fn(screen, self.shared_cam.offset, (sw, sh))
            center = (sw // 2, sh // 2)
            if hud_fn:
                hud_fn(screen, 0, center)
                hud_fn(screen, 1, center)
            return

        sl_dx = math.cos(self.split_angle)
        sl_dy = math.sin(self.split_angle)
        p1_side = self._determine_p1_side(rect1, rect2)
        norm_x = -sl_dy * p1_side
        norm_y = sl_dx * p1_side
        shift = sw // 4
        p1_center = (int(sw / 2 + norm_x * shift), int(sh / 2 + norm_y * shift))
        p2_center = (int(sw / 2 - norm_x * shift), int(sh / 2 - norm_y * shift))

        surf1, surf2, mask, composite = self._get_surfaces(sw, sh)

        off1 = self._blended_offset(self.cam1)
        off2 = self._blended_offset(self.cam2)

        draw_fn(surf1, off1, (sw, sh))
        draw_fn(surf2, off2, (sw, sh))

        if hud_fn:
            hud_fn(surf1, 0, p1_center)
            hud_fn(surf2, 1, p2_center)

        p1_poly = self._build_half_polygon(sw, sh, p1_side)
        screen.blit(surf2, (0, 0))

        mask.fill((0, 0, 0, 0))
        pygame.draw.polygon(mask, (255, 255, 255, 255), p1_poly)

        composite.fill((0, 0, 0, 0))
        composite.blit(surf1, (0, 0))
        composite.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        screen.blit(composite, (0, 0))

        cx, cy = sw / 2, sh / 2
        diag = math.hypot(sw, sh)
        lp1 = (cx - sl_dx * diag, cy - sl_dy * diag)
        lp2 = (cx + sl_dx * diag, cy + sl_dy * diag)
        width = max(1, int(self.DIVIDER_WIDTH * self.split_amount))
        pygame.draw.line(screen, self.DIVIDER_COLOR, lp1, lp2, width)
