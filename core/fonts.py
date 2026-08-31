from functools import lru_cache

import pygame

from core.resource import resource_path

FONT_PATH = resource_path("assets/font/NotoSansSC-Variable.ttf")


@lru_cache(maxsize=None)
def get_font(size: int) -> pygame.font.Font:
    if not pygame.font.get_init():
        pygame.font.init()
    return pygame.font.Font(str(FONT_PATH), size)
