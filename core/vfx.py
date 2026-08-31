from pathlib import Path

import pygame


class VFXAnimation:
    def __init__(
        self,
        frames: list[pygame.Surface],
        x: int,
        y: int,
        speed: float = 0.05,
    ) -> None:
        self.frames = frames
        self.x = x
        self.y = y
        self.speed = speed
        self.frame_index = 0.0
        self.finished = False

    def update(self, dt: float) -> None:
        self.frame_index += dt / self.speed
        if self.frame_index >= len(self.frames):
            self.finished = True

    def draw(self, surface: pygame.Surface, camera_offset: tuple[int, int] = (0, 0)) -> None:
        if self.finished:
            return
        frame = self.frames[int(self.frame_index)]
        ox, oy = camera_offset
        rect = frame.get_rect(midbottom=(self.x - ox, self.y - oy))
        surface.blit(frame, rect)


def load_vfx_frames(folder: str | Path, scale: float = 1.0) -> list[pygame.Surface]:
    folder = Path(folder)
    paths = sorted(folder.glob("*.png"))
    frames: list[pygame.Surface] = []
    for path in paths:
        img = pygame.image.load(path).convert_alpha()
        if scale != 1.0:
            scaled_size = (int(img.get_width() * scale), int(img.get_height() * scale))
            img = pygame.transform.scale(img, scaled_size)
        frames.append(img)
    return frames
