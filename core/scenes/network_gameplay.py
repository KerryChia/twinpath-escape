import pygame

from core.config.constants import LOCAL_OUTLINE, P1_KEYS, REMOTE_OUTLINE
from core.localization import t
from core.network import GameClient, GameServer
from core.player import Player
from core.scene import SceneManager
from core.scenes.base_gameplay import BaseGameplay


class NetworkGameplay(BaseGameplay):
    def __init__(
        self,
        manager: SceneManager,
        client: GameClient,
        server: GameServer | None,
        is_host: bool,
        level_id: str = "tutorial_001",
    ) -> None:
        super().__init__(manager, level_id)
        self.client = client
        self.server = server
        self.is_host = is_host

        local_char = "green" if self.client.my_slot == 0 else "orange"
        remote_char = "orange" if self.client.my_slot == 0 else "green"

        remote_name = t("common.player")
        for p in self.client.lobby_players:
            if p["slot"] != self.client.my_slot:
                remote_name = p["name"]

        local_spawn = (
            (self.spawn_x, self.spawn_y)
            if self.client.my_slot == 0
            else (self.spawn_b_x, self.spawn_b_y)
        )
        remote_spawn = (
            (self.spawn_b_x, self.spawn_b_y)
            if self.client.my_slot == 0
            else (self.spawn_x, self.spawn_y)
        )

        self.local_player = Player(
            local_spawn[0],
            local_spawn[1],
            keys=P1_KEYS,
            outline_color=LOCAL_OUTLINE,
            character=local_char,
            name=self.client.my_name,
        )
        self.remote_player = Player(
            remote_spawn[0],
            remote_spawn[1],
            keys=P1_KEYS,
            outline_color=REMOTE_OUTLINE,
            character=remote_char,
            name=remote_name,
        )
        self.players = [self.local_player, self.remote_player]
        self._sync_player_scales()

    def _should_draw_player(self, index: int) -> bool:
        return not (index == 1 and not self.client.has_remote_player)

    def _show_nametag(self, index: int) -> bool:
        return index == 1  # only remote

    def _should_play_sfx(self, player_index: int) -> bool:
        return player_index == 0  # only local player

    def _on_level_complete(self) -> None:
        from core.scenes.main_menu import MainMenu

        self.manager.replace(MainMenu(self.manager))

    def _send_local_state(self) -> None:
        self.client.send_state(
            {
                "x": self.local_player.pos.x,
                "y": self.local_player.pos.y,
                "vx": self.local_player.velocity.x,
                "vy": self.local_player.velocity.y,
                "state": self.local_player.state,
                "facing": self.local_player.facing_right,
                "on_ground": self.local_player.on_ground,
            }
        )

    def _apply_remote_state(self) -> None:
        rs = self.client.remote_state
        if not rs:
            return
        self.remote_player.pos.x = rs.get("x", self.remote_player.pos.x)
        self.remote_player.pos.y = rs.get("y", self.remote_player.pos.y)
        self.remote_player.velocity.x = rs.get("vx", 0)
        self.remote_player.velocity.y = rs.get("vy", 0)
        self.remote_player.rect.x = int(self.remote_player.pos.x)
        self.remote_player.rect.y = int(self.remote_player.pos.y)
        self.remote_player.facing_right = rs.get("facing", True)
        self.remote_player.on_ground = rs.get("on_ground", False)
        self.remote_player.state = rs.get("state", "idle")

    def update(self, dt: float) -> None:
        self.client.pump()

        if self.client.was_connected and not self.client.connected:
            from core.scenes.disconnected import Disconnected

            self.manager.replace(Disconnected(self.manager, t("disconnect.host_connection_lost")))
            return

        self._update_world(dt)
        self._update_player(0, self.local_player, dt)

        if self.client.has_remote_player:
            self._apply_remote_state()
            self.remote_player._animate(dt)

        self._send_local_state()
        self._update_shared(dt)

    def draw(self, surface: pygame.Surface) -> None:
        if self.client.has_remote_player:
            self.split_screen.render(
                surface,
                self._draw_world,
                self.local_player.rect,
                self.remote_player.rect,
                hud_fn=self._draw_player_hud,
            )
        else:
            sw, sh = surface.get_size()
            self.split_screen.shared_cam.follow_rect(self.local_player.rect, sw, sh)
            self.split_screen.shared_cam.update(1 / 60)
            self._draw_world(surface, self.split_screen.shared_cam.offset, (sw, sh))
            self._draw_player_hud(surface, 0, (sw // 2, sh // 2))

        self._draw_shared_hud(surface)
