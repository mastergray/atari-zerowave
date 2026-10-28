# Atari ZeroWave implementation specification

Implement the game defined in [PORT_OUTLINE.md](PORT_OUTLINE.md) as a native Atari 2600 cartridge: a stationary turret, eight-way joystick beam, button-triggered bomb, triangle/square variants and a blue rhombus, health, score, and levels with increasing enemy counts.

The first playable build must support two active enemies. The implementation reserves four enemy slots and separates storage capacity from the current level's cap. Three- and four-enemy levels are enabled only after their display schedules pass the tests below. Controls and combat rules are requirements; tuning values are initial defaults that may change through playtesting.

Implementation status: the two-enemy combat prototype through milestone 2 is
available. See [build and play instructions](../README.md) and
[measured kernel timing](KERNEL_TIMING.md). It includes movement, both enemy types,
beam/bomb damage, health, score, and start/game-over/restart. Opening difficulty
is fixed at two enemies, speed 32/256, spawn interval 90, and square weight 1/4.
Level quotas/transitions and hit/death sound cues remain future work. A separate
display-test ROM retains the static SELECT layouts. The sections below continue
to define the full game target; level-specific rules are not enabled yet.

The enemy rules below were revised on 2026-10-27. They are the next implementation
target: the current ROM still lets bombs kill triangles and has no fast triangle,
armored square, or blue rhombus. Existing test results describe that current ROM,
not completion of these revised rules.

## Platform and build decisions

| Item | Implementation decision |
| --- | --- |
| Console | Stock Atari 2600, NTSC first, one joystick in the left port |
| Runtime | 6502/6507 assembly using documented instructions; no Godot runtime |
| Assembler | DASM, with a pinned release recorded by the build |
| Cartridge | 8 KiB F8 ROM, two 4 KiB banks; no cartridge RAM or coprocessor |
| Working RAM | 128 bytes including stack, with the allocation below |
| Simulation | One fixed game update per video frame |
| Display | Custom ball/playfield beam kernels, player graphics for turret/enemies |
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

Holding a direction keeps the beam attack active in that direction; damage follows the target's vulnerability and hit interval below. The graphic stays visible as a single solid beam whose entire color changes over time; during bombs it shares alternate frames with the ring. Diagonals produce one diagonal beam. Neutral immediately disables damage and sound, but the last beam fades for 15 updates with its direction and hue fixed. Changing direction replaces any afterglow with a bright beam on the next visible beam phase. Keep the last valid direction and visual state separate from attack input. Do not require button input to fire the beam.

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
| `BOMB_ANIMATION_FRAMES` | 16 updates | Four expanding ring sizes, four updates each |
| `BOMB_SOUND_FRAMES` | 6 updates | Short noise envelope independent of animation |
| `BEAM_FADE_START` | 15 | Initial release brightness; countdown through 1, then hide |
| `ENEMY_BURST_FRAMES` | 18 updates | Three destruction stages, six updates each |
| `LEVEL_BREAK` | 60 updates | Pause after a cleared level |
| `SQUARE_SPAWN_GAP` | 72 updates | Minimum spacing between square spawns |

Each active enemy subtracts its type's speed for the current level and distance from its fixed-point distance once per update. Speeds are fractional-byte values, so `32` means `32/256` radial units per update. Saturate subtraction at zero; an underflow must never wrap an enemy to the outer rim.

Standard enemies use steady speeds. The smaller magenta triangle is the fastest
type at every distance. The blue rhombus accelerates as it approaches the turret;
use a small table of distance bands with increasing speeds, selected from its
distance before movement. Its maximum speed must stay below the magenta
triangle's. The armored square needs a slower profile that permits two bombs
with the existing cooldown and a usable reaction margin. Exact speeds and band
boundaries remain tuning choices; all types retain the same eight straight lanes.

Generate movement tables offline from lane direction and radius. Start with horizontal extent 44 color clocks and vertical extent 35 logical rows at radius 63, giving room for the sprites within the arena. Use sine/cosine only in the generator, share cardinal/diagonal magnitudes and sign information, and adjust these extents if television aspect-ratio testing requires it. Cache sprite top-left positions in each slot. The current enemies use eight-color-clock-wide, four-logical-row-high sprite windows; variants need a smaller triangle and a larger square silhouette, centered on the same lane coordinates. Verify each shape's bounds and destruction-burst alignment.

