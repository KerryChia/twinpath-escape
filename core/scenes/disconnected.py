import pygame

from core.config.constants import BG_COLOR
from core.config.game_settings import settings
from core.gui import Button, Divider, Label
from core.localization import t
from core.scene import Scene, SceneManager


class Disconnected(Scene):
    def __init__(self, manager: SceneManager, reason: str | None = None) -> None:
        super().__init__(manager)

        self.title = Label(t("disconnect.title"), size=46)
        self.div_l = Divider(scale=0.9, style=3, fade=True)
        self.div_r = Divider(scale=0.9, style=3, fade=True)
        self.div_r.image = pygame.transform.flip(self.div_r.image, True, False)

        self.reason = Label(
            reason or t("disconnect.default_reason"),
            size=24,
            color=(180, 175, 160),
            max_width=600,
        )

        self.menu_btn = Button(
            t("disconnect.back_menu"), width=320, height=66, font_size=28, variant="primary"
        )
        self.menu_btn.callback = self._on_menu

        self._layout(*settings.screen_size)

    def _layout(self, sw: int, sh: int) -> None:
        cx = sw // 2
        cy = sh // 2
        self.menu_btn.set_position(cx, cy + 40)

    def on_resize(self, width: int, height: int) -> None:
        self._layout(width, height)

    def _on_menu(self) -> None:
        from core.scenes.main_menu import MainMenu

        self.manager.stack.clear()
        self.manager.push(MainMenu(self.manager))

    def handle_event(self, event: pygame.event.Event) -> None:
        self.menu_btn.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BG_COLOR)
        sw, _sh = surface.get_size()
        cx = sw // 2
        cy = _sh // 2
        title_y = cy - 80

        title_gap = self.title.rect.width // 2 + 100
        self.div_l.draw(surface, cx - title_gap, title_y)
        self.title.draw(surface, cx, title_y)
        self.div_r.draw(surface, cx + title_gap, title_y)

        self.reason.draw(surface, cx, title_y + 50)
        self.menu_btn.draw(surface)
