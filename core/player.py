from pathlib import Path

import pygame

from core.config.constants import (
    DEATH_ANIM_DURATION,
    DEATH_ANIM_SPEED_MOD,
    FALL_DEATH_AIRTIME,
    NAMETAG_COLOR,
    NAMETAG_OFFSET_Y,
    NAMETAG_SIZE,
    P1_KEYS,
    PLAYER_ACCELERATION,
    PLAYER_ANIMATION_SPEED,
    PLAYER_FAST_FALL,
    PLAYER_FRICTION,
    PLAYER_GRAVITY,
    PLAYER_JUMP_FORCE,
    PLAYER_MAX_SPEED,
    PLAYER_SCALE,
    SPRITE_FRAME_COUNT,
    SPRITE_FRAME_SIZE,
    SQUASH_DURATION,
    SQUASH_FACTOR,
    STAIRS_CLIMB_SPEED,
    STAIRS_DESCEND_SPEED,
    STAIRS_FRICTION,
    STAIRS_JUMP_MOD,
    STRETCH_DURATION,
    STRETCH_FACTOR,
    VELOCITY_DEAD_ZONE,
    WATER_ANIM_MOD,
    WATER_GRAVITY_MOD,
    WATER_JUMP_MOD,
    WATER_MAX_FALL_MOD,
    WATER_SPEED_MOD,
)
from core.ai.actions import Action, ActionProvider, KeyboardActionProvider
from core.fonts import get_font
from core.localization import t
from core.utils import add_outline, lerp, load_spritesheet

KEY_MAP = {
    "a": pygame.K_a,
    "d": pygame.K_d,
    "w": pygame.K_w,
    "s": pygame.K_s,
    "[1]": pygame.K_KP_1,
    "[2]": pygame.K_KP_2,
    "[3]": pygame.K_KP_3,
    "[5]": pygame.K_KP_5,
    "left": pygame.K_LEFT,
    "right": pygame.K_RIGHT,
    "up": pygame.K_UP,
    "down": pygame.K_DOWN,
}

OUTLINE_COLOR = (255, 255, 255)
ANIM_KEYS = ["idle", "walk", "jump", "die"]


def _build_animations(
    sprite_dir: Path,
    prefix: str,
    scale: float,
    outline_color: tuple[int, int, int] = OUTLINE_COLOR,
) -> dict[str, list[pygame.Surface]]:
    raw = {}
    for key in ANIM_KEYS:
        path = sprite_dir / f"{prefix}_{key}.png"
        raw[key] = load_spritesheet(path, SPRITE_FRAME_SIZE, SPRITE_FRAME_COUNT, scale)
    return {key: [add_outline(f, outline_color) for f in frames] for key, frames in raw.items()}


