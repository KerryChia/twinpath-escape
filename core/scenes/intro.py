"""Intro narration cutscene with cinematic text animations synced to voice."""

import math

import pygame

from core.config.constants import BG_COLOR
from core.fonts import get_font
from core.gui import Divider, Label
from core.localization import t
from core.text import wrap_text
from core.resource import resource_path
from core.scene import Scene, SceneManager

VOICE_PATH = resource_path("assets/audio/cues/intro.wav")

# Exact subtitle timings — offset by PRE_DELAY so audio doesn't start immediately
PRE_DELAY = 2.5
POST_DELAY = 3.0

NARRATION = [
    (0.176, 2.994, "intro.01", False, ("intro.name.fig", "intro.name.moss")),
    (2.994, 4.703, "intro.02", True, ()),
    (4.704, 6.879, "intro.03", False, ()),
    (6.880, 8.798, "intro.04", False, ()),
    (8.798, 10.821, "intro.05", False, ()),
    (12.475, 15.284, "intro.06", False, ()),
    (15.285, 16.729, "intro.07", False, ()),
    (16.730, 19.001, "intro.08", False, ()),
    (19.001, 21.442, "intro.09", True, ()),
    (21.442, 24.492, "intro.10", False, ()),
    (24.493, 27.214, "intro.11", False, ()),
    (28.853, 29.672, "intro.12", False, ()),
    (31.182, 33.310, "intro.13", False, ()),
    (33.310, 35.679, "intro.14", False, ("intro.name.fig", "intro.name.moss")),
    (35.679, 37.631, "intro.15", False, ()),
    (37.631, 39.583, "intro.16", False, ()),
    (41.928, 42.313, "intro.17", True, ()),
    (44.032, 44.746, "intro.18", False, ()),
    (44.747, 46.144, "intro.19", False, ()),
    (46.144, 48.465, "intro.20", False, ()),
    (48.465, 50.810, "intro.21", False, ()),
    (52.545, 54.200, "intro.22", True, ()),
]

TYPEWRITER_SPEED = 40

NAME_COLORS = [(255, 100, 100), (100, 150, 255)]


