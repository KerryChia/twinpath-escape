import pygame

from core.gui import Divider, Label


class ZoneAnnouncement:
    FADE_IN = 0.8
    HOLD = 4.0
    FADE_OUT = 0.8

    def __init__(self, subtitle: str, title: str) -> None:
        self.subtitle_label = Label(subtitle, size=22, color=(190, 195, 205))
        self.title_label = Label(title, size=30)

        self.div_left = Divider(scale=0.6, style=3, fade=True)
        self.div_right = Divider(scale=0.6, style=3, fade=True)
        self.div_right.image = pygame.transform.flip(self.div_right.image, True, False)

        self.subtitle_w = self.subtitle_label.rect.width

        self.timer = 0.0
        self.total = self.FADE_IN + self.HOLD + self.FADE_OUT
        self.finished = False

    @property
    def alpha(self) -> int:
        if self.timer < self.FADE_IN:
            return int(255 * (self.timer / self.FADE_IN))
        elif self.timer < self.FADE_IN + self.HOLD:
            return 255
        else:
            t = (self.timer - self.FADE_IN - self.HOLD) / self.FADE_OUT
            return int(255 * (1.0 - t))

    def update(self, dt: float) -> None:
        self.timer += dt
        if self.timer >= self.total:
            self.finished = True

    def draw(self, surface: pygame.Surface) -> None:
        if self.finished:
            return

        sw, sh = surface.get_size()
        cx = sw // 2
        y = sh // 4

        alpha = max(0, min(255, self.alpha))

        temp = pygame.Surface((sw, sh), pygame.SRCALPHA)

        gap = self.subtitle_w // 2 + 100
        self.div_left.draw(temp, cx - gap, y)
        self.subtitle_label.draw(temp, cx, y)
        self.div_right.draw(temp, cx + gap, y)
        self.title_label.draw(temp, cx, y + 30)

        temp.set_alpha(alpha)
        surface.blit(temp, (0, 0))
