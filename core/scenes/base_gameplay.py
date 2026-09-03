import math
from enum import Enum, auto

import pygame

from core.ai.actions import Action
from core.ai.graph import PlatformGraphExtractor
from core.ai.observation import from_scene

from core.camera import SplitScreen
from core.config.constants import (
    BASE_MAP_SCALE,
    BG_COLOR,
    DEATH_ANIM_DURATION,
    DEATH_FLASH_COLOR,
    DEATH_FLASH_MAX_ALPHA,
    LANDING_SHAKE_DURATION,
    LANDING_SHAKE_INTENSITY,
    LAVA_COUNTDOWN_COLOR,
    LAVA_COUNTDOWN_SIZE,
    LAVA_DEATH_SHAKE_DURATION,
    LAVA_DEATH_SHAKE_INTENSITY,
    LAVA_DEATH_TIME,
    LAVA_DECAY_RATE,
    LAVA_JOLT_BASE_INTENSITY,
    LAVA_JOLT_DURATION,
    LAVA_JOLT_INTERVAL,
    LAVA_JOLT_MULTIPLIER,
    LAVA_VIGNETTE_COLOR,
    LAVA_VIGNETTE_MAX_ALPHA,
    PLAYER_SCALE,
    PLAYER_SPAWN_OFFSET,
    SCALE_EPSILON,
    SIGN_DIALOG_Y_RATIO,
)
from core.config.levels import LEVELS
from core.doors import CoopDoorManager, DoorManager
from core.fonts import get_font
from core.hud import ZoneAnnouncement
from core.interactable import BreakableManager, PressurePlateManager, SignDialog, SignManager
from core.localization import t
from core.map_loader import TMXMap
from core.moving_platform import MovingPlatformManager
from core.player import Player
from core.portal import Portal
from core.resource import resource_path
from core.scene import Scene, SceneManager
from core.text import render_multiline
from core.tutorial import TutorialManager
from core.vfx import VFXAnimation, load_vfx_frames


ENDING_DELAY = 1.0
ENDING_NARRATION = [
    (0.998, 4.881, "ending.01"),
    (6.621, 9.303, "ending.02"),
    (9.304, 12.815, "ending.03"),
    (12.816, 15.257, "ending.04"),
]
ENDING_TYPEWRITER_SPEED = 30
ENDING_BYE_DELAY = 2.0
ENDING_BYE_NARRATION = [
    (0.0, 1.2, "ending.thanks"),
    (1.2, 2.3, "ending.goodnight"),
]
ENDING_MUSIC_DUCK = 0.12
ENDING_TEXT_COLOR = (210, 190, 150)
ENDING_GLOW_COLOR = (180, 150, 100)
ENDING_PREV_COLOR = (100, 85, 60)
ENDING_FINAL_COLOR = (230, 210, 170)
SUCCESS_PAGE_DURATION = 2.5


class FinaleState(Enum):
    PLAYING = auto()
    SUCCESS = auto()
    FADING = auto()
    NARRATION = auto()
    RETURNING = auto()


class FloatingText:
    """Wavy floating text rendered in world space."""

    WAVE_SPEED = 4.0
    WAVE_AMPLITUDE = 3.0
    WAVE_SPACING = 0.3
    FADE_SPEED = 3.0

    def __init__(self, text: str, world_pos: tuple[float, float], font_size: int = 16) -> None:
        self.text = text
        self.world_x, self.world_y = world_pos
        self.font = get_font(font_size)
        self.alpha = 0.0
        self.time = 0.0
        self.active = False

    def update(self, dt: float) -> None:
        self.time += dt
        if self.active:
            self.alpha = min(self.alpha + self.FADE_SPEED * dt, 1.0)
        else:
            self.alpha = max(self.alpha - self.FADE_SPEED * dt, 0.0)

    def draw(self, surface: pygame.Surface, cam_offset: tuple[int, int]) -> None:
        if self.alpha < 0.01:
            return

        screen_x = self.world_x - cam_offset[0]
        screen_y = self.world_y - cam_offset[1]

        chars = list(self.text)
        total_width = sum(self.font.size(c)[0] for c in chars)
        x = screen_x - total_width // 2
        a = int(self.alpha * 255)

        for i, char in enumerate(chars):
            wave_y = (
                math.sin(self.time * self.WAVE_SPEED + i * self.WAVE_SPACING) * self.WAVE_AMPLITUDE
            )
            char_surf = self.font.render(char, True, (255, 255, 255))
            char_surf.set_alpha(a)
            surface.blit(char_surf, (x, screen_y + wave_y))
            x += self.font.size(char)[0]


