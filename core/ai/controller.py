"""Cooperative task selection and Action-only execution of searched graph paths."""

from dataclasses import dataclass
from enum import Enum
import math

from core.ai.actions import Action
from core.ai.observation import Observation
from core.ai.script_controller import LevelScriptController, ScriptDirective
from core.ai.search import SearchResult, SearchStats, search


@dataclass(frozen=True, slots=True)
class ControllerMetrics:
    algorithm: str
    goal: str
    expanded: int
    path_length: int
    replans: int
    candidates: tuple[str, ...] = ()
    winner: str = ""


class _GoalOrderedGraph:
    """Deterministic neighbor ordering; search semantics remain unchanged."""

    def __init__(self, graph, goal: str) -> None:
        self.graph = graph
        self.goal = goal

    def neighbors(self, node: str, conditions: frozenset[str]):
        goal_pos = self.graph.nodes[self.goal].position
        values = list(self.graph.neighbors(node, conditions))
        values.sort(key=lambda item: math.dist(self.graph.nodes[item[0]].position, goal_pos))
        return values


class CooperativeTaskController:
    """Backward-compatible facade over the explicit per-level script controller."""

    def __init__(self, player_index: int = 1) -> None:
        self.player_index = player_index
        self.scripts = LevelScriptController(player_index)

    def choose_goal(self, observation: Observation) -> tuple[str | None, str]:
        directive = self.scripts.directive(observation)
        return directive.node_id, directive.goal_key

    def directive(self, observation: Observation) -> ScriptDirective:
        return self.scripts.directive(observation)


class ExecutionState(str, Enum):
    FOLLOWING = "FOLLOWING"
    APPROACH = "APPROACH"
    BRAKE = "BRAKE"
    HOLD = "HOLD"
    WAIT = "WAIT"
    COMPLETE = "COMPLETE"