Use the same coordinate transform for beam graphics and enemy positions. The generator must verify that the beam crosses every legal enemy silhouette and that all sprite bounds fit. The horizontal playfield ray covers the enemy center; a thin ball ray may differ from the rounded center by at most one color clock. Normalize radial distance across lanes so bomb reach does not change merely because the enemy approaches diagonally.

For radius comparisons, explicitly compare both bytes: `24.00` is inside the bomb, `24.01` is outside. Rendering may use the integer byte; the bomb-range cue uses the exact combat comparison.

## Combat rules

| Target | Health | Beam | Bomb inside radius | Kill score |
| --- | --- | --- | --- | --- |
| Standard green triangle | 1 | One damage on matching lane | No effect | 10 |
| Smaller magenta triangle | 1 | One damage on matching lane | No effect | To tune |
| Standard pink square | 1 | No effect | One damage | 25 |
| Larger armored square | 2 | No effect | One damage per detonation | To tune |
| Blue rhombus | More than 1; exact value to tune | One damage per eligible beam tick on matching lane | One damage per detonation | To tune |

The beam pierces: every eligible target on its selected lane is checked,
including frames when the beam graphic is omitted. Squares do not block the
ray. Gate damage on `BeamEnabled` and use `Direction`; release afterglow never
deals damage. Both triangle types die on the first matching beam update.

The rhombus needs a short per-enemy interval between beam hits, so multiple
health points cannot disappear on consecutive updates. The first beam hit is
immediate; subsequent hits require the interval to expire and the beam to match
again. Continue advancing that interval while the beam is aimed elsewhere;
releasing or redirecting must not reset it early. Keep the beam's continuous
graphic and sound. The interval's length remains provisional. This gate applies
only to beam damage on rhombuses; it cannot suppress a bomb hit.

A bomb checks every active slot once and deals one damage to squares and
rhombuses within radius. Triangles are immune. Its expanding outline is cosmetic
and causes no subsequent damage; there is no moving damage front. A target
outside the radius takes no bomb damage. Armored squares require two separate
accepted detonations; a held button or lingering ring cannot supply the second.

Process bomb damage before beam damage, then process center contacts. As an
initial combination rule, a rhombus may receive one bomb hit and an eligible
beam hit in the same update if it survives the first hit. Immediately mark a
zero-health enemy inactive; award score and quota credit exactly once, only on
death. A nonlethal hit leaves it active and eligible for contact. Contacted
enemies are removed without score or quota credit. Each surviving contact costs
one player HP regardless of type or remaining enemy health, saturating at zero;
there is no player invulnerability mechanic in the baseline.

Show nonlethal damage with a brief hit flash or damaged silhouette. The armored
square must visibly lose armor after its first bomb, while remaining bomb-only.
Its damaged state must remain distinguishable from the bomb-range fill cue.
Reserve the existing destruction burst for the final hit.

A scored kill starts an 18-update cosmetic burst at the last cached position.
It cannot move, be hit again, or damage the turret. Three eight-row sprite shapes
show a white flash, gold sparks, then dim red embers. Each stage lasts six updates.
The existing `visual_state` byte holds the countdown; zero means no burst.
Contacts do not produce this kill effect. Effects continue to expire during game
over, and starting/resetting a run clears them.

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

After sampling input, advance existing burst timers in all modes before handling
reset or transitions. A burst created by later combat keeps its full lifetime
for that first picture.

1. Sample and normalize input; handle RESET or non-play mode transitions.
2. Decrement nonzero cooldown, bomb-animation, spawn, square-spacing, and per-enemy beam-hit timers. A timer set later in this update is not decremented again.
3. Move enemies that were active at the start of the update.
4. Accept a fresh bomb press if ready; set cooldown to 60 and bomb-animation timer to 16. Emit one bomb event for damage and sound.
5. Resolve bomb damage, eligible beam damage, and surviving center contacts in that order. Award kills only when enemy health reaches zero.
6. Resolve death, quota completion, and level-break entry.
7. If still playing with quota remaining, attempt at most one spawn when due.
8. Update beam visual state, select sound events, and save input history. In `PLAY`, arm the fade while held and advance it on neutral updates; clear it on reset or leaving play. Prepare display data before the next visible arena.

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

The current prototype stores eight fields per slot as eight arrays of four bytes:

