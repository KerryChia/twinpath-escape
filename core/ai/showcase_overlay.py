"""Localized showcase HUD narrating the dual-AI presentation run.

Unlike AIDebugOverlay (a single-provider diagnostic panel toggled with F3),
this overlay is the presentation layer of AI_SHOWCASE: it always renders, one
panel per AI, and narrates level, semantic goal, execution state, planner
winner and replan counts in the player's language.
"""

import pygame

from core.fonts import get_font
from core.localization import t


class ShowcaseOverlay:
    def __init__(self, visible: bool = True) -> None:
        self.visible = visible
        self.font = get_font(16)
        self.title_font = get_font(19)
        self._colors = {
            0: (150, 235, 170),  # green player accent
            1: (245, 185, 120),  # orange player accent
        }
        self._state_keys = {
            "FOLLOWING": "ai.showcase.state.following",
            "APPROACH": "ai.showcase.state.approach",
            "BRAKE": "ai.showcase.state.brake",
            "HOLD": "ai.showcase.state.hold",
            "WAIT": "ai.showcase.state.wait",
            "COMPLETE": "ai.showcase.state.complete",
        }

    def toggle(self) -> None:
        self.visible = not self.visible

    def _panel(self, surface: pygame.Surface, provider, index: int, right_side: bool) -> None:
        accent = self._colors.get(index, (220, 220, 220))
        metrics = provider.metrics
        state_key = self._state_keys.get(
            getattr(provider.execution_state, "value", ""), "ai.showcase.state.wait"
        )
        strategy = metrics.algorithm
        if metrics.winner:
            strategy = f"{metrics.algorithm}/{metrics.winner}"
        lines = [
            t("ai.showcase.goal", goal=t(metrics.goal)),
            t("ai.showcase.step", step=provider.script_step, state=t(state_key)),
            t("ai.showcase.planner", planner=strategy),
            t("ai.showcase.replans", count=metrics.replans),
        ]
        width = min(300, surface.get_width() // 2 - 28)
        height = 24 + len(lines) * 22
        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill((10, 8, 20, 195))
        pygame.draw.rect(panel, (*accent, 210), panel.get_rect(), 2, border_radius=8)
        label = self.title_font.render(t(f"common.{'green' if index == 0 else 'orange'}") + " AI", True, accent)
        panel.blit(label, (10, 5))
        for i, line in enumerate(lines):
            panel.blit(self.font.render(line, True, (238, 234, 222)), (10, 28 + i * 22))
        x = surface.get_width() - width - 12 if right_side else 12
        surface.blit(panel, (x, 12))

    def draw(self, surface: pygame.Surface, providers, level_id: str) -> None:
        if not self.visible:
            return
        from core.config.levels import level_title_key

        title = self.title_font.render(
            t("ai.showcase.title", level=t(level_title_key(level_id))), True, (225, 215, 185)
        )
        banner = pygame.Surface((title.get_width() + 24, 30), pygame.SRCALPHA)
        banner.fill((10, 8, 20, 170))
        pygame.draw.rect(banner, (190, 175, 130, 190), banner.get_rect(), 2, border_radius=8)
        banner.blit(title, (12, 4))
        banner_rect = banner.get_rect(midtop=(surface.get_width() // 2, 8))
        surface.blit(banner, banner_rect)
        for index, provider in enumerate(providers[:2]):
            if provider is None:
                continue
            self._panel(surface, provider, index, right_side=index == 1)
