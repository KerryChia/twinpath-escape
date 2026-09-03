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
        y = max(170, int(height * 0.34))
        self.debug_toggle.set_position(cx + 135, y + 130)
        self.start_button.set_position(cx, y + 190)
        self.back_button.set_position(cx, min(height - 45, y + 265))

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
        self.title.draw(surface, cx, max(65, int(height * 0.14)))
        y = self.start_button.rect.centery
        self.strategy_label.draw(surface, cx, y - 100)
        self.role_label.draw(surface, cx, y - 70)
        self.debug_label.draw(surface, cx - 70, y + 100)
        self.debug_toggle.draw(surface)
        self.start_button.draw(surface)
        self.back_button.draw(surface)