| Field | Meaning |
| --- | --- |
| `flags_lane` | Bit 7 active, bit 6 square type, bits 0–2 direction; other bits reserved |
| `radius_hi` | Integer distance |
| `radius_lo` | Fractional distance |
| `screen_x` | Cached left edge in color clocks |
| `screen_y` | Cached top logical row |
| `draw_phase` | Selected display phase/scheduling assignment |
| `draw_age` | Consecutive visible frames omitted, for scheduler checks |
| `visual_state` | Remaining destruction-burst updates; square fill is derived from radius |

The variant implementation must replace the one-bit square discriminator with
a type ID for all five variants and allocate remaining health plus the rhombus's
beam-hit interval. Prefer packing/reusing existing per-slot fields after checking
their lifetimes; update this map and its tests with the implementation. Derive
speed from type, level, and distance rather than storing another speed byte per
enemy. Vulnerability, score, sprite, and starting health come from type data.

Attempt a spawn only if there is a free slot, active count is below cap, quota remains, and the spawn timer is zero. Choose a lane and type using a one-byte deterministic LFSR: shift right, XOR with `$B8` when the old low bit was one; seed `$A5` on reset. A host check verifies its nonzero cycle. Determinism enables replayable tests.

A slot with a nonzero burst timer is reserved even though its active flag is clear.
The total of live enemies and bursts must remain below the validated display cap
before spawning. This may defer a due spawn for up to the burst's 18 updates;
movement, attacks, cooldowns, and the surviving enemies continue normally.

Do not place two enemies in the same lane in the baseline. For each attempt, choose a starting lane and examine at most eight lanes cyclically. Reject occupied lanes and arrangements forbidden by the validated renderer. If none are permitted, defer the spawn eight updates; do not add a hidden enemy or retry indefinitely. A successful spawn reloads the level's spawn interval. Track actual encounter density in playtests so scheduling restrictions do not silently erase the intended difficulty increase.

Replace the prototype's single square probability with per-type spawn weights.
Both square variants share bomb-demand spacing; armored squares must account
for two detonations. The old 72-update square spawn gap was tuned for equal-speed,
one-health enemies and is not sufficient evidence of fairness for mixed speeds.
Check arrival times at bomb range and contact, not just time between spawns.

With bomb radius 24, contact radius 8, and speed `56/256`, the old square has
about 73 updates between those boundaries, leaving only about 13 updates beyond
the 60-update bomb cooldown. Do not reuse that late-level speed for two-hit armor
without verifying a useful first-hit reaction window and a second ready bomb.
Test combinations of normal/armored squares and rhombuses against the cooldown;
rhombuses also offer the beam as an alternative. Exact spacing and weights need
playtesting. These bounds assume usable bomb timing, not recovery from every
wasted bomb.

## Level data and increasing density

The original level rows below contain `requested_cap`, `kill_quota`,
`spawn_interval`, `speed_fraction`, and `square_weight` out of four. They remain
a provisional baseline for standard triangles and squares. Variant integration
must replace `square_weight` with per-type weights and select speed profiles,
introducing the new types gradually. Do not enable new variants using these old
fairness assumptions unchanged. No runtime difficulty formula is needed.

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

Use the ball for vertical/diagonal beams and the playfield for horizontal beams and bomb outlines, with player 0 for the turret and player 1 for enemies. Leave missiles disabled. Keep the background black; use cycling rainbow colors for beam frames and fixed gold for ring frames. HUD graphics occupy a separate vertical region.

The beam uses eight fixed rays, one selected by direction. Vertical and diagonal rays are one color clock wide; diagonal ball motion advances at most one color clock each physical scanline. Horizontal rays retain their two-scanline thickness and independently controlled playfield halves so a right shot cannot create a left copy. Both kernels repeat the turret/enemy graphics across two scanlines per logical row. While held, cycle the entire beam through eight hues, one every four frames, at luminance 14. On release, freeze the last hue and direction and count brightness from 15 through 1, once per update, then hide the pattern. This follows Laser Blast's decay cadence; [kernel notes](KERNEL_TIMING.md#effect-scheduling) record the reference and TIA luminance behavior. Re-aiming cancels the fade immediately. Set the color before the arena and keep it fixed across all rows; there is no spatial gradient or separate glow layer.

Keep the turret visible every frame. Draw the beam on both frame phases normally. During a bomb, odd frames draw the ring and even frames draw the beam, giving each effect about 30 appearances per second without adding omissions to enemy graphics. Ring colors stay gold on both physical scanlines. Input, damage, and beam audio remain independent of this display phase. Use no transparency or trails.

