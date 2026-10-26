# Atari ZeroWave implementation specification

Implement the game defined in [PORT_OUTLINE.md](PORT_OUTLINE.md) as a native Atari 2600 cartridge: a stationary turret, eight-way joystick beam, button-triggered bomb, two enemy types, health, score, and levels with increasing enemy counts.

The first playable build must support two active enemies. The implementation reserves four enemy slots and separates storage capacity from the current level's cap. Three- and four-enemy levels are enabled only after their display schedules pass the tests below. Controls and combat rules are requirements; tuning values are initial defaults that may change through playtesting.

## Platform and build decisions

| Item | Implementation decision |
| --- | --- |
| Console | Stock Atari 2600, NTSC first, one joystick in the left port |
| Runtime | 6502/6507 assembly using documented instructions; no Godot runtime |
| Assembler | DASM, with a pinned release recorded by the build |
| Cartridge | 8 KiB F8 ROM, two 4 KiB banks; no cartridge RAM or coprocessor |
| Working RAM | 128 bytes including stack, with the allocation below |
| Simulation | One fixed game update per video frame |
| Display | Custom kernel; coarse playfield beam, player graphics for turret/enemies |
| Development | Make, Python 3 standard-library generation/checks, Stella debugger |
| Later work | PAL timing/palette conversion, more than four enemy slots, richer effects |

