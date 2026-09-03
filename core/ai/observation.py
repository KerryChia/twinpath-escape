"""Read-only snapshots supplied to ActionProvider implementations."""

from dataclasses import dataclass
from typing import Any


RectTuple = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class PlayerObservation:
    position: tuple[float, float]
    velocity: tuple[float, float]
    rect: RectTuple
    on_ground: bool
    on_stairs: bool
    in_water: bool
    dead: bool
    has_double_jump: bool
    platform_id: str | None


@dataclass(frozen=True, slots=True)
class DoorObservation:
    door_id: str
    open: bool
    target_open: bool
    rect: RectTuple = (0, 0, 1, 1)
    latched: bool = False


@dataclass(frozen=True, slots=True)
class PlateObservation:
    """A pressure plate with a stable semantic identity and real world rect."""

    plate_id: str
    group: str
    rect: RectTuple
    pressed: bool
    activated: bool
    owner: int | None = None
    controls: str | None = None
    mode: str = "hold"


@dataclass(frozen=True, slots=True)
class MovingPlatformObservation:
    platform_id: str
    rect: RectTuple
    direction: int
    progress: float


@dataclass(frozen=True, slots=True)
class DoorSpecObservation:
    """Stable data-driven semantics for an ordinary mechanism door."""
    door_id: str
    plate_index: int | None
    required_player: int | None
    mode: str


@dataclass(frozen=True, slots=True)
class Observation:
    level_id: str
    players: tuple[PlayerObservation, PlayerObservation]
    platforms: tuple[RectTuple, ...]
    stairs: tuple[RectTuple, ...]
    water: tuple[RectTuple, ...]
    lava: tuple[RectTuple, ...]
    pressure_plates: tuple[tuple[RectTuple, bool, bool], ...]
    doors: tuple[DoorObservation, ...]
    door_specs: tuple[DoorSpecObservation, ...]
    coop_doors_open: bool
    coop_plate_owner: tuple[int | None, ...]
    coop_plate_centers: tuple[RectTuple, ...]
    moving_platforms: tuple[MovingPlatformObservation, ...]
    exits: tuple[RectTuple, ...]
    has_portal: bool
    portal_active: bool
    portal_entered: tuple[bool, bool]
    graph: Any
    graph_conditions: frozenset[str]
    plates: tuple[PlateObservation, ...] = ()
    portal_rect: RectTuple | None = None
    final_exit_entered: tuple[bool, bool] = (False, False)
    finale_state: str = "PLAYING"
    solids: tuple[RectTuple, ...] = ()


def _rect(rect: Any) -> RectTuple:
    return (rect.x, rect.y, rect.width, rect.height)


def locate_platform(graph: Any, center: tuple[int, int]) -> str | None:
    if graph is None or not graph.nodes:
        return None
    grounded = [
        node for node in graph.nodes.values()
        if node.kind in {"platform", "dock"}
        and node.rect[0] - 4 <= center[0] <= node.rect[0] + node.rect[2] + 4
        and abs(node.position[1] - center[1]) <= 18
    ]
    if grounded:
        return min(grounded, key=lambda node: abs(node.position[1] - center[1])).node_id
    # `platform_id` means the support actually under the player's feet. The
    # controller has its own nearest-node fallback when planning from mid-air;
    # returning a distant nearest platform here falsely fast-forwards paths.
    return None


def locate_support(graph: Any, rect: tuple[int, int, int, int]) -> str | None:
    """Resolve the platform carrying the player's feet.

    Unlike `locate_platform` (a point probe at the box center), this accepts
    any real overlap between the player box and the support span: a box
    hanging two-thirds off a 40px ledge keeps its support identity, which the
    controller's fast-forward and replan anchoring depend on.
    """
    if graph is None or not graph.nodes:
        return None
    left, top, width, height = rect
    feet = top + height
    grounded = [
        node for node in graph.nodes.values()
        if node.kind in {"platform", "dock"}
        and node.rect[0] < left + width and node.rect[0] + node.rect[2] > left
        and node.rect[1] - 6 <= feet <= node.rect[1] + node.rect[3] + 18
    ]
    if grounded:
        return min(grounded, key=lambda node: abs(node.rect[1] - feet)).node_id
    return None


