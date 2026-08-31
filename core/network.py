import json
import random
import shutil
import socket
import string
import subprocess
import threading
import time
import urllib.request

from repod import Channel, ConnectionListener, Server

from core.localization import t

DEFAULT_PORT = 5071
DISCOVERY_PORT = 5072


def generate_party_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except OSError:
        ip = "127.0.0.1"
    return ip


class PartyBroadcaster:
    def __init__(self, code: str, tcp_port: int, host_name: str) -> None:
        self.code = code
        self.tcp_port = tcp_port
        self.host_name = host_name
        self.running = False

    def start(self) -> None:
        self.running = True
        threading.Thread(target=self._broadcast, daemon=True).start()

    def stop(self) -> None:
        self.running = False

    def _broadcast(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1.0)

        ip = _get_local_ip()
        msg = json.dumps(
            {"code": self.code, "host": ip, "port": self.tcp_port, "name": self.host_name}
        ).encode()

        while self.running:
            try:
                sock.sendto(msg, ("<broadcast>", DISCOVERY_PORT))
                sock.sendto(msg, ("127.0.0.1", DISCOVERY_PORT))
            except OSError:
                pass
            time.sleep(0.5)
        sock.close()


class PartyFinder:
    def __init__(self) -> None:
        self.found_host: str | None = None
        self.found_port: int | None = None
        self.found_name: str | None = None
        self.searching = False
        self.error: str | None = None

    def find(self, code: str, timeout: float = 15.0) -> None:
        self.searching = True
        self.error = None
        threading.Thread(target=self._listen, args=(code, timeout), daemon=True).start()

    def _listen(self, code: str, timeout: float) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", DISCOVERY_PORT))
            sock.settimeout(1.0)
        except OSError:
            self.error = t("lobby.network_error")
            self.searching = False
            return

        deadline = time.time() + timeout
        while self.searching and time.time() < deadline:
            try:
                data, _addr = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                if msg.get("code") == code.upper():
                    self.found_host = msg["host"]
                    self.found_port = msg["port"]
                    self.found_name = msg.get("name", t("common.host"))
                    break
            except (TimeoutError, json.JSONDecodeError):
                continue
        sock.close()
        if not self.found_host:
            self.error = t("lobby.not_found")
        self.searching = False


class GameChannel(Channel["GameServer"]):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.player_name = ""
        self.slot = -1
        self.state: dict = {}

    def Network_join(self, data: dict) -> None:
        self.player_name = data.get("name", t("common.player"))
        self.server.on_player_join(self)

    def Network_state(self, data: dict) -> None:
        self.state = data
        relay = {k: v for k, v in data.items() if k != "action"}
        relay["action"] = "remote_state"
        for ch in self.server.players:
            if ch is not self:
                ch.send(relay)

    def Network_start_game(self, data: dict) -> None:
        self.server.on_start_game()

    def on_close(self) -> None:
        self.server.on_player_leave(self)


class GameServer(Server[GameChannel]):
    channel_class = GameChannel

    def __init__(self, host: str = "0.0.0.0", port: int = DEFAULT_PORT) -> None:
        super().__init__(host, port)
        self.players: list[GameChannel] = []
        self.game_started = False
        self._loop = None
        self._thread = None

    def start_background(self) -> threading.Thread:
        self._thread = super().start_background()
        return self._thread

    def stop_sync(self) -> None:
        """Stop the server synchronously from the main thread."""
        if hasattr(self, "_tcp_server") and self._tcp_server:
            loop = self._tcp_server.get_loop()
            loop.call_soon_threadsafe(self._tcp_server.close)
            time.sleep(0.2)

    def on_connect(self, channel: GameChannel, addr: tuple[str, int]) -> None:
        pass

    def on_player_join(self, channel: GameChannel) -> None:
        if channel in self.players:
            return
        if len(self.players) >= 2:
            channel.send({"action": "full"})
            return

        channel.slot = len(self.players)
        self.players.append(channel)
        channel.send({"action": "welcome", "slot": channel.slot})

        self._broadcast_lobby()

    def on_player_leave(self, channel: GameChannel) -> None:
        if channel in self.players:
            self.players.remove(channel)
            self._broadcast_lobby()

    def _broadcast_lobby(self) -> None:
        self.send_to_all(
            {
                "action": "lobby_update",
                "players": [{"name": p.player_name, "slot": p.slot} for p in self.players],
            }
        )

    def on_start_game(self) -> None:
        if len(self.players) == 2 and not self.game_started:
            self.game_started = True
            self.send_to_all({"action": "game_started"})

    def on_disconnect(self, channel: GameChannel) -> None:
        self.on_player_leave(channel)


class NgrokTunnel:
    """Manages an ngrok TCP tunnel for internet play."""

    def __init__(self, port: int = DEFAULT_PORT) -> None:
        self.port = port
        self.public_url: str | None = None
        self.error: str | None = None
        self.ready = False
        self._process: subprocess.Popen | None = None

    @staticmethod
    def is_available() -> bool:
        return shutil.which("ngrok") is not None

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            self._process = subprocess.Popen(
                ["ngrok", "tcp", str(self.port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(30):
                time.sleep(0.5)
                url = self._get_url()
                if url:
                    self.public_url = url
                    self.ready = True
                    return
            self.error = t("lobby.ngrok_no_url")
        except FileNotFoundError:
            self.error = t("lobby.ngrok_missing")
        except Exception:
            self.error = t("lobby.network_error")

    def _get_url(self) -> str | None:
        try:
            resp = urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=2)
            data = json.loads(resp.read())
            for tunnel in data.get("tunnels", []):
                if tunnel.get("proto") == "tcp":
                    return tunnel["public_url"].replace("tcp://", "")
        except Exception:
            return None

    def stop(self) -> None:
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        self.ready = False
        self.public_url = None


class GameClient(ConnectionListener):
    def __init__(self) -> None:
        self.connected = False
        self.was_connected = False
        self.my_slot = -1
        self.my_name = ""
        self.lobby_players: list[dict] = []
        self.game_started = False
        self.remote_state: dict = {}
        self.server_full = False
        self.has_remote_player = False

    def join(self, host: str, port: int, name: str) -> None:
        self.my_name = name
        self.connect(host, port)

    def Network_connected(self, data: dict) -> None:
        self.connected = True
        self.was_connected = True
        self.send({"action": "join", "name": self.my_name})

    def Network_disconnected(self, data: dict) -> None:
        self.connected = False
        self.has_remote_player = False

    def Network_error(self, data: dict) -> None:
        self.connected = False

    def Network_welcome(self, data: dict) -> None:
        self.my_slot = data["slot"]

    def Network_full(self, data: dict) -> None:
        self.server_full = True

    def Network_lobby_update(self, data: dict) -> None:
        self.lobby_players = data["players"]
        self.has_remote_player = len(self.lobby_players) >= 2

    def Network_game_started(self, data: dict) -> None:
        self.game_started = True

    def Network_remote_state(self, data: dict) -> None:
        self.remote_state = data

    def send_state(self, player_data: dict) -> None:
        if self.connected:
            self.send({"action": "state", **player_data})