Choose 8 KiB to give game logic and rendering separate ROM budgets without making 4 KiB compression a prerequisite. Extra ROM does not relax scanline deadlines. [DASM](https://dasm-assembler.github.io/) supports the processor and supplies Atari headers/macros; retain their provenance when vendoring a pinned copy. Stella identifies ordinary F8 as an [8 KiB Atari cartridge format](https://stella-emu.github.io/docs/index.html).

The source checkout under `res/` remains the reference game. New implementation code lives at the workspace root, alongside `docs/`. Build-time JSON is allowed for tuning and generation; the cartridge contains only compiled constants, tables, and native code.

## Player controls

Read input once per game update. The left joystick directions are active-low in the upper nibble of `SWCHA`; the button is active-low on bit 7 of `INPT4`. Configure joystick pins as inputs and keep button latching disabled for direct press/release sampling. These register behaviors are specified in Atari's [Stella Programmer's Guide](https://alienbill.com/2600/101/docs/stella.html).

Invert and shift the direction nibble to obtain `up=1`, `down=2`, `left=4`, `right=8`. Cancel up+down and left+right independently before lookup.

| Direction | Normalized input | Direction ID |
| --- | ---: | ---: |
| N | 1 | 0 |
| NE | 9 | 1 |
| E | 8 | 2 |
| SE | 10 | 3 |
| S | 2 | 4 |
| SW | 6 | 5 |
| W | 4 | 6 |
| NW | 5 | 7 |
| Neutral | 0 | 255 |

Holding a direction enables one continuous beam in that direction. Diagonals produce one diagonal beam. Changing direction changes the next rendered beam; neutral disables both its graphic and damage. Remember the last valid direction separately if needed for a HUD cue. Do not require button input to fire the beam.

A button press edge detonates a bomb only when its cooldown is zero. Holding the button never repeats, and presses during cooldown are discarded rather than queued. The beam continues during a bomb. Maintain button history even when an action is rejected or the game is between levels.

Power-on shows a small title/ready screen. A fresh fire press starts a run without also firing a bomb. A RESET press edge starts a fresh run from any mode. SELECT and difficulty switches have no gameplay function in this version. A held button across startup, reset, game over, or a level transition must be released before it can cause another press action.

## Arena coordinates and movement

The visible layout uses 24 scanlines for the HUD, eight for separation/setup, and 160 for the arena. The arena has 80 logical rows, each drawn twice. Define the turret center as `(80, 40)` in horizontal color clocks and arena logical rows; its visible vertical coordinate is `32 + 2*40 = 112`.

Game geometry uses an eight-way lane and a radial distance, not free Cartesian movement. Store distance as unsigned 8.8 fixed point: an integer byte plus a fractional byte. Initial constants are:

| Constant | Default | Meaning |
| --- | ---: | --- |
| `SPAWN_RADIUS` | 63 | Enemy spawn distance, fraction initially zero |
| `CONTACT_RADIUS` | 8 | A surviving enemy at or inside this radius reaches the turret |
| `BOMB_RADIUS` | 24 | Fixed local damage radius |
| `BEAM_RANGE` | 63 | Beam reaches the full approach lane |
| `START_HP` | 5 | Health at the start of each run |
| `BOMB_COOLDOWN` | 60 updates | Approximately one second at the target frame rate |
| `BOMB_FLASH` | 6 updates | Brief visual confirmation |
| `LEVEL_BREAK` | 60 updates | Pause after a cleared level |
| `SQUARE_SPAWN_GAP` | 72 updates | Minimum spacing between square spawns |

Each active enemy subtracts the current level's speed from its fixed-point distance once per update. Speeds in the level table are fractional-byte values, so `32` means `32/256` radial units per update. Saturate subtraction at zero; an underflow must never wrap an enemy to the outer rim.

Generate movement tables offline from lane direction and radius. Start with horizontal extent 44 color clocks and vertical extent 35 logical rows at radius 63, giving room for the sprites within the arena. Use sine/cosine only in the generator, share cardinal/diagonal magnitudes and sign information, and adjust these extents if television aspect-ratio testing requires it. Cache sprite top-left positions in each slot; use 8-color-clock-wide, four-logical-row-high enemy silhouettes initially.

Use the same coordinate transform for beam graphics and enemy positions. The generator must verify that every legal enemy center lies on its lane's rasterized beam and that all sprite bounds fit. A coarse ray may be widened around rounding boundaries to make hits visually credible. Normalize radial distance across lanes so bomb reach does not change merely because the enemy approaches diagonally.

For radius comparisons, explicitly compare both bytes: `24.00` is inside the bomb, `24.01` is outside. Rendering may use the integer byte; the bomb-range cue uses the exact combat comparison.

## Combat rules

| Target | Beam | Bomb inside radius | Reaching turret | Kill score |
| --- | --- | --- | --- | ---: |
| Triangle | Destroy on matching lane within beam range | Destroy | Lose one HP | 10 |
| Square | No effect; does not block the ray | Destroy | Lose one HP | 25 |

The beam pierces: all eligible triangles on its selected lane can be destroyed in the same update. A bomb checks every active slot once and destroys both types within radius. Its flash is cosmetic and causes no subsequent damage. A square outside the radius survives even if the whole arena flashes.

Process bomb damage before beam damage, then process center contacts. Immediately mark destroyed enemies inactive; an enemy hit by both weapons earns score and quota credit exactly once. Attacks therefore win a same-update tie with reaching the turret. Contacted enemies are removed without score or quota credit. Each surviving contact costs one HP, saturating at zero; there is no invulnerability mechanic in the baseline.

Use four decimal score digits stored as two packed-BCD bytes, saturating at 9999. BCD arithmetic must leave decimal mode clear before returning to other code. One scoring routine updates score and decrements the level's remaining kill quota, also saturating at zero. Multiple kills in one update all earn score even if the first exhausts the quota.

Squares change from an outline to a filled silhouette when inside bomb range. This is a shape cue, not only a color change, and introduces no extra graphic object. The cue must use the same radius predicate as bomb damage.

## Modes and level transitions

| Mode | Behavior | Exit |
| --- | --- | --- |
| `TITLE` | Turret/title mark and start cue; no combat or spawns | Fresh fire press or RESET starts a run |
| `PLAY` | Input, movement, attacks, contacts, spawning, scoring | HP zero goes to `GAME_OVER`; cleared quota and empty arena go to `LEVEL_BREAK` |
| `LEVEL_BREAK` | Empty arena; show next level, stop beam and spawns, retain HP/score | After 60 updates, load the next row and return to `PLAY` |
| `GAME_OVER` | Freeze final score; silence beam, play death cue | Fresh fire press or RESET starts a run |

A fresh run sets level 1, HP 5, score zero, bomb ready, empty enemy pool, cleared effect timers, and a deterministic nonzero random seed. It loads the first level row and starts its spawn countdown. It does not consume an attack from the start/reset input.

When the kill quota reaches zero, stop spawning but keep `PLAY` active until all remaining enemies are killed or reach the center. Apply all contacts before deciding the next mode. Death takes priority over level completion. At the end of `LEVEL_BREAK`, reset spawn/bomb/effect timers for the new level, preserve HP/score, and retain input history. Existing enemies never have their speed changed by a level transition because the arena must be empty first.

Entering `LEVEL_BREAK` sets its counter to 60; each following update decrements it once and the update that reaches zero loads the next level. A non-play mode handler or RESET consumes that update, so it cannot also execute combat/spawning in the newly entered `PLAY` mode. Every exit path commits the sampled input history.

## Update order and video schedule

One game update produces the state for the next visible frame:

1. Sample and normalize input; handle RESET or non-play mode transitions.
2. Decrement nonzero cooldown, flash, spawn, and square-spacing timers. A timer set later in this update is not decremented again.
3. Move enemies that were active at the start of the update.
4. Accept a fresh bomb press if ready; set cooldown to 60 and flash to six.
5. Resolve bomb kills, beam kills, and surviving center contacts in that order.
6. Resolve death, quota completion, and level-break entry.
7. If still playing with quota remaining, attempt at most one spawn when due.
8. Select sound events and save input history. Prepare display data before the next visible arena.

New spawns cannot move or be attacked until the following update; spawning therefore cannot grant a same-update kill. Their first drawing opportunity follows the enemy omission limit below. Timer semantics mean a bomb accepted at update `t` can next be accepted at `t+60`, with a new press edge; `t+59` is too early.

Use a stable NTSC frame: three VSYNC lines, 37 VBLANK lines, 192 visible lines, and 30 overscan lines. Each scanline has 76 CPU cycles. The frame is software-timed, as described in the [Atari timing reference](https://alienbill.com/2600/101/docs/stella.html).

| Phase | Work | Initial software budget |
| --- | --- | --- |
| Overscan | Sample input and run the game update for the next picture | At most 2,000 of 2,280 cycles |
| VSYNC | Fixed synchronization sequence | Exactly three lines |
| VBLANK | Derive coordinates, choose enemy draw schedule, prepare HUD/beam pointers, position objects | At most 2,400 of 2,812 cycles |
| Visible | Draw HUD, separation, and arena | Exactly 192 lines; each path meets register deadlines |

These are allocation targets to measure in the first implementation. Bank changes, timer setup, branches, and wait alignment count toward each budget. Move bounded work between overscan and VBLANK if necessary, documenting the handoff; never lengthen the frame to finish logic. Wait out unused time. Do not perform spawning, random retries, scoring, or unbounded loops inside the visible kernel.

## Enemy storage and spawning

Use `MAX_ENEMIES=4` as compiled storage capacity and initially `VALIDATED_ENEMY_CAP=2` as the gameplay ceiling under test. Runtime `active_cap` is the smaller of the level request and validated cap. Every enemy loop uses slot indices and an active flag; there must be no separate hard-coded enemy-one/enemy-two logic.

Store eight fields per slot as eight arrays of four bytes:

| Field | Meaning |
| --- | --- |
| `flags_lane` | Bit 7 active, bit 6 square type, bits 0–2 direction; other bits reserved |
| `radius_hi` | Integer distance |
| `radius_lo` | Fractional distance |
| `screen_x` | Cached left edge in color clocks |
| `screen_y` | Cached top logical row |
| `draw_phase` | Selected display phase/scheduling assignment |
| `draw_age` | Consecutive visible frames omitted, for scheduler checks |
| `visual_state` | Sprite variant, including square bomb-range cue |

Attempt a spawn only if there is a free slot, active count is below cap, quota remains, and the spawn timer is zero. Choose a lane and type using a one-byte deterministic LFSR: shift right, XOR with `$B8` when the old low bit was one; seed `$A5` on reset. A host check verifies its nonzero cycle. Determinism enables replayable tests.

Do not place two enemies in the same lane in the baseline. For each attempt, choose a starting lane and examine at most eight lanes cyclically. Reject occupied lanes and arrangements forbidden by the validated renderer. If none are permitted, defer the spawn eight updates; do not add a hidden enemy or retry indefinitely. A successful spawn reloads the level's spawn interval. Track actual encounter density in playtests so scheduling restrictions do not silently erase the intended difficulty increase.

Use the row's square probability unless the square-spacing timer is nonzero, in which case spawn a triangle. Successful square spawns set that timer to 72. All enemies use the same speed within a level. With bomb radius 24, contact radius 8, and maximum initial speed `56/256`, a square has about 73 updates between those boundaries. This exceeds the 60-update cooldown by about 13 updates; validate the fixed-point boundary cases. The spacing rule and same-speed arrivals further separate bomb demands. This is a starting fairness constraint, not a guarantee after the player wastes a ready bomb or reacts late.

## Level data and increasing density

Each level row contains `requested_cap`, `kill_quota`, `spawn_interval`, `speed_fraction`, and `square_weight` out of four. No runtime difficulty formula is needed initially.

| Level | Requested cap | Kill quota | Spawn interval in updates | Speed fraction | Square weight |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 2 | 8 | 90 | 32 | 1/4 |
| 2 | 2 | 10 | 75 | 40 | 1/4 |
| 3 | 2 | 12 | 60 | 48 | 1/4 |
| 4 | 3 | 12 | 60 | 48 | 1/4 |
| 5 | 3 | 14 | 54 | 48 | 2/4 |
| 6 | 4 | 14 | 54 | 48 | 2/4 |
| 7 | 4 | 16 | 48 | 56 | 2/4 |
| 8 onward | 4 | 18 | 42 | 56 | 2/4 |

Levels 4 and 6 introduce density without also raising speed. These are candidate assignments, subject to playtesting. Development builds clamp unvalidated caps and identify the configured limit in their build report. Demonstrating the accepted later-level density goal requires validating at least three simultaneous enemies; a build clamped permanently at two only completes the baseline milestone.

After level 8, reuse the final difficulty row. Track a displayed level number up to 99, saturating there without stopping play. Derive the data row as `min(level, 8)`; never index beyond the table. Further difficulty tuning must remain within tested density and bomb-response bounds.

## Beam and enemy rendering

Allocate the playfield to the beam, player 0 to the turret, and player 1 to enemies. Leave missiles and ball disabled initially. Use a background-color flash for bombs, preserving beam/enemy contrast. HUD graphics occupy a separate vertical region.

The beam uses eight opaque raster patterns, one selected by direction. Both halves of the playfield must be independently controlled so a right shot cannot create a left copy. Repeat each logical row across two scanlines. Keep turret and beam visible every frame; use no transparency or trails.

The asset generator emits six playfield byte streams per direction, with identical streams and blank runs shared where practical. Eight uncompressed patterns at 80 rows and six bytes per row cost 3,840 bytes, so sharing is required to leave room in the renderer bank. Start with deduplicated full row streams for simple timed loads. Change representation only with a measured cycle and ROM benefit. Keep indexed streams within pages where the kernel assumes fixed load timing, or explicitly account for page crossings.

Each scanline still has its own write deadlines in a two-line kernel. Before accepting it, produce an instruction-cycle schedule covering both playfield halves, both player graphics, loop control, and horizontal positioning. No particular register schedule is considered proven by this specification.

### Initial two-enemy display

For the first kernel, position one enemy graphic during blanking and draw that enemy for the frame. When two enemies are active, alternate them; when one is active, draw it every frame. Choose by greatest draw age with a stable slot-index tie-break so spawning/freeing slots cannot starve an enemy. This avoids mid-arena repositioning in the first implementation.

At two enemies this targets one omitted frame between appearances, approximately 30 appearances per second per enemy. It must pass television readability testing; if it is too faint, improve reuse at separated heights before calling the baseline complete. Use software combat state even on omitted frames. Never let alternate-frame drawing cause alternate-frame damage.

### Display expansion for later levels

Before increasing the validated cap, add vertical reuse of player graphics. Build a small draw schedule during blanking, sorted by screen height. Player 1 can serve multiple enemies in nonoverlapping vertical regions with a measured repositioning gap. Player 0 may also serve enemies outside the turret's protected vertical band once its state is safely restored for the turret.

Represent candidate draws as vertical intervals expanded by the measured setup gap. Assign them to available hardware-player/time slots and, if necessary, two alternating frame phases. The turret always owns player 0 in its band. Maintain a maximum of one consecutive omitted frame for each active enemy. Merely alternating three or four enemies through one whole-frame slot does not meet this requirement.

If a candidate population cannot be scheduled, the renderer reports overload in debug builds. The spawn filter may restrict demonstrated troublesome arrangements, but testing must also cover their later movement and convergence. Reject a higher cap if any reachable state starves an enemy, breaks timing, or needs excessive flicker. Do not silently pause, teleport, or remove enemies to solve rendering conflicts. Same-height east/west enemies and diagonals closing on the center are mandatory stress cases.

The exact reuse gaps and accepted lane combinations are outputs of kernel testing. Preserve them as scheduler constants/fixtures so the spawn rules and renderer agree.

## HUD and sound

Display four score digits, five health marks, a bomb-ready mark, and the level number. Keep text compact; there are no menus, upgrade screens, or run statistics. Readiness is lit at zero cooldown, health marks disappear as HP falls, and title/game-over screens reuse the same small font/graphics.

Use two sound channels: one sustained beam cue and one prioritized event cue. Event priority is death, bomb, player hit, then enemy kill. Coalesce multiple same-update kills into one cue; no dynamic sound queue. End the beam tone as soon as neutral or a non-play mode disables firing. Define effect envelopes as short ROM tables; tune timbre on hardware. Music is outside scope.

## RAM allocation

The initial map uses the full available address range, with explicit reserve and stack space. Generate symbols and fail the build on overlap.

| Address range | Bytes | Allocation |
| --- | ---: | --- |
| `$80–$9F` | 32 | Four enemy slots, eight arrays of four bytes |
| `$A0–$AF` | 16 | Mode, level, quota, HP, two score bytes, mode timer, spawn timer, square timer, RNG, active count, active cap, speed, spawn interval, square weight, spare game byte |
| `$B0–$B7` | 8 | Direction, last direction, previous button/reset bits, beam enable, bomb cooldown, flash timer, bomb event, frame phase |
| `$B8–$BF` | 8 | Two sound-channel states, four bytes each |
| `$C0–$D7` | 24 | Renderer pointers, row bytes, and draw/HUD state |
| `$D8–$E7` | 16 | Shared scratch for logic, spawning, and schedule construction |
| `$E8–$EF` | 8 | Unallocated margin; guard pattern in debug builds |
| `$F0–$FF` | 16 | Stack reservation |
| Total | 128 | Includes stack and margin |

The 24 renderer bytes initially allow six two-byte playfield pointers, six row bytes, one two-byte sprite pointer, and four control bytes. Later sprite reuse must fit or explicitly revise this allocation. Scratch can be reused only across nonoverlapping lifetimes; record clobbered registers and scratch in each routine's header. ROM switching does not preserve a second copy of RAM.

Initialize the stack at `$FF` and keep peak stack consumption within 16 bytes, including nested subroutines and any explicit pushes. Verify the high-water mark in the busiest frame. Increasing storage beyond four slots requires a revised map; it is not enabled by changing only a level row.

## ROM banks and module boundaries

F8 selects its lower and upper 4 KiB banks through cartridge hotspots `$1FF8` and `$1FF9`; the game can address their `$FFF8`/`$FFF9` mirrors. Stella's [F8 mapper implementation](https://github.com/stella-emu/stella/blob/master/src/emucore/CartF8.cxx) provides a reference for these selections.

| Bank | Contents |
| --- | --- |
| 0 | Reset/init, input, modes, movement, attacks, spawning, scoring, levels, audio updates |
| 1 | Display preparation, coordinate lookup tables, kernel, beam streams, sprites, font/HUD data |

Place matching bank-switch trampolines at `$FF80–$FFF7` in both banks, reserve `$FFF8–$FFF9` as hotspots, and put matching vectors at `$FFFA–$FFFF`. Both reset vectors enter a common stub that explicitly selects bank 0, so startup does not depend on the initial bank.

Cross-bank transitions use explicit jump stubs whose next instructions are identical at the same address in both banks. Do not use a normal cross-bank `JSR`/`RTS` convention. Switch into bank 1 before synchronization/display preparation, remain there for the visible kernel, then switch back under blanking for the overscan update. Any large data needed by a bank must be in that bank or copied into an explicitly budgeted RAM field.

### Planned project files

These are implementation deliverables, not files supplied by the spec:

| Path | Responsibility |
| --- | --- |
| `Makefile` | Generate assets, assemble ROM, run checks, launch emulator |
| `src/main.asm` | Bank layout, includes, vectors, common entry points |
| `src/ram.inc` and `src/constants.inc` | State allocation and fixed hardware/game constants |
| `src/input.asm`, `src/game.asm` | Input decoding and mode/update orchestration |
| `src/enemies.asm`, `src/combat.asm` | Slot pool, spawning, movement, hits, score/quota |
| `src/audio.asm` | Sound state and event priorities |
| `src/render.asm`, `src/kernel.asm` | Display schedule, pointer setup, timed screen output |
| `config/tuning.json`, `config/levels.json` | Single source for provisional numbers and level rows |
| `tools/generate_assets.py` | Deterministic geometry, beam, font, and level-table generation |
| `tools/check_rom.py` | Image size, vectors, bank stubs, RAM layout, table bounds |
| `tests/test_rules.py` | Host-side rule vectors and generator invariants |
| `tests/scenarios/` | Deterministic cartridge/debug scenarios and expected state traces |
| `vendor/dasm/` | Pinned Atari headers/macros and their license/provenance |
| `build/` | Generated includes, ROM, symbols, listing, and validation reports |

Each assembly routine declares inputs, outputs, register clobbers, scratch use, and its applicable cycle bound. `game.asm` owns update order; `render.asm` consumes state and may change only render caches/diagnostics, never HP, score, enemy movement, or combat outcomes.

## Build and verification workflow

Define `make all` to generate tables and produce `build/atari-zerowave.bin`, `.sym`, and `.lst`. The ROM must be exactly 8,192 bytes with deterministic padding. Define `make check` for host checks, `make run` for a configured NTSC/F8 Stella launch, and `make debug` for the same cartridge with symbols and scenarios. These targets are to be implemented.

Pin the assembler/tool inputs and record versions, source revision, validated enemy cap, and ROM checksum in a build report. Fail on unresolved symbols, bank overflow, RAM/stack reservation overlap, missing table entries, or mismatched common stubs. Keep build output disposable and out of the reference checkout.

DASM must be made available before assembly; it was not found on the current shell path during planning. Stella is installed, but interactive validation requires a graphical session or virtual display. These prerequisites do not prevent writing the source or running host checks.

Host tests verify the integer model and generated data; they do not prove the assembly or TIA timing. Run the same state/input scenarios against the actual cartridge and compare its RAM state using symbols and debugger checkpoints. Use Stella's [debugger timers, watches, scanline stepping, and symbol/list support](https://stella-emu.github.io/docs/debugger.html) to inspect the assembled result. Check the release image too if debug instrumentation changes code placement.

## Acceptance tests

| Area | Required cases and result |
| --- | --- |
| Input | All eight directions, neutral, and opposite-axis combinations decode deterministically; neutral disables beam damage and sound. |
| Button edges | Held fire causes one bomb; cooldown presses do not queue; activation at `t+59` fails and a fresh press at `t+60` succeeds. Start/reset/transition inputs do not create accidental bombs. |
| Beam | Matching-lane triangles die, wrong lanes survive, squares remain, and a square does not block a triangle behind it. Beam pattern covers its legal lane positions. |
| Bomb boundary | With zero movement in the fixture, `24.00` dies and `24.01` survives; square fill state agrees. Both types can die in one bomb. |
| Resolution order | Same-frame beam+bomb grants one kill per target. A successful attack prevents contact damage; multiple surviving contacts reduce HP without underflow. |
| Movement | Fractional stepping, subtraction near zero, and every lane/radius mapping are correct. No sprite leaves the arena. |
| Spawn limits | Never exceed active cap, duplicate a baseline lane, overwrite a live slot, or spin on failed placement. Square spacing is honored. |
| Fairness | At each speed, measure the exact number of updates from bomb-range entry to contact. Later-level spawn mixes retain usable bomb windows. |
| Progression | Multi-kill quota crossing stops spawns, waits for remaining enemies, and enters a 60-update break. Death overrides advancement. Level 99 and score 9999 saturate safely. |
| Display | Turret and beam remain steady through bombs; every active enemy appears at least every other frame. Check same-height pairs and center convergence. |
| Memory and ROM | Both possible startup banks reset correctly; bank stubs match; stack remains in its reservation; guard bytes remain intact; each bank fits. |
| Timing | All states use the intended frame/scanline counts. Worst-case bomb kills, score carry, failed spawns, transitions, and display schedules stay within measured budgets. |

Use small deterministic fixtures for logic failures, then a longer scripted stress run with repeated restarts, level transitions, and dense layouts. A hardware pass must cover a real joystick's diagonals, bomb responsiveness, flicker/readability on a television, and sound. Record emulator timing evidence separately from hardware observations.

## Implementation milestones

| Milestone | Deliverable | Exit criterion |
| --- | --- | --- |
| 0 | Pinned build, F8 startup/bank stubs, stable blank ROM | Correct image/vectors and stable frame from either initial bank |
| 1 | Turret, eight beam patterns, one enemy graphic, bomb flash | Cycle schedule and Stella measurements prove the core display |
| 2 | Input, two-enemy pool/display, movement, combat, HP, score, restart | Rule fixtures pass in the cartridge; two-enemy overlap remains readable |
| 3 | Both enemy types, bomb cue/cooldown, level table, sound | Opening levels are playable and fair; baseline hardware pass |
| 4 | Vertical sprite reuse and three-enemy scheduling | Three-enemy stress cases meet timing and omission limits; enable level 4 density |
| 5 | Four-enemy scheduling and later-level balancing | Four-enemy cases pass before enabling level 6 density; otherwise retain the measured lower cap |

Implement milestones in order. If milestone 1 fails, revise the kernel while keeping eight-way beam and button bomb behavior. If higher densities fail, adjust scheduling and spawn arrangements or keep the lower validated cap; do not restore removed visual effects to compensate. Charge bombs, trails, reflectors, shifters, XP, and upgrades remain outside this implementation.