Generate four ring sizes in the same radial geometry as the lanes, initially radii 6, 12, 18, and 24. Each lasts four updates, ensuring two visible ring frames regardless of the firing phase. The final outline marks the bomb's maximum radius. Treat the 16-update animation as feedback for immediate damage, not a persisting blast. Validate both beam/ring phases, neutral-stick bombs, every stage, and target visibility during the largest ring.

The generator encodes six playfield planes per pattern; ball-ray patterns have blank playfield data. The current geometry keeps left PF0 and right PF2 at zero, allowing four timed stream loads in the playfield kernel. Horizontal rays, neutral, and four rings share 14 unique 80-byte streams. Two additional packed motion streams serve all four diagonals; vertical rays reuse the zero stream. Pack three streams per page. Keep indexed streams within pages where the kernel assumes fixed load timing, or explicitly account for page crossings. Expanding the geometry into the constant-zero outer planes requires revising the playfield kernel.

The ball kernel strobes HMOVE at cycle 3 of every arena scanline. Clear all object motion registers in the separator so the turret and enemy stay fixed; write the ball's next motion at least 24 cycles after HMOVE. Store both physical lines' motion nibbles in one byte per logical row. Enable the ball only between the ray's generated row bounds, and disable it before the next HUD. The ball shares the playfield's color register, preserving the beam palette without changing sprite colors.

Each scanline still has its own write deadlines in a two-line kernel. Before accepting it, produce an instruction-cycle schedule covering both playfield halves, both player graphics, loop control, and horizontal positioning. No particular register schedule is considered proven by this specification.

### Initial two-enemy display

For the first kernel, position one enemy or burst graphic during blanking and draw it for the frame. When two objects are present, alternate them; when one is present, draw it every frame. Choose by greatest draw age with a stable slot-index tie-break so spawning/freeing slots cannot starve an enemy. Kills retain their draw age when switching to a burst. This avoids mid-arena repositioning in the first implementation.

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

The current map uses the full available address range, with explicit reserve and stack space. Generate symbols and fail the build on overlap. Reclaim prototype diagnostics and revise the shared lifetimes when adding variant, level, and audio state.

| Address range | Bytes | Allocation |
| --- | ---: | --- |
| `$80–$9F` | 32 | Four enemy slots, eight arrays of four bytes |
| `$A0–$AF` | 16 | Layout ID, frame counter, bomb count, mode, HP, two score bytes, spawn timer, square timer, RNG, active count, active cap, speed, spawn interval, square weight, spare |
| `$B0–$B7` | 8 | Direction, last direction, previous button/reset bits, beam enable, bomb cooldown, bomb-animation timer, bomb event, frame phase |
| `$B8–$BF` | 8 | Two HUD health masks; six bytes reserved for audio |
| `$C0–$D7` | 24 | Renderer pointers, row bytes, and draw/HUD state |
| `$D8–$E7` | 16 | Ten HUD score row bytes, four status-pointer bytes, draw-age temporary, general temporary; logic scratch aliases the HUD storage during overscan |
| `$E8–$EF` | 8 | Unallocated margin; guard pattern in debug builds |
| `$F0–$FF` | 16 | Stack reservation |
| Total | 128 | Includes stack and margin |

The 24 renderer bytes currently hold four two-byte playfield pointers, a two-byte sprite pointer, selected slot, HUD color, arena color, display-pattern ID, four beam visual bytes (fade timer, frozen hue, draw direction, draw color), a two-byte ball-motion pointer, two ball row bounds, a kernel selector, and one reserved byte. Later sprite reuse must fit or explicitly revise this allocation. Scratch can be reused only across nonoverlapping lifetimes; record clobbered registers and scratch in each routine's header. ROM switching does not preserve a second copy of RAM.

The game commits `PreviousButtons` before render preparation overwrites the sampled-input scratch with HUD rows. Movement/spawn scratch is also dead by then. Persistent health, score, timers, input history, enemy positions and beam state never alias those HUD buffers.

Initialize the stack at `$FF` and keep peak stack consumption within 16 bytes, including nested subroutines and any explicit pushes. Verify the high-water mark in the busiest frame. Increasing storage beyond four slots requires a revised map; it is not enabled by changing only a level row.

## ROM banks and module boundaries

F8 selects its lower and upper 4 KiB banks through cartridge hotspots `$1FF8` and `$1FF9`; the game can address their `$FFF8`/`$FFF9` mirrors. Stella's [F8 mapper implementation](https://github.com/stella-emu/stella/blob/master/src/emucore/CartF8.cxx) provides a reference for these selections.