def from_scene(scene: Any) -> Observation:
    graph = getattr(scene, "platform_graph", None)
    players = []
    for player in scene.players:
        players.append(
            PlayerObservation(
                position=(player.pos.x, player.pos.y),
                velocity=(player.velocity.x, player.velocity.y),
                rect=_rect(player.rect),
                on_ground=player.on_ground,
                on_stairs=player.on_stairs,
                in_water=player.in_water,
                dead=player.dead,
                has_double_jump=player.has_double_jump,
                platform_id=locate_support(graph, (player.rect.x, player.rect.y, player.rect.width, player.rect.height)),
            )
        )
    doors = []
    typed_plates: list[PlateObservation] = []
    conditions: set[str] = set()
    door_specs = []
    dm = scene.door_manager
    for i, door in enumerate(dm.doors):
        door_id = getattr(door, "door_id", f"door:{i}")
        originals = door.original_positions
        box = originals[0].unionall(originals[1:]) if len(originals) > 1 else originals[0]
        linked = [pi for pi, di in dm.plate_door_map.items() if di == i]
        latched = any(pi in dm._latched for pi in linked)
        doors.append(DoorObservation(door_id, door.is_open, door.target_open, _rect(box), latched))
        if door.is_open:
            conditions.add(f"open:{door_id}")
    for pi, plate in enumerate(dm.plates):
        di = dm.plate_door_map.get(pi)
        door = dm.doors[di] if di is not None and di < len(dm.doors) else None
        door_id = getattr(door, "door_id", f"door:{di}") if door else None
        required = dm._required_players.get(pi)
        mode = dm._modes.get(pi, "hold")
        door_specs.append(
            DoorSpecObservation(
                door_id=door_id,
                plate_index=pi if door is not None else None,
                required_player=required if required is not None else None,
                mode=mode,
            )
        )
        typed_plates.append(PlateObservation(
            f"door_plate:{door_id}", "door", _rect(plate.rect), plate.pressed,
            plate.pressed or pi in dm._latched, required, door_id, mode,
        ))
    for i, door in enumerate(scene.coop_doors.doors):
        door_id = getattr(door, "door_id", f"coop:{i}")
        originals = door.original_positions
        box = originals[0].unionall(originals[1:]) if len(originals) > 1 else originals[0]
        doors.append(DoorObservation(door_id, door.is_open, door.target_open, _rect(box), scene.coop_doors._opened))
        if door.is_open:
            conditions.add(f"open:{door_id}")
    coop_plate_owner = tuple(
        getattr(plate, "player_index", None) for plate in scene.coop_doors.plates
    )
    coop_plate_centers = tuple(
        _rect(plate.rect) for plate in scene.coop_doors.plates
    )
    for plate in scene.coop_doors.plates:
        typed_plates.append(PlateObservation(
            f"coop:player:{plate.player_index}", "coop", _rect(plate.rect),
            plate.pressed, scene.coop_doors._opened, plate.player_index,
        ))
    ordinary = sorted(scene.pressure_plates.plates, key=lambda plate: plate.rect.centerx)
    for i, plate in enumerate(ordinary):
        role = "left" if i == 0 else "right" if i == len(ordinary) - 1 else f"middle:{i}"
        typed_plates.append(PlateObservation(
            f"ordinary:{role}", "ordinary", _rect(plate.rect), plate.pressed, plate.activated,
        ))
    moving = tuple(
        MovingPlatformObservation(f"moving:{i}", _rect(p.rect), p.direction, p.progress)
        for i, p in enumerate(scene.moving_platforms.platforms)
    )
    if graph is not None:
        for i, platform in enumerate(scene.moving_platforms.platforms):
            conditions.update(graph.update_moving_platform(i, platform.progress, platform.direction))
    portal = scene.portal
    exits = scene.map.final_exit_rects or scene.map.portal_rects
    return Observation(
        level_id=scene.level_id,
        players=(players[0], players[1]),
        platforms=tuple(
            _rect(r) for r in (
                scene.map.collision_rects
                + scene.map.platform_rects
                + scene.breakables.active_rects()
                + scene.moving_platforms.rects()
            )
        ),
        stairs=tuple(_rect(r) for r in scene.map.stairs_rects),
        water=tuple(_rect(r) for r in scene.map.water_rects),
        lava=tuple(_rect(r) for r in scene.map.lava_rects),
        pressure_plates=(
            tuple((_rect(p.rect), p.pressed, p.pressed) for p in scene.door_manager.plates)
            + tuple((_rect(p.rect), p.pressed, p.pressed) for p in scene.coop_doors.plates)
            + tuple(
                (_rect(p.rect), p.pressed, getattr(p, "activated", p.pressed))
                for p in scene.pressure_plates.plates
            )
        ),
        doors=tuple(doors),
        door_specs=tuple(door_specs),
        coop_doors_open=scene.coop_doors._opened,
        coop_plate_owner=coop_plate_owner,
        coop_plate_centers=coop_plate_centers,
        moving_platforms=moving,
        exits=tuple(_rect(r) for r in exits),
        has_portal=portal is not None,
        portal_active=bool(portal and portal.is_active),
        portal_entered=(bool(portal and portal.p1_entered), bool(portal and portal.p2_entered)),
        graph=graph,
        graph_conditions=frozenset(conditions),
        plates=tuple(typed_plates),
        portal_rect=_rect(scene.map.portal_rects[0]) if scene.map.portal_rects else None,
        final_exit_entered=tuple(scene.final_exit_entered),
        finale_state=scene.finale_state.name,
        solids=tuple(
            _rect(r) for r in (
                scene.map.collision_rects
                + scene.door_manager.collision_rects()
                + scene.coop_doors.collision_rects()
            )
        ),
    )
