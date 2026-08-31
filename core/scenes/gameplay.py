from core.config.constants import (
    CONTROL_SETS,
    P1_OUTLINE_LOCAL,
    P2_OUTLINE_LOCAL,
)
from core.config.game_settings import settings
from core.localization import t
from core.player import Player
from core.scene import SceneManager
from core.scenes.base_gameplay import BaseGameplay


class Gameplay(BaseGameplay):
    def __init__(
        self,
        manager: SceneManager,
        level_id: str = "tutorial_001",
        p1_name: str | None = None,
        p2_name: str | None = None,
    ) -> None:
        super().__init__(manager, level_id)
        p1_name = p1_name or t("common.green")
        p2_name = p2_name or t("common.orange")
        self._p1_name = p1_name
        self._p2_name = p2_name

        p1_keys = CONTROL_SETS[settings.p1_controls]
        p2_keys = CONTROL_SETS[settings.p2_controls]

        self.player1 = Player(
            self.spawn_x,
            self.spawn_y,
            keys=p1_keys,
            outline_color=P1_OUTLINE_LOCAL,
            character="green",
            name=p1_name,
        )
        self.player2 = Player(
            self.spawn_b_x,
            self.spawn_b_y,
            keys=p2_keys,
            outline_color=P2_OUTLINE_LOCAL,
            character="orange",
            name=p2_name,
        )
        self.players = [self.player1, self.player2]
        self._sync_player_scales()

    def _on_level_complete(self) -> None:
        if self.next_level:
            self.manager.replace(
                Gameplay(self.manager, self.next_level, self._p1_name, self._p2_name)
            )
        else:
            from core.scenes.main_menu import MainMenu

            self.manager.replace(MainMenu(self.manager))

    def update(self, dt: float) -> None:
        self._update_world(dt)
        for i, p in enumerate(self.players):
            self._update_player(i, p, dt)
        self._update_shared(dt)

    def draw(self, surface) -> None:
        self.split_screen.render(
            surface,
            self._draw_world,
            self.player1.rect,
            self.player2.rect,
            hud_fn=self._draw_player_hud,
        )
        self._draw_shared_hud(surface)