class Intro(Scene):
    def __init__(
        self,
        manager: SceneManager,
        p1_name: str | None = None,
        p2_name: str | None = None,
        level_id: str = "tutorial_001",
    ) -> None:
        super().__init__(manager)
        self.p1_name = p1_name or t("common.green")
        self.p2_name = p2_name or t("common.orange")
        self.level_id = level_id

        self.font = get_font(24)
        self.emphasis_font = get_font(32)
        self.prev_font = get_font(14)
        self.timer = 0.0
        self.audio_timer = 0.0
        self.current_idx = -1
        self.prev_idx = -1
        self.finished = False
        self._started_audio = False
        self._fade_out = 0.0

        self._skip_label = Label(t("intro.skip"), size=12, color=(60, 55, 50))
        self._div_l = Divider(scale=0.5, style=3, fade=True, color=(60, 55, 50))
        self._div_r = Divider(scale=0.5, style=3, fade=True, color=(60, 55, 50))
        self._div_r.image = pygame.transform.flip(self._div_r.image, True, False)

        self._vignette: pygame.Surface | None = None

    def _render_colored_text(
        self,
        text: str,
        font: pygame.font.Font,
        default_color: tuple[int, int, int],
        colored_terms: tuple[str, ...] = (),
        max_width: int = 900,
    ) -> pygame.Surface:
        lines = wrap_text(text, font, max_width)
        rendered_lines = []
        for line in lines:
            pieces = []
            cursor = 0
            while cursor < len(line):
                match = next((term for term in colored_terms if line.startswith(term, cursor)), None)
                if match:
                    color = NAME_COLORS[colored_terms.index(match) % len(NAME_COLORS)]
                    pieces.append(font.render(match, True, color))
                    cursor += len(match)
                else:
                    pieces.append(font.render(line[cursor], True, default_color))
                    cursor += 1
            width = sum(piece.get_width() for piece in pieces)
            row = pygame.Surface((max(1, width), font.get_height()), pygame.SRCALPHA)
            x = 0
            for piece in pieces:
                row.blit(piece, (x, 0))
                x += piece.get_width()
            rendered_lines.append(row)
        width = max(row.get_width() for row in rendered_lines)
        height = len(rendered_lines) * (font.get_height() + 4) - 4
        result = pygame.Surface((width, height), pygame.SRCALPHA)
        for i, row in enumerate(rendered_lines):
            result.blit(row, ((width - row.get_width()) // 2, i * (font.get_height() + 4)))
        return result

    def _get_vignette(self, sw: int, sh: int) -> pygame.Surface:
        if self._vignette is None or self._vignette.get_size() != (sw, sh):
            self._vignette = pygame.Surface((sw, sh), pygame.SRCALPHA)
            for radius_pct in range(100, 0, -2):
                alpha = int(60 * (1.0 - radius_pct / 100.0))
                r = int(max(sw, sh) * 0.7 * radius_pct / 100)
                pygame.draw.circle(self._vignette, (0, 0, 0, alpha), (sw // 2, sh // 2), r)
        return self._vignette

    def update(self, dt: float) -> None:
        if self.finished:
            return

        self.timer += dt

        if self.timer >= PRE_DELAY and not self._started_audio:
            pygame.mixer.music.load(VOICE_PATH)
            pygame.mixer.music.play()
            self._started_audio = True

        if self._started_audio:
            self.audio_timer = self.timer - PRE_DELAY

        old_idx = self.current_idx
        self.current_idx = -1
        for i, (start, end, _key, _emphasis, _terms) in enumerate(NARRATION):
            if start <= self.audio_timer <= end + 0.3:
                self.current_idx = i

        if self.current_idx != old_idx and old_idx >= 0:
            self.prev_idx = old_idx

        if self._started_audio and not pygame.mixer.music.get_busy() and self.audio_timer > 3.0:
            self._fade_out += dt
            if self._fade_out >= POST_DELAY:
                self._finish()

    def _finish(self) -> None:
        self.finished = True
        pygame.mixer.music.stop()

        from core.scenes.gameplay import Gameplay

        self.manager.replace(Gameplay(self.manager, self.level_id, self.p1_name, self.p2_name))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN or (
            event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
        ):
            self._finish()

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BG_COLOR)
        sw, sh = surface.get_size()
        cx = sw // 2
        cy = sh // 2

        screen_alpha = min(self.timer / 1.5, 1.0)

        surface.blit(self._get_vignette(sw, sh), (0, 0))

        if self._fade_out > 0:
            fade_alpha = min(self._fade_out / POST_DELAY, 1.0)
            fade_surf = pygame.Surface((sw, sh))
            fade_surf.fill(BG_COLOR)
            fade_surf.set_alpha(int(255 * fade_alpha))
            surface.blit(fade_surf, (0, 0))
            return

        if self.current_idx < 0:
            if self.timer < PRE_DELAY:
                dots = "." * (1 + int(self.timer * 2) % 3)
                dot_surf = self.prev_font.render(dots, True, (60, 55, 50))
                dot_rect = dot_surf.get_rect(center=(cx, cy))
                dot_surf.set_alpha(int(150 * screen_alpha))
                surface.blit(dot_surf, dot_rect)

            self._skip_label.draw(surface, cx, sh - 30)
            return

        start, _end, key, is_emphasis, term_keys = NARRATION[self.current_idx]
        colored_terms = tuple(t(term_key) for term_key in term_keys)
        text = t(key)
        elapsed = self.audio_timer - start
        font = self.emphasis_font if is_emphasis else self.font

        chars_to_show = int(min(elapsed * TYPEWRITER_SPEED, len(text)))
        visible = text[:chars_to_show]

        if visible:
            line_age = elapsed
            slide_offset = max(0, 10 - line_age * 40)
            text_alpha = min(line_age * 4, 1.0)

            if is_emphasis:
                scale = 1.0 + 0.02 * math.sin(self.timer * 3)
                rendered = self._render_colored_text(visible, font, (255, 250, 240), colored_terms, sw - 120)
                if scale != 1.0:
                    new_w = int(rendered.get_width() * scale)
                    new_h = int(rendered.get_height() * scale)
                    rendered = pygame.transform.scale(rendered, (new_w, new_h))
            else:
                rendered = self._render_colored_text(visible, font, (200, 195, 185), colored_terms, sw - 120)

            rendered.set_alpha(int(255 * text_alpha * screen_alpha))
            rect = rendered.get_rect(center=(cx, cy + int(slide_offset)))
            surface.blit(rendered, rect)

            if is_emphasis and chars_to_show >= len(text):
                div_alpha = min((elapsed - len(text) / TYPEWRITER_SPEED) * 3, 1.0)
                if div_alpha > 0:
                    gap = rendered.get_width() // 2 + 80
                    div_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
                    self._div_l.draw(div_surf, cx - gap, cy + int(slide_offset))
                    self._div_r.draw(div_surf, cx + gap, cy + int(slide_offset))
                    div_surf.set_alpha(int(180 * div_alpha * screen_alpha))
                    surface.blit(div_surf, (0, 0))

        if self.prev_idx >= 0:
            prev_key = NARRATION[self.prev_idx][2]
            prev_text = t(prev_key)
            prev_age = self.audio_timer - NARRATION[self.prev_idx][1]
            prev_alpha = max(0, 1.0 - prev_age * 1.5)

            if prev_alpha > 0.05:
                prev_slide = prev_age * 15
                prev_terms = tuple(t(term_key) for term_key in NARRATION[self.prev_idx][4])
                prev_rendered = self._render_colored_text(prev_text, self.prev_font, (80, 75, 65), prev_terms, sw - 120)
                prev_rendered.set_alpha(int(200 * prev_alpha * screen_alpha))
                prev_rect = prev_rendered.get_rect(center=(cx, cy - 45 - int(prev_slide)))
                surface.blit(prev_rendered, prev_rect)

        skip_alpha = int(100 * screen_alpha)
        skip_surf = self._skip_label.image.copy()
        skip_surf.set_alpha(skip_alpha)
        sr = skip_surf.get_rect(center=(cx, sh - 30))
        surface.blit(skip_surf, sr)
