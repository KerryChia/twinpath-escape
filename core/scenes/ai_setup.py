"""Pre-game setup for local human + AI cooperation (P1 keyboard, P2 AI)."""

import pygame

from core.config.constants import BG_COLOR
from core.config.game_mode import GameMode
from core.config.game_settings import settings
from core.gui import Button, Label, Toggle
from core.localization import t
from core.scene import Scene, SceneManager


class AISetup(Scene):
    def __init__(self, manager: SceneManager) -> None:
        super().__init__(manager)
        self.debug = True
        self.title = Label(t("ai.setup.title"), 44)
        self.strategy_label = Label(t("ai.setup.algorithm"), 23)
        self.role_label = Label(t("ai.setup.role"), 23)
        self.debug_label = Label(t("ai.setup.debug"), 23)
        self.debug_toggle = Toggle(active=True)
        self.debug_toggle.on_change = self._set_debug
        self.start_button = Button(t("ai.setup.start"), 300, 64, font_size=28, variant="primary")
        self.start_button.callback = self._start
        self.back_button = Button(t("common.back"), 220, 54, font_size=22)
        self.back_button.callback = manager.pop
        self.buttons = [self.start_button, self.back_button]
        self._layout(*settings.screen_size)

    def _set_debug(self, active: bool) -> None:
        self.debug = active

    def _start(self) -> None:
        from core.scenes.gameplay import Gameplay

        self.manager.replace(
            Gameplay(self.manager, mode=GameMode.HUMAN_AI, debug_ai=self.debug)
        )

    def _layout(self, width: int, height: int) -> None:
        cx = width // 2
        top = max(80, int(height * 0.14))          # title (draw centers itself on this y)
        row_y = top + 250                          # debug label + toggle row
        self.debug_toggle.set_position(cx + 150, row_y)
        self.start_button.set_position(cx, row_y + 90)
        self.back_button.set_position(cx, min(height - 45, row_y + 165))

    def on_resize(self, width: int, height: int) -> None:
        self._layout(width, height)

    def handle_event(self, event: pygame.event.Event) -> None:
        for button in self.buttons:
            button.handle_event(event)
        self.debug_toggle.handle_event(event)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.manager.pop()

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BG_COLOR)
        width, height = surface.get_size(); cx = width // 2
        top = max(80, int(height * 0.14))
        self.title.draw(surface, cx, top)
        self.strategy_label.draw(surface, cx, top + 130)
        self.role_label.draw(surface, cx, top + 175)
        # Debug row: label centered slightly left of the toggle so the two
        # read as one line instead of overlapping.
        row_y = top + 250
        self.debug_label.draw(surface, cx - 60, row_y)
        self.debug_toggle.draw(surface)
        self.start_button.draw(surface)
        self.back_button.draw(surface)
