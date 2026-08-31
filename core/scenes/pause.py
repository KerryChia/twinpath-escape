import pygame

from core.config.game_settings import settings
from core.gui import Button, Divider, Label, Panel
from core.localization import t
from core.scene import Scene, SceneManager


class Pause(Scene):
    def __init__(self, manager: SceneManager) -> None:
        super().__init__(manager)

        self.title = Label(t("pause.title"), size=42)
        self.divider_left = Divider(scale=0.55, style=3, fade=True)
        self.divider_right = Divider(scale=0.55, style=3, fade=True)
        self.divider_right.image = pygame.transform.flip(self.divider_right.image, True, False)

        self.resume_btn = Button(t("pause.resume"), width=300, height=66, font_size=28, variant="primary")
        self.resume_btn.callback = self._on_resume

        self.settings_btn = Button(
            t("menu.settings"), width=260, height=58, font_size=24, variant="secondary"
        )
        self.settings_btn.callback = self._on_settings

        self.quit_btn = Button(t("pause.quit_menu"), width=260, height=58, font_size=22, variant="danger")
        self.quit_btn.callback = self._on_quit

        self.buttons = [self.resume_btn, self.settings_btn, self.quit_btn]
        self._layout(*settings.screen_size)

    def _layout(self, sw: int, sh: int) -> None:
        cx = sw // 2
        cy = sh // 2

        self.bg_panel = Panel(
            460, 400, style=6, transparent=True, fill_color=(14, 7, 27), border_color=(80, 75, 65)
        )
        self.bg_x = (sw - 460) // 2
        self.bg_y = cy - 200

        self.resume_btn.set_position(cx, cy - 30)
        self.settings_btn.set_position(cx, cy + 55)
        self.quit_btn.set_position(cx, cy + 135)

    def on_resize(self, width: int, height: int) -> None:
        self._layout(width, height)

    def _on_resume(self) -> None:
        self.manager.pop()

    def _on_settings(self) -> None:
        from core.scenes.settings import Settings

        self.manager.push(Settings(self.manager))

    def _on_quit(self) -> None:
        from core.scenes.main_menu import MainMenu

        self.manager.stack.clear()
        self.manager.push(MainMenu(self.manager))

    def update(self, dt: float) -> None:
        from core.scenes.network_gameplay import NetworkGameplay

        for scene in self.manager.stack:
            if isinstance(scene, NetworkGameplay):
                scene.update(dt)
                break

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._on_resume()
            return
        for btn in self.buttons:
            btn.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        sw, sh = surface.get_size()
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        cx = sw // 2
        title_y = self.bg_y + 60

        self.bg_panel.draw(surface, self.bg_x, self.bg_y)
        title_gap = self.title.rect.width // 2 + 70
        self.divider_left.draw(surface, cx - title_gap, title_y)
        self.title.draw(surface, cx, title_y)
        self.divider_right.draw(surface, cx + title_gap, title_y)

        for btn in self.buttons:
            btn.draw(surface)
