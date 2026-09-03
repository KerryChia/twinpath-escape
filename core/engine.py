import pygame

from core.config.constants import FPS, TITLE
from core.config.game_settings import settings
from core.fonts import get_font
from core.localization import t
from core.resource import resource_path
from core.scene import SceneManager

CURSOR_PATH = resource_path("assets/gui/icons/ic_cursor_fill.png")
CURSOR_SIZE = 24


class Engine:
    def __init__(self, start_level: str | None = None) -> None:
        pygame.init()
        pygame.mixer.init()
        self.screen = settings.apply_display_mode()
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.scene_manager = SceneManager()

        if start_level:
            from core.scenes.gameplay import Gameplay

            self.scene_manager.push(Gameplay(self.scene_manager, level_id=start_level))
        else:
            from core.scenes.main_menu import MainMenu

            self.scene_manager.push(MainMenu(self.scene_manager))
        settings.consume_dirty()
        self._fps_font = get_font(14)

        cursor_img = pygame.image.load(CURSOR_PATH).convert_alpha()
        self._cursor = pygame.transform.scale(cursor_img, (CURSOR_SIZE, CURSOR_SIZE))
        pygame.mouse.set_visible(False)

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.get_time() / 1000.0, 1 / 20)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                self.scene_manager.handle_event(event)

            if settings.consume_dirty():
                self.screen = pygame.display.get_surface()
                self.scene_manager.notify_resize(*settings.screen_size)

            self.scene_manager.update(dt)
            self.scene_manager.draw(self.screen)

            if settings.show_fps:
                fps_text = self._fps_font.render(
                    t("common.fps", fps=f"{self.clock.get_fps():.0f}"), True, (200, 200, 200)
                )
                self.screen.blit(fps_text, (8, 8))

            from core.scenes.base_gameplay import BaseGameplay

            top = self.scene_manager.current
            in_gameplay = isinstance(top, BaseGameplay)
            if not in_gameplay:
                mx, my = pygame.mouse.get_pos()
                self.screen.blit(self._cursor, (mx, my))

            pygame.display.flip()
            self.clock.tick(FPS)

        for scene in self.scene_manager.stack:
            if hasattr(scene, "tunnel") and scene.tunnel:
                scene.tunnel.stop()
            if hasattr(scene, "server") and scene.server:
                scene.server.stop_sync()
            if hasattr(scene, "broadcaster") and scene.broadcaster:
                scene.broadcaster.stop()

        pygame.quit()
