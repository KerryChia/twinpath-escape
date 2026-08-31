"""Action-based per-player tutorial with animated key prompts."""

import math

import pygame

from core.config.constants import BG_COLOR
from core.gui import Label
from core.localization import t
from core.resource import resource_path

KEYS_DIR = resource_path("assets/gui/keys/1-bit-input-prompts-pixel-16/Tiles (White)")
KEY_SIZE = 16
KEY_SCALE = 4
SCALED_SIZE = KEY_SIZE * KEY_SCALE

KEY_TILES: dict[str, list[int]] = {
    "W": [358],
    "A": [392],
    "S": [393],
    "D": [394],
    "5": [327],
    "1": [323],
    "2": [324],
    "3": [325],
    "UP": [166],
    "DOWN": [168],
    "RIGHT": [167],
    "LEFT": [169],
    "SPACE": [507, 508, 509],
}

# Maps WASD action names to each control set's display keys
CONTROL_KEY_MAP: dict[str, dict[str, str]] = {
    "WASD": {"W": "W", "A": "A", "S": "S", "D": "D"},
    "Numpad": {"W": "5", "A": "1", "S": "2", "D": "3"},
    "Arrows": {"W": "UP", "A": "LEFT", "S": "DOWN", "D": "RIGHT"},
}

FADE_SPEED = 4.0
PULSE_SPEED = 2.5
PULSE_SCALE = 0.08
COMPLETE_FLASH_DURATION = 0.6
COMPLETE_SCALE_BOOST = 0.3
WAIT_AFTER_COMPLETE = 0.8


def _load_key_image(tile_indices: list[int]) -> pygame.Surface:
    tiles = []
    for idx in tile_indices:
        img = pygame.image.load(KEYS_DIR / f"tile_{idx:04d}.png").convert_alpha()
        tiles.append(pygame.transform.scale(img, (SCALED_SIZE, SCALED_SIZE)))
    total_w = SCALED_SIZE * len(tiles)
    surface = pygame.Surface((total_w, SCALED_SIZE), pygame.SRCALPHA)
    for i, tile in enumerate(tiles):
        surface.blit(tile, (i * SCALED_SIZE, 0))
    return surface


class TutorialStep:
    def __init__(self, p1_keys: list[str], text: str, action: str) -> None:
        self.text = text
        self.action = action
        self._base_keys = p1_keys  # stored as WASD names

        from core.config.game_settings import settings

        p1_map = CONTROL_KEY_MAP.get(settings.p1_controls, CONTROL_KEY_MAP["WASD"])
        p2_map = CONTROL_KEY_MAP.get(settings.p2_controls, CONTROL_KEY_MAP["Numpad"])

        p1_mapped = [p1_map.get(k.upper(), k.upper()) for k in p1_keys]
        p2_mapped = [p2_map.get(k.upper(), k.upper()) for k in p1_keys]

        self.p1_images = [_load_key_image(KEY_TILES[k]) for k in p1_mapped if k in KEY_TILES]
        self.p2_images = [_load_key_image(KEY_TILES[k]) for k in p2_mapped if k in KEY_TILES]

        self.label = Label(text, size=18, color=(220, 215, 200))


