"""AI showcase launcher: pick a starting level, then watch two AIs play it.

The showcase runs the very same hybrid planner the human+AI mode uses; this
scene only differs in presentation (level selection, showcase HUD) and in that
both characters are AI-driven with zero interaction.
"""

import pygame

from core.config.constants import BG_COLOR
from core.config.game_mode import GameMode
from core.config.game_settings import settings
from core.config.levels import level_title_key
from core.gui import Button, Label
from core.localization import t
from core.scene import Scene, SceneManager

SHOWCASE_LEVELS = ("tutorial_001", "level_001", "level_002")


class AIShowcase(Scene):
    def __init__(self, manager: SceneManager) -> None:
        super().__init__(manager)
        self.title = Label(t("ai.showcase.setup.title"), 44)
        self.hint_label = Label(t("ai.showcase.setup.hint"), 23)
        self.level_buttons: list[Button] = []
        for level_id in SHOWCASE_LEVELS:
            btn = Button(t(level_title_key(level_id)), 340, 62, font_size=27, variant="secondary")
            btn.callback = lambda lid=level_id: self._start(lid)
            self.level_buttons.append(btn)
        self.back_button = Button(t("common.back"), 220, 54, font_size=22)
        self.back_button.callback = manager.pop
        self.buttons = [*self.level_buttons, self.back_button]
        self._layout(*settings.screen_size)

    def _start(self, level_id: str) -> None:
        from core.scenes.gameplay import Gameplay

        self.manager.replace(
            Gameplay(self.manager, level_id, mode=GameMode.AI_SHOWCASE, debug_ai=True)
        )

    def _layout(self, width: int, height: int) -> None:
        cx = width // 2
        y = max(200, int(height * 0.36))
        for i, btn in enumerate(self.level_buttons):
            btn.set_position(cx, y + i * 78)
        last = self.level_buttons[-1].rect.bottom
        self.back_button.set_position(cx, min(height - 45, last + 45))

    def on_resize(self, width: int, height: int) -> None:
        self._layout(width, height)

    def handle_event(self, event: pygame.event.Event) -> None:
        for button in self.buttons:
            button.handle_event(event)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.manager.pop()

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BG_COLOR)
        width, height = surface.get_size(); cx = width // 2
        self.title.draw(surface, cx, max(70, int(height * 0.15)))
        self.hint_label.draw(surface, cx, max(120, int(height * 0.24)))
        for btn in self.buttons:
            btn.draw(surface)
