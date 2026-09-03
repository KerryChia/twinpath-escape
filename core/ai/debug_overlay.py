"""Localized, resolution-independent AI diagnostics overlay."""

import pygame

from core.fonts import get_font
from core.localization import t


class AIDebugOverlay:
    def __init__(self, visible: bool = True) -> None:
        self.visible = visible
        self.font = get_font(16)

    def toggle(self) -> None:
        self.visible = not self.visible

    def draw(self, surface: pygame.Surface, provider) -> None:
        if not self.visible:
            return
        metrics = provider.metrics
        strategy = metrics.algorithm
        if metrics.winner:
            strategy = f"{metrics.algorithm}/{metrics.winner}"
        lines = [
            t("ai.overlay.algorithm", algorithm=strategy),
            t("ai.overlay.goal", goal=t(metrics.goal)),
            t("ai.overlay.expanded", count=metrics.expanded),
            t("ai.overlay.path", count=metrics.path_length),
            t("ai.overlay.replans", count=metrics.replans),
        ]
        width = min(330, surface.get_width() - 24)
        height = 18 + len(lines) * 23
        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill((8, 6, 18, 205))
        pygame.draw.rect(panel, (190, 175, 130, 220), panel.get_rect(), 2, border_radius=6)
        for i, line in enumerate(lines):
            panel.blit(self.font.render(line, True, (240, 235, 220)), (12, 10 + i * 23))
        surface.blit(panel, (12, 12))