class Player:
    _nametag_font: pygame.font.Font | None = None

    def __init__(
        self,
        x: float,
        y: float,
        keys: dict[str, str] | None = None,
        outline_color: tuple[int, int, int] = OUTLINE_COLOR,
        character: str = "green",
        name: str | None = None,
        action_provider: ActionProvider | None = None,
    ) -> None:
        bindings = keys or P1_KEYS
        self.action_provider: ActionProvider = action_provider or KeyboardActionProvider(bindings, KEY_MAP)
        self.last_action = Action()

        self.name = name or t("common.player")
        self.outline_color = outline_color
        from core.resource import resource_path

        self.sprite_dir = resource_path(f"assets/characters/{character}")
        self.sprite_prefix = character
        self.current_scale = PLAYER_SCALE
        self.animations = _build_animations(
            self.sprite_dir, self.sprite_prefix, PLAYER_SCALE, outline_color
        )

        self.state = "idle"
        self.pos = pygame.math.Vector2(x, y)
        self.velocity = pygame.math.Vector2(0, 0)
        self.acceleration = pygame.math.Vector2(0, 0)

        self.on_ground = False
        self.was_airborne = False
        self.just_landed = False
        self.in_water = False
        self.in_lava = False
        self.on_stairs = False
        self.dropping_through = False
        self.has_double_jump = False
        self.facing_right = True
        self.dead = False
        self._death_timer = 0.0
        self._airtime = 0.0

        self.frame_index = 0.0
        self.image = self.animations[self.state][0]
        self.rect = self.image.get_rect(topleft=(int(x), int(y)))

        self.scale_x = 1.0
        self.scale_y = 1.0
        self._squash_timer = 0.0
        self._stretch_timer = 0.0

    def rescale(self, new_scale: float) -> None:
        self.current_scale = new_scale
        self.animations = _build_animations(
            self.sprite_dir, self.sprite_prefix, new_scale, self.outline_color
        )
        self.image = self.animations[self.state][int(self.frame_index)]
        old_center = self.rect.center
        self.rect = self.image.get_rect(center=old_center)
        self.pos.x = float(self.rect.x)
        self.pos.y = float(self.rect.y)

    def respawn(self, x: float, y: float) -> None:
        self.dead = False
        self._death_timer = 0.0
        self._airtime = 0.0
        self.pos.x = x
        self.pos.y = y
        self.rect.x = int(x)
        self.rect.y = int(y)
        self.velocity.x = 0
        self.velocity.y = 0
        self.state = "idle"
        self.frame_index = 0.0

    def handle_input(self, action: Action) -> None:
        """Apply an Action to intent/velocity; providers never manipulate physics."""
        self.last_action = action
        self.acceleration.x = 0

        if action.left and not action.right:
            self.acceleration.x = -PLAYER_ACCELERATION
            self.facing_right = False
        elif action.right and not action.left:
            self.acceleration.x = PLAYER_ACCELERATION
            self.facing_right = True

        if action.jump:
            if self.in_water:
                self.velocity.y = PLAYER_JUMP_FORCE * WATER_JUMP_MOD
            elif self.on_stairs:
                self.velocity.y = PLAYER_JUMP_FORCE * STAIRS_JUMP_MOD
                self.on_stairs = False
            elif self.on_ground:
                self.velocity.y = PLAYER_JUMP_FORCE
                self.on_ground = False
                self.has_double_jump = True
                self._stretch_timer = STRETCH_DURATION
                self._squash_timer = 0.0
            elif self.has_double_jump and self._near_apex():
                self.velocity.y = PLAYER_JUMP_FORCE
                self.has_double_jump = False
                self._stretch_timer = STRETCH_DURATION
                self._squash_timer = 0.0

        if action.down:
            if self.on_ground and not self.on_stairs:
                self.dropping_through = True
            elif not self.on_ground:
                self.velocity.y += PLAYER_FAST_FALL
        else:
            self.dropping_through = False

    def update(
        self,
        dt: float,
        collision_rects: list[pygame.Rect],
        water_rects: list[pygame.Rect],
        stairs_rects: list[pygame.Rect] | None = None,
        lava_rects: list[pygame.Rect] | None = None,
        platform_rects: list[pygame.Rect] | None = None,
        breakable_rects: list[pygame.Rect] | None = None,
        action: Action | None = None,
    ) -> None:
        dt = min(dt, 1 / 30)
        if self.dead:
            self._death_timer += dt
            self._animate_death(dt)
            return

        self.in_water = any(self.rect.colliderect(w) for w in water_rects)
        self.in_lava = any(self.rect.colliderect(lv) for lv in (lava_rects or []))
        self.on_stairs = any(self.rect.colliderect(s) for s in (stairs_rects or []))
        speed_mod = WATER_SPEED_MOD if self.in_water else 1.0
        gravity_mod = WATER_GRAVITY_MOD if self.in_water else 1.0

        action = action if action is not None else self.action_provider.get_action(None)
        self.handle_input(action)

        if self.on_stairs:
            if action.jump:
                self.velocity.y = -PLAYER_MAX_SPEED * STAIRS_CLIMB_SPEED
            elif action.down:
                self.velocity.y = PLAYER_MAX_SPEED * STAIRS_DESCEND_SPEED
            else:
                self.velocity.y *= STAIRS_FRICTION
            gravity_mod = 0.0

        self.velocity.x += self.acceleration.x * speed_mod * dt
        self.velocity.x -= self.velocity.x * PLAYER_FRICTION * dt

        max_speed = PLAYER_MAX_SPEED * speed_mod
        if abs(self.velocity.x) > max_speed:
            self.velocity.x = max_speed if self.velocity.x > 0 else -max_speed

        if abs(self.velocity.x) < VELOCITY_DEAD_ZONE:
            self.velocity.x = 0

        self.pos.x += self.velocity.x * dt
        self.rect.x = int(self.pos.x)
        self._collide_x(collision_rects)

        self.velocity.y += PLAYER_GRAVITY * gravity_mod * dt

        if self.in_water:
            max_fall = PLAYER_MAX_SPEED * WATER_MAX_FALL_MOD
            if self.velocity.y > max_fall:
                self.velocity.y = max_fall

        prev_bottom = self.rect.bottom
        self.pos.y += self.velocity.y * dt
        self.rect.y = int(self.pos.y)
        self._collide_y(collision_rects)

        if not self.dropping_through:
            self._collide_platforms(platform_rects or [], prev_bottom)
            self._collide_platforms(breakable_rects or [], prev_bottom)

        self._check_ground(collision_rects)
        if not self.dropping_through:
            self._check_ground(platform_rects or [])
            self._check_ground(breakable_rects or [])

        self.just_landed = self.on_ground and self.was_airborne
        landed_airtime = self._airtime
        if not self.on_ground and self.velocity.y > 0:
            self._airtime += dt
        elif not self.just_landed:
            self._airtime = 0.0
        self.was_airborne = not self.on_ground

        if self.just_landed:
            if landed_airtime >= FALL_DEATH_AIRTIME and not self.in_water:
                self.dead = True
                self._death_timer = 0.0
                self.state = "die"
                self.frame_index = 0.0
            self._airtime = 0.0
            self._squash_timer = SQUASH_DURATION
            self._stretch_timer = 0.0

        self._update_squash_stretch(dt)
        self._animate(dt)

    def _animate_death(self, dt: float) -> None:
        frames = self.animations["die"]
        self.frame_index += dt / (PLAYER_ANIMATION_SPEED * DEATH_ANIM_SPEED_MOD)
        if self.frame_index >= len(frames):
            self.frame_index = len(frames) - 1
        frame = frames[int(self.frame_index)]
        self.image = pygame.transform.flip(frame, True, False) if not self.facing_right else frame

    @property
    def death_complete(self) -> bool:
        return self.dead and self._death_timer >= DEATH_ANIM_DURATION

    def _update_squash_stretch(self, dt: float) -> None:
        if self._squash_timer > 0:
            t = 1.0 - (self._squash_timer / SQUASH_DURATION)
            self.scale_x = lerp(STRETCH_FACTOR, 1.0, t)
            self.scale_y = lerp(SQUASH_FACTOR, 1.0, t)
            self._squash_timer -= dt
        elif self._stretch_timer > 0:
            t = 1.0 - (self._stretch_timer / STRETCH_DURATION)
            self.scale_x = lerp(SQUASH_FACTOR, 1.0, t)
            self.scale_y = lerp(STRETCH_FACTOR, 1.0, t)
            self._stretch_timer -= dt
        else:
            self.scale_x = 1.0
            self.scale_y = 1.0

    def _collide_x(self, rects: list[pygame.Rect]) -> None:
        for wall in rects:
            if self.rect.colliderect(wall):
                if self.velocity.x > 0:
                    self.rect.right = wall.left
                elif self.velocity.x < 0:
                    self.rect.left = wall.right
                self.pos.x = float(self.rect.x)
                self.velocity.x = 0

    def _collide_y(self, rects: list[pygame.Rect]) -> None:
        self.on_ground = False
        for wall in rects:
            if self.rect.colliderect(wall):
                if self.velocity.y > 0:
                    self.rect.bottom = wall.top
                    self.on_ground = True
                    self.has_double_jump = False
                elif self.velocity.y < 0:
                    self.rect.top = wall.bottom
                self.pos.y = float(self.rect.y)
                self.velocity.y = 0

    def _collide_platforms(self, rects: list[pygame.Rect], prev_bottom: int) -> None:
        for plat in rects:
            if not self.rect.colliderect(plat):
                continue
            # Only collide if falling AND player was above the platform top before this frame
            if self.velocity.y > 0 and prev_bottom <= plat.top + 4:
                self.rect.bottom = plat.top
                self.on_ground = True
                self.has_double_jump = False
                self.pos.y = float(self.rect.y)
                self.velocity.y = 0

    def _check_ground(self, rects: list[pygame.Rect]) -> None:
        if self.on_ground:
            return
        probe = pygame.Rect(self.rect.x, self.rect.y + 4, self.rect.width, self.rect.height)
        for wall in rects:
            if probe.colliderect(wall) and self.velocity.y >= 0:
                self.on_ground = True
                return

    def _near_apex(self) -> bool:
        threshold = abs(PLAYER_JUMP_FORCE) * 0.2
        return abs(self.velocity.y) <= threshold

    def _get_state(self) -> str:
        if not self.on_ground:
            return "jump"
        if abs(self.velocity.x) > VELOCITY_DEAD_ZONE:
            return "walk"
        return "idle"

    def _animate(self, dt: float) -> None:
        new_state = self._get_state()
        if new_state != self.state:
            self.state = new_state
            self.frame_index = 0.0

        anim_speed = PLAYER_ANIMATION_SPEED
        if self.in_water:
            anim_speed *= WATER_ANIM_MOD

        frames = self.animations[self.state]
        self.frame_index += dt / anim_speed
        if self.frame_index >= len(frames):
            self.frame_index = 0.0

        frame = frames[int(self.frame_index)]
        self.image = pygame.transform.flip(frame, True, False) if not self.facing_right else frame

    def draw(
        self,
        surface: pygame.Surface,
        camera_offset: tuple[int, int] = (0, 0),
        show_nametag: bool = False,
    ) -> None:
        ox, oy = camera_offset
        if self.scale_x != 1.0 or self.scale_y != 1.0:
            w, h = self.image.get_size()
            new_w = int(w * self.scale_x)
            new_h = int(h * self.scale_y)
            scaled = pygame.transform.scale(self.image, (new_w, new_h))
            anchor = (self.rect.midbottom[0] - ox, self.rect.midbottom[1] - oy)
            draw_rect = scaled.get_rect(midbottom=anchor)
            surface.blit(scaled, draw_rect)
        else:
            surface.blit(self.image, (self.rect.x - ox, self.rect.y - oy))

        if show_nametag and self.name:
            self._draw_nametag(surface, ox, oy)

    def _draw_nametag(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        if Player._nametag_font is None:
            Player._nametag_font = get_font(NAMETAG_SIZE)

        display_name = self.name
        while len(display_name) > 1 and Player._nametag_font.size(display_name)[0] > 220:
            display_name = display_name[:-1]
        if display_name != self.name:
            display_name += "…"
        tag = Player._nametag_font.render(display_name, True, NAMETAG_COLOR)
        tag_rect = tag.get_rect(
            midbottom=(self.rect.centerx - ox, self.rect.top - NAMETAG_OFFSET_Y - oy)
        )
        surface.blit(tag, tag_rect)
