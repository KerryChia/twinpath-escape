import pygame

from core.config.constants import (
    BASE_MAP_SCALE,
    BG_COLOR,
    P1_OUTLINE_LOCAL,
    P2_OUTLINE_LOCAL,
    PLAYER_SCALE,
    TITLE,
)
from core.config.game_settings import settings
from core.gui import Button, Divider, Label
from core.localization import t
from core.menu_bots import AIPlayer, MenuBackground
from core.scene import Scene, SceneManager


class MainMenu(Scene):
    def __init__(self, manager: SceneManager) -> None:
        super().__init__(manager)

        from core.audio import play_music

        play_music("menu")

        from importlib.metadata import version as pkg_version

        try:
            ver = pkg_version("twinpath-escape")
        except Exception:
            ver = "0.1.2"

        self.version_label = Label(f"v{ver}", size=18, color=(100, 95, 85))
        self.credit_label = Label(t("menu.credit"), size=18, color=(100, 95, 85))

        self.title = Label(TITLE, size=64)
        self.title_div_l = Divider(scale=1.2, style=3, fade=True)
        self.title_div_r = Divider(scale=1.2, style=3, fade=True)
        self.title_div_r.image = pygame.transform.flip(self.title_div_r.image, True, False)
        self.title_w = self.title.rect.width

        self.subtitle = Label(t("menu.subtitle"), size=24, color=(160, 155, 140))

        self.local_btn = Button(
            t("menu.local"), width=360, height=72, font_size=32, variant="primary"
        )
        self.local_btn.callback = self._on_local

        self.host_btn = Button(
            t("menu.host"), width=320, height=66, font_size=28, variant="secondary"
        )
        self.host_btn.callback = self._on_host

        self.join_btn = Button(
            t("menu.join"), width=320, height=66, font_size=28, variant="secondary"
        )
        self.join_btn.callback = self._on_join

        self.sep_div_l = Divider(scale=0.7, style=2, fade=True, color=(120, 115, 100))
        self.sep_div_r = Divider(scale=0.7, style=2, fade=True, color=(120, 115, 100))
        self.sep_div_r.image = pygame.transform.flip(self.sep_div_r.image, True, False)

        self.settings_btn = Button(
            t("menu.settings"), width=260, height=58, font_size=24, variant="secondary"
        )
        self.settings_btn.callback = self._on_settings

        self.quit_btn = Button(t("menu.quit"), width=260, height=58, font_size=24, variant="danger")
        self.quit_btn.callback = self._on_quit

        self.buttons = [
            self.local_btn,
            self.host_btn,
            self.join_btn,
            self.settings_btn,
            self.quit_btn,
        ]

        self.bg = MenuBackground(settings.screen_size)
        self._init_bots()
        self._overlay: pygame.Surface | None = None
        self._layout(*settings.screen_size)

    def _init_bots(self) -> None:
        bounds = self.bg.get_bounds()
        player_scale = PLAYER_SCALE * (self.bg.scale / BASE_MAP_SCALE)

        spawn_a = self.bg.get_spawn("A")
        spawn_b = self.bg.get_spawn("B")
        x1 = spawn_a[0] if spawn_a else bounds.left + bounds.width // 3
        y1 = spawn_a[1] if spawn_a else bounds.top + 20
        x2 = spawn_b[0] if spawn_b else bounds.left + bounds.width * 2 // 3
        y2 = spawn_b[1] if spawn_b else bounds.top + 20

        self.bots = [
            AIPlayer(x1, y1, P1_OUTLINE_LOCAL, "green"),
            AIPlayer(x2, y2, P2_OUTLINE_LOCAL, "orange"),
        ]
        for bot in self.bots:
            bot.rescale(player_scale)

    def _layout(self, sw: int, sh: int) -> None:
        cx = sw // 2
        cy = sh // 2

        self.local_btn.set_position(cx, cy - 80)
        self.host_btn.set_position(cx, cy + 10)
        self.join_btn.set_position(cx, cy + 90)
        self.settings_btn.set_position(cx, cy + 200)
        self.quit_btn.set_position(cx, cy + 270)

    def on_resize(self, width: int, height: int) -> None:
        old_scale = self.bg.scale
        old_offset = self.bg.offset
        self.bg.rescale((width, height))
        player_scale = PLAYER_SCALE * (self.bg.scale / BASE_MAP_SCALE)

        for bot in self.bots:
            rel_x = (bot.pos.x - old_offset[0]) / old_scale
            rel_y = (bot.pos.y - old_offset[1]) / old_scale
            bot.rescale(player_scale)
            bot.pos.x = rel_x * self.bg.scale + self.bg.offset[0]
            bot.pos.y = rel_y * self.bg.scale + self.bg.offset[1]
            bot.rect.x = int(bot.pos.x)
            bot.rect.y = int(bot.pos.y)

        self._overlay = None
        self._layout(width, height)

    def update(self, dt: float) -> None:
        bounds = self.bg.get_bounds()
        spawns = [self.bg.get_spawn("A"), self.bg.get_spawn("B")]
        for i, bot in enumerate(self.bots):
            bot.update_ai(dt, bounds)
            bot.update(dt, self.bg.collision_rects, [])
            if bot.dead or bot.rect.top > bounds.bottom + 50:
                sp = spawns[i]
                sx = sp[0] if sp else bounds.left + bounds.width // 3 * (i + 1)
                sy = sp[1] if sp else bounds.top + 20
                bot.respawn(sx, sy)

    def _on_local(self) -> None:
        from core.scenes.name_input import LocalNameInput

        self.manager.push(LocalNameInput(self.manager))

    def _on_host(self) -> None:
        from core.scenes.lobby import HostLobby

        self.manager.push(HostLobby(self.manager))

    def _on_join(self) -> None:
        from core.scenes.lobby import JoinLobby

        self.manager.push(JoinLobby(self.manager))

    def _on_settings(self) -> None:
        from core.scenes.settings import Settings

        self.manager.push(Settings(self.manager))

    def _on_quit(self) -> None:
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def handle_event(self, event: pygame.event.Event) -> None:
        for btn in self.buttons:
            btn.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BG_COLOR)
        sw, sh = surface.get_size()
        cx = sw // 2
        cy = sh // 2

        # Map background + AI players
        self.bg.draw(surface)
        for bot in self.bots:
            bot.draw(surface)

        # Dark overlay so UI stays readable
        if self._overlay is None or self._overlay.get_size() != (sw, sh):
            self._overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
            self._overlay.fill((*BG_COLOR, 120))
        surface.blit(self._overlay, (0, 0))

        # UI
        title_y = cy - 200
        gap = self.title_w // 2 + 130
        self.title_div_l.draw(surface, cx - gap, title_y)
        self.title.draw(surface, cx, title_y)
        self.title_div_r.draw(surface, cx + gap, title_y)
        self.subtitle.draw(surface, cx, title_y + 42)

        self.local_btn.draw(surface)
        self.host_btn.draw(surface)
        self.join_btn.draw(surface)

        sep_y = self.join_btn.rect.bottom + 30
        self.sep_div_l.draw(surface, cx - 80, sep_y)
        self.sep_div_r.draw(surface, cx + 80, sep_y)

        self.settings_btn.draw(surface)
        self.quit_btn.draw(surface)

        self.credit_label.draw(surface, 120, sh - 16)
        self.version_label.draw(surface, sw - 40, sh - 16)