| Bank | Contents |
| --- | --- |
| 0 | Reset/init, input, modes, movement and coordinate magnitudes, attacks, spawning, scoring, future levels, audio updates |
| 1 | Display preparation, kernels, beam streams, sprites, font/HUD data |

Place matching bank-switch trampolines at `$FF80–$FFF7` in both banks, reserve `$FFF8–$FFF9` as hotspots, and put matching vectors at `$FFFA–$FFFF`. Both reset vectors enter a common stub that explicitly selects bank 0, so startup does not depend on the initial bank.

Cross-bank transitions use explicit jump stubs whose next instructions are identical at the same address in both banks. Do not use a normal cross-bank `JSR`/`RTS` convention. Switch into bank 1 before synchronization/display preparation, remain there for the visible kernel, then switch back under blanking for the overscan update. Any large data needed by a bank must be in that bank or copied into an explicitly budgeted RAM field.

### Planned project files

These are the planned deliverables for the full game; the prototype supplies the
build, combat, display, generation, and cartridge-test subset:

| Path | Responsibility |
| --- | --- |
| `Makefile` | Generate assets, assemble ROM, run checks, launch emulator |
| `src/main.asm` | Bank layout, includes, vectors, common entry points |
| `src/ram.inc` and `src/constants.inc` | State allocation and fixed hardware/game constants |
| `src/input.asm`, `src/game.asm`, `src/play.asm` | Input decoding, frame orchestration and playable mode/update order |
| `src/enemies.asm`, `src/combat.asm` | Slot pool, spawning, movement, hits, score/quota |
| `src/audio.asm` | Sound state and event priorities |
| `src/render.asm`, `src/hud.asm`, `src/kernel.asm` | Display schedule, score/status preparation, pointer setup, timed screen output |
| `config/tuning.json`, `config/levels.json` | Single source for provisional numbers and level rows |
| `tools/generate_assets.py` | Deterministic geometry, beam, font, and level-table generation |
| `tools/check_rom.py` | Image size, vectors, bank stubs, RAM layout, table bounds |
| `tests/test_combat.py`, `tests/test_prototype.py` | Actual-cartridge rule, timing, input and display tests; generator invariants |
| `tests/scenarios/` | Deterministic cartridge/debug scenarios and expected state traces |
| `vendor/dasm/` | Pinned Atari headers/macros and their license/provenance |
| `build/` | Generated includes, ROM, symbols, listing, and validation reports |

Each assembly routine declares inputs, outputs, register clobbers, scratch use, and its applicable cycle bound. `play.asm` owns combat update order; `game.asm` owns frame entry and the static display-test path. `render.asm` consumes state and may change only render caches/diagnostics, never HP, score, enemy movement, or combat outcomes.

## Build and verification workflow

`make all` generates tables and produces `build/atari-zerowave.bin`, `.sym`, and `.lst`, plus the separate `atari-zerowave-display` artifacts compiled with `DISPLAY_TEST=1`. Each ROM must be exactly 8,192 bytes with deterministic padding. `make check` runs host checks, `make run` launches the playable cartridge in configured NTSC/F8 Stella, and `make debug` opens it with symbols. `make run-display` opens the static fixture cartridge. `make stella-check` runs automated scenarios for both under X11.

Pin the assembler/tool inputs and record versions, source revision, validated enemy cap, and ROM checksum in a build report. Fail on unresolved symbols, bank overflow, RAM/stack reservation overlap, missing table entries, or mismatched common stubs. Keep build output disposable and out of the reference checkout.

`make bootstrap` obtains the pinned DASM and py65 sources under `.tools/` and builds DASM locally. Stella validation requires a graphical session or virtual display; the automated invocation is `xvfb-run -a make stella-check`.

Host tests verify the integer model and generated data; they do not prove the assembly or TIA timing. Run the same state/input scenarios against the actual cartridge and compare its RAM state using symbols and debugger checkpoints. Use Stella's [debugger timers, watches, scanline stepping, and symbol/list support](https://stella-emu.github.io/docs/debugger.html) to inspect the assembled result. Check the release image too if debug instrumentation changes code placement.

## Acceptance tests