class BaseGameplay(Scene):
    def __init__(self, manager: SceneManager, level_id: str = "tutorial_001") -> None:
        super().__init__(manager)
        self.level_id = level_id
        level = LEVELS[level_id]

        self.map = TMXMap(str(resource_path(level["map"])), zoom=level.get("zoom"))

        from core.audio import play_music

        play_music(level_id)

        spawn_a = self.map.get_spawn("A")
        spawn_b = self.map.get_spawn("B")
        self.spawn_x = spawn_a[0] if spawn_a else self.map.offset[0] + self.map.scaled_size[0] // 2
        self.spawn_y = spawn_a[1] if spawn_a else self.map.offset[1] + self.map.scaled_size[1] // 2
        self.spawn_b_x = spawn_b[0] if spawn_b else self.spawn_x
        self.spawn_b_y = spawn_b[1] if spawn_b else self.spawn_y
        self.checkpoints = [
            (self.spawn_x, self.spawn_y),
            (self.spawn_b_x, self.spawn_b_y),
        ]

        self.players: list[Player] = []  # subclass fills this

        self.landing_frames = load_vfx_frames(
            str(resource_path("assets/vfx/landing")), scale=self.map.scale
        )
        self.vfx_list: list[VFXAnimation] = []
        self.split_screen = SplitScreen()
        self.zone_announcement = ZoneAnnouncement(level["zone_subtitle"], level["zone_title"])

        all_rects = list(self.map.sign_rects)
        all_texts = dict(level.get("signs", {}))

        npc_config = level.get("npcs", {})
        for layer_name, rect in self.map.npc_rects:
            npc_texts = npc_config.get(layer_name, {})
            # Count how many of this NPC type we've seen
            count = sum(1 for n, _ in self.map.npc_rects if n == layer_name)
            idx_in_layer = sum(1 for r in all_rects if r == rect) if count > 1 else 0
            text = npc_texts.get(idx_in_layer, "...")
            all_texts[len(all_rects)] = text
            all_rects.append(rect)

        self.sign_manager = SignManager(all_rects, all_texts)
        self.sign_dialogs = [SignDialog(), SignDialog()]

        self.pressure_plates = PressurePlateManager(self.map.pressure_rects, self.map.scale)
        self.breakables = BreakableManager(self.map.get_layer_tiles("BrakablePlatform"))

        self.door_manager = DoorManager(
            self.map.get_layer_tiles("Door"),
            self.map.door_pressure_rects,
            self.map.scale,
            self.map.mechanism_specs,
        )

        self.coop_doors = CoopDoorManager(
            self.map.get_layer_tiles("SecondDoor"),
            self.map.second_door_pressure_rects,
            self.map.scale,
        )

        self.moving_platforms = MovingPlatformManager(
            self.map.get_layer_tiles("MovingPlatforms"),
            self.map.moving_platform_points,
        )
        self.platform_graph = PlatformGraphExtractor(self.map, self.moving_platforms).extract()
        self.final_exit_rects = self.map.final_exit_rects
        self.final_exit_entered = [False, False]
        self.finale_state = FinaleState.PLAYING
        self._success_timer = 0.0
        self._success_title_font: pygame.font.Font | None = None
        self._success_body_font: pygame.font.Font | None = None

        portal_rects = self.map.portal_rects
        self.portal: Portal | None = None
        if portal_rects:
            self.portal = Portal(portal_rects[0], self.map.scale)
        self.next_level = level.get("next_level")
        self._portal_activated = False
        self._lava_timers = [0.0, 0.0]
        self._death_flash = [0.0, 0.0]
        self._on_platform_timer = 0.0  # hysteresis for platform music
        self._idle_timer = 0.0
        self._idle_stage = 0  # 0=waiting, 1=still played, 2=still_2 played
        self._players_moved = False
        self._voice_channel: pygame.mixer.Channel | None = None

        self.tutorial: TutorialManager | None = None
        if level.get("tutorial"):
            self.tutorial = TutorialManager(level.get("tutorial"))

        jump_rects = self.map.jump_rects
        self._jump_text: FloatingText | None = None
        if jump_rects:
            r = jump_rects[0]
            self._jump_text = FloatingText(t("world.jump"), (r.centerx, r.top - 50), font_size=32)

        self._limit_rects = self.map.limit_rects
        self._fade_to_black = 0.0
        self._limit_triggered = False
        self._ending_timer = 0.0
        self._ending_voice_started = False
        self._ending_audio_timer = 0.0
        self._ending_sub_idx = -1
        self._ending_prev_idx = -1
        self._ending_phase = 0  # 0=nights, 1=pause, 2=bye, 3=linger
        self._ending_bye_timer = 0.0
        self._ending_bye_idx = -1
        self._ending_bye_prev_idx = -1
        self._ending_linger = 0.0
        self._ending_font: pygame.font.Font | None = None
        self._ending_prev_font: pygame.font.Font | None = None
        self._ending_big_font: pygame.font.Font | None = None

    def _sync_player_scales(self) -> None:
        new_scale = PLAYER_SCALE * (self.map.scale / BASE_MAP_SCALE)
        for p in self.players:
            if abs(new_scale - p.current_scale) > SCALE_EPSILON:
                p.rescale(new_scale)

    def _base_resize(self, width: int, height: int) -> None:
        old_scale = self.map.scale
        old_offset = self.map.offset
        self.map.rescale((width, height))

        for p in self.players:
            rel_x = (p.pos.x - old_offset[0]) / old_scale
            rel_y = (p.pos.y - old_offset[1]) / old_scale
            p.pos.x = rel_x * self.map.scale + self.map.offset[0]
            p.pos.y = rel_y * self.map.scale + self.map.offset[1]
            p.rect.x = int(p.pos.x)
            p.rect.y = int(p.pos.y)
        self.checkpoints = [
            (
                (x - old_offset[0]) / old_scale * self.map.scale + self.map.offset[0],
                (y - old_offset[1]) / old_scale * self.map.scale + self.map.offset[1],
            )
            for x, y in self.checkpoints
        ]

        self._sync_player_scales()
        self.landing_frames = load_vfx_frames(
            str(resource_path("assets/vfx/landing")), scale=self.map.scale
        )
        self.vfx_list.clear()

        all_rects = list(self.map.sign_rects)
        for _layer_name, rect in self.map.npc_rects:
            all_rects.append(rect)
        self.sign_manager = SignManager(all_rects, self.sign_manager._texts)
        self.sign_dialogs = [SignDialog(), SignDialog()]
        self.pressure_plates = PressurePlateManager(self.map.pressure_rects, self.map.scale)
        self.breakables = BreakableManager(self.map.get_layer_tiles("BrakablePlatform"))
        door_latched = set(self.door_manager._latched)
        door_open_ratios = [
            door.open_amount / door.max_displacement if door.max_displacement else 0.0
            for door in self.door_manager.doors
        ]
        self.door_manager = DoorManager(
            self.map.get_layer_tiles("Door"),
            self.map.door_pressure_rects,
            self.map.scale,
            self.map.mechanism_specs,
        )
        self.door_manager._latched = door_latched
        for door, ratio in zip(self.door_manager.doors, door_open_ratios, strict=False):
            door.open_amount = ratio * door.max_displacement
            door.set_open(door.door_id in {
                self.door_manager.doors[self.door_manager.plate_door_map[pi]].door_id
                for pi in door_latched if pi in self.door_manager.plate_door_map
            })
            door.update(0.0)
        coop_was_opened = self.coop_doors._opened
        self.coop_doors = CoopDoorManager(
            self.map.get_layer_tiles("SecondDoor"),
            self.map.second_door_pressure_rects,
            self.map.scale,
        )
        self.coop_doors._opened = coop_was_opened
        self.moving_platforms = MovingPlatformManager(
            self.map.get_layer_tiles("MovingPlatforms"),
            self.map.moving_platform_points,
        )
        self.platform_graph = PlatformGraphExtractor(self.map, self.moving_platforms).extract()
        self.final_exit_rects = self.map.final_exit_rects

        spawn_a = self.map.get_spawn("A")
        spawn_b = self.map.get_spawn("B")
        self.spawn_x = spawn_a[0] if spawn_a else self.map.offset[0] + self.map.scaled_size[0] // 2
        self.spawn_y = spawn_a[1] if spawn_a else self.map.offset[1] + self.map.scaled_size[1] // 2
        self.spawn_b_x = spawn_b[0] if spawn_b else self.spawn_x
        self.spawn_b_y = spawn_b[1] if spawn_b else self.spawn_y

        jump_rects = self.map.jump_rects
        if jump_rects and self._jump_text:
            r = jump_rects[0]
            self._jump_text.world_x = r.centerx
            self._jump_text.world_y = r.top - 50
        self._limit_rects = self.map.limit_rects

        portal_was_active = self.portal.is_active if self.portal else False
        portal_rects = self.map.portal_rects
        if portal_rects:
            new_portal = Portal(portal_rects[0], self.map.scale)
            if portal_was_active:
                new_portal.state = self.portal.state
                new_portal.frame_index = self.portal.frame_index
                new_portal.p1_entered = self.portal.p1_entered
                new_portal.p2_entered = self.portal.p2_entered
            self.portal = new_portal

    def on_resize(self, width: int, height: int) -> None:
        self._base_resize(width, height)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            from core.scenes.pause import Pause

            self.manager.push(Pause(self.manager))
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
            overlay = getattr(self, "ai_overlay", None)
            if overlay:
                overlay.toggle()

    def _respawn_player(self, index: int, player: Player) -> None:
        player.respawn(*self.checkpoints[index])
        self._lava_timers[index] = 0.0

    def _update_checkpoint(self, index: int, player: Player) -> None:
        if self.level_id != "level_002" or not player.on_ground or player.dead:
            return
        if player.in_lava or player.in_water:
            return
        # Progress-only checkpoints never move backwards and avoid door bodies.
        if player.pos.x <= self.checkpoints[index][0] + 80:
            return
        if any(player.rect.colliderect(rect.inflate(12, 8)) for rect in self.map.door_rects + self.map.second_door_rects):
            return
        self.checkpoints[index] = (player.pos.x, player.pos.y)

    def _update_player(self, i: int, p: Player, dt: float) -> None:
        if self.portal and self.portal.should_hide_player(i):
            return
        if p.dead:
            p.update(dt, self.map.collision_rects, self.map.water_rects, action=Action())
            if p.death_complete:
                self._respawn_player(i, p)
                self._death_flash[i] = 0.0
            return

        observation = from_scene(self)
        provider = p.action_provider
        action = provider.tick(dt, observation) if hasattr(provider, "tick") else provider.get_action(observation)
        if hasattr(provider, "consume_reset_request") and provider.consume_reset_request():
            self._respawn_player(i, p)
            return

        collision = (
            self.map.collision_rects
            + self.door_manager.collision_rects()
            + self.coop_doors.collision_rects()
        )
        platforms = self.map.platform_rects + self.moving_platforms.rects()
        p.update(
            dt,
            collision,
            self.map.water_rects,
            stairs_rects=self.map.stairs_rects,
            lava_rects=self.map.lava_rects,
            platform_rects=platforms,
            breakable_rects=self.breakables.active_rects(),
            action=action,
        )

        if p.in_lava:
            self._lava_timers[i] += dt
            if int(self._lava_timers[i] / LAVA_JOLT_INTERVAL) != int(
                (self._lava_timers[i] - dt) / LAVA_JOLT_INTERVAL
            ):
                intensity = LAVA_JOLT_BASE_INTENSITY + self._lava_timers[i] * LAVA_JOLT_MULTIPLIER
                self.split_screen.shake_all(intensity, LAVA_JOLT_DURATION)
            if self._lava_timers[i] >= LAVA_DEATH_TIME:
                self._respawn_player(i, p)
                self._lava_timers[i] = 0.0
                self.split_screen.shake_all(LAVA_DEATH_SHAKE_INTENSITY, LAVA_DEATH_SHAKE_DURATION)
                if self._should_play_sfx(i):
                    from core.audio import play_sfx

                    play_sfx("error")
        else:
            self._lava_timers[i] = max(self._lava_timers[i] - dt * LAVA_DECAY_RATE, 0.0)

        map_bottom = self.map.offset[1] + self.map.scaled_size[1] + 200
        if p.pos.y > map_bottom and not p.dead:
            self._respawn_player(i, p)
            self.split_screen.shake_all(6.0, 0.2)

        if p.dead and p._death_timer < dt * 2:
            self._death_flash[i] = DEATH_ANIM_DURATION
            self.split_screen.shake_all(10.0, 0.3)
            if self._should_play_sfx(i):
                from core.audio import play_sfx

                play_sfx("impact")
        if p.death_complete:
            self._respawn_player(i, p)
            self._death_flash[i] = 0.0
        if self._death_flash[i] > 0:
            self._death_flash[i] = max(self._death_flash[i] - dt, 0.0)

        self._update_checkpoint(i, p)

        if p.just_landed and self.landing_frames and not p.in_water:
            self.vfx_list.append(VFXAnimation(self.landing_frames, p.rect.centerx, p.rect.bottom))
            self.split_screen.shake_all(LANDING_SHAKE_INTENSITY, LANDING_SHAKE_DURATION)

    def _update_world(self, dt: float) -> None:
        """Update world systems BEFORE player physics so positions are current."""
        self.moving_platforms.update(dt, self.players)
        self.door_manager.update(dt, *(p.rect for p in self.players))
        self.coop_doors.update(dt, [p.rect for p in self.players])

        from core.audio import play_music

        on_platform = False
        for p in self.players:
            probe = pygame.Rect(p.rect.x, p.rect.y, p.rect.width, p.rect.height + 6)
            if any(probe.colliderect(mr) for mr in self.moving_platforms.rects()):
                on_platform = True
                break

        if on_platform:
            self._on_platform_timer = 0.5
        elif self._on_platform_timer > 0:
            self._on_platform_timer -= dt

        if self._on_platform_timer > 0 and self.moving_platforms.platforms:
            play_music("moving_platform", fade_ms=800)
        else:
            play_music(self.level_id, fade_ms=800)

    def _update_shared(self, dt: float) -> None:
        for vfx in self.vfx_list:
            vfx.update(dt)
        self.vfx_list = [v for v in self.vfx_list if not v.finished]

        self.breakables.update(dt, *(p.rect for p in self.players))
        self.pressure_plates.update(dt, *(p.rect for p in self.players))

        if self.portal:
            all_pressed = all(p.activated for p in self.pressure_plates.plates)
            if all_pressed and not self._portal_activated:
                self.portal.activate()
                self._portal_activated = True
            self.portal.update(dt, self.players[0].rect, self.players[1].rect)

            if self.portal.is_done:
                self._on_level_complete()
                return

        if self.final_exit_rects and self.finale_state == FinaleState.PLAYING:
            for i, player in enumerate(self.players):
                target = self.final_exit_rects[min(i, len(self.final_exit_rects) - 1)]
                self.final_exit_entered[i] = target.colliderect(player.rect)
            if all(self.final_exit_entered):
                self._start_success()
        elif self.finale_state == FinaleState.SUCCESS:
            self._success_timer += dt
            if self._success_timer >= SUCCESS_PAGE_DURATION:
                self._start_ending()

        if self.portal and (self.portal.p1_entered or self.portal.p2_entered):
            remaining = self.players[1] if self.portal.p1_entered else self.players[0]
            self.split_screen.update(dt, remaining.rect, remaining.rect)
        else:
            self.split_screen.update(dt, self.players[0].rect, self.players[1].rect)

        if self.zone_announcement and not self.zone_announcement.finished:
            self.zone_announcement.update(dt)

        for i, p in enumerate(self.players):
            text = self.sign_manager.get_active_text(p.rect)
            if text:
                self.sign_dialogs[i].show(text)
            else:
                self.sign_dialogs[i].hide()
            self.sign_dialogs[i].update(dt)

        if self.tutorial and len(self.players) >= 2:
            self.tutorial.update(dt, self.players[0], self.players[1])

        if self._jump_text:
            self._jump_text.active = True
            self._jump_text.update(dt)

        if self._limit_rects and not self._limit_triggered:
            for p in self.players:
                if any(p.rect.colliderect(r) for r in self._limit_rects):
                    self._limit_triggered = True
                    from core.config.game_settings import settings as gs

                    pygame.mixer.music.set_volume(gs.music_volume * ENDING_MUSIC_DUCK)
                    break

        if self._limit_triggered:
            self._fade_to_black = min(self._fade_to_black + dt * 1.5, 1.0)
            if self._fade_to_black >= 1.0:
                self._ending_timer += dt
                self._update_ending_sequence(dt)

        if not self._players_moved:
            anyone_moving = any(abs(p.velocity.x) > 10 for p in self.players)
            if anyone_moving:
                self._players_moved = True
            else:
                self._idle_timer += dt
                if self._idle_stage == 0 and self._idle_timer >= 30.0:
                    self._idle_stage = 1
                    self._play_voice("assets/audio/cues/idle_first.wav")
                elif self._idle_stage == 1 and self._idle_timer >= 120.0:
                    self._idle_stage = 2
                    self._play_voice("assets/audio/cues/idle_second.wav")

        if self._voice_channel and not self._voice_channel.get_busy():
            self._voice_channel = None
            from core.config.game_settings import settings as gs

            pygame.mixer.music.set_volume(gs.music_volume)

    def _start_success(self) -> None:
        if self.finale_state != FinaleState.PLAYING:
            return
        self.finale_state = FinaleState.SUCCESS
        self._success_timer = 0.0
        for player in self.players:
            player.velocity.update(0, 0)

    def _start_ending(self) -> None:
        if self.finale_state not in {FinaleState.PLAYING, FinaleState.SUCCESS}:
            return
        self.finale_state = FinaleState.FADING
        self._limit_triggered = True
        from core.config.game_settings import settings as gs

        pygame.mixer.music.set_volume(gs.music_volume * ENDING_MUSIC_DUCK)

    def _update_ending_sequence(self, dt: float) -> None:
        if self._ending_phase < 4:
            self.finale_state = FinaleState.NARRATION
        # Phase 0: play ending voice with localized subtitles
        if self._ending_phase == 0:
            if self._ending_timer >= ENDING_DELAY and not self._ending_voice_started:
                self._ending_voice_started = True
                self._play_voice("assets/audio/cues/ending.wav")

            if self._ending_voice_started:
                self._ending_audio_timer += dt
                old_idx = self._ending_sub_idx
                self._ending_sub_idx = -1
                for i, (start, end, _) in enumerate(ENDING_NARRATION):
                    if start <= self._ending_audio_timer <= end + 0.3:
                        self._ending_sub_idx = i
                if self._ending_sub_idx != old_idx and old_idx >= 0:
                    self._ending_prev_idx = old_idx

                last_end = ENDING_NARRATION[-1][1]
                if self._ending_audio_timer > last_end + 1.5:
                    self._ending_phase = 1
                    self._ending_bye_timer = 0.0

        # Phase 1: pause between voices
        elif self._ending_phase == 1:
            self._ending_bye_timer += dt
            if self._ending_bye_timer >= ENDING_BYE_DELAY:
                self._ending_phase = 2
                self._ending_bye_timer = 0.0
                self._play_voice("assets/audio/cues/goodnight.wav")

        # Phase 2: play bye.mp3 with subtitles
        elif self._ending_phase == 2:
            self._ending_bye_timer += dt
            old_idx = self._ending_bye_idx
            self._ending_bye_idx = -1
            for i, (start, end, _) in enumerate(ENDING_BYE_NARRATION):
                if start <= self._ending_bye_timer <= end + 0.5:
                    self._ending_bye_idx = i
            if self._ending_bye_idx != old_idx and old_idx >= 0:
                self._ending_bye_prev_idx = old_idx

            if self._ending_bye_timer > ENDING_BYE_NARRATION[-1][1] + 0.5:
                self._ending_phase = 3
                self._ending_linger = 0.0

        # Phase 3: "Good night." lingers, then fade music and return to menu
        elif self._ending_phase == 3:
            self._ending_linger += dt
            if self._ending_linger > 2.0:
                from core.audio import stop_music

                stop_music(fade_ms=3000)
                self._ending_phase = 4
                self.finale_state = FinaleState.RETURNING

        elif self._ending_phase == 4:
            self._ending_linger += dt
            if self._ending_linger > 6.0:
                from core.scenes.main_menu import MainMenu

                self.manager.replace(MainMenu(self.manager))

    def _play_voice(self, relative_path: str) -> None:
        from core.config.game_settings import settings
        from core.resource import resource_path

        path = resource_path(relative_path)
        if not path.exists():
            return

        pygame.mixer.music.set_volume(settings.music_volume * 0.15)

        sound = pygame.mixer.Sound(path)
        sound.set_volume(settings.sfx_volume)
        self._voice_channel = sound.play()

    def _on_level_complete(self) -> None:
        """Override in subclass for level transition behavior."""
        from core.scenes.main_menu import MainMenu

        self.manager.replace(MainMenu(self.manager))

    def _draw_world(
        self,
        surface: pygame.Surface,
        cam_offset: tuple[int, int],
        view_size: tuple[int, int],
    ) -> None:
        surface.fill(BG_COLOR)
        self.map.draw(surface, cam_offset)
        self.breakables.draw(surface, cam_offset)
        self.moving_platforms.draw(surface, cam_offset)
        self.door_manager.draw(surface, cam_offset)
        self.coop_doors.draw(surface, cam_offset)
        self.pressure_plates.draw(surface, cam_offset)
        if self.portal:
            self.portal.draw(surface, cam_offset)
        for i, exit_rect in enumerate(self.final_exit_rects):
            color = (100, 220, 150) if i == 0 else (235, 155, 80)
            draw_rect = exit_rect.move(-cam_offset[0], -cam_offset[1])
            pygame.draw.rect(surface, color, draw_rect, max(2, int(self.map.scale)), border_radius=5)
            pygame.draw.line(surface, color, draw_rect.midtop, draw_rect.midbottom, 2)
        for i, p in enumerate(self.players):
            if self.portal and self.portal.should_hide_player(i):
                continue
            if not self._should_draw_player(i):
                continue
            p.draw(surface, cam_offset, show_nametag=self._show_nametag(i))
        for vfx in self.vfx_list:
            vfx.draw(surface, cam_offset)
        if self.tutorial:
            for i, p in enumerate(self.players):
                if self.portal and self.portal.should_hide_player(i):
                    continue
                self.tutorial.draw_for_player(surface, i, p.rect, cam_offset)
        if self._jump_text:
            self._jump_text.draw(surface, cam_offset)

    def _should_draw_player(self, index: int) -> bool:
        return True

    def _show_nametag(self, index: int) -> bool:
        return True

    def _should_play_sfx(self, player_index: int) -> bool:
        """Override in network gameplay to only play SFX for local player."""
        return True

    def _draw_player_hud(
        self, surface: pygame.Surface, player_index: int, center: tuple[int, int]
    ) -> None:
        sw, sh = surface.get_size()
        cx, cy = center

        flash = self._death_flash[player_index]
        if flash > 0.01:
            alpha = int(DEATH_FLASH_MAX_ALPHA * (flash / DEATH_ANIM_DURATION))
            overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
            overlay.fill((*DEATH_FLASH_COLOR, alpha))
            surface.blit(overlay, (0, 0))

        lava_t = self._lava_timers[player_index]
        if lava_t > 0.01:
            progress = min(lava_t / LAVA_DEATH_TIME, 1.0)
            alpha = int(LAVA_VIGNETTE_MAX_ALPHA * progress)
            vignette = pygame.Surface((sw, sh), pygame.SRCALPHA)
            vignette.fill((*LAVA_VIGNETTE_COLOR, alpha))
            surface.blit(vignette, (0, 0))

            from core.gui import Label

            remaining = max(0, LAVA_DEATH_TIME - lava_t)
            countdown = Label(
                f"{remaining:.1f}", size=LAVA_COUNTDOWN_SIZE, color=LAVA_COUNTDOWN_COLOR
            )
            countdown.draw(surface, cx, cy)

        self.sign_dialogs[player_index].draw_at(surface, cx, int(sh * SIGN_DIALOG_Y_RATIO))

    def _ending_glow(
        self, surface: pygame.Surface, text_surf: pygame.Surface, pos: tuple[int, int], alpha: float
    ) -> None:
        """Draw a soft glow behind text for warmth."""
        gw = text_surf.get_width() + 20
        gh = text_surf.get_height() + 12
        glow = pygame.Surface((gw, gh), pygame.SRCALPHA)
        glow.fill((*ENDING_GLOW_COLOR, int(25 * alpha)))
        gr = glow.get_rect(center=pos)
        surface.blit(glow, gr)

    def _draw_ending_subtitles(self, surface: pygame.Surface) -> None:
        sw, sh = surface.get_size()
        cx, cy = sw // 2, sh // 2

        if self._ending_font is None:
            self._ending_font = get_font(24)
            self._ending_prev_font = get_font(14)
            self._ending_big_font = get_font(36)

        # Phase 0: nights.mp3 subtitles
        if self._ending_phase <= 1:
            self._draw_narration_line(
                surface,
                cx,
                cy,
                ENDING_NARRATION,
                self._ending_sub_idx,
                self._ending_prev_idx,
                self._ending_audio_timer,
            )

        # Phase 2: bye.mp3 subtitles
        elif self._ending_phase == 2:
            self._draw_bye_line(surface, cx, cy)

        # Phase 3: "Good night." lingers
        elif self._ending_phase == 3:
            self._draw_goodnight_linger(surface, cx, cy)

    def _draw_narration_line(
        self,
        surface: pygame.Surface,
        cx: int,
        cy: int,
        narration: list,
        sub_idx: int,
        prev_idx: int,
        audio_t: float,
    ) -> None:
        breathe = 1.0 + 0.015 * math.sin(self._ending_timer * 1.5)

        if sub_idx >= 0:
            start, _end, key = narration[sub_idx]
            text = t(key)
            elapsed = audio_t - start
            chars_to_show = int(min(elapsed * ENDING_TYPEWRITER_SPEED, len(text)))
            visible = text[:chars_to_show]

            if visible:
                slide = max(0, 8 - elapsed * 30)
                alpha = min(elapsed * 3, 1.0)

                rendered = render_multiline(visible, self._ending_font, ENDING_TEXT_COLOR, surface.get_width() - 120)
                bw = int(rendered.get_width() * breathe)
                bh = int(rendered.get_height() * breathe)
                rendered = pygame.transform.scale(rendered, (bw, bh))

                pos = (cx, cy + int(slide))
                self._ending_glow(surface, rendered, pos, alpha)
                rendered.set_alpha(int(255 * alpha))
                surface.blit(rendered, rendered.get_rect(center=pos))

        if prev_idx >= 0:
            _ps, prev_end, prev_key = narration[prev_idx]
            prev_text = t(prev_key)
            prev_age = audio_t - prev_end
            prev_alpha = max(0, 1.0 - prev_age * 1.2)
            if prev_alpha > 0.05:
                drift = prev_age * 12
                rendered = render_multiline(prev_text, self._ending_prev_font, ENDING_PREV_COLOR, surface.get_width() - 120)
                rendered.set_alpha(int(180 * prev_alpha))
                surface.blit(rendered, rendered.get_rect(center=(cx, cy - 40 - int(drift))))

    def _draw_bye_line(self, surface: pygame.Surface, cx: int, cy: int) -> None:
        elapsed_time = self._ending_bye_timer
        breathe = 1.0 + 0.02 * math.sin(elapsed_time * 1.2)

        if self._ending_bye_idx >= 0:
            start, _end, key = ENDING_BYE_NARRATION[self._ending_bye_idx]
            text = t(key)
            elapsed = elapsed_time - start
            chars_to_show = int(min(elapsed * 25, len(text)))
            visible = text[:chars_to_show]

            if visible:
                alpha = min(elapsed * 3, 1.0)
                font = self._ending_big_font if self._ending_bye_idx == 1 else self._ending_font
                rendered = render_multiline(visible, font, ENDING_FINAL_COLOR, surface.get_width() - 120)
                bw = int(rendered.get_width() * breathe)
                bh = int(rendered.get_height() * breathe)
                rendered = pygame.transform.scale(rendered, (bw, bh))

                pos = (cx, cy)
                self._ending_glow(surface, rendered, pos, alpha)
                rendered.set_alpha(int(255 * alpha))
                surface.blit(rendered, rendered.get_rect(center=pos))

        if self._ending_bye_prev_idx >= 0:
            _ps, prev_end, prev_key = ENDING_BYE_NARRATION[self._ending_bye_prev_idx]
            prev_text = t(prev_key)
            prev_age = elapsed_time - prev_end
            prev_alpha = max(0, 1.0 - prev_age * 0.8)
            if prev_alpha > 0.05:
                drift = prev_age * 10
                rendered = render_multiline(prev_text, self._ending_prev_font, ENDING_PREV_COLOR, surface.get_width() - 120)
                rendered.set_alpha(int(150 * prev_alpha))
                surface.blit(rendered, rendered.get_rect(center=(cx, cy - 40 - int(drift))))

    def _draw_goodnight_linger(self, surface: pygame.Surface, cx: int, cy: int) -> None:
        elapsed_time = self._ending_linger
        breathe = 1.0 + 0.025 * math.sin(elapsed_time * 0.8)
        fade = max(0, 1.0 - max(0, elapsed_time - 4.0) * 0.3)

        rendered = self._ending_big_font.render(t("ending.goodnight"), True, ENDING_FINAL_COLOR)
        bw = int(rendered.get_width() * breathe)
        bh = int(rendered.get_height() * breathe)
        rendered = pygame.transform.scale(rendered, (bw, bh))

        pos = (cx, cy)
        self._ending_glow(surface, rendered, pos, fade)
        rendered.set_alpha(int(255 * fade))
        surface.blit(rendered, rendered.get_rect(center=pos))

    def _draw_success_page(self, surface: pygame.Surface) -> None:
        if self._success_title_font is None:
            self._success_title_font = get_font(46)
            self._success_body_font = get_font(23)
        sw, sh = surface.get_size()
        panel_width = min(680, sw - 48)
        panel_height = min(230, sh - 48)
        panel = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel.fill((10, 8, 22, 225))
        pygame.draw.rect(panel, (210, 180, 95, 255), panel.get_rect(), 3, border_radius=18)
        pygame.draw.rect(panel, (85, 170, 130, 150), panel.get_rect().inflate(-16, -16), 2, border_radius=13)
        title = self._success_title_font.render(t("ending.success.title"), True, (245, 220, 140))
        body = self._success_body_font.render(t("ending.success.body"), True, (225, 230, 218))
        panel.blit(title, title.get_rect(center=(panel_width // 2, panel_height // 2 - 34)))
        panel.blit(body, body.get_rect(center=(panel_width // 2, panel_height // 2 + 38)))
        alpha = min(1.0, self._success_timer * 2.5)
        if self._success_timer > SUCCESS_PAGE_DURATION - 0.5:
            alpha = max(0.0, (SUCCESS_PAGE_DURATION - self._success_timer) * 2.0)
        panel.set_alpha(int(alpha * 255))
        surface.blit(panel, panel.get_rect(center=(sw // 2, sh // 2)))

    def _draw_shared_hud(self, surface: pygame.Surface) -> None:
        if self.zone_announcement and not self.zone_announcement.finished:
            self.zone_announcement.draw(surface)
        if self.finale_state == FinaleState.SUCCESS:
            self._draw_success_page(surface)
        if self.portal:
            self.portal.draw_cutaway(surface)
            cam = self.split_screen.shared_cam.offset
            self.portal.draw_vignette(surface, cam)
        if self._fade_to_black > 0.01:
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, int(self._fade_to_black * 255)))
            surface.blit(overlay, (0, 0))
            if self._ending_voice_started:
                self._draw_ending_subtitles(surface)
