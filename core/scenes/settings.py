import pygame

from core.config.constants import BG_COLOR
from core.config.game_settings import settings
from core.gui import Button, Divider, Label, Panel, Slider, Toggle
from core.localization import t
from core.resource import resource_path
from core.scene import Scene, SceneManager

ICON_DIR = resource_path("assets/gui/icons")
TAB_ICON_SIZE = 32
TAB_NAMES = [
    t("settings.tab.screen"),
    t("settings.tab.audio"),
    t("settings.tab.gameplay"),
    t("settings.tab.credits"),
]
TAB_ICONS = [
    "ic_video_fill.png",
    "ic_volume_on_fill.png",
    "ic_settings_fill.png",
    "ic_star_fill.png",
]


def _load_icon(name: str, size: int = TAB_ICON_SIZE) -> pygame.Surface:
    img = pygame.image.load(ICON_DIR / name).convert_alpha()
    return pygame.transform.scale(img, (size, size))


class Settings(Scene):
    def __init__(self, manager: SceneManager) -> None:
        super().__init__(manager)

        self.title = Label(t("settings.title"), size=42)
        self.divider_top = Divider(scale=0.8, style=3, fade=True)
        self.divider_bottom = Divider(scale=0.8, style=3, fade=True)
        self.divider_bottom.image = pygame.transform.flip(self.divider_bottom.image, True, False)

        self.tab_icons = [_load_icon(name) for name in TAB_ICONS]
        self.tab_labels = [Label(name, size=14, color=(160, 155, 140)) for name in TAB_NAMES]
        self.active_tab = 0
        self.tab_rects: list[pygame.Rect] = []

        self.fullscreen_label = Label(t("settings.fullscreen"), size=24)
        self.fullscreen_toggle = Toggle(width=80, height=42, active=settings.is_fullscreen, style=6)
        self.fullscreen_toggle.on_change = self._on_fullscreen

        self.resolutions = [(1280, 720), (1920, 1080), (800, 600)]
        self.res_index = next(
            (i for i, r in enumerate(self.resolutions) if r == settings.screen_size), 0
        )
        self.res_label = Label(t("settings.resolution"), size=24)
        self.res_value = Label(self._res_text(), size=22)
        self.res_left = Button("<", width=46, height=46, font_size=22, variant="secondary")
        self.res_left.callback = self._prev_res
        self.res_right = Button(">", width=46, height=46, font_size=22, variant="secondary")
        self.res_right.callback = self._next_res

        self.fps_label = Label(t("settings.show_fps"), size=24)
        self.fps_toggle = Toggle(width=80, height=42, active=settings.show_fps, style=6)
        self.fps_toggle.on_change = self._on_fps

        self.music_label = Label(t("settings.music"), size=24)
        self.music_slider = Slider(width=240, height=42, value=settings.music_volume, style=6)
        self.music_slider.on_change = self._on_music

        self.sfx_label = Label(t("settings.sfx"), size=24)
        self.sfx_slider = Slider(width=240, height=42, value=settings.sfx_volume, style=6)
        self.sfx_slider.on_change = self._on_sfx

        self.ui_label = Label(t("settings.ui_sounds"), size=24)
        self.ui_slider = Slider(width=240, height=42, value=settings.ui_volume, style=6)
        self.ui_slider.on_change = self._on_ui

        from core.config.constants import CONTROL_NAMES

        self._control_names = CONTROL_NAMES
        self.p1_controls_label = Label(t("settings.player1"), size=24, color=(255, 100, 100))
        self.p1_controls_value = Label(t(f"settings.control.{settings.p1_controls}"), size=22)
        self.p1_left_btn = Button("<", width=46, height=46, font_size=22, variant="secondary")
        self.p1_left_btn.callback = self._prev_p1_controls
        self.p1_right_btn = Button(">", width=46, height=46, font_size=22, variant="secondary")
        self.p1_right_btn.callback = self._next_p1_controls

        self.p2_controls_label = Label(t("settings.player2"), size=24, color=(100, 150, 255))
        self.p2_controls_value = Label(t(f"settings.control.{settings.p2_controls}"), size=22)
        self.p2_left_btn = Button("<", width=46, height=46, font_size=22, variant="secondary")
        self.p2_left_btn.callback = self._prev_p2_controls
        self.p2_right_btn = Button(">", width=46, height=46, font_size=22, variant="secondary")
        self.p2_right_btn.callback = self._next_p2_controls

        self.controls_error = Label("", size=14, color=(200, 80, 80))

        self._credits = [
            (
                t("settings.credit.characters"),
                "dajeki",
                "https://dajeki.itch.io/dajekis-8x8-fantasy-character-sprites",
            ),
            (t("settings.credit.ui_borders"), "kenney", "https://kenney-assets.itch.io/fantasy-ui-borders"),
            (t("settings.credit.font"), "yukipixels", "https://yukipixels.itch.io/boldpixels"),
            (t("settings.credit.font"), "Google / Noto", "https://github.com/google/fonts/tree/main/ofl/notosanssc"),
            (t("settings.credit.key_prompts"), "kenney", "https://kenney-assets.itch.io/1-bit-pixel-input-prompts-16"),
            (t("settings.credit.music"), "tallbeard", "https://tallbeard.itch.io/music-loop-bundle"),
        ]
        self._credit_labels = []
        for what, who, _url in self._credits:
            what_l = Label(what, size=16, color=(220, 215, 200))
            who_l = Label(who, size=16, color=(160, 200, 160))
            self._credit_labels.append((what_l, who_l))
        self._credit_rects: list[pygame.Rect] = []
        self._credits_title = Label(t("settings.credits.title"), size=22, color=(240, 235, 220))
        self._credits_hint = Label(t("settings.credits.hint"), size=12, color=(90, 85, 75))

        self.back_btn = Button(t("common.back"), width=240, height=58, font_size=24, variant="secondary")
        self.back_btn.callback = self._on_back

        self._build_tab_widgets()
        self._layout(*settings.screen_size)

    def _build_tab_widgets(self) -> None:
        tab_widgets = {
            0: [self.fullscreen_toggle, self.res_left, self.res_right, self.fps_toggle],
            1: [self.music_slider, self.sfx_slider, self.ui_slider],
            2: [self.p1_left_btn, self.p1_right_btn, self.p2_left_btn, self.p2_right_btn],
            3: [],
        }
        self._tab_widgets = tab_widgets
        self._update_active_widgets()

    def _update_active_widgets(self) -> None:
        self.widgets = [*self._tab_widgets.get(self.active_tab, []), self.back_btn]

    def _layout(self, sw: int, sh: int) -> None:
        cx = sw // 2
        cy = sh // 2

        self.bg_panel = Panel(
            680, 600, style=6, transparent=True, fill_color=BG_COLOR, border_color=(80, 75, 65)
        )
        self.bg_x = (sw - 680) // 2
        self.bg_y = cy - 300

        tab_y = self.bg_y + 110
        tab_total_w = len(TAB_NAMES) * 130
        tab_start_x = cx - tab_total_w // 2

        self.tab_rects = []
        for i in range(len(TAB_NAMES)):
            tx = tab_start_x + i * 130
            self.tab_rects.append(pygame.Rect(tx, tab_y, 120, 55))

        content_y = self.bg_y + 200
        label_x = cx - 160
        control_x = cx + 130

        self.fullscreen_toggle.set_position(control_x, content_y)
        self.res_left.set_position(control_x - 90, content_y + 85)
        self.res_right.set_position(control_x + 90, content_y + 85)
        self.fps_toggle.set_position(control_x, content_y + 170)

        self.music_slider.set_position(control_x, content_y + 10)
        self.sfx_slider.set_position(control_x, content_y + 90)
        self.ui_slider.set_position(control_x, content_y + 170)

        self.p1_left_btn.set_position(control_x - 90, content_y + 30)
        self.p1_right_btn.set_position(control_x + 90, content_y + 30)
        self.p2_left_btn.set_position(control_x - 90, content_y + 110)
        self.p2_right_btn.set_position(control_x + 90, content_y + 110)

        self.back_btn.set_position(cx, self.bg_y + 555)

        self._label_x = label_x
        self._control_x = control_x
        self._content_y = content_y

    def on_resize(self, width: int, height: int) -> None:
        self._layout(width, height)

    def _res_text(self) -> str:
        w, h = self.resolutions[self.res_index]
        return f"{w}x{h}"

    def _prev_res(self) -> None:
        self.res_index = (self.res_index - 1) % len(self.resolutions)
        self._apply_resolution()

    def _next_res(self) -> None:
        self.res_index = (self.res_index + 1) % len(self.resolutions)
        self._apply_resolution()

    def _apply_resolution(self) -> None:
        self.res_value.set_text(self._res_text())
        if not settings.is_fullscreen:
            w, h = self.resolutions[self.res_index]
            settings.screen_width = w
            settings.screen_height = h
            settings.apply_display_mode()

    def _on_fullscreen(self, active: bool) -> None:
        settings.is_fullscreen = active
        if not active:
            w, h = self.resolutions[self.res_index]
            settings.screen_width = w
            settings.screen_height = h
        settings.apply_display_mode()

    def _on_music(self, value: float) -> None:
        settings.set_music_volume(value)

    def _on_sfx(self, value: float) -> None:
        settings.set_sfx_volume(value)

    def _on_ui(self, value: float) -> None:
        settings.ui_volume = value

    def _cycle_control(self, current: str, direction: int) -> str:
        idx = self._control_names.index(current)
        return self._control_names[(idx + direction) % len(self._control_names)]

    def _validate_controls(self) -> bool:
        if settings.p1_controls == settings.p2_controls:
            self.controls_error.set_text(t("settings.control_conflict"))
            return False
        self.controls_error.set_text("")
        return True

    def _prev_p1_controls(self) -> None:
        settings.p1_controls = self._cycle_control(settings.p1_controls, -1)
        if settings.p1_controls == settings.p2_controls:
            settings.p1_controls = self._cycle_control(settings.p1_controls, -1)
        self.p1_controls_value.set_text(t(f"settings.control.{settings.p1_controls}"))
        self._validate_controls()

    def _next_p1_controls(self) -> None:
        settings.p1_controls = self._cycle_control(settings.p1_controls, 1)
        if settings.p1_controls == settings.p2_controls:
            settings.p1_controls = self._cycle_control(settings.p1_controls, 1)
        self.p1_controls_value.set_text(t(f"settings.control.{settings.p1_controls}"))
        self._validate_controls()

    def _prev_p2_controls(self) -> None:
        settings.p2_controls = self._cycle_control(settings.p2_controls, -1)
        if settings.p2_controls == settings.p1_controls:
            settings.p2_controls = self._cycle_control(settings.p2_controls, -1)
        self.p2_controls_value.set_text(t(f"settings.control.{settings.p2_controls}"))
        self._validate_controls()

    def _next_p2_controls(self) -> None:
        settings.p2_controls = self._cycle_control(settings.p2_controls, 1)
        if settings.p2_controls == settings.p1_controls:
            settings.p2_controls = self._cycle_control(settings.p2_controls, 1)
        self.p2_controls_value.set_text(t(f"settings.control.{settings.p2_controls}"))
        self._validate_controls()

    def _on_fps(self, active: bool) -> None:
        settings.show_fps = active

    def _on_back(self) -> None:
        self.manager.pop()

    def update(self, dt: float) -> None:
        from core.scenes.network_gameplay import NetworkGameplay

        for scene in self.manager.stack:
            if isinstance(scene, NetworkGameplay):
                scene.update(dt)
                break

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._on_back()
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.tab_rects):
                if rect.collidepoint(event.pos):
                    self.active_tab = i
                    self._update_active_widgets()
                    return

            if self.active_tab == 3:
                for i, rect in enumerate(self._credit_rects):
                    if rect.collidepoint(event.pos) and i < len(self._credits):
                        import webbrowser

                        webbrowser.open(self._credits[i][2])
                        return

        for widget in self.widgets:
            widget.handle_event(event)

    def _draw_tabs(self, surface: pygame.Surface, cx: int) -> None:
        for i, rect in enumerate(self.tab_rects):
            is_active = i == self.active_tab

            color = (60, 55, 48) if is_active else (35, 32, 28)
            border = (160, 155, 140) if is_active else (80, 75, 65)
            tab_panel = Panel(
                rect.width, rect.height, style=6, fill_color=color, border_color=border
            )
            tab_panel.draw(surface, rect.x, rect.y)

            icon = self.tab_icons[i]
            icon_x = rect.centerx - TAB_ICON_SIZE // 2
            icon_y = rect.y + 5
            surface.blit(icon, (icon_x, icon_y))

            self.tab_labels[i].draw(surface, rect.centerx, rect.bottom - 8)

    def _draw_screen_tab(self, surface: pygame.Surface) -> None:
        y = self._content_y
        self.fullscreen_label.draw(surface, self._label_x, y)
        self.fullscreen_toggle.draw(surface)

        self.res_label.draw(surface, self._label_x, y + 85)
        self.res_left.draw(surface)
        self.res_value.draw(surface, self._control_x, y + 85)
        self.res_right.draw(surface)

        self.fps_label.draw(surface, self._label_x, y + 170)
        self.fps_toggle.draw(surface)

    def _draw_audio_tab(self, surface: pygame.Surface) -> None:
        y = self._content_y + 10
        self.music_label.draw(surface, self._label_x, y)
        self.music_slider.draw(surface)

        self.sfx_label.draw(surface, self._label_x, y + 80)
        self.sfx_slider.draw(surface)

        self.ui_label.draw(surface, self._label_x, y + 160)
        self.ui_slider.draw(surface)

    def _draw_gameplay_tab(self, surface: pygame.Surface, cx: int, cy: int) -> None:
        y = self._content_y + 30
        self.p1_controls_label.draw(surface, self._label_x, y)
        self.p1_left_btn.draw(surface)
        self.p1_controls_value.draw(surface, self._control_x, y)
        self.p1_right_btn.draw(surface)

        y += 80
        self.p2_controls_label.draw(surface, self._label_x, y)
        self.p2_left_btn.draw(surface)
        self.p2_controls_value.draw(surface, self._control_x, y)
        self.p2_right_btn.draw(surface)

        self.controls_error.draw(surface, cx, y + 60)

    def _draw_credits_tab(self, surface: pygame.Surface, cx: int, cy: int) -> None:
        y = self._content_y + 5
        self._credits_title.draw(surface, cx, y)
        y += 35
        self._credit_rects.clear()
        for what_label, who_label in self._credit_labels:
            what_label.draw(surface, cx - 90, y)
            who_label.draw(surface, cx + 90, y)
            who_rect = pygame.Rect(
                cx + 90 - who_label.rect.width // 2, y - 10, who_label.rect.width, 20
            )
            self._credit_rects.append(who_rect)
            y += 26
        self._credits_hint.draw(surface, cx, y + 10)

    def draw(self, surface: pygame.Surface) -> None:
        sw, sh = surface.get_size()
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        cx = sw // 2
        title_y = self.bg_y + 55

        self.bg_panel.draw(surface, self.bg_x, self.bg_y)
        title_gap = self.title.rect.width // 2 + 110
        self.divider_top.draw(surface, cx - title_gap, title_y)
        self.title.draw(surface, cx, title_y)
        self.divider_bottom.draw(surface, cx + title_gap, title_y)

        self._draw_tabs(surface, cx)

        content_cy = self._content_y + 100
        if self.active_tab == 0:
            self._draw_screen_tab(surface)
        elif self.active_tab == 1:
            self._draw_audio_tab(surface)
        elif self.active_tab == 2:
            self._draw_gameplay_tab(surface, cx, content_cy)
        elif self.active_tab == 3:
            self._draw_credits_tab(surface, cx, content_cy)

        self.back_btn.draw(surface)
