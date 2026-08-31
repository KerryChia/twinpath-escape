import pygame

from core.config.constants import (
    BREAKABLE_SHAKE_MULTIPLIER,
    BREAKABLE_TIMER,
    INTERACT_RADIUS,
    PRESSURE_FPS,
    SIGN_DIALOG_BORDER,
    SIGN_DIALOG_FADE_SPEED,
    SIGN_DIALOG_FILL,
    SIGN_DIALOG_FONT_SIZE,
    SIGN_DIALOG_MIN_WIDTH,
    SIGN_DIALOG_PADDING,
    SIGN_DIALOG_STYLE,
    SIGN_DIALOG_Y_RATIO,
)
from core.fonts import get_font
from core.gui import Label, Panel
from core.resource import resource_path
from core.text import wrap_text
from core.utils import load_spritesheet

PRESSURE_PLATE_PATH = resource_path("assets/adve/pressure_plate.png")
PRESSURE_FRAME_SIZE = (8, 8)
PRESSURE_FRAME_COUNT = 3


class Sign:
    def __init__(self, rect: pygame.Rect, text: str) -> None:
        self.rect = rect
        self.text = text

    def in_range(self, player_rect: pygame.Rect) -> bool:
        cx, cy = self.rect.center
        px, py = player_rect.center
        dx = abs(cx - px)
        dy = abs(cy - py)
        return dx < INTERACT_RADIUS and dy < INTERACT_RADIUS


class SignManager:
    def __init__(self, sign_rects: list[pygame.Rect], texts: dict[int, str]) -> None:
        self._texts = texts
        self.signs: list[Sign] = []
        for i, rect in enumerate(sign_rects):
            text = texts.get(i, "...")
            self.signs.append(Sign(rect, text))

    def get_active_text(self, *player_rects: pygame.Rect) -> str | None:
        for sign in self.signs:
            for pr in player_rects:
                if sign.in_range(pr):
                    return sign.text
        return None


