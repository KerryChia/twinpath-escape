from core.ai.controller import SearchActionProvider
from core.ai.debug_overlay import AIDebugOverlay
from core.ai.showcase_overlay import ShowcaseOverlay
from core.config.constants import (
    CONTROL_SETS,
    P1_OUTLINE_LOCAL,
    P2_OUTLINE_LOCAL,
)
from core.config.game_mode import GameMode
from core.config.game_settings import settings
from core.localization import t
from core.player import Player
from core.scene import SceneManager
from core.scenes.base_gameplay import BaseGameplay, FinaleState


class Gameplay(BaseGameplay):
    def __init__(
        self,
        manager: SceneManager,
        level_id: str = "tutorial_001",
        p1_name: str | None = None,
        p2_name: str | None = None,
        ai_algorithm: str | None = None,
        debug_ai: bool = True,
        mode: GameMode | None = None,
    ) -> None:
        super().__init__(manager, level_id)
        p1_name = p1_name or t("common.green")
        p2_name = p2_name or t("common.orange")
        self._p1_name = p1_name
        self._p2_name = p2_name
        # Every AI-driven mode always uses the hybrid planner (BFS+DFS+A*); the
        # ai_algorithm value is only carried forward as a test-only `prefer`
        # hint and never as a user-facing single-algorithm pick. `mode` is the
        # authoritative selector. A legacy ai_algorithm call site (tests,
        # headless scripts) used the old ai_mode semantics = BOTH characters
        # AI-driven, so it maps to AI_SHOWCASE to preserve that behaviour; the
        # human+AI entry passes mode=HUMAN_AI explicitly.
        self.mode = mode or (GameMode.AI_SHOWCASE if ai_algorithm is not None else GameMode.LOCAL)
        self.ai_algorithm = ai_algorithm
        self.ai_mode = self.mode is not GameMode.LOCAL
        self.showcase = self.mode is GameMode.AI_SHOWCASE
        if self.ai_mode:
            # P2 is always AI-driven; P1 joins only in the showcase, where the
            # whole run is an autonomous presentation.
            self.ai_provider = SearchActionProvider(player_index=1, prefer=ai_algorithm)
            self.p1_provider = (
                SearchActionProvider(player_index=0, prefer=ai_algorithm) if self.showcase else None
            )
        else:
            self.ai_provider = None
            self.p1_provider = None
        if self.showcase:
            self.ai_overlay = ShowcaseOverlay(debug_ai)
        else:
            self.ai_overlay = AIDebugOverlay(debug_ai) if self.ai_mode else None

        p1_keys = CONTROL_SETS[settings.p1_controls]
        p2_keys = CONTROL_SETS[settings.p2_controls]

        self.player1 = Player(
            self.spawn_x,
            self.spawn_y,
            keys=p1_keys,
            outline_color=P1_OUTLINE_LOCAL,
            character="green",
            name=p1_name,
            action_provider=self.p1_provider,
        )
        self.player2 = Player(
            self.spawn_b_x,
            self.spawn_b_y,
            keys=p2_keys,
            outline_color=P2_OUTLINE_LOCAL,
            character="orange",
            name=p2_name,
            action_provider=self.ai_provider,
        )
        # Keyboard sets stay bound in AI modes (hot-swap back to human play),
        # but the providers, not the keys, feed the physics.
        self.players = [self.player1, self.player2]
        self._sync_player_scales()

    def _on_level_complete(self) -> None:
        if self.next_level:
            self.manager.replace(
                Gameplay(
                    self.manager,
                    self.next_level,
                    self._p1_name,
                    self._p2_name,
                    self.ai_algorithm,
                    self.ai_overlay.visible if self.ai_overlay else True,
                    self.mode,
                )
            )
        else:
            from core.scenes.main_menu import MainMenu

            self.manager.replace(MainMenu(self.manager))

    def update(self, dt: float) -> None:
        if self.finale_state == FinaleState.PLAYING:
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
        if self.ai_overlay and self.ai_provider:
            if self.showcase:
                self.ai_overlay.draw(surface, [self.p1_provider, self.ai_provider], self.level_id)
            else:
                self.ai_overlay.draw(surface, self.ai_provider)
