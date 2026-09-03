# AI Architecture

## Control contract

`core/ai/actions.py` defines frozen `Action(left, right, jump, down)` and the `ActionProvider` protocol. `Player` asks its provider for an action and applies that action through the same acceleration, gravity, collision, stairs, water, lava, jump and death code. The AI does not post keyboard events or write player coordinates/velocity.

Gameplay modes are explicit (`core/config/game_mode.py`): `LOCAL` keeps two `KeyboardActionProvider` instances; `HUMAN_AI` replaces only player 2's provider with the hybrid planner (player 1 keeps the keyboard); `AI_SHOWCASE` drives **both** characters with the same hybrid planner and adds a localized presentation HUD (`core/ai/showcase_overlay.py`). `Gameplay` takes a `mode` argument and carries it through the level chain; a legacy `ai_algorithm=` call site (tests, headless scripts) maps to `HUMAN_AI` for backwards compatibility, and the dual-AI test suite assigns both providers explicitly.

## Observation and graph

`Observation` is a frozen snapshot containing both players, platform membership, static platforms, stairs, water/lava, ordinary and co-op doors/plates, moving-platform position/direction, exits and portal state. `PlatformGraphExtractor` derives standable platform segments and semantic nodes for stairs, plates, door sides, moving-platform docks and exits. Edges describe walk, jump, drop, stairs, ride and conditionally open doors. Lava and closed-door geometry block ordinary edges.

TMX `Mechanisms` objects may specify `trigger_id`, `controls`, `plate_index`, `door_index`, `required_player` and `mode` (`hold` or `latch`). Maps without this metadata retain nearest-plate compatibility.

## Search and hybrid planning

`core/ai/search.py` retains the public BFS, DFS, A\*, result dataclasses and dispatcher signatures, but contains no search loops. `core/ai/native_backend.py` traverses `graph.neighbors(node, conditions)` in application order, maps arbitrary hashable nodes to dense IDs, materializes costs and heuristic values as C `double`, and calls the stable ABI in `core/ai/native/search_native.{h,cpp}`. The C++17 engine runs BFS, DFS and A\* over CSR arrays and returns the exact expanded/generated/frontier/path-cost statistics. Nodes are mapped back before callers see the result. The native library has no Python headers or runtime dependency, and loading is strict: missing binaries, ABI mismatch and failed self-tests are fatal rather than invoking a production fallback.

The preserved behavior is: BFS minimizes edge count and detects a goal while generating it; DFS reverses each ordered neighbor range before stack insertion and likewise detects on generation; A\* uses stable insertion serials, detects its goal on pop, and minimizes edge cost using straight-line distance times the graph's smallest positive cost-per-pixel ratio (admissible, proven optimal against an independent Dijkstra). `_GoalOrderedGraph` therefore keeps its existing DFS ordering effect, while `PlatformGraph.neighbors` continues to apply live conditions and runtime costs before serialization.

`SearchActionProvider` is a **hybrid planner**. Every plan runs BFS, DFS and A\* together over the same graph, conditions, running-cost updates and edge blacklist, then fuses them into one executable route:

- A\* is the baseline (minimum cost).
- If A\*'s next edge is blacklisted or fails, an alternative candidate (BFS or DFS) whose next edge is free of the blacklist is chosen.
- Ties break by a move-safety penalty (walk/stairs < door/ride < drop/jump) so the AI prefers dependable steps.
- `metrics.candidates` lists every algorithm that found a path and `metrics.winner` names the fused winner; the debug overlay shows `Hybrid/<winner>`. The user never selects one algorithm manually.

## Execution: scripted jump rollouts

Waypoint following handles walking and drops. Rising edges go through a model-predictive executor in `SearchActionProvider._simulate_edge`: a headless clone (`core/physics_clone.py`) of the live player state rolls candidate policies against the observation's real geometry — solid walls separated from one-way platforms exactly like the scene does. Candidates include walk-up delays to the takeoff lip, stand jumps, backswing run-ups (walk away from the target first to buy runway), hold-jump stairs climbs, and mid-flight release taps for narrow one-way landings. The winning candidate's complete action sequence is committed and replayed frame by frame into the live action stream (returning only the first frame would never consume the delayed jump), with safety valves: the replay aborts once the target is genuinely reached, keeps its final drift until touchdown when physics drifts past the predicted landing, and suspends the stuck clock while running (a backswing intentionally walks away from the waypoint). A sticky cache reuses the committed script for ~1s per target instead of re-running the rollout sweep every frame; it is cleared on replan, goal change and reset.

