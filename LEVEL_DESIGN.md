# Level Design

## Dual-AI routes

Both pressure-plate levels are provably completable by two search agents with no teleports, scripted inputs or coordinate edits. `tutorial_001` gives each character a floor-level plate and a shared portal. `level_001` sends each character up its own tower: the orange route climbs the east staircase column and the 43→33→59 one-way chain to `plate:1`; the green route uses the `platform:47 → platform:39` step and a single added one-way side pad at (120, 520) — the minimal tolerance change that makes the west plate physically reachable, because the original west ascent was sealed by the submerged `platform:35` and an overhang above `platform:41`. The pad sits clear of water, lava and ceilings and only creates a landing the executor can jump to; all other routes remain untouched.

## Finale: `level_002`

The rebuilt finale is a broad, forgiving three-stage cooperation puzzle with explicit player-specific exits. It no longer contains or depends on the old `Limit` layer.

1. Orange crosses the opening section and activates `orange_latch`. This latches `door:0` open so Green can pass.
2. Green activates `green_latch`, which latches `door:1` open for Orange. The reverse dependency ensures each partner creates passage for the other without a closing door trapping either player.
3. Green and Orange take their color-assigned `SecondDoorPressure` plates. The existing permanent co-op door opens only when both are present.
4. Both follow the safe final floor to `FinalExitA` and `FinalExitB`. Completion requires both explicit rectangles simultaneously, freezes gameplay on a localized `Cooperation Complete / 协作成功` page for 2.5 seconds, then enters the deterministic ending narration and finally returns to the main menu.

The stage retains existing mechanics: two data-linked pressure doors, a two-player permanent co-op door, water, a short visible lava hazard, stairs, a moving platform with declared docks, and forgiving breakable platforms. Broad landings and alternate ground routes avoid pixel-perfect jumps. Safe grounded progress advances a per-player checkpoint; death or bounded AI recovery returns to that checkpoint while completed latches remain open, so the long finale does not restart from the original spawn.

## Data integrity

The `Mechanisms` object group identifies both ordinary triggers with stable `controls`, player assignment, mode and indices. Automated validation checks both spawns, both exits, two ordinary doors, two co-op plates, metadata references and graph-search routes for BFS, DFS and A*.