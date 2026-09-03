# Changelog

## Unreleased

- Split the AI entry point into explicit modes (`core/config/game_mode.py`): `LOCAL` (two keyboards), `HUMAN_AI` (player 1 keyboard + AI-driven player 2, restored as its own menu entry), and `AI_SHOWCASE` (both characters driven by the same hybrid planner). The showcase adds a level-select launcher (`ai_showcase.py`), a localized presentation HUD per AI (goal, script step, execution state, planner winner, replans), a new main-menu button, and mode-aware level chaining.
- Polished AI motion: HOLD/approach now use dead-band control with a release-friction brake model (`|vx|/10` glide instead of a quadratic under-estimate), eliminating the frame-by-frame left/right oscillation while holding pressure plates (bounded ≤2 flips/s, asserted in tests); double jumps now trigger for high climbs AND flat gaps wider than ~150px, with the replay injecting the second press adaptively when live physics drifts off the scripted apex frame; committed simulator scripts are reused via a short-lived sticky cache instead of re-searching every frame.
- Added `tests/test_ai_behavior_polish.py`: HOLD anti-oscillation rate bound on tutorial_001 and a requirement that level_001's wide gap-leap chain (33→59→58) commits a trajectory with a genuine mid-air double-jump press.
- Made both campaign characters fully AI-driven in AI-vs-level mode (human-vs-AI mode still binds keyboard to player 1), enabling true two-search-agent co-op runs of the whole campaign.
- Added a model-predictive jump executor: headless player clones roll candidate policies (walk-up delays, stand jumps, backswing run-ups, stairs hold-jumps, mid-flight release taps) against real collision geometry and replay the winning action script frame by frame with landing-abort safety.
- Fixed the simulator feeding one-way platforms as solid walls (which destroyed every double jump), aligned the double-jump near-apex gate with `Player._near_apex` (±144), and reset committed-script indexes that stalled scripted climbs.
- Aligned graph edges with measured physics: single-jump rise capped at 144px, double-jump envelope, water-jump rejection for submerged takeoffs, stairs movement restricted to short column climbs, and plates/exits resting on their support reached by walking instead of bogus jumps.
- Fixed path fast-forward identity (`platform_id` now requires a real feet overlap instead of a nearest-node guess), grounded-only waypoint arrival for platforms, final-goal stuck tracking before acquisition, and replay suspension of the stuck clock during backswing run-ups.
- Gated drop-through: Down is pressed only inside the target span while grounded and held through the whole fall, eliminating the one-pixel land/snap limbo on one-way pads, with predictive air braking toward drop targets.
- Minimal level tolerance per approved plan: level_001 gained one one-way side pad so the west pressure plate has a physically executable route; no teleports, no coordinate edits, no scripted inputs.
- Added dual-AI completion tests: both search agents finish tutorial_001, level_001, level_002 (co-op chain → dual exits → SUCCESS) and the full campaign returns to the main menu, all through real physics.
- Localized the new script goal keys (plate_left/plate_right/portal/wait_door/cross_door/latch/cross_coop/complete) in English and Simplified Chinese; synced catalogs into the packaged app.
- Fixed the ending state machine rewriting RETURNING back to NARRATION, and verified three-resolution rendering plus packaged native DLL loading.

## Previous

- Migrated BFS, DFS and A* execution to a required C++17 CSR library with a stable versioned C ABI, exact legacy path/statistics semantics, double costs/heuristics, and no Python headers.
- Added a strict ctypes graph adapter for arbitrary hashable nodes, native identity/ABI/self-tests, source and PyInstaller library discovery, and explicit failure instead of a production Python fallback.
- Added cross-platform native build automation, stale/atomic validated replacement, Windows compiler discovery, launcher/CI/PyInstaller integration, and native authenticity/parity tests.
- Added local human–AI cooperation and made player 2 default to arrow keys (`←/→/↑/↓`) while retaining numpad as an optional scheme.
- Replaced pre-start algorithm picking with a data-driven hybrid planner: every plan runs BFS, DFS and A* together and fuses them (A* baseline, blacklist/risk-aware fallback), with `candidates`/`winner` metrics on the F3 overlay.
- Made the cooperative task controller infer goals from live mechanism state instead of hard-coded level ids, so it understands pressing/holding a door plate, waiting for the partner, taking the assigned co-op plate and reaching the exit in tutorial_001, level_001 and level_002.
- Added immutable shared Action providers so keyboard and search AI use identical Player physics.
- Added frozen observations, TMX/runtime platform-graph extraction, conditional-door edges, search statistics, stuck detection and F3 diagnostics.
- Rebuilt `level_002` as a complete reciprocal-cooperation finale with stable TMX trigger metadata and explicit two-player exits.
- Replaced the `Limit` ending trigger with an explicit localized success page followed by the deterministic narration/return state machine and completed localized ending text.
- Fixed moving platforms carrying riders, long-fall airtime evaluation, deterministic co-op plate assignment, and doors closing through players.
- Capped simulation delta for stable physics and replanning.
- Added search, graph, controls/mechanics, all-level/finale integration tests and a multi-resolution headless runtime smoke harness.
- Made production A* optimal via an admissible geometric heuristic, added dynamic ride availability/cost, repeated-edge recovery, finale checkpoints, swept safe door closing, and latch preservation across resize.
- Updated English and Simplified Chinese locale catalogs and project documentation.