The double-jump press fires only inside `Player._near_apex` (±144 px/s); presses outside that window are silently ignored by `handle_input`. Because that window is only a few frames wide, the replay injects the scripted double-jump press **adaptively**: while the live `|vy|` has not yet entered the window, the scripted drift is held and the press is delayed (bounded) until the window arrives. Double jumps are selected for high climbs (`dy` beyond a single jump's 144px rise) **and** for flat gaps wider than ~150px, where a full-speed single jump's ~150-175px glide falls short; flat-but-wide edges keep single-jump candidates too so an overshooting second jump cannot starve the search.

Hold/approach discipline is dead-band control: inside the hold band (±25% of the target's width, clamped) no input is pressed and friction stops the player; only a genuine band exit triggers a single-side correction. Release-brake glide distance is `|vx|/10` (exponential friction coefficient 10), which replaced an under-estimating quadratic brake model that ping-ponged around targets. `provider.hold_flips` counts band-entry corrections so tests can assert the absence of oscillation.

Edge predicates mirror measured physics: a single jump rises 144px, a double jump ≈288px, jump force 720 over gravity 1800 yields the flat-arc reach, stairs columns are climbed by holding jump, and a submerged player jumps at 60% force (tall arcs from underwater supports are rejected at graph build time). `platform_id` requires a real feet-overlap with a support span (a center-point probe mis-attributed supports and fast-forwarded paths falsely), and waypoint arrival on platform-like nodes additionally requires being grounded, so a mid-air flyby cannot advance the route.

## Cooperation and recovery

The small cooperative task controller selects a goal from the live mechanism state rather than hard-coded level ids. The `Observation` exposes portal presence, per-door plate/required-player/hold-or-latch semantics, co-op plate ownership, exits and condition updates, so the same planner infers what to do in tutorial_001, level_001 and level_002: press a plate to open a door, hold/latch it, wait at a door side for the partner, stand on the color-assigned co-op plate, and finally reach the assigned exit or portal. Every movement route is searched by the fused planner. Changed door conditions, changed goals, or 1.5 seconds without useful motion trigger replanning. Repeated identical failed first edges are counted and temporarily blacklisted so the next real search tries an alternative. Repeated no-path/failure cycles use cooldowns and eventually request a finite checkpoint reset through the scene; the provider never writes coordinates. The F3 overlay shows strategy, localized goal, expanded nodes, path length and replans. Moving-platform ride edges are available only at the correct departure dock and direction, with cost updated from runtime progress.

## Native deployment

`tools/build_native.py --ensure` discovers MSVC through `vswhere`/`vcvars64.bat` before trying MinGW g++ on Windows, uses g++ on Linux and clang++ on macOS, and writes only a validated temporary build into `build/native/<platform>-<arch>/`. PyInstaller packages that same relative tree so the ctypes locator works both from source and `sys._MEIPASS`. See `docs/NATIVE_SEARCH_BUILD.md`.

## Known limits

The graph is a conservative platform abstraction, not a full trajectory simulator. Deterministic goal-oriented neighbor ordering keeps DFS explainable while avoiding irrelevant optional branches. The current TMX mechanism schema supports one trigger linked to one door; one-trigger-to-multiple-target fan-out is not implemented because the finale does not require it. Full deterministic real-physics finale completion is tested for BFS, DFS and A*. In AI showcase mode both characters are search-driven; in human+AI mode player 1 keeps the keyboard. The dual-AI completion suite (`tests/test_dual_ai_completion.py`) proves tutorial_001, level_001 and level_002 plus the full campaign under real physics; `tests/test_ai_behavior_polish.py` additionally pins the HOLD anti-oscillation bound (≤2 flips/s) and the presence of real double-jump presses on level_001's wide gap-leap edges.