class SearchActionProvider:
    """Plan on a platform graph and emit only immutable Action values.

    Hybrid planner: every plan runs BFS, DFS and A* over the same graph,
    conditions and edge blacklist, then fuses them into a single executable
    route by preferring the lowest-cost path while penalising risky moves and
    favouring an alternative when A*'s first edge has been blacklisted. The
    winner and the full candidate set are exposed for the debug overlay and
    tests, but the user never chooses a single algorithm.
    """

    STUCK_SECONDS = 1.5
    WAYPOINT_RADIUS = 34
    VERTICAL_CLIMB_SPAN = 110
    SINGLE_RISE = 144
    # Flat gaps wider than this can only be cleared with the extra air time of
    # a double jump (a full-speed single jump glides ~150-175px); narrower flat
    # gaps stay single-jump so the second jump cannot overshoot the target.
    DOUBLE_GAP_SPAN = 150
    STABLE_FRAMES = 8
    SIM_STICKY_SECONDS = 1.0
    # Grace window for the adaptive double-jump injection: if the live player
    # has not entered the near-apex band this many frames after the scripted
    # double-jump frame, the double jump is spent anyway (it expires on
    # landing, so holding it forever only delays the next edge).
    DOUBLE_WAIT_FRAMES = 45
    SAFETY = {"walk": 0.0, "stairs": 0.0, "door": 2.0, "ride": 3.0, "drop": 4.0, "jump": 5.0}

    def __init__(self, algorithm: str | None = None, player_index: int = 1, prefer: str | None = None) -> None:
        # `prefer` is test-only: it forces a specific winner without removing the
        # hybrid run of all three algorithms. `algorithm` is kept for backward
        # compatibility with older call sites that used positional algorithm names.
        self.algorithm = "Hybrid"
        self._prefer = prefer.upper().replace("ASTAR", "A*") if prefer else None
        self.player_index = player_index
        self.tasks = CooperativeTaskController(player_index)
        self.path: tuple[str, ...] = ()
        self.path_index = 0
        self.goal_node: str | None = None
        self.goal_key = "ai.goal.wait"
        self.stats = SearchStats()
        self.replans = 0
        self.winner = ""
        self.candidates: tuple[str, ...] = ()
        self._last_position: tuple[float, float] | None = None
        self._still_time = 0.0
        self._best_progress: float = float("inf")
        self._best_progress_node: str | None = None
        self._last_conditions = frozenset()
        self._jump_held = False
        self._plan_attempts = 0
        self._retry_cooldown = 0.0
        self._failed_edges: dict[tuple[str, str], int] = {}
        self._blacklisted_edges: set[tuple[str, str]] = set()
        self._consecutive_failures = 0
        self._reset_requested = False
        self.execution_state = ExecutionState.WAIT
        self.script_step = 0
        self.operation = "wait"
        self.semantic_target: str | None = None
        self._task_identity: tuple[int, str, str | None] | None = None
        self._directive: ScriptDirective | None = None
        self._stable_frames = 0
        self._sim_script: list[Action] | None = None
        self._sim_index = 0
        self._sim_target: tuple[str, object] | None = None
        # Sticky simulator cache: a committed script is reused for a short
        # window instead of re-searching every frame (the rollout is the
        # single most expensive operation in the tick).
        self._sim_cache: tuple[str, tuple[Action, ...], tuple[float, float], int | None] | None = None
        self._sim_cache_ttl = 0.0
        self._sim_double_index: int | None = None
        self._sim_double_wait = 0
        # Hold discipline: single-side dead-band correction with a public flip
        # counter so tests can assert the absence of left/right oscillation.
        self._hold_direction = 0
        self.hold_flips = 0
        # Sticky re-search guard: after a successful commit, short-circuit
        # repeated _simulate_edge rollouts for the same target while the
        # player stays near where the script was found.
        self._sim_probe_rect: tuple[float, float] | None = None

    @property
    def metrics(self) -> ControllerMetrics:
        return ControllerMetrics(
            self.algorithm,
            self.goal_key,
            self.stats.expanded,
            len(self.path),
            self.replans,
            self.candidates,
            self.winner,
        )

    def _run_all(self, graph, start: str, goal: str, conditions: frozenset[str]) -> list[tuple[str, SearchResult]]:
        """Run BFS, DFS and A* and return their (name, result) pairs."""
        runs: list[tuple[str, SearchResult]] = []
        for name in ("BFS", "DFS", "A*"):
            search_graph = _GoalOrderedGraph(graph, goal) if name == "DFS" else graph
            runs.append((name, search(
                name,
                search_graph,
                start,
                goal,
                graph.heuristic,
                conditions,
            )))
        return runs

    @staticmethod
    def _path_risk(graph, path: tuple[str, ...]) -> float:
        risk = 0.0
        for a, b in zip(path, path[1:]):
            edge = graph.edge(a, b)
            if edge is not None:
                risk += SearchActionProvider.SAFETY.get(edge.movement, 2.0)
        return risk

    def _select(self, runs: list[tuple[str, SearchResult]], graph) -> tuple[str, SearchResult] | None:
        """Fuse candidates: prefer a found path, lowest cost, then lowest risk."""
        found = [(name, result) for name, result in runs if result.found]
        self.candidates = tuple(
            name for name, result in runs if result.found
        ) or tuple(name for name, _ in runs)
        if not found:
            self.winner = ""
            return None
        if self._prefer in {name for name, _ in found}:
            for name, result in found:
                if name == self._prefer:
                    self.winner = name
                    return name, result
        self.candidates = tuple(name for name, _ in found)
        best = min(
            found,
            key=lambda item: (item[1].stats.path_cost, self._path_risk(graph, item[1].path)),
        )
        self.winner = best[0]
        return best

    def _safe_winner(self, result: tuple[str, SearchResult], graph) -> tuple[str, SearchResult]:
        if not result[1].found or len(result[1].path) < 2:
            return result
        first = (result[1].path[0], result[1].path[1])
        if first in self._blacklisted_edges:
            # Prefer an alternative candidate whose next edge is not blacklisted.
            backups = [
                (name, r) for name, r in self._last_runs
                if r.found and (r.path[0], r.path[1]) not in self._blacklisted_edges
            ]
            if backups and any(name != result[0] for name, _ in backups):
                return min(
                    backups,
                    key=lambda item: (item[1].stats.path_cost, self._path_risk(graph, item[1].path)),
                )
        return result

    def _apply_directive(self, directive: ScriptDirective) -> bool:
        changed = directive.identity != self._task_identity
        self._directive = directive
        self.script_step = directive.step_index
        self.operation = directive.operation
        self.semantic_target = directive.semantic_target
        self.goal_key = directive.goal_key
        if changed:
            self._task_identity = directive.identity
            self.path = (); self.path_index = 0; self.goal_node = None
            self._still_time = 0.0; self._stable_frames = 0
            self._failed_edges.clear(); self._blacklisted_edges.clear()
            self._consecutive_failures = 0; self._retry_cooldown = 0.0
            self._sim_cache = None; self._sim_cache_ttl = 0.0
            self._sim_double_index = None; self._sim_double_wait = 0
        if directive.complete:
            self.execution_state = ExecutionState.COMPLETE
        elif directive.operation == "wait":
            self.execution_state = ExecutionState.WAIT
        elif changed:
            self.execution_state = ExecutionState.FOLLOWING
        return changed

    def _plan(self, observation: Observation, directive: ScriptDirective | None = None) -> None:
        graph = observation.graph
        directive = directive or self.tasks.directive(observation)
        self._apply_directive(directive)
        goal = directive.node_id
        if self._plan_attempts:
            self.replans += 1
        self._plan_attempts += 1
        if graph is None or goal is None:
            self.path = (); self.goal_node = goal; self.winner = ""; self.candidates = ()
            if directive.operation not in {"wait", "complete"}:
                self._retry_cooldown = 0.5
                self._consecutive_failures += 1
                if self._consecutive_failures >= 6:
                    self._reset_requested = True; self._consecutive_failures = 0
            return
        me = observation.players[self.player_index]
        start = me.platform_id or graph.nearest_node(me.rect[:2]).node_id
        blocked = frozenset(f"blocked:{a}>{b}" for a, b in self._blacklisted_edges)
        conditions = observation.graph_conditions | blocked
        runs = self._run_all(graph, start, goal, conditions)
        self._last_runs = runs
        selected = self._select(runs, graph)
        if selected is None:
            self.path = (); self.goal_node = goal; self.stats = SearchStats()
            self._last_conditions = observation.graph_conditions
            self._consecutive_failures += 1
            self._retry_cooldown = min(1.5, 0.25 * self._consecutive_failures)
            if self._consecutive_failures >= 6:
                self._reset_requested = True
                self._consecutive_failures = 0
                self._blacklisted_edges.clear()
            return
        selected = self._safe_winner(selected, graph)
        self.path = selected[1].path
        self.path_index = 1 if len(self.path) > 1 else 0
        self.goal_node = goal
        self.stats = selected[1].stats
        self._last_conditions = observation.graph_conditions
        self.execution_state = ExecutionState.FOLLOWING if self.path_index < len(self.path) - 1 else ExecutionState.APPROACH
        if not selected[1].found:
            self._consecutive_failures += 1
            self._retry_cooldown = min(1.5, 0.25 * self._consecutive_failures)
            if self._consecutive_failures >= 6:
                self._reset_requested = True
                self._consecutive_failures = 0
                self._blacklisted_edges.clear()
        else:
            self._consecutive_failures = 0

    def consume_reset_request(self) -> bool:
        requested = self._reset_requested
        self._reset_requested = False
        if requested:
            self.path = ()
            self.path_index = 0
            self.goal_node = None
            self._last_position = None
            self._best_progress = float("inf")
            self._best_progress_node = None
            self._still_time = 0.0
            self._last_conditions = frozenset()
            self._retry_cooldown = 0.0
            self._failed_edges.clear()
            self._blacklisted_edges.clear()
            self._sim_script = None; self._sim_index = 0; self._sim_target = None
            self._sim_cache = None; self._sim_cache_ttl = 0.0
            self._sim_double_index = None; self._sim_double_wait = 0
        return requested

    @staticmethod
    def _overlaps_target(me, rect) -> bool:
        if rect is None:
            return False
        feet = (me.rect[0] + 2, me.rect[1] + me.rect[3] - 14, me.rect[2] - 4, 16)
        return (feet[0] < rect[0] + rect[2] and feet[0] + feet[2] > rect[0]
                and feet[1] < rect[1] + rect[3] and feet[1] + feet[3] > rect[1])

    def _acquired(self, observation: Observation, directive: ScriptDirective) -> bool:
        me = observation.players[self.player_index]
        if directive.operation in {"hold", "latch"}:
            return self._overlaps_target(me, directive.target_rect) and abs(me.velocity[0]) <= 45 and me.on_ground
        if directive.operation == "enter" and directive.semantic_target == "portal":
            return observation.portal_entered[self.player_index]
        if directive.operation == "enter" and directive.semantic_target and directive.semantic_target.startswith("exit:"):
            return observation.final_exit_entered[self.player_index]
        if directive.operation == "cross" and directive.target_rect:
            return me.rect[0] >= directive.target_rect[0]
        return False

    def _record_edge_success(self) -> None:
        if 0 < self.path_index < len(self.path):
            edge = (self.path[self.path_index - 1], self.path[self.path_index])
            failures = self._failed_edges.get(edge, 0)
            if failures <= 1:
                self._failed_edges.pop(edge, None)
            else:
                self._failed_edges[edge] = failures - 1
            self._blacklisted_edges.discard(edge)

    def tick(self, dt: float, observation: Observation) -> Action:
        self._retry_cooldown = max(0.0, self._retry_cooldown - dt)
        if self._sim_cache_ttl > 0.0:
            self._sim_cache_ttl = max(0.0, self._sim_cache_ttl - dt)
        directive = self.tasks.directive(observation)
        self._apply_directive(directive)
        if self.execution_state in {ExecutionState.WAIT, ExecutionState.COMPLETE}:
            self._still_time = 0.0
            return Action()
        if self.execution_state == ExecutionState.HOLD:
            self._still_time = 0.0
            return self._hold_action(observation, directive)

        me = observation.players[self.player_index]
        if self.path and self.path_index >= len(self.path):
            self.path_index = len(self.path) - 1
        position = me.position
        # A jump/drop may land on a later platform in the planned route before
        # entering an intermediate waypoint radius. Fast-forward to the reached
        # support instead of repeatedly steering back toward an obsolete node.
        if me.on_ground and me.platform_id in self.path[self.path_index:]:
            reached = max(i for i in range(self.path_index, len(self.path)) if self.path[i] == me.platform_id)
            if reached >= self.path_index:
                self.path_index = min(reached + 1, len(self.path) - 1)
                self._still_time = 0.0
                self._record_edge_success()
        if self._last_position is None:
            self._last_position = position
        moved = math.dist(position, self._last_position)
        # While a simulator-validated script is being replayed the stuck clock
        # is suspended: the script IS the recovery plan, and a backswing run-up
        # deliberately walks away from the waypoint before jumping, which the
        # waypoint-distance metric would otherwise read as being stuck.
        sim_running = self._sim_script is not None
        active_edge = bool(
            self.path
            and (
                self.path_index < len(self.path) - 1
                or not self._acquired(observation, directive)
            )
        ) and not sim_running
        # An edge only counts as succeeded once the player actually arrives at
        # its target node (the fast-forward above). Raw per-frame movement must
        # not clear failure history: bouncing under an unreachable waypoint
        # moves plenty every frame and would erase the blacklist forever.
        if moved >= 8:
            if not active_edge:
                self._record_edge_success()
            # Raw movement cannot distinguish progress from a jump loop under
            # an unreachable waypoint: vertical bobbing reverts every frame.
            # Progress is measured as the closest the player has ever come to
            # the current waypoint; bouncing that returns to the same distance
            # never resets the stuck clock, only a genuinely closer approach or
            # a new waypoint does.
            waypoint = None
            if self.path and self.path_index < len(self.path) and observation.graph is not None:
                waypoint = observation.graph.nodes[self.path[self.path_index]].position
            if waypoint is not None and self.path[self.path_index] == self._best_progress_node:
                distance = math.dist((position[0], me.rect[1] + me.rect[3]), waypoint)
                if distance < self._best_progress - 24:
                    self._best_progress = distance
                    self._still_time = 0.0
                else:
                    self._still_time += dt
            else:
                self._best_progress_node = self.path[self.path_index] if waypoint is not None else None
                self._best_progress = math.dist((position[0], me.rect[1] + me.rect[3]), waypoint) if waypoint is not None else 0.0
                self._still_time = 0.0
            self._last_position = position
        elif active_edge and not me.dead:
            self._still_time += dt
        else:
            self._still_time = 0.0
        stuck = active_edge and self._still_time >= self.STUCK_SECONDS
        if stuck and self.path_index > 0:
            failed = (self.path[self.path_index - 1], self.path[self.path_index])
            self._failed_edges[failed] = self._failed_edges.get(failed, 0) + 1
            if self._failed_edges[failed] >= 2:
                self._blacklisted_edges.add(failed); self._consecutive_failures += 1
            if self._consecutive_failures >= 6:
                self._reset_requested = True; self._consecutive_failures = 0; self._blacklisted_edges.clear()
        must_replan = ((not self.path and self._retry_cooldown <= 0)
                       or directive.node_id != self.goal_node
                       or (observation.graph_conditions != self._last_conditions and active_edge)
                       or stuck)
        if must_replan:
            self._plan(observation, directive)
            self._sim_script = None
            self._sim_index = 0
            self._sim_cache = None
            self._sim_cache_ttl = 0.0
            self._sim_double_index = None
            self._sim_double_wait = 0
            self._still_time = 0.0; self._last_position = position
            self._best_progress = float("inf"); self._best_progress_node = None
        return self._action_for_path(observation, directive)

    def get_action(self, observation: Observation | None) -> Action:
        return Action() if observation is None else self.tick(1 / 60, observation)

    def _hold_action(self, observation: Observation, directive: ScriptDirective) -> Action:
        """Stay parked on the target band without oscillating.

        Dead-band control: inside the band no input is pressed at all —
        friction brings the player to a stop — and only when the player has
        actually drifted out of the band does a single-side correction kick
        in. Pressing the opposite key at speed (the old behaviour) fought the
        momentum every frame and showed up as per-frame left/right flipping.
        """
        me = observation.players[self.player_index]; rect = directive.target_rect
        if rect is None:
            return Action()
        center = me.rect[0] + me.rect[2] / 2
        band = min(12.0, max(4.0, rect[2] * 0.25))
        band_left = rect[0] + band
        band_right = rect[0] + rect[2] - band
        if band_left <= center <= band_right:
            self._hold_direction = 0
            return Action()
        wanted = 1 if center < band_left else -1
        if wanted != self._hold_direction:
            self._hold_direction = wanted
            self.hold_flips += 1
        return Action(right=wanted > 0, left=wanted < 0)

    def _approach_action(self, observation: Observation, directive: ScriptDirective) -> Action:
        me = observation.players[self.player_index]; rect = directive.target_rect
        if rect is None:
            return Action()
        dx = rect[0] + rect[2] / 2 - (me.rect[0] + me.rect[2] / 2)
        vx = me.velocity[0]
        if directive.operation == "cross":
            self.execution_state = ExecutionState.APPROACH
            return Action(left=dx < -4, right=dx > 4)
        if self._acquired(observation, directive):
            self._stable_frames += 1
            if self._stable_frames >= self.STABLE_FRAMES:
                self.execution_state = ExecutionState.HOLD if directive.operation == "hold" else ExecutionState.WAIT if directive.operation == "latch" else ExecutionState.COMPLETE
                return Action()
        else:
            self._stable_frames = 0
        # Releasing input invokes Player friction and is a stable brake; opposite
        # input near the target was the source of frame-by-frame direction flips.
        # Friction decays |vx| exponentially (coefficient 10), so the glide
        # distance of a release-brake is ~|vx|/10; the old quadratic model
        # under-estimated it and the player repeatedly overshot the centre and
        # ping-ponged around the target.
        if self._overlaps_target(me, rect) or abs(dx) <= max(8, abs(vx) / 10 + 8):
            self.execution_state = ExecutionState.BRAKE
            return Action()
        self.execution_state = ExecutionState.APPROACH
        return Action(left=dx < -8, right=dx > 8)

    def _wants_jump(self, edge, me, dy: float, span: float = 0.0) -> bool:
        if edge is None or edge.movement not in {"jump", "stairs"}:
            return False
        if me.in_water and dy < 0:
            return True
        if me.on_ground:
            return not self._jump_held
        # Double jump is only consumed near the apex, and only when the
        # remaining climb exceeds a single jump's rise or the horizontal span
        # demands the extra air time of a second jump (mirrors
        # `_simulate_edge`'s use_double gate). Short hops must not overshoot
        # onto higher ledges or over the target.
        if not me.on_ground:
            self._jump_held = False
        if dy >= -self.SINGLE_RISE and span <= self.DOUBLE_GAP_SPAN:
            return False
        return bool(me.has_double_jump and abs(me.velocity[1]) <= 180)

    def _takeoff_alignment(self, observation: Observation, me, edge, target) -> Action | None:
        """Build speed and align before a rising jump.

        A jump taken from a standing start covers only a fraction of the
        graph's 430px horizontal envelope: horizontal velocity needs ~17
        frames to reach max, so long arcs land short and pin the player
        against side faces. Near-vertical climbs instead must NOT press
        toward the target during takeoff: wall/ceiling tiles at the target's
        flank catch the drifting player. So: long jumps require |vx| near
        max in the edge direction first; short climbs require standing in
        the target's x-band before jumping.
        """
        if edge is None or edge.movement != "jump" or not me.on_ground:
            return None
        target_top = target.rect[1]
        feet = me.rect[1] + me.rect[3]
        if target_top >= feet - 8:
            return None
        dx = target.position[0] - me.position[0]
        span = abs(dx)
        direction = 1 if dx > 0 else -1
        vx = me.velocity[0]
        if span > self.VERTICAL_CLIMB_SPAN:
            # Long arc: accelerate in the edge direction; the physics cap is
            # the run speed, so demand full speed before takeoff (the arc
            # sweep on the graph side already proved the span reachable).
            required = min(183.0, 60.0 + span * 1.6)
            if vx * direction < required - 12:
                self.execution_state = ExecutionState.APPROACH
                return Action(right=direction > 0, left=direction < 0)
            return None
        # Near-vertical climb: horizontal input during takeoff only causes
        # wall/ceiling pinning. Walk until the player box genuinely overlaps
        # the target's x-span (not merely touches its edge), then jump.
        # A step-up whose band can never be overlapped from below (the
        # player wedged against the target's own flank) must jump from the
        # face: rising while pressing into it clears the lip.
        band_left, band_right = target.rect[0], target.rect[0] + target.rect[2]
        my_left, my_right = me.rect[0], me.rect[0] + me.rect[2]
        pressing = me.velocity[0] == 0 or (me.velocity[0] > 0 == (dx > 0)) or (me.velocity[0] < 0 == (dx < 0))
        wedged = abs(me.velocity[0]) < 8 and (
            (dx > 0 and my_right >= band_left - 2) or (dx < 0 and my_left <= band_right + 2)
        )
        if my_right < band_left + 8 and not wedged:
            self.execution_state = ExecutionState.APPROACH
            return Action(right=True)
        if my_left > band_right - 8 and not wedged:
            self.execution_state = ExecutionState.APPROACH
            return Action(left=True)
        if wedged:
            direction = 1 if dx > 0 else -1
            return Action(jump=True, right=direction > 0, left=direction < 0)
        return Action(jump=True)

    def _commit_sim_script(self, trail: list[Action], target, _pg) -> None:
        """Commit a simulator-validated trajectory for frame-by-frame replay.

        The index of the mid-air double-jump press is recorded so the replay
        can inject it adaptively (see `_action_for_path`): the near-apex
        window is only a few frames wide, so a literal frame-indexed replay
        misses it whenever live physics drifts a handful of frames from the
        rollout. The target and player snapshot key the drift check.
        """
        me_rect = getattr(self, "_sim_probe_rect", None)
        self._sim_script = list(trail)
        self._sim_index = 1  # trail[0] is returned by the caller
        self._sim_target = (target.node_id, _pg.Rect(target.rect).copy())
        presses = [i for i in range(len(trail)) if trail[i].jump and (i == 0 or not trail[i - 1].jump)]
        self._sim_double_index = presses[1] if len(presses) > 1 else None
        self._sim_double_wait = 0
        self._sim_cache = (
            target.node_id,
            tuple(trail),
            me_rect if me_rect is not None else (0.0, 0.0),
            self._sim_double_index,
        )
        self._sim_cache_ttl = self.SIM_STICKY_SECONDS

    def _simulate_edge(self, observation: Observation, me, target) -> Action | None:
        """Search a short Action script that lands on `target` by simulation.

        Headless Player clones roll candidate policies (walk-forward delays,
        stand-jumps, double jump at apex) against the real collision geometry.
        The winning candidate's FULL action sequence is committed to
        `_sim_script` and replayed into the live action stream: returning only
        the first frame would re-run the search next frame and never consume
        the delayed jump, looping forever on walk. Replay aborts early once
        the target is actually reached, absorbing world drift.
        """
        import pygame as _pg

        from core.physics_clone import clone_observed_player

        # Sticky cache: while the player stands near where the cached script
        # was found and the TTL has not expired, reuse the committed script
        # instead of re-running the (expensive) rollout sweep every frame.
        self._sim_probe_rect = (me.rect[0], me.rect[1])
        if (
            self._sim_cache is not None
            and self._sim_cache_ttl > 0.0
            and self._sim_cache[0] == target.node_id
            and self._sim_cache[2] == self._sim_probe_rect
        ):
            self._sim_script = list(self._sim_cache[1])
            self._sim_index = 1
            self._sim_target = (target.node_id, _pg.Rect(target.rect).copy())
            self._sim_double_index = self._sim_cache[3]
            self._sim_double_wait = 0
            return self._sim_script[0]

        def rollout(first: Action, delay: int, hold_dir: int, use_double: bool, horizon: int, hold_jump: bool = False, release: int = 0):
            sim = clone_observed_player(me)

            # Real-game split: collision solids stop on all sides; one-way
            # platforms only catch a falling player. Feeding one-way platform
            # tiles as solids made the clones head-bump platforms from below
            # (vy zeroed) and destroyed every double jump.
            collision = [_pg.Rect(r) for r in (observation.solids or observation.platforms)]
            oneway = [_pg.Rect(r) for r in observation.platforms]
            water = [_pg.Rect(r) for r in observation.water]
            stairs = [_pg.Rect(r) for r in observation.stairs] or None
            lava = [_pg.Rect(r) for r in observation.lava] or None
            target_rect = _pg.Rect(target.rect)
            double_fired = not use_double
            best = (1e9, 0, False)
            trail: list[Action] = []
            for i in range(horizon):
                drift = 0 if (release and not sim.on_ground and i >= release) else hold_dir
                if hold_jump:
                    # Stairs climb: every frame re-presses jump. Each press
                    # resets vy to the stairs climb impulse while inside the
                    # stairs column, so a single tap only rises ~40px before
                    # friction decays it — holding jumps the full column.
                    act = Action(jump=True, right=drift > 0, left=drift < 0)
                elif i == delay and sim.on_ground and delay >= 0:
                    act = Action(jump=True, right=drift > 0, left=drift < 0)
                elif (
                    not double_fired
                    and not sim.on_ground
                    and sim.has_double_jump
                    and abs(sim.velocity.y) <= self.SINGLE_RISE
                ):
                    # Must match Player._near_apex (|vy| <= 0.2*jump_force =
                    # 144): presses outside that window are silently ignored,
                    # so a 180-gate wastes the double jump entirely.
                    act = Action(jump=True, right=drift > 0, left=drift < 0)
                    double_fired = True
                else:
                    act = first if i == 0 else Action(right=drift > 0, left=drift < 0)
                trail.append(act)
                sim.update(1 / 60, collision, water, stairs, lava, oneway, [], action=act)
                feet = sim.rect.bottom
                dist = abs(sim.rect.centerx - target.position[0]) + abs(feet - target_rect.top)
                over = target_rect.left - 4 <= sim.rect.centerx <= target_rect.right + 4
                if sim.on_ground and over and abs(feet - target_rect.top) <= 12:
                    return (0.0, i, True, trail)
                # A rising player inside a stairs target's x-span at its top
                # level has effectively climbed that rung. Ordinary platforms
                # must wait for a real grounded landing; otherwise the path
                # advances while the live player is still below the pad.
                if hold_jump and feet <= target_rect.top + 6 and over:
                    return (0.0, i, True, trail)
                if dist < best[0]:
                    best = (dist, i, False)
                if sim.dead or sim.in_lava or sim.rect.top > target_rect.top + 700:
                    return (best[0] + 1000, i, False, trail)
            return (best[0], horizon, best[2], trail)

        dx = target.position[0] - me.position[0]
        direction = 1 if dx > 0 else -1
        dy = target.rect[1] - (me.rect[1] + me.rect[3])
        # Double jump is for big climbs AND for long flat gaps: a full-speed
        # single jump only glides ~150-175px, so anything wider needs the
        # extra air time of a second jump (the old `dy < -SINGLE_RISE` gate
        # left every gap-leap edge landing short).
        use_double = dy < -self.SINGLE_RISE or abs(dx) > self.DOUBLE_GAP_SPAN
        walk = Action(right=direction > 0, left=direction < 0)
        needs_double = dy < -self.SINGLE_RISE
        use_double = needs_double or abs(dx) > self.DOUBLE_GAP_SPAN
        # A flat gap only *forces* the double jump beyond the span threshold;
        # for those edges also keep single-jump variants so an overshooting
        # second jump cannot starve the search of a landing candidate.
        dbl_variants: tuple[bool, ...] = (True, False) if use_double and not needs_double else (use_double,)
        candidates: list[tuple[Action, int, int, bool, bool, int]] = []
        if me.on_ground:
            # delay = the rollout frame that presses jump; the walk frames
            # before it carry the player to the takeoff edge (e.g. the lip of
            # the platform below the target). delay < 0 means jump NOW — the
            # first action itself is the jump, there is no walk phase.
            # release = airborne frames after takeoff to keep drifting before
            # going neutral; several narrow ledges (40px one-way tiles flanked
            # by walls) are only landable if the drift stops mid-flight.
            for delay in (1, 3, 6, 10, 16, 24, 36, 52):
                for dbl in dbl_variants:
                    candidates.append((walk, delay, direction, dbl, False, 0))
            for dbl in dbl_variants:
                candidates.append((Action(jump=True, right=direction > 0, left=direction < 0), -1, direction, dbl, False, 0))
            candidates.append((walk, -1, -direction, False, False, 0))
            # Backswing run-ups: the takeoff edge may need full speed in the
            # jump direction while the only runway lies BEHIND the current
            # spot (e.g. standing on a ledge's far corner). Walk away first,
            # then turn and jump with the acquired momentum.
            for delay in (4, 8, 14, 22, 32):
                for dbl in dbl_variants:
                    candidates.append((Action(right=(-direction > 0), left=(-direction < 0)), delay, direction, dbl, False, 0))
            if use_double:
                for dbl in dbl_variants:
                    for rel in (4, 8, 12, 18, 26, 36):
                        candidates.append((Action(jump=True, right=direction > 0, left=direction < 0), -1, direction, dbl, False, rel))
            if dy < 0 and (target.kind == "stairs" or me.on_stairs):
                # Stairs-style climb: hold jump every frame and drift toward
                # the target (covers the stairs columns, whose repeated
                # impulses are the only way to ascend).
                candidates.append((walk, -1, direction, False, True, 0))
                candidates.append((walk, -1, 0, False, True, 0))
        else:
            candidates.append((walk, 0, direction, use_double, False, 0))
            candidates.append((walk, 0, 0, False, False, 0))
            candidates.append((walk, 0, -direction, False, False, 0))
        best = None
        best_cost = 1e9
        for first, delay, hold_dir, dbl, hj, rel in candidates:
            cost, _, landed, trail = rollout(first, delay, hold_dir, dbl, 130, hj, rel)
            if landed and trail:
                # Commit the whole validated trajectory, jump frame included.
                # Abort the replay the moment the live player reaches the
                # target band so minor physics drift cannot carry it past.
                self._commit_sim_script(trail, target, _pg)
                return trail[0]
            if cost < best_cost:
                best_cost = cost
                best = first
        return best

    def _action_for_path(self, observation: Observation, directive: ScriptDirective | None = None) -> Action:
        directive = directive or self._directive or self.tasks.directive(observation)
        graph = observation.graph
        if not self.path or graph is None:
            return Action()
        me = observation.players[self.player_index]
        if self.path_index >= len(self.path):
            # A fast-forward consumed the last node; switch to approach/hold.
            self.path_index = len(self.path) - 1
        # Replay a simulator-validated script frame by frame: the jump frame
        # lives mid-script, so per-frame re-searching would only ever consume
        # the leading walk action. Abort once the target is genuinely reached
        # (waypoint radius or landing overlap) so drift re-searches instead of
        # completing a stale trajectory.
        if self._sim_script is not None:
            reached = False
            if self._sim_target is not None and self.path_index < len(self.path):
                node_id, target_rect = self._sim_target
                feet = me.rect[1] + me.rect[3]
                center = me.rect[0] + me.rect[2] / 2
                over = target_rect.left - 4 <= center <= target_rect.right + 4
                if node_id == self.path[self.path_index] and (
                    (me.on_ground and over and abs(feet - target_rect.top) <= 12)
                    or (abs(center - (target_rect.centerx)) <= self.WAYPOINT_RADIUS
                        and abs(feet - target_rect.top) <= 55)
                ):
                    reached = True
            if reached:
                self._sim_script = None
                self._sim_index = 0
                self._sim_target = None
            elif self._sim_index >= len(self._sim_script):
                if me.on_ground:
                    self._sim_script = None
                    self._sim_index = 0
                    self._sim_target = None
                else:
                    # Replay exhausted while still airborne: live physics
                    # drifted a few frames past the predicted landing. Hold
                    # the trail's final drift until touchdown instead of
                    # recomputing mid-flight (a fresh rollout from the air
                    # picks a hold that overshoots narrow one-way tiles).
                    self._sim_index = len(self._sim_script) - 1
                    act = self._sim_script[self._sim_index]
                    self._sim_index += 1
                    self.execution_state = ExecutionState.FOLLOWING
                    return act
            else:
                act = self._sim_script[self._sim_index]
                if (
                    self._sim_double_index is not None
                    and self._sim_index == self._sim_double_index
                    and not me.on_ground
                    and abs(me.velocity[1]) > self.SINGLE_RISE
                ):
                    # Live physics drifted off the scripted double-jump frame.
                    # Pressing outside the near-apex window would be silently
                    # dropped by Player, wasting the second jump; hold the
                    # scripted drift and fire the press the instant the real
                    # |vy| enters the window (bounded so a spent jump cannot
                    # stall the edge).
                    self._sim_double_wait += 1
                    if self._sim_double_wait <= self.DOUBLE_WAIT_FRAMES:
                        self.execution_state = ExecutionState.FOLLOWING
                        return Action(left=act.left, right=act.right, down=act.down)
                    self._sim_double_index = None
                self._sim_double_wait = 0
                self._sim_index += 1
                self.execution_state = ExecutionState.FOLLOWING
                return act
        target_id = self.path[self.path_index]; target = graph.nodes[target_id]
        dx = target.position[0] - (me.rect[0] + me.rect[2] / 2)
        dy = target.position[1] - (me.rect[1] + me.rect[3])
        arrived = abs(dx) <= self.WAYPOINT_RADIUS and abs(dy) <= 55
        if target.kind not in {"stairs", "exit"}:
            arrived = arrived and me.on_ground
        if arrived:
            self._record_edge_success(); self.path_index += 1
            if self.path_index >= len(self.path) - 1:
                return self._approach_action(observation, directive)
            target_id = self.path[self.path_index]; target = graph.nodes[target_id]
            dx = target.position[0] - (me.rect[0] + me.rect[2] / 2); dy = target.position[1] - (me.rect[1] + me.rect[3])
        self.execution_state = ExecutionState.FOLLOWING
        previous = self.path[self.path_index - 1] if self.path_index else self.path[0]
        edge = graph.edge(previous, target_id)
        if edge is not None and edge.movement in {"jump", "stairs"}:
            simulated = self._simulate_edge(observation, me, target)
            if simulated is not None:
                return simulated
        aligned = self._takeoff_alignment(observation, me, edge, target)
        if aligned is not None:
            return aligned
        wants_jump = self._wants_jump(edge, me, dy, abs(dx))
        if edge and edge.movement == "drop":
            if me.on_ground:
                horizontal = edge.direction
            else:
                target_center = target.rect[0] + target.rect[2] / 2
                center = me.rect[0] + me.rect[2] / 2
                projected = center + me.velocity[0] * 0.18
                error = target_center - projected
                horizontal = (error > 6) - (error < -6)
            # Hold Down through the whole fall: handle_input resets
            # dropping_through on any airborne frame without Down, which
            # re-engages the one-way platform mid-fall and traps the player
            # in a 1-pixel land/snap limbo above the target pad. While still
            # grounded, Down is pressed only when already inside the target's
            # x-span — holding it during the walk-off would fall through the
            # source one-way platform beneath the player's feet instead of
            # carrying them to the ledge edge.
            target_center = target.rect[0] + target.rect[2] / 2
            center = me.rect[0] + me.rect[2] / 2
            inside_span = target.rect[0] - 8 <= center <= target.rect[0] + target.rect[2] + 8
            return Action(left=horizontal < 0, right=horizontal > 0, down=inside_span)
        horizontal = (dx > 8) - (dx < -8)
        return Action(left=horizontal < 0, right=horizontal > 0, jump=wants_jump or bool(edge and edge.movement == "stairs" and dy < 0))
