"""Platform-level navigation graph extracted from TMX and runtime entities."""

from dataclasses import dataclass, field
import math
from typing import Iterable

import pygame


@dataclass(frozen=True, slots=True)
class PlatformNode:
    node_id: str
    position: tuple[int, int]
    kind: str = "platform"
    rect: tuple[int, int, int, int] = (0, 0, 1, 1)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class PlatformEdge:
    source: str
    target: str
    movement: str
    direction: int
    cost: float
    condition: str | None = None


@dataclass
class PlatformGraph:
    nodes: dict[str, PlatformNode] = field(default_factory=dict)
    adjacency: dict[str, list[PlatformEdge]] = field(default_factory=dict)
    runtime_costs: dict[tuple[str, str], float] = field(default_factory=dict)

    def add_node(self, node: PlatformNode) -> None:
        self.nodes[node.node_id] = node
        self.adjacency.setdefault(node.node_id, [])

    def add_edge(self, edge: PlatformEdge, bidirectional: bool = False) -> None:
        self.adjacency.setdefault(edge.source, []).append(edge)
        if bidirectional:
            self.adjacency.setdefault(edge.target, []).append(
                PlatformEdge(edge.target, edge.source, edge.movement, -edge.direction, edge.cost, edge.condition)
            )

    def neighbors(self, node: str, conditions: frozenset[str] = frozenset()) -> Iterable[tuple[str, float]]:
        blocked = {value.removeprefix("blocked:") for value in conditions if value.startswith("blocked:")}
        for edge in self.adjacency.get(node, ()):
            edge_key = f"{edge.source}>{edge.target}"
            if edge_key in blocked:
                continue
            if edge.condition is None or edge.condition in conditions:
                yield edge.target, self.runtime_costs.get((edge.source, edge.target), edge.cost)

    def update_moving_platform(self, index: int, progress: float, direction: int) -> frozenset[str]:
        """Expose rides only while the platform is boarding at the departure dock."""
        a, b = f"dock:{index}:a", f"dock:{index}:b"
        if a not in self.nodes or b not in self.nodes:
            return frozenset()
        base = max(0.2, math.dist(self.nodes[a].position, self.nodes[b].position) / 60.0)
        conditions: set[str] = set()
        if progress <= 0.15 and direction > 0:
            conditions.add(f"ride:{index}:a>b")
            self.runtime_costs[(a, b)] = base * (1.0 - progress)
        if progress >= 0.85 and direction < 0:
            conditions.add(f"ride:{index}:b>a")
            self.runtime_costs[(b, a)] = base * progress
        return frozenset(conditions)

    def edge(self, source: str, target: str) -> PlatformEdge | None:
        return next((e for e in self.adjacency.get(source, ()) if e.target == target), None)

    def nearest_node(self, position: tuple[int, int], kinds: set[str] | None = None) -> PlatformNode:
        candidates = [n for n in self.nodes.values() if kinds is None or n.kind in kinds]
        if not candidates:
            raise ValueError("platform graph has no matching nodes")
        return min(candidates, key=lambda n: math.dist(position, n.position))

    def heuristic(self, source: str, target: str) -> float:
        """Return an admissible geometric lower bound for A*.

        The smallest cost-per-pixel ratio among all current edges is a lower
        bound for every edge. Multiplying it by straight-line distance remains
        admissible by the triangle inequality, including paths that use cheap
        semantic or runtime-cost edges.
        """
        ratios = []
        for edges in self.adjacency.values():
            for edge in edges:
                distance = math.dist(
                    self.nodes[edge.source].position,
                    self.nodes[edge.target].position,
                )
                if distance > 0:
                    cost = self.runtime_costs.get((edge.source, edge.target), edge.cost)
                    ratios.append(cost / distance)
        if not ratios:
            return 0.0
        return min(ratios) * math.dist(
            self.nodes[source].position,
            self.nodes[target].position,
        )


