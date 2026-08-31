"""Centralized audio system for music and sound effects."""

import pygame

from core.config.game_settings import settings
from core.resource import resource_path

_SFX_DIR = resource_path("assets/audio/ui/original")

UI_SFX = {
    "button_hover": _SFX_DIR / "hover.wav",
    "button_click": _SFX_DIR / "click.wav",
    "error": _SFX_DIR / "error.wav",
    "success": _SFX_DIR / "success.wav",
}

GAME_SFX = {
    "impact": _SFX_DIR / "impact.wav",
}

_MUSIC_DIR = resource_path("assets/audio/sountracks")

MUSIC = {
    "menu": _MUSIC_DIR / "music-loop-bundle-download_2025_q4/Sketchbook 2025-11-26.ogg",
    "tutorial_001": _MUSIC_DIR / "music-loop-bundle-download_2024_q4/Sketchbook 2024-11-07.ogg",
    "level_001": _MUSIC_DIR / "music-loop-bundle-download_2024_q3/Sketchbook 2024-08-21.ogg",
    "level_002": _MUSIC_DIR / "music-loop-bundle-download_2024_q2/Sketchbook 2024-06-19.ogg",
    "moving_platform": _MUSIC_DIR
    / "music-loop-bundle-download_2024_q3/Interior Birdecorator Decorate.ogg",
}


class AudioManager:
    _instance = None
    _sfx_cache: dict[str, pygame.mixer.Sound] = {}  # noqa: RUF012
    _current_music: str | None = None

    @classmethod
    def instance(cls) -> "AudioManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.set_num_channels(16)

    def _get_sound(self, name: str) -> pygame.mixer.Sound | None:
        all_sfx = {**UI_SFX, **GAME_SFX}
        if name not in all_sfx:
            return None
        if name not in self._sfx_cache:
            self._sfx_cache[name] = pygame.mixer.Sound(all_sfx[name])
        return self._sfx_cache[name]

    def play_ui(self, name: str) -> None:
        sound = self._get_sound(name)
        if sound:
            sound.set_volume(settings.ui_volume)
            sound.play()

    def play_sfx(self, name: str) -> None:
        sound = self._get_sound(name)
        if sound:
            sound.set_volume(settings.sfx_volume)
            sound.play()

    def play_music(self, name: str, fade_ms: int = 1000) -> None:
        if name == self._current_music:
            return
        if name not in MUSIC:
            return
        self._current_music = name
        pygame.mixer.music.load(MUSIC[name])
        pygame.mixer.music.set_volume(settings.music_volume)
        pygame.mixer.music.play(-1, fade_ms=fade_ms)

    def stop_music(self, fade_ms: int = 500) -> None:
        self._current_music = None
        pygame.mixer.music.fadeout(fade_ms)


def play_ui(name: str) -> None:
    AudioManager.instance().play_ui(name)


def play_sfx(name: str) -> None:
    AudioManager.instance().play_sfx(name)


def play_music(name: str, fade_ms: int = 1000) -> None:
    AudioManager.instance().play_music(name, fade_ms)


def stop_music(fade_ms: int = 500) -> None:
    AudioManager.instance().stop_music(fade_ms)
