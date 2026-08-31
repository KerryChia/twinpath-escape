import pygame

from core.config.constants import BG_COLOR
from core.config.game_settings import settings
from core.gui import Button, Divider, Label, TextInput
from core.localization import t
from core.scene import Scene, SceneManager


class LocalNameInput(Scene):
    def __init__(self, manager: SceneManager) -> None:
        super().__init__(manager)

        self.title = Label(t("names.title"), size=46)
        self.div_l = Divider(scale=0.9, style=3, fade=True)
        self.div_r = Divider(scale=0.9, style=3, fade=True)
        self.div_r.image = pygame.transform.flip(self.div_r.image, True, False)

        self.p1_label = Label(t("names.player1", controls=t("settings.control.WASD")), size=22, color=(255, 80, 80))
        self.p1_input = TextInput(width=320, height=54, placeholder=t("names.green_placeholder"), font_size=22)

        self.p2_label = Label(t("names.player2", controls=t("settings.control.Numpad")), size=22, color=(80, 130, 255))
        self.p2_input = TextInput(width=320, height=54, placeholder=t("names.orange_placeholder"), font_size=22)

        self.play_btn = Button(t("names.start"), width=320, height=66, font_size=28, variant="primary")
        self.play_btn.callback = self._on_play

        self.back_btn = Button(t("common.back"), width=240, height=58, font_size=24, variant="secondary")
        self.back_btn.callback = self._on_back

        self.widgets = [self.p1_input, self.p2_input, self.play_btn, self.back_btn]
        self._layout(*settings.screen_size)

    def _layout(self, sw: int, sh: int) -> None:
        cx = sw // 2
        cy = sh // 2

        self.p1_input.set_position(cx, cy - 80)
        self.p2_input.set_position(cx, cy + 10)
        self.play_btn.set_position(cx, cy + 100)
        self.back_btn.set_position(cx, cy + 260)

    def on_resize(self, width: int, height: int) -> None:
        self._layout(width, height)

    def _on_play(self) -> None:
        from core.scenes.intro import Intro

        p1_name = self.p1_input.text.strip() or t("common.green")
        p2_name = self.p2_input.text.strip() or t("common.orange")
        self.manager.replace(Intro(self.manager, p1_name=p1_name, p2_name=p2_name))

    def _on_back(self) -> None:
        self.manager.pop()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._on_back()
            return
        for w in self.widgets:
            w.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BG_COLOR)
        sw, _sh = surface.get_size()
        cx = sw // 2
        cy = _sh // 2
        title_y = cy - 200

        title_gap = self.title.rect.width // 2 + 100
        self.div_l.draw(surface, cx - title_gap, title_y)
        self.title.draw(surface, cx, title_y)
        self.div_r.draw(surface, cx + title_gap, title_y)

        self.p1_label.draw(surface, cx, cy - 120)
        self.p1_input.draw(surface)
        self.p2_label.draw(surface, cx, cy - 30)
        self.p2_input.draw(surface)
        self.play_btn.draw(surface)
        self.back_btn.draw(surface)