class PlatformGraphExtractor:
    MAX_JUMP_X = 430
    # Physics: jump force 720, gravity 1800 → a single jump rises 144px and a
    # double jump chained at the apex reaches ≈288px. Edge predicates must never
    # exceed what the executor can physically perform: anything above the
    # single-jump rise is only traversable as a double jump inside the tight
    # horizontal envelope the second impulse allows.
    MAX_JUMP_UP = 144
    MAX_DOUBLE_JUMP_UP = 288
    MAX_DOUBLE_JUMP_X = 160
    MAX_DROP = 520

    def __init__(self, map_data, moving_platforms=None) -> None:
        self.map = map_data
        self.moving_platforms = moving_platforms

    @staticmethod
    def _top_surfaces(rects: list[pygame.Rect]) -> list[pygame.Rect]:
        """Keep only collision tiles whose top edge is exposed and standable."""
        surfaces: list[pygame.Rect] = []
        for rect in rects:
            probe = pygame.Rect(rect.left + 1, rect.top - 2, max(1, rect.width - 2), 2)
            if not any(other is not rect and probe.colliderect(other) for other in rects):
                surfaces.append(rect)
        return surfaces

    @staticmethod
    def _segments(rects: list[pygame.Rect]) -> list[pygame.Rect]:
        by_y: dict[int, list[pygame.Rect]] = {}
        for rect in rects:
            by_y.setdefault(rect.top, []).append(rect)
        segments: list[pygame.Rect] = []
        for y, row in by_y.items():
            row.sort(key=lambda r: r.left)
            current = row[0].copy()
            for rect in row[1:]:
                if rect.left <= current.right + 2:
                    current.union_ip(rect)
                else:
                    segments.append(current); current = rect.copy()
            segments.append(current)
        return segments

    def extract(self) -> PlatformGraph:
        graph = PlatformGraph()
        collision_surfaces = self._top_surfaces(self.map.collision_rects)
        standable = collision_surfaces + self.map.platform_rects + self.map.breakable_rects
        hazards = self.map.lava_rects
        blockers = self.map.door_rects + self.map.second_door_rects
        raw_segments = [r for r in self._segments(standable) if not any(r.colliderect(h) for h in hazards)]
        segments: list[pygame.Rect] = []
        for segment in raw_segments:
            parts = [segment]
            for blocker in blockers:
                if blocker.left <= segment.left or blocker.right >= segment.right:
                    continue
                next_parts = []
                for part in parts:
                    if part.left < blocker.left < part.right:
                        next_parts.extend((pygame.Rect(part.left, part.top, blocker.left - part.left, part.height), pygame.Rect(blocker.right, part.top, part.right - blocker.right, part.height)))
                    else:
                        next_parts.append(part)
                parts = [part for part in next_parts if part.width > 2]
            segments.extend(parts)
        for i, rect in enumerate(segments):
            graph.add_node(PlatformNode(f"platform:{i}", (rect.centerx, rect.top), "platform", tuple(rect)))
        self._add_special(graph, "stairs", self.map.stairs_rects)
        self._add_special(graph, "plate", self.map.door_pressure_rects + self.map.second_door_pressure_rects + self.map.pressure_rects)
        self._add_special(graph, "exit", self.map.final_exit_rects or self.map.portal_rects)
        self._add_door_sides(graph)
        self._add_moving_docks(graph)
        self._connect_geometry(graph, hazards, self.map.door_rects + self.map.second_door_rects)
        return graph

    def _add_special(self, graph: PlatformGraph, kind: str, rects: list[pygame.Rect]) -> None:
        for i, rect in enumerate(rects):
            node_id = f"{kind}:{i}"
            graph.add_node(PlatformNode(node_id, rect.center, kind, tuple(rect)))
            platforms = [n for n in graph.nodes.values() if n.kind == "platform"]
            supports = [
                n for n in platforms
                if n.rect[0] - 4 <= rect.centerx <= n.rect[0] + n.rect[2] + 4
                and n.rect[1] >= rect.bottom - 12
            ]
            if platforms:
                nearest = min(supports, key=lambda n: n.rect[1]) if supports else min(
                    platforms, key=lambda n: math.dist(rect.midbottom, n.position)
                )
                dy = nearest.position[1] - rect.centery
                # The inward attachment is only an edge when the executor can
                # actually reach the special node from the support: upward
                # moves are bounded by the double-jump envelope. Anything
                # higher becomes a one-way outward edge only.
                if dy > 0 and dy > self.MAX_DOUBLE_JUMP_UP:
                    graph.add_edge(PlatformEdge(node_id, nearest.node_id, "drop", 0, 0.05))
                    continue
                # A special object whose bottom rests on the support's top is
                # reached by walking into it (plates, portals and final exits
                # are trigger rectangles, not ledges). Using rect.centery made
                # a 40px-tall exit look 20px above the floor and removed its
                # only inbound edge during jump-arc validation.
                if abs(nearest.rect[1] - rect.bottom) <= 12:
                    outward = inward = "walk"
                else:
                    outward = "drop" if dy > 45 else "jump" if dy < 0 else "walk"
                    inward = "jump" if dy > 0 else "drop" if dy < -45 else "walk"
                graph.add_edge(PlatformEdge(node_id, nearest.node_id, outward, 0, 0.05))
                if inward == "jump":
                    # Attachment jumps must obey the same physical arc as
                    # geometry edges, otherwise the planner routes through
                    # an unreachable stepping stone.
                    hazards = self.map.lava_rects
                    if self._line_hits_hazard(nearest.position, (rect.centerx, rect.centery), hazards):
                        continue
                    solids = self._top_surfaces(self.map.collision_rects) + self.map.platform_rects + self.map.breakable_rects
                    if not self._jump_arc_clear(nearest, graph.nodes[node_id], solids):
                        continue
                graph.add_edge(PlatformEdge(nearest.node_id, node_id, inward, 0, 0.05))

    def _add_door_sides(self, graph: PlatformGraph) -> None:
        margin = max(24, int(self.map.tile_size[0] * self.map.scale * 1.2))
        for prefix, source in (("door", self.map.door_rects), ("coop", self.map.second_door_rects)):
            groups: dict[int, list[pygame.Rect]] = {}
            for rect in source:
                groups.setdefault(rect.centerx, []).append(rect)
            for i, rects in enumerate(groups.values()):
                box = rects[0].unionall(rects[1:]) if len(rects) > 1 else rects[0]
                base = f"{prefix}:{i}"
                # Each side node needs a real stand rect at the door's base:
                # the default (0,0,1,1) placeholder breaks the walk probe
                # (a_probe_y = 0) and the jump-arc sweep for every edge
                # touching the door side, silently detaching it from the
                # platform it stands on.
                left = PlatformNode(f"{base}:left", (box.left - margin, box.bottom), "door_side",
                                    (box.left - margin - 20, box.bottom, 40, 8))
                right = PlatformNode(f"{base}:right", (box.right + margin, box.bottom), "door_side",
                                     (box.right + margin - 20, box.bottom, 40, 8))
                graph.add_node(left); graph.add_node(right)
                graph.add_edge(PlatformEdge(left.node_id, right.node_id, "door", 1, 0.2, f"open:{base}"), True)

    def _add_moving_docks(self, graph: PlatformGraph) -> None:
        points = self.map.moving_platform_points
        for i in range(0, len(points) - 1, 2):
            a, b = points[i], points[i + 1]
            na = PlatformNode(f"dock:{i // 2}:a", a.center, "dock", tuple(a))
            nb = PlatformNode(f"dock:{i // 2}:b", b.center, "dock", tuple(b))
            graph.add_node(na); graph.add_node(nb)
            cost = max(0.2, math.dist(a.center, b.center) / 60.0)
            graph.add_edge(PlatformEdge(na.node_id, nb.node_id, "ride", 0, cost, f"ride:{i // 2}:a>b"))
            graph.add_edge(PlatformEdge(nb.node_id, na.node_id, "ride", 0, cost, f"ride:{i // 2}:b>a"))

    @staticmethod
    def _line_hits_hazard(a: tuple[int, int], b: tuple[int, int], hazards: list[pygame.Rect]) -> bool:
        samples = max(2, int(math.dist(a, b) / 20))
        return any(h.collidepoint(a[0] + (b[0] - a[0]) * i / samples, a[1] + (b[1] - a[1]) * i / samples) for h in hazards for i in range(samples + 1))

    # Measured executor physics: jump force 720 / gravity 1800 with the
    # always-on friction capping horizontal speed at ≈183 px/s. A single
    # jump rises 144px; the double jump chained at the apex reaches 273px;
    # a full flat arc lands ≈235px away after ≈76 frames.
    PLAYER_W = 62
    PLAYER_H = 62
    RUN_SPEED = 183.0
    JUMP_V = 720.0
    GRAVITY = 1800.0
    SINGLE_RISE = 144
    DOUBLE_RISE = 273
    FLAT_ARC_DX = 235
    TILE = 40

    def _jump_arc_clear(self, a: PlatformNode, b: PlatformNode, solids: list[pygame.Rect]) -> bool:
        """Sweep the player box along the physical double-jump arc.

        The executor takes off from a's top, rises with the measured
        gravity profile while drifting toward b at run speed, and must land
        on b's top. Every swept player box may intersect only b (its
        landing support); any other solid tile clipping the box is a head
        bump or side pin the executor cannot escape.
        """
        a_box = pygame.Rect(a.rect)
        b_box = pygame.Rect(b.rect)
        ay = a_box.top
        by = b_box.top
        # The executor takes off from the edge of a facing b, not from a's
        # center: wide platforms shrink the true gap substantially.
        if b_box.centerx >= a_box.centerx:
            ax = a_box.right - self.PLAYER_W / 2 - 2
            bx = b_box.left + self.PLAYER_W / 2 + 2
        else:
            ax = a_box.left + self.PLAYER_W / 2 + 2
            bx = b_box.right - self.PLAYER_W / 2 - 2
        rise = ay - by  # positive when b is above a
        if rise < 0:
            rise = 0
        if rise > self.DOUBLE_RISE:
            return False
        # Time to apex with double jump (second impulse at apex): the
        # effective rise profile is approximated by two parabolas; sample
        # time until the arc descends back to by.
        v0 = self.JUMP_V
        t_apex = v0 / self.GRAVITY
        h1 = v0 * v0 / (2 * self.GRAVITY)  # single-impulse rise = 144
        # Full double-jump airtime: rise, boost at apex, rise again, fall
        # back to the takeoff height (≈1.2s). Landing higher than takeoff
        # only shortens the effective window; the arc keeps being swept so
        # the executor can drift horizontally while descending onto the
        # target top.
        total_air = 3 * t_apex
        start_feet = ay
        dx_total = bx - ax
        speed = self.RUN_SPEED
        t_needed = abs(dx_total) / speed
        if t_needed > total_air:
            return False
        # Rising with horizontal input pinned against a flank face keeps the
        # player right of that face; the executor only starts drifting once
        # its feet clear the tallest intervening solid in the corridor.
        corridor = pygame.Rect(min(ax, bx) - self.PLAYER_W, min(ay, by) - 4, abs(bx - ax) + 2 * self.PLAYER_W, abs(ay - by) + 4)
        clear_top = by
        for solid in solids:
            if solid == a_box or solid == b_box or a_box.contains(solid) or b_box.contains(solid):
                continue
            if solid.colliderect(corridor) and solid.top >= by:
                clear_top = min(clear_top, solid.top)
        t_clear = 0.0
        if clear_top < start_feet:
            need = start_feet - clear_top + self.PLAYER_H * 0.0
            if need <= h1:
                t_clear = math.sqrt(2 * need / self.GRAVITY)
            elif need <= 2 * h1:
                t_clear = t_apex + math.sqrt(2 * (need - h1) / self.GRAVITY)
            else:
                return False
        steps = max(8, int(total_air * 60))
        # Land as soon as the box rests on the target top; sweeping the
        # rest of the full airtime would climb into ceilings far above the
        # destination (e.g. a plate on a column under an overhang).
        land_top = min(by, start_feet - h1 if by < start_feet else by)
        for i in range(steps + 1):
            t = total_air * i / steps
            # Vertical position under the two-impulse profile.
            if t <= t_apex:
                h = v0 * t - 0.5 * self.GRAVITY * t * t
            elif t <= 2 * t_apex:
                t2 = t - t_apex
                h = h1 + v0 * t2 - 0.5 * self.GRAVITY * t2 * t2
            else:
                t3 = t - 2 * t_apex
                h = 2 * h1 - 0.5 * self.GRAVITY * t3 * t3
            feet = start_feet - h
            if by < start_feet and feet < by:
                feet = by  # clamp ascent at the landing top
            if by >= start_feet and h >= 0 and t > t_apex and feet > by:
                feet = by  # clamp descent onto a lower/equal target
            # Drift toward the target only after clearing the corridor top,
            # and never faster than the run speed allows.
            drift = min(abs(dx_total), speed * max(0.0, t - t_clear))
            x = ax + (drift if dx_total >= 0 else -drift)
            box = pygame.Rect(int(x - self.PLAYER_W / 2), int(feet - self.PLAYER_H), self.PLAYER_W, self.PLAYER_H)
            for solid in solids:
                # The takeoff and landing supports themselves are not
                # obstacles: the executor slides up the landing flank and
                # comes down onto its top, so any tile contained in either
                # node's merged rect is part of the route.
                if solid == a_box or solid == b_box or a_box.contains(solid) or b_box.contains(solid):
                    continue
                if box.colliderect(solid):
                    # Ceiling (more than a tile above the landing top):
                    # substantial overlap traps the arc. Anything lower is
                    # a step pad the executor slides onto and steps off,
                    # so only reject it when the box is deeply swallowed.
                    is_ceiling = solid.top < b_box.top - self.TILE
                    inter = box.clip(solid)
                    if is_ceiling and inter.width > 30 and inter.height > 8:
                        return False
                    if not is_ceiling and solid.top > b_box.top + self.TILE and inter.width > 20 and inter.height > 20:
                        return False
            if box.colliderect(b_box.inflate(0, 8)) and box.bottom <= b_box.top + 8:
                return True
        return False

    def _connect_geometry(self, graph: PlatformGraph, hazards: list[pygame.Rect], blockers: list[pygame.Rect]) -> None:
        nodes = list(graph.nodes.values())
        existing = {(e.source, e.target) for edges in graph.adjacency.values() for e in edges}
        solids = self._top_surfaces(self.map.collision_rects) + self.map.platform_rects + self.map.breakable_rects
        for a in nodes:
            for b in nodes:
                if a is b or (a.node_id, b.node_id) in existing:
                    continue
                dx = b.position[0] - a.position[0]; dy = b.position[1] - a.position[1]
                # The straight hazard check only makes sense for flat/downward
                # lines: an upward jump's straight chord dips through the lava
                # pit it is leaping OVER, while the real parabolic flight (arc
                # sweep below, with hazards merged into the swept solids)
                # clears it. Filtering upward jumps here cut the double-jump
                # onto the showcase ledge across the lava gorge.
                if dy >= 0 and self._line_hits_hazard(a.position, b.position, hazards):
                    continue
                line = (a.position, b.position)
                if any(blocker.clipline(line) for blocker in blockers):
                    continue
                movement = None
                if 0 <= dy <= 45 and abs(dx) <= 520:
                    # Walking requires a continuous floor: probe that the
                    # straight span between the two tops is supported every
                    # step, otherwise the executor would stride into a pit.
                    a_probe_y = a.rect[1]
                    b_probe_y = b.rect[1]
                    supported = True
                    span_l, span_r = min(a.position[0], b.position[0]), max(a.position[0], b.position[0])
                    step = self.TILE // 2
                    for px in range(span_l, span_r + 1, step):
                        if not any(
                            r.left <= px <= r.right and r.top >= min(a_probe_y, b_probe_y) - 4 and r.top <= max(a_probe_y, b_probe_y) + self.TILE + 8
                            for r in solids
                        ):
                            supported = False
                            break
                    if supported:
                        movement = "walk"
                elif dy < 0 and abs(dx) <= self.MAX_JUMP_X + self.TILE and (
                    abs(dy) <= self.MAX_JUMP_UP
                    or abs(dy) <= self.MAX_DOUBLE_JUMP_UP
                ):
                    # Wide-platform prescreen: the center-to-center dx above
                    # systematically kills double jumps onto a wide ledge from
                    # a narrow perch (ledge center sits far out even when the
                    # takeoff edge is adjacent). The arc sweep below is the
                    # precise judge; the prescreen only bounds the *edge gap*.
                    edge_gap = max(0, abs(dx) - (a.rect[2] + b.rect[2]) / 2)
                    if not (abs(dy) <= self.MAX_JUMP_UP or (abs(dy) <= self.MAX_DOUBLE_JUMP_UP and edge_gap <= self.MAX_DOUBLE_JUMP_X)):
                        continue
                    # A player standing with its lower body inside water jumps
                    # at 60% force and does not receive the normal ground-set
                    # double jump. Reject tall dry-physics arcs from submerged
                    # supports; these were routing through the level_001 west
                    # pool even though the live player rises only ~52px.
                    feet_box = pygame.Rect(a.rect[0], a.rect[1] - self.PLAYER_H, a.rect[2], self.PLAYER_H)
                    submerged = any(feet_box.colliderect(w) for w in self.map.water_rects)
                    if submerged and abs(dy) > 80:
                        continue
                    # Stairs movement means climbing the column by holding
                    # jump; that only applies to short spans inside the same
                    # staircase. Long traverses to/from a stairs tile must be
                    # judged as ordinary jump/drop geometry instead.
                    movement = (
                        "stairs"
                        if (a.kind == "stairs" or b.kind == "stairs") and abs(dx) <= self.TILE * 3
                        else "jump"
                    )
                elif 0 < dy <= 80 and abs(dx) <= self.MAX_JUMP_X and abs(dx) > self.TILE:
                    # Gap leap: the span is not walkable (the walk probe
                    # above failed), but a shallow downward jump crosses
                    # the gap. Validated by the same physical arc sweep.
                    movement = "jump"
                elif dy > 0 and abs(dx) <= 260 and dy <= self.MAX_DROP:
                    movement = "drop"
                if movement == "jump" and a.kind != "stairs" and b.kind != "stairs":
                    a_rect = pygame.Rect(a.rect) if len(a.rect) == 4 else pygame.Rect(a.position[0] - 20, a.position[1], 40, 40)
                    b_rect = pygame.Rect(b.rect) if len(a.rect) == 4 else pygame.Rect(b.position[0] - 20, b.position[1], 40, 40)
                    # Hazards ride along in the swept solids: the parabolic
                    # flight may not clip lava even though the straight chord
                    # pre-filter no longer rejects upward jumps.
                    if not self._jump_arc_clear(PlatformNode(a.node_id, a.position, a.kind, tuple(a_rect)), PlatformNode(b.node_id, b.position, b.kind, tuple(b_rect)), solids + hazards):
                        continue
                    # A jump (including a shallow gap leap) through a closed
                    # door body is not executable either: the arc sweep above
                    # only knows collision solids, so door rects must veto the
                    # edge here. Conditionally-open door edges added elsewhere
                    # remain the legal way across.
                    if any(blocker.clipline((a.position, b.position)) for blocker in blockers):
                        continue
                if movement:
                    cost = max(0.1, math.dist(a.position, b.position) / (450 if movement == "walk" else 300))
                    graph.add_edge(PlatformEdge(a.node_id, b.node_id, movement, (dx > 0) - (dx < 0), cost))