class PlayerTutorial:
    def __init__(self, steps: list[TutorialStep], player_index: int) -> None:
        self.steps = steps
        self.player_index = player_index
        self.current_index = 0
        self.alpha = 0.0
        self.time = 0.0
        self._complete_timer = -1.0  # -1 = not completing
        self._wait_timer = 0.0

    @property
    def current(self) -> TutorialStep | None:
        if self.current_index < len(self.steps):
            return self.steps[self.current_index]
        return None

    @property
    def is_completing(self) -> bool:
        return self._complete_timer >= 0

    def complete_current(self) -> None:
        if not self.is_completing and self.current:
            self._complete_timer = 0.0
            from core.audio import play_ui

            play_ui("success")

    def update(self, dt: float) -> None:
        self.time += dt
        step = self.current

        if step is None:
            self.alpha = max(self.alpha - FADE_SPEED * dt, 0.0)
            return

        # Completing animation
        if self.is_completing:
            self._complete_timer += dt
            if self._complete_timer >= COMPLETE_FLASH_DURATION:
                self._complete_timer = -1.0
                self._wait_timer = WAIT_AFTER_COMPLETE
                self.current_index += 1
                self.alpha = 0.0
            return

        # Wait between steps
        if self._wait_timer > 0:
            self._wait_timer -= dt
            return

        self.alpha = min(self.alpha + FADE_SPEED * dt, 1.0)

    def draw(
        self, surface: pygame.Surface, player_rect: pygame.Rect, camera_offset: tuple[int, int]
    ) -> None:
        step = self.current
        if step is None and not self.is_completing:
            return
        if self.alpha <= 0.01 and not self.is_completing:
            return

        # Use the completing step if mid-animation
        if self.is_completing and self.current_index < len(self.steps):
            step = self.steps[self.current_index]
        elif step is None:
            return

        ox, oy = camera_offset
        cx = player_rect.centerx - ox
        cy = player_rect.top - oy - 80

        images = step.p1_images if self.player_index == 0 else step.p2_images
        if not images:
            return

        sw, sh = surface.get_size()

        pulse = 1.0 + math.sin(self.time * PULSE_SPEED * math.pi) * PULSE_SCALE

        if self.is_completing:
            t = self._complete_timer / COMPLETE_FLASH_DURATION
            pulse = 1.0 + COMPLETE_SCALE_BOOST * (1.0 - t)
            alpha = int(255 * (1.0 - t))
        else:
            alpha = int(255 * self.alpha)

        if alpha <= 0:
            return

        total_keys_w = sum(img.get_width() for img in images) + 8 * (len(images) - 1)
        panel_w = max(total_keys_w + 40, step.label.rect.width + 40)
        panel_h = SCALED_SIZE + 40

        panel = pygame.Surface((int(panel_w * pulse), int(panel_h * pulse)), pygame.SRCALPHA)
        panel.fill((*BG_COLOR, 180))
        pygame.draw.rect(panel, (80, 75, 65, 120), panel.get_rect(), 2, border_radius=6)

        panel_rect = panel.get_rect(center=(cx, cy))
        panel.set_alpha(alpha)
        surface.blit(panel, panel_rect)

        temp = pygame.Surface((sw, sh), pygame.SRCALPHA)
        kx = cx - total_keys_w // 2
        ky = cy - SCALED_SIZE // 2

        for img in images:
            scaled_w = int(img.get_width() * pulse)
            scaled_h = int(img.get_height() * pulse)
            scaled_img = pygame.transform.scale(img, (scaled_w, scaled_h))
            img_rect = scaled_img.get_rect(
                center=(int(kx + img.get_width() // 2), int(ky + SCALED_SIZE // 2))
            )

            if self.is_completing:
                tint = pygame.Surface(scaled_img.get_size(), pygame.SRCALPHA)
                tint.fill(
                    (
                        100,
                        255,
                        100,
                        int(100 * (1.0 - self._complete_timer / COMPLETE_FLASH_DURATION)),
                    )
                )
                scaled_img = scaled_img.copy()
                scaled_img.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

            temp.blit(scaled_img, img_rect)
            kx += img.get_width() + 8

        step.label.draw(temp, int(cx), int(cy + SCALED_SIZE // 2 + 14))

        temp.set_alpha(alpha)
        surface.blit(temp, (0, 0))


def detect_action(player: object, action: str) -> bool:
    if action == "move":
        return abs(player.velocity.x) > 10
    if action == "jump":
        return player.velocity.y < -100 and not player.on_ground
    if action == "double_jump":
        return not player.has_double_jump and player.velocity.y < -100
    if action == "fast_fall":
        return player.velocity.y > 500 and not player.on_ground
    if action == "swim":
        return player.in_water and abs(player.velocity.x) > 5
    if action == "swim_up":
        return player.in_water and player.velocity.y < -50
    return False


TUTORIAL_STEPS = [
    {"keys": ["A", "D"], "text": t("tutorial.move"), "action": "move"},
    {"keys": ["W"], "text": t("tutorial.jump"), "action": "jump"},
    {"keys": ["W", "W"], "text": t("tutorial.double_jump"), "action": "double_jump"},
    {"keys": ["S"], "text": t("tutorial.fast_fall"), "action": "fast_fall"},
]


class TutorialManager:
    def __init__(self, steps_data: list[dict] | None = None) -> None:
        data = steps_data or TUTORIAL_STEPS
        steps = [TutorialStep(s["keys"], s["text"], s["action"]) for s in data]
        self.p1 = PlayerTutorial(steps, 0)
        self.p2 = PlayerTutorial(list(steps), 1)

    def update(self, dt: float, player1: object, player2: object) -> None:
        self.p1.update(dt)
        self.p2.update(dt)

        # Detect actions for each player
        for tut, player in [(self.p1, player1), (self.p2, player2)]:
            step = tut.current
            if (
                step
                and not tut.is_completing
                and tut.alpha >= 0.5
                and detect_action(player, step.action)
            ):
                tut.complete_current()

    def draw_for_player(
        self,
        surface: pygame.Surface,
        player_index: int,
        player_rect: pygame.Rect,
        camera_offset: tuple[int, int],
    ) -> None:
        tut = self.p1 if player_index == 0 else self.p2
        tut.draw(surface, player_rect, camera_offset)
