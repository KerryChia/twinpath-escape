import pygame


class GameSettings:
    def __init__(self) -> None:
        self.screen_width = 1280
        self.screen_height = 720
        self.is_fullscreen = False
        self.music_volume = 0.7
        self.sfx_volume = 0.8
        self.ui_volume = 0.1
        self.p1_controls = "WASD"
        self.p2_controls = "Numpad"
        self.show_fps = False
        self._dirty = False

    @property
    def screen_size(self) -> tuple[int, int]:
        return (self.screen_width, self.screen_height)

    def apply_display_mode(self) -> pygame.Surface:
        if self.is_fullscreen:
            surface = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self.screen_width, self.screen_height = surface.get_size()
        else:
            surface = pygame.display.set_mode((self.screen_width, self.screen_height))
        self._dirty = True
        pygame.mixer.music.set_volume(self.music_volume)
        return surface

    def set_music_volume(self, value: float) -> None:
        self.music_volume = value
        pygame.mixer.music.set_volume(value)

    def set_sfx_volume(self, value: float) -> None:
        self.sfx_volume = value

    def consume_dirty(self) -> bool:
        if self._dirty:
            self._dirty = False
            return True
        return False


settings = GameSettings()