class SignDialog:
    WAVE_SPEED = 4.0
    WAVE_AMPLITUDE = 3.0
    WAVE_SPACING = 0.3

    def __init__(self) -> None:
        self.current_text = ""
        self.alpha = 0.0
        self.visible = False
        self.time = 0.0

        self.panel = Panel(
            400,
            80,
            style=SIGN_DIALOG_STYLE,
            fill_color=SIGN_DIALOG_FILL,
            border_color=SIGN_DIALOG_BORDER,
        )
        self.label = Label("", size=SIGN_DIALOG_FONT_SIZE)
        self._has_wavy = False
        self._font: pygame.font.Font | None = None

    MAX_WIDTH = 500

    def show(self, text: str) -> None:
        if text != self.current_text:
            self.current_text = text
            self._has_wavy = "*" in text

            clean = text.replace("*", "")
            font = self._get_font()

            # Word-wrap into lines
            self._lines = self._wrap_text(clean, font, self.MAX_WIDTH)
            self.label.set_text(clean)

            line_w = max(font.size(line)[0] for line in self._lines) if self._lines else 0
            panel_w = max(line_w + SIGN_DIALOG_PADDING, SIGN_DIALOG_MIN_WIDTH)
            panel_h = 50 + len(self._lines) * (font.get_height() + 4)
            self.panel = Panel(
                panel_w,
                panel_h,
                style=SIGN_DIALOG_STYLE,
                fill_color=SIGN_DIALOG_FILL,
                border_color=SIGN_DIALOG_BORDER,
            )
            self._panel_h = panel_h
        self.visible = True

    @staticmethod
    def _wrap_text(text: str, font: pygame.font.Font, max_w: int) -> list[str]:
        return wrap_text(text, font, max_w)

    def hide(self) -> None:
        self.visible = False

    def update(self, dt: float) -> None:
        self.time += dt
        target = 1.0 if self.visible else 0.0
        if self.alpha < target:
            self.alpha = min(self.alpha + SIGN_DIALOG_FADE_SPEED * dt, 1.0)
        elif self.alpha > target:
            self.alpha = max(self.alpha - SIGN_DIALOG_FADE_SPEED * dt, 0.0)

    def draw(self, surface: pygame.Surface) -> None:
        sw, sh = surface.get_size()
        self.draw_at(surface, sw // 2, int(sh * SIGN_DIALOG_Y_RATIO))

    def _get_font(self) -> pygame.font.Font:
        if self._font is None:
            self._font = get_font(SIGN_DIALOG_FONT_SIZE)
        return self._font

    def _draw_wavy_text(self, surface: pygame.Surface, cx: int, base_y: int) -> None:
        """Render wrapped text with *wavy* sections animated per-character."""
        import math

        font = self._get_font()
        text = self.current_text
        line_h = font.get_height() + 4
        num_lines = len(self._lines) if hasattr(self, "_lines") else 1
        start_y = base_y - (num_lines * line_h) // 2

        segments: list[tuple[str, bool]] = []
        parts = text.split("*")
        for idx, part in enumerate(parts):
            if part:
                segments.append((part, idx % 2 == 1))

        chars: list[tuple[str, bool]] = []
        for seg_text, is_wavy in segments:
            for c in seg_text:
                chars.append((c, is_wavy))

        global_idx = 0
        for line_num, line in enumerate(self._lines):
            line_w = font.size(line)[0]
            lx = cx - line_w // 2
            ly = start_y + line_num * line_h

            for _ in line:
                if global_idx >= len(chars):
                    break
                char, is_wavy = chars[global_idx]

                char_surf = font.render(char, True, (255, 255, 255))

                if is_wavy:
                    offset_y = (
                        math.sin(self.time * self.WAVE_SPEED + global_idx * self.WAVE_SPACING)
                        * self.WAVE_AMPLITUDE
                    )
                else:
                    offset_y = 0

                surface.blit(char_surf, (lx, ly + int(offset_y)))
                lx += char_surf.get_width()
                global_idx += 1

    def draw_at(self, surface: pygame.Surface, cx: int, y: int) -> None:
        if self.alpha <= 0.01:
            return

        sw, sh = surface.get_size()
        temp = pygame.Surface((sw, sh), pygame.SRCALPHA)

        ph = getattr(self, "_panel_h", 80)
        pw = self.panel.image.get_width()
        self.panel.draw(temp, cx - pw // 2, y - ph // 2)

        if self._has_wavy:
            self._draw_wavy_text(temp, cx, y)
        elif hasattr(self, "_lines") and len(self._lines) > 1:
            font = self._get_font()
            line_h = font.get_height() + 4
            start_y = y - (len(self._lines) * line_h) // 2
            for i, line in enumerate(self._lines):
                line_surf = font.render(line, True, (255, 255, 255))
                line_rect = line_surf.get_rect(center=(cx, start_y + i * line_h + line_h // 2))
                temp.blit(line_surf, line_rect)
        else:
            self.label.draw(temp, cx, y)

        temp.set_alpha(int(255 * self.alpha))
        surface.blit(temp, (0, 0))


def _load_pressure_frames(scale: float) -> list[pygame.Surface]:
    return load_spritesheet(PRESSURE_PLATE_PATH, PRESSURE_FRAME_SIZE, PRESSURE_FRAME_COUNT, scale)


class PressurePlate:
    def __init__(self, rect: pygame.Rect, frames: list[pygame.Surface]) -> None:
        self.rect = rect
        self.frames = frames
        self.pressed = False
        self.frame_index = 0.0
        self.activated = False

    def update(self, dt: float, *player_rects: pygame.Rect) -> None:
        was_pressed = self.pressed
        self.pressed = any(self.rect.colliderect(pr) for pr in player_rects)

        if self.pressed and not was_pressed:
            self.frame_index = 0.0
            self.activated = True

        if self.pressed:
            self.frame_index = min(
                self.frame_index + dt * PRESSURE_FPS,
                PRESSURE_FRAME_COUNT - 1,
            )
        elif self.frame_index > 0:
            self.frame_index = max(self.frame_index - dt * PRESSURE_FPS, 0.0)
            if self.frame_index == 0.0:
                self.activated = False

    def draw(self, surface: pygame.Surface, camera_offset: tuple[int, int] = (0, 0)) -> None:
        ox, oy = camera_offset
        frame = self.frames[int(self.frame_index)]
        pos = (self.rect.x - ox, self.rect.y - oy)
        surface.blit(frame, pos)


class BreakablePlatform:
    def __init__(self, rect: pygame.Rect, image: pygame.Surface) -> None:
        self.rect = rect
        self.image = image
        self.timer = 0.0
        self.triggered = False
        self.broken = False

    @property
    def shake_amount(self) -> float:
        if self.triggered and not self.broken:
            return min(self.timer / BREAKABLE_TIMER, 1.0) * BREAKABLE_SHAKE_MULTIPLIER
        return 0.0

    def update(self, dt: float, *player_rects: pygame.Rect) -> None:
        if self.broken:
            return

        touching = any(
            pr.colliderect(self.rect)
            or (
                pr.bottom >= self.rect.top
                and pr.bottom <= self.rect.top + 4
                and pr.right > self.rect.left
                and pr.left < self.rect.right
            )
            for pr in player_rects
        )

        if touching and not self.triggered:
            self.triggered = True
            self.timer = 0.0

        if self.triggered:
            self.timer += dt
            if self.timer >= BREAKABLE_TIMER:
                self.broken = True

    def draw(self, surface: pygame.Surface, camera_offset: tuple[int, int] = (0, 0)) -> None:
        if self.broken:
            return
        ox, oy = camera_offset
        x = self.rect.x - ox
        y = self.rect.y - oy
        if self.shake_amount > 0:
            import random

            x += random.randint(int(-self.shake_amount), int(self.shake_amount))
            y += random.randint(int(-self.shake_amount), int(self.shake_amount))
        surface.blit(self.image, (x, y))


class BreakableManager:
    def __init__(self, tiles: list[tuple[pygame.Rect, pygame.Surface]]) -> None:
        self.platforms = [BreakablePlatform(rect, img) for rect, img in tiles]

    def active_rects(self) -> list[pygame.Rect]:
        return [p.rect for p in self.platforms if not p.broken]

    def update(self, dt: float, *player_rects: pygame.Rect) -> None:
        for p in self.platforms:
            p.update(dt, *player_rects)

    def draw(self, surface: pygame.Surface, camera_offset: tuple[int, int] = (0, 0)) -> None:
        for p in self.platforms:
            p.draw(surface, camera_offset)


class PressurePlateManager:
    def __init__(self, rects: list[pygame.Rect], scale: float) -> None:
        self.frames = _load_pressure_frames(scale)
        self.plates = [PressurePlate(r, self.frames) for r in rects]

    def update(self, dt: float, *player_rects: pygame.Rect) -> None:
        for plate in self.plates:
            plate.update(dt, *player_rects)

    def any_activated(self) -> bool:
        return any(p.activated for p in self.plates)

    def draw(self, surface: pygame.Surface, camera_offset: tuple[int, int] = (0, 0)) -> None:
        for plate in self.plates:
            plate.draw(surface, camera_offset)