| Area | Required cases and result |
| --- | --- |
| Input | All eight directions, neutral, and opposite-axis combinations decode deterministically; neutral disables beam damage and sound. |
| Release fade | Held beam stays bright; neutral freezes its hue/direction for the 15-update countdown, then clears it. Re-aiming restores brightness immediately. Reset clears afterglow. Bomb animation and enemy scheduling continue during the fade. |
| Button edges | Held fire causes one bomb; cooldown presses do not queue; activation at `t+59` fails and a fresh press at `t+60` succeeds. Start/reset/transition inputs do not create accidental bombs. |
| Weapon/type matrix | Both triangle types take beam damage only; both square types take bomb damage only; rhombuses accept either. Immune hits never reduce health or award score. |
| Beam | Matching-lane triangles die immediately; wrong lanes survive; squares do not block the ray. Rhombus hit cadence works during held/released/re-aimed beam and ring frames. Beam pattern crosses every variant's legal positions. |
| Bomb boundary | With zero movement, an eligible target at `24.00` takes one damage and at `24.01` takes none; square fill agrees. Triangles survive at either radius. Armor survives one bomb and dies to a second; the ring cannot hit again. |
| Resolution order | Same-frame beam+bomb can damage a rhombus twice if eligible, but grants one kill per target. Lethal attacks prevent contact; a nonlethal hit does not. Multiple surviving contacts reduce player HP without underflow. |
| Destruction burst | A scored kill draws all three stages at its final position, awards score once, and expires after 18 updates. Two bursts or a burst plus a live enemy each appear at least every other frame. A reserved burst slot cannot be reused early; reset clears all effects. |
| Movement | Fractional stepping, subtraction near zero, and every lane/radius mapping are correct. Rhombus speed increases at each inward distance band and stays below the magenta triangle. No variant or burst leaves the arena. |
| Spawn limits | Never exceed active cap, duplicate a baseline lane, overwrite a live slot, or spin on failed placement. Square spacing is honored. |
| Fairness | At each speed profile, measure the exact updates from bomb-range entry to contact. Armored squares allow two bombs plus reaction time. Mixed-speed arrivals retain usable bomb windows. |
| Progression | Multi-kill quota crossing stops spawns, waits for remaining enemies, and enters a 60-update break. Death overrides advancement. Level 99 and score 9999 saturate safely. |
| Display | Turret stays steady; beam and bomb ring alternate without disabling beam damage. Every active enemy appears at least every other frame. Test every ring stage on both press phases, neutral-stick bombs, same-height pairs, and center convergence. |
| Memory and ROM | Both possible startup banks reset correctly; bank stubs match; stack remains in its reservation; guard bytes remain intact; each bank fits. |
| Timing | All states use the intended frame/scanline counts. Worst-case bomb kills, score carry, failed spawns, transitions, and display schedules stay within measured budgets. |

Use small deterministic fixtures for logic failures, then a longer scripted stress run with repeated restarts, level transitions, and dense layouts. A hardware pass must cover a real joystick's diagonals, bomb responsiveness, flicker/readability on a television, and sound. Record emulator timing evidence separately from hardware observations.

## Implementation milestones

| Milestone | Deliverable | Exit criterion |
| --- | --- | --- |
| 0 | Pinned build, F8 startup/bank stubs, stable blank ROM | Correct image/vectors and stable frame from either initial bank |
| 1 | Turret, eight color-cycling beam patterns, one enemy graphic, expanding bomb outline | Cycle schedule and Stella measurements prove the core display and both effect phases |
| 2 | Input, two-enemy pool/display, movement, combat, HP, score, restart | Rule fixtures pass in the cartridge; two-enemy overlap remains readable |
| 3a | Revised vulnerabilities, fast triangle, armored square, accelerating blue rhombus | Weapon matrix, hit cadence, movement, readability, and bomb fairness pass at the two-enemy cap |
| 3b | Level table, transitions, and remaining sound cues | Opening levels introduce variants gradually and are playable and fair; baseline hardware pass |
| 4 | Vertical sprite reuse and three-enemy scheduling | Three-enemy stress cases meet timing and omission limits; enable level 4 density |
| 5 | Four-enemy scheduling and later-level balancing | Four-enemy cases pass before enabling level 6 density; otherwise retain the measured lower cap |

Implement milestones in order. If milestone 1 fails, revise the kernel while keeping eight-way beam and button bomb behavior. If higher densities fail, adjust scheduling and spawn arrangements or keep the lower validated cap; do not restore removed visual effects to compensate. Charge bombs, trails, reflectors, shifters, XP, and upgrades remain outside this implementation.
