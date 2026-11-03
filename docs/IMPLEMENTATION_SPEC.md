# Atari ZeroWave implementation specification

Implement the game defined in [PORT_OUTLINE.md](PORT_OUTLINE.md) as a native Atari 2600 cartridge: a stationary turret, eight-way joystick beam, button-triggered bomb, triangle/square variants and a blue diamond, health, score, and levels with increasing enemy counts.

The first playable build must support two active enemies. The implementation reserves four enemy slots and separates storage capacity from the current level's cap. Three- and four-enemy levels are enabled only after their display schedules pass the tests below. Controls and combat rules are requirements; tuning values are initial defaults that may change through playtesting.

Implementation status (2026-11-01): the playable ROM includes one beam shot per
joystick flick, nine enemy variants, health, score, damage/immunity feedback,
destruction bursts, attack/combat sound cues, start/game-over/restart, and level
quotas/transitions. See [play instructions](../README.md) and [measured kernel
timing](KERNEL_TIMING.md). Eight early difficulty rows introduce variants gradually,
followed by faster spawning at level 10, reinforced triangles at level 20, and
reinforced diamonds at level 25. Level 1 keeps two enemies; level 2 onward permits
four with vertical sprite reuse and approach-spacing checks. Bomb recharge is
half a second. Completed waves get a brief all-clear celebration, replacements arrive rapidly within waves, and the
HUD shows score, health, and level, with a filling progress bar below the arena. From wave 2, up to two
bomb-only squares may coexist. CPU/register tests cover four-target layouts and
current headless Stella captures cover the HUD and both display phases. Level
balancing and hardware readability remain to be validated. A separate display-test ROM retains the
legacy held beam and static SELECT layouts.

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

Fire one beam shot per deliberate joystick flick from center into a direction.
Holding the direction never repeats. Returning the stick to center rearms the
next shot. Moving directly between non-neutral directions neither fires again
nor redirects an existing shot. Require actual center (all four direction
switches released) to rearm; opposing inputs that normalize to neutral must not
create a synthetic release. Do not require button input to fire the beam.

Each accepted shot emits a one-update `BeamEvent`, latches its direction, and
starts a bright-to-dark fade immediately. Damage occurs once on that event;
the remaining picture is cosmetic. Fade for 15 updates as a starting duration,
whether the stick remains held or is released. A new, rearmed shot replaces the
previous fade, even if it has not finished. There is no automatic firing cadence
or extra shot cooldown in this design. Preserve one uniform hue per shot and
cycle through the bright palette across shots. Diagonals still produce one ray.

Maintain the rearm latch in all modes. Starting, resetting, or changing levels
consumes that update and must not fire a beam. A direction held across a mode
transition requires a return to center before firing. Validate deliberate
diagonal flicks on a real joystick; any direction-settling adjustment must
preserve one shot per center-to-direction movement.

A button press edge detonates a bomb only when its cooldown is zero. Holding the button never repeats, and presses during cooldown are discarded rather than queued. Beam shots can fire during a bomb, including in the same update. Maintain button history even when an action is rejected or the game is between levels.

Power-on shows a small title/ready screen. A fresh fire press starts a run without also firing a bomb. A RESET press edge starts a fresh run from any mode. SELECT and difficulty switches have no gameplay function in this version. A held button across startup, reset, game over, or a level transition must be released before it can cause another press action.

## Arena coordinates and movement

The playable layout uses 29 scanlines for the top HUD, one for separation/setup,
160 for the arena, and two for the bottom wave-progress bar. The diagnostic
retains a 24-line HUD and eight-line separator with no footer. The arena has 80
logical rows, each drawn twice. Define the turret center as `(80, 40)` in horizontal
color clocks and arena logical rows; its playable visible vertical coordinate is
`30 + 2*40 = 110`. Moving the bar to the bottom shifts the arena up two scanlines
without changing its size or the 192-line visible region.

Game geometry uses an eight-way lane and a radial distance, not free Cartesian movement. Store distance as unsigned 8.8 fixed point: an integer byte plus a fractional byte. Initial constants are:

| Constant | Default | Meaning |
| --- | ---: | --- |
| `SPAWN_RADIUS` | 63 | Enemy spawn distance, fraction initially zero |
| `CONTACT_RADIUS` | 8 | A surviving enemy at or inside this radius reaches the turret |
| `BOMB_RADIUS` | 24 | Fixed local damage radius |
| `BEAM_RANGE` | 63 | Beam reaches the full approach lane |
| `START_HP` | 5 | Health at the start of each run |
| `BOMB_COOLDOWN` | 30 updates | Approximately half a second at the target frame rate |
| `BOMB_ANIMATION_FRAMES` | 16 updates | Four expanding ring sizes, four updates each |
| `BOMB_SOUND_FRAMES` | 6 updates | Short noise envelope independent of animation |
| `BEAM_FADE_START` | 15 | Initial shot brightness; countdown through 1, then hide, independent of release |
| `ENEMY_BURST_FRAMES` | 18 updates | Three destruction stages, six updates each |
| `IMMUNE_FLASH_FRAMES` | 18 updates | Three bright yellow/orange shake stages |
| `HIT_FLASH_FRAMES` | 6 updates | White nonlethal enemy-hit flash |
| `PLAYER_HIT_FRAMES` | 12 updates | Four red background shades, three updates each |
| `level_background_colors` | 8 colors | Persistent dark backgrounds, indexed by `(decimal level - 1) % 8` |
| `LEVEL_BREAK` | 32 updates | Celebration after a cleared level |
| `SQUARE_SPAWN_GAP` | 72 updates | Minimum spacing between square spawns |

Each active enemy subtracts its type's speed for its distance from its fixed-point distance once per update. Type speeds remain the same across the current level rows. Speeds are fractional-byte values, so `32` means `32/256` radial units per update. Saturate subtraction at zero; an underflow must never wrap an enemy to the outer rim.

The current type speeds are 32/256 for standard/reinforced triangles, standard squares, and hexagons,
48/256 for orange squares, 80/256 for magenta triangles, and 20/256 for armored squares. Diamonds use 32/256 at radius
40 or greater, 48/256 from 24 up to 40, and 64/256 below 24. Select the band from
distance before movement; the magenta triangle remains fastest everywhere.
The armor speed leaves about 204 updates from bomb range to contact, compared
with a 30-update recharge. Tests include a 30-update first-hit reaction delay
and the full recharge before the second bomb. Speeds and bands remain tuning
choices; all types retain the same eight straight lanes. `MovementEnabled=0`
freezes motion for debugger fixtures without changing their type or health.

Generate movement tables offline from lane direction and radius. Start with horizontal extent 44 color clocks and vertical extent 35 logical rows at radius 63, giving room for the sprites within the arena. Use sine/cosine only in the generator, share cardinal/diagonal magnitudes and sign information, and adjust these extents if television aspect-ratio testing requires it. Cache sprite top-left positions in each slot. The current enemies use eight-color-clock-wide, four-logical-row-high sprite windows; variants need a smaller triangle and a larger square silhouette, centered on the same lane coordinates. Verify each shape's bounds and destruction-burst alignment.

Use the same coordinate transform for beam graphics and enemy positions. The generator must verify that the beam crosses every legal enemy silhouette and that all sprite bounds fit. The horizontal playfield ray covers the enemy center; a thin ball ray may differ from the rounded center by at most one color clock. Normalize radial distance across lanes so bomb reach does not change merely because the enemy approaches diagonally.

For radius comparisons, explicitly compare both bytes: `24.00` is inside the bomb, `24.01` is outside. Rendering may use the integer byte; the bomb-range cue uses the exact combat comparison.

## Combat rules

| Target | Enemy health | Beam | Bomb inside radius | Contact damage to player | Kill score |
| --- | --- | --- | --- | --- | --- |
| Standard green triangle | 1 | One damage on matching lane | No effect | 1 | 10 |
| Smaller magenta triangle | 1 | One damage on matching lane | No effect | 2 | 20 |
| Standard pink square | 1 | No effect | One damage | 1 | 25 |
| Larger armored square | 2 | No effect | One damage per detonation | 1 | 50 |
| Blue diamond | 3 | One damage per beam shot on matching lane | One damage per detonation | 1 | 40 |
| Amber/orange fast square | 1 | No effect | One damage | 1 | 35 |
| Cyan hexagon | 1 | Survives; player loses one HP | Defeated by one bomb | 1 | 60 |
| Violet reinforced triangle (level 20) | 2 | One damage per matching shot | No effect | 1 | 30 |
| Gold reinforced diamond (level 25) | 4 | One damage per matching shot | One damage per detonation | 1 | 40 |

Diamond health and new score awards are provisional playtest values.

The beam pierces: each shot checks every eligible target on its latched lane,
including updates when the beam graphic is omitted for a bomb ring. Squares do
not block the ray. `BeamEvent` aliases the former `BeamEnabled` byte in the
playable ROM; it is a one-update event, not a held-input gate. A visible fade
never causes additional hits. Green and magenta
triangles die to one matching shot; violet triangles need two. A diamond loses one health per shot
and requires separate center-to-direction movements for further beam damage.
No per-enemy beam-hit interval is needed. An enemy entering or spawning into a
fading beam after the event takes no damage from that old shot.

A bomb checks every active slot once and deals one damage to squares, hexagons,
and diamonds within radius. Triangles are immune. Its expanding outline is cosmetic
and causes no subsequent damage; there is no moving damage front. A target
outside the radius takes no bomb damage. Armored squares require two separate
accepted detonations; a held button or lingering ring cannot supply the second.

A hexagon retaliates once for each fresh beam event on its lane, subtracting
one player HP with saturating damage, the existing red flash, and a distinct
12-update electrical rejection buzz. Ordinary hexagon contact uses the normal
player-hit sound; beam retaliation takes priority over other nonfatal cues.
The hexagon keeps its HP and shows the immunity flash/shake. Holding a direction,
the cosmetic fade, or a missed lane cannot trigger retaliation. The beam still
pierces. Bomb damage resolves first for each slot: a bomb that kills a hexagon
prevents its beam retaliation and contact in that update. A surviving hexagon
can retaliate and then make contact, costing two HP in total. All slots resolve
before death, score healing, or wave advancement; fatal retaliation wins over
healing. A full-health milestone clears hexagons without retaliation or extra score.

The orange square reuses the normal square's outline/fill cue. The cyan hexagon
has a flat-topped six-sided silhouette and stays filled at every distance; use
the existing bomb ring as its range guide. Its graphic shares the first white
destruction flash, preserving the ten-entry sprite atlas and 8 KiB format.

Process bomb damage before beam damage, then process center contacts. As an
initial combination rule, a diamond may receive one bomb hit and an eligible
beam hit in the same update if it survives the first hit. Immediately mark a
zero-health enemy inactive; award score and quota credit exactly once, only on
death. A nonlethal hit leaves it active and eligible for contact. Contacted
enemies are removed without score or quota credit. A small magenta triangle
deals two player damage on contact; every other type deals one. Contact damage
does not depend on the enemy's remaining health. Saturate player health at zero,
including a two-damage contact at one HP; there is no player invulnerability
mechanic in the baseline.

Show nonlethal damage with a brief white hit flash. The armored
square loses its larger outline and becomes a normal-sized square after its
first bomb, while remaining bomb-only and retaining its 50-point kill value.
Its damaged state must remain distinguishable from the bomb-range fill cue.
Reserve the existing destruction burst for the final hit.

The reinforced triangle reuses the standard triangle silhouette at its normal
speed, colored violet (`$6E`). It keeps that color after a nonlethal flash and
retains one contact damage. Type ID 3 (`$30` in the packed flags) uses the last
available type code; existing health and feedback arrays need no extra RAM.

From level 25, new diamonds start with four HP and a gold color (`$1E`). A hit
flashes white, then exposes the ordinary blue diamond with three HP. This is a
health state of type 2, preserving its acceleration, weapon permissions, one
contact damage, and 40-point score. Only diamonds can have four HP, so the
renderer can select gold from health alone after selecting the diamond/hexagon
sprite family. Damage/immunity feedback still overrides the base color.
Four bombs cannot fit between bomb range and contact at the unchanged near
speed and 30-update cooldown; the player must use some beam damage to defeat a
full-health reinforced diamond before it arrives.

A scored kill starts an 18-update cosmetic burst at the last cached position.
It cannot move, be hit again, or damage the turret. Three eight-row sprite shapes
show a white flash, gold sparks, then dim red embers. Each stage lasts six updates.
When a slot is inactive, `visual_state` holds the countdown; zero means no burst.
Contacts do not produce this kill effect. Effects continue to expire during game
over, and starting/resetting a run clears them.

Use four decimal score digits stored as two packed-BCD bytes, saturating at 9999. BCD arithmetic must leave decimal mode clear before returning to other code. One scoring routine updates score and decrements the level's remaining kill quota, also saturating at zero. Multiple kills in one update all earn score even if the first exhausts the quota.

Each crossed 1,000-point boundary restores one HP, capped at `START_HP=5`.
Snapshot `ScoreHi` before combat, then compare its thousands nibble after all
kills and contacts. Current awards and four slots cannot cross two milestones
in one update. Fatal contacts take priority; otherwise restore health after
contact damage, independent of slot order. At full health after contacts, instead
clear every surviving active enemy regardless of armor, HP, lane, range, or
weapon immunity. These removals decrement the remaining kill quota, saturating
at zero, but award no score. Clearing cannot trigger another milestone. Play
fresh destruction bursts at the survivors' last displayed positions; preserve
already-running bursts. Reset the spawn countdown to the current interval to
avoid a same-update replacement, then enter the wave-completion sequence if its quota is exhausted.
Scan the resulting slots before spawning, so counts and reserved burst slots
stay consistent. Healing from four to five does not also clear enemies. Score saturation at 9999 cannot
repeat a reward; valid milestones are 1000 through 9000, reset by a new run.
The snapshot aliases `HudScoreRight+4`; combat and enemy scanning preserve it,
and it expires before HUD preparation.

Healing requests the 32-update `heal` sound: four rising pure-tone notes, eight
updates each, with cyan `$BA` flashes. A full-health clear requests `clear`: a
32-update descending noise explosion, four eight-update stages, with yellow
`$1A` flashes. It stretches the normal kill sound's noise stages for a distinct
screen-clear cue. For either event, bit 3 of the post-audio countdown selects
the flash color for updates 0–7 and 16–23; other updates show the current level
background. Both reuse the existing event timer, adding no persistent RAM.
Player damage and death can interrupt/discard either cue; red hit feedback
always wins over yellow or cyan. Discarded bonus cues are not queued.
Reset/restart clears the cue. Wave completion uses the clear cue after any
remaining red damage feedback; it supersedes a coincident heal cue without
undoing the HP reward. The next level starts after the clear cue finishes.
Both healing and clearing are independent of playback.


Squares change from an outline to a filled silhouette when inside bomb range. This is a shape cue, not only a color change, and introduces no extra graphic object. The cue must use the same radius predicate as bomb damage.

### Ineffective-attack cue

Signal weapon immunity with an 18-update bright yellow/orange flash and a small
sideways shake. Three six-update stages use colors `$1E`, `$2E`, `$1E` and draw
offsets -2, +2, 0 color clocks respectively. Keep the original silhouette,
including square armor and bomb-range cues. The cached enemy coordinates and
collision position remain unchanged. Restore its normal color when the timer
expires. This is distinct from the six-update white successful-hit flash and
the expanding destruction burst. Do not hide the sprite or add a display phase.
Each six-update stage includes three appearances for either draw phase.

Trigger the pulse only when an attack reaches an immune target: a new beam shot
on a square or hexagon's lane, or an accepted bomb with a triangle inside its exact radius.
Trigger once per attack event; neither holding the stick nor the shot's fade
restarts the pulse. A separate flick may trigger a new pulse. Bomb immunity
feedback occurs once per detonation.

Missed lanes, out-of-range bombs, cooldown-rejected button presses, and cosmetic
beam fades do not count as weapon immunity. The expanding ring cannot retrigger
feedback. Resolve all combat results before choosing the picture: destruction takes priority over
successful-hit feedback, which takes priority over immunity feedback. Thus a
square hit by both weapons shows the bomb's actual result.

The flash/shake itself is cosmetic; hexagon retaliation is a separate combat rule.
The cue must not pause movement, alter health, delay a valid
attack, or change scoring. Advance its state independently of whether the
sprite is selected for drawing, and clear it on death, slot reuse, and reset.
The live slot's `EnemyVisual` byte stores the timer in bits 0–6 and a successful
hit flag in bit 7. Death replaces it with the burst lifetime. Both draw phases
are tested so the pulse cannot disappear because of alternate-frame scheduling.

### Player damage feedback

A contact that reduces player health starts `PlayerHitTimer` at 12. Set the
whole visible background, including the HUD and arena, to `$48`, `$46`, `$44`,
then `$42` for three updates each before restoring the current level background.
Background color
is selected during blanking and stays fixed throughout each visible picture.
Clear HMCLR/ENABL with zero independently of the flash color.

Advance the timer before combat, including during game over, so a newly started
flash has its full lifetime and fatal hits still show it. Multiple contacts in
one update share one flash; another contact on a later update restarts it.
Contacts continue to deal their normal damage. A lethal attack that prevents
contact does not start the player flash. Starting or resetting a run clears the
timer; stopping weapons on game over does not. The timer uses one former audio
reserve byte and does not change the sprite schedule.

## Modes and level transitions

| Mode | Behavior | Exit |
| --- | --- | --- |
| `TITLE` | Turret/title mark and start cue; no combat or spawns | Fresh fire press or RESET starts a run |
| `PLAY` | Input, movement, attacks, contacts, spawning, scoring | HP zero goes to `GAME_OVER`; cleared quota enters `LEVEL_BREAK` |
| `LEVEL_BREAK` | Full green bar, frozen combat, survivor bursts and the all-clear cue | After 32 celebration updates, increment and load the next level |
| `GAME_OVER` | Retain/display final score and level with OVER; silence beam, play death cue | Fresh fire press or RESET starts a run and resets results |

A fresh run sets level 1, HP 5, score zero, bomb ready, empty enemy pool, cleared effect timers, and a deterministic nonzero random seed. It loads the first level row and starts its spawn countdown. It does not consume an attack from the start/reset input.

When the kill quota reaches zero, finish resolving all attacks, contacts, and
score milestones. Death takes priority. Otherwise enter `LEVEL_BREAK` with
`SpawnTimer=0`, retaining the completed level and full green bar for the first
picture. Freeze movement, attacks, contacts, and spawning. Once `PlayerHitTimer`
reaches zero, clear surviving enemies at their last displayed positions using
`ClearEnemyBonus`, preserve existing bursts, and set `ActiveCount=0`. This
ignores armor/immunity and grants no extra points or health. Request `SFX_CLEAR`
and set `SpawnTimer=LEVEL_BREAK_FRAMES` (32 updates), without decrementing it in
the starting update. The yellow flashes and explosion use the existing sound
and background logic; bursts continue updating.

During the countdown, consume input and clear weapons. At zero, increment the
BCD level, saturating at 99, then call `LoadLevel`: load its quota, interval,
type mix, cap, and background; clear slots/effects; ready the bomb; restart the
normal spawn countdown. Preserve HP, score, RNG, and input history. A held stick
or button cannot fire on entry. Multi-kills saturate the completed quota and do
not spill into the next one. The existing 1,000-point reward still applies once;
a coincident full-health clear preserves its already-running bursts, while a
coincident heal still grants its HP before the completion cue takes over.

`ConfigureLevel` only updates difficulty, quota, and background. `LoadLevel`
also clears arena/effect state for the next wave, restart, or debugger fixture.
For debugger compatibility, mode 3 with a positive quota and a positive countdown
loads the requested level at zero without incrementing it. Normal completion
has a zero quota. RESET works in every phase. Every exit commits input history.

Each level selects a persistent background from `level_background_colors` in
`config/tuning.json`, indexed by `(decimal level - 1) % 8`. The palette is black
`$00`, navy `$90`, teal `$B0`, plum `$60`, forest `$D0`, brown `$20`, indigo `$80`,
and charcoal `$02`. Low luminance preserves contrast with bright enemies. The
background changes immediately on advancement and stays fixed until the next
level; level 9 repeats level 1, independently of the final difficulty row.
Level 99 retains its color when the displayed level saturates. Red player-hit
feedback temporarily overrides the level color, then restores it, including
on game over. Fresh starts/reset select black; debugger loads select the requested
level's color. The wave-clear flashes finish before selecting the next background.
`LevelBackground` reuses the diagnostic `HudColor` byte, which gameplay no longer
needs for bomb readiness; the diagnostic ROM retains its original HUD behavior.

## Update order and video schedule

One game update produces the state for the next visible frame:

After sampling input, advance existing enemy-feedback/burst and player-hit timers in all modes before handling
reset or transitions. A burst created by later combat keeps its full lifetime
for that first picture.

1. Sample and normalize input; handle RESET or non-play mode transitions.
2. Decrement nonzero cooldown, bomb-animation, spawn, square-spacing timers. A timer set later in this update is not decremented again.
3. Move enemies that were active at the start of the update.
4. Accept a rearmed joystick direction as one beam event and latch its shot direction. Accept a fresh bomb press if ready; set cooldown to 30 and bomb-animation timer to 16. Emit each attack event for damage and sound once; clear events at the start of the next update.
5. Resolve bomb damage, eligible beam damage, and surviving center contacts in that order. Award kills only when enemy health reaches zero.
6. Resolve death first; if alive and a score milestone was crossed, restore one HP below full health or clear survivors at full health. Scan slots and enter `LEVEL_BREAK` if the quota is exhausted; skip spawning on completion.
7. If still playing, attempt at most one spawn when due, using the current level's settings.
8. Update beam visual state and save input history. If the event voice is idle, find the nearest fast triangle for the approach warning. In `PLAY`, start the fade on a new shot; otherwise advance it regardless of joystick state. Clear it on reset or leaving play. At the start of VBLANK, select/output the sound envelope before preparing display data and bonus-flash color for the next visible arena.

New spawns cannot move or be attacked until the following update; spawning therefore cannot grant a same-update kill. Their first drawing opportunity follows the enemy omission limit below. Timer semantics mean a bomb accepted at update `t` can next be accepted at `t+30`, with a new press edge; `t+29` is too early.

Use a stable NTSC frame: three VSYNC lines, 37 VBLANK lines, 192 visible lines, and 30 overscan lines. Each scanline has 76 CPU cycles. The frame is software-timed, as described in the [Atari timing reference](https://alienbill.com/2600/101/docs/stella.html).

| Phase | Work | Initial software budget |
| --- | --- | --- |
| Overscan | Sample input and run the game update for the next picture | At most 2,000 of 2,280 cycles |
| VSYNC | Fixed synchronization sequence | Exactly three lines |
| VBLANK | Output sound, derive coordinates, choose enemy draw schedule, prepare HUD/beam pointers, position objects | At most 2,400 of 2,812 cycles |
| Visible | Draw HUD, separation, and arena | Exactly 192 lines; each path meets register deadlines |

These are allocation targets to measure in the first implementation. Bank changes, timer setup, branches, and wait alignment count toward each budget. Move bounded work between overscan and VBLANK if necessary, documenting the handoff; never lengthen the frame to finish logic. Wait out unused time. Do not perform spawning, random retries, scoring, or unbounded loops inside the visible kernel.

## Enemy storage and spawning

Use `MAX_ENEMIES=4` as compiled storage capacity and `VALIDATED_ENEMY_CAP=4` as the tested gameplay ceiling. Runtime `active_cap` is the smaller of the level request and validated cap. Every enemy loop uses slot indices and an active flag; there must be no separate hard-coded enemy-one/enemy-two logic.

The current prototype stores eight fields per slot as eight arrays of four bytes:

| Field | Meaning |
| --- | --- |
| `flags_lane` | Bit 7 active; active bits 4–6 type (0 triangle, 1 fast triangle, 2 diamond, 3 reinforced triangle, 4 square, 5 armor, 6 fast square, 7 hexagon); bits 0–2 lane. Inactive `$40 | lane` temporarily marks a scored burst awaiting coordinate preparation. |
| `radius_hi` | Integer distance |
| `radius_lo` | Fractional distance |
| `screen_x` | Cached left edge in color clocks |
| `screen_y` | Cached top logical row |
| `health` | Remaining enemy health; reuses the former unused `EnemyPhase` array |
| Former `draw_age` array | Gameplay: four shared bytes for second sprite pointer, remaining X displacement, and color. Diagnostics retain draw ages. |
| `visual_state` | Live: bit 7 successful-hit feedback, bits 0–6 remaining feedback updates; inactive: destruction-burst updates |

Vulnerability, score, sprite, starting health, speed, and contact damage come
from generated type tables, with diamond starting HP overridden from level 25.
Diamond speed also depends on distance. There is no
per-enemy speed byte or beam-hit timer. Square fill is derived from exact radius;
the damaged armor shape is derived from health. The seven enemy arrays plus four renderer bytes occupy
32 bytes, leaving the existing guard and stack reservations intact.

Attempt a spawn only if there is a free slot, active count is below cap, quota remains, and the spawn timer is zero. Choose a lane and type using a one-byte deterministic LFSR: shift right, XOR with `$B8` when the old low bit was one; seed `$A5` on reset. Use the first result's low three bits for the starting lane and the second result's high three bits for the type index. This avoids correlated low-bit choices excluding fast triangles from one horizontal direction. A host check verifies the nonzero cycle and that both horizontal directions remain reachable. Determinism enables replayable tests.

A slot with a nonzero burst timer is reserved even though its active flag is clear.
The total of live enemies and bursts must remain below the validated display cap
before spawning. This may defer a due spawn for up to the burst's 18 updates;
movement, attacks, cooldowns, and the surviving enemies continue normally.

Do not place two enemies in the same lane in the baseline. For each attempt, choose a starting lane and examine at most eight lanes cyclically. Reject occupied lanes and arrangements forbidden by the validated renderer. If none are permitted, defer the spawn two updates; do not add a hidden enemy or retry indefinitely. A successful spawn reloads the level's spawn interval. Track actual encounter density in playtests so scheduling restrictions do not silently erase the intended difficulty increase.

Level 4's spawn table chooses triangles 3/8, fast triangles 2/8, diamonds
1/8, squares 1/8, and armor 1/8. Each eight-entry row is in `config/levels.json`.
All square variants and hexagons share the 72-update spacing timer. Wave 1 allows one
bomb-only enemy; from wave 2, two can coexist, reserving half the four-slot pool
for beam targets. The gate accepts a bomb-only enemy only when twice the current bomb-only
count is below the active cap and the spacing timer is zero. A rejected selection falls
back to a standard triangle. This makes actual type frequencies conditional on
the current population and preserves a usable two-bomb window for armor.
Later density changes must revisit arrival spacing rather than merely relaxing
this rule or relying on the old equal-speed assumptions.

With bomb radius 24, contact radius 8, and speed `56/256`, the old square has
about 73 updates between those boundaries, leaving only about 13 updates beyond
the former 60-update bomb cooldown. Do not reuse that late-level speed for two-hit armor
without verifying a useful first-hit reaction window and a second ready bomb.
Test combinations of normal/armored squares and diamonds against the cooldown;
diamonds also offer the beam as an alternative. Exact spacing and weights need
playtesting. These bounds assume usable bomb timing, not recovery from every
wasted bomb.

## Level data and increasing density

`config/levels.json` contains the quota rule (`start=8`, `step=4`, `cap=64`)
and spawn rows with `cap`, `spawn_interval`, and eight weighted `types`. The
separate `late_spawn` setting (`start_level=10`, `interval=4`) overrides the
minimum spawn delay. `late_mix` selects a ninth, type-only row from level 20;
`reinforced_diamond` raises diamond spawn HP to four and selects gold at level 25.
Quota is `min(8 + 4 * (decimal level - 1), 64)`, independent of the spawn row.
Generated spawn tables keep the tested type profiles and speeds. Current
progression settings prioritize a full arena and quick replacement of kills:

| Level | Cap | Kill quota | Minimum spawn delay (updates) | Weights: triangle / fast triangle / diamond / square / armor / fast square / hexagon / reinforced triangle |
| --- | ---: | ---: | ---: | --- |
| 1 | 2 | 8 | 24 | 6 / 0 / 0 / 2 / 0 / 0 / 0 / 0 |
| 2 | 4 | 12 | 12 | 5 / 2 / 0 / 1 / 0 / 0 / 0 / 0 |
| 3 | 4 | 16 | 12 | 4 / 2 / 0 / 1 / 1 / 0 / 0 / 0 |
| 4 | 4 | 20 | 10 | 3 / 2 / 1 / 1 / 1 / 0 / 0 / 0 |
| 5 | 4 | 24 | 8 | 3 / 2 / 1 / 1 / 1 / 0 / 0 / 0 |
| 6 | 4 | 28 | 8 | 2 / 2 / 2 / 0 / 1 / 1 / 0 / 0 |
| 7 | 4 | 32 | 8 | 2 / 2 / 2 / 1 / 0 / 1 / 0 / 0 |
| 8 | 4 | 36 | 8 | 2 / 2 / 2 / 0 / 0 / 1 / 1 / 0 |
| 9 | 4 | 40 | 8 | 2 / 2 / 2 / 0 / 0 / 1 / 1 / 0 |
| 10–14 | 4 | 44–60 (four more each level) | 4 | 2 / 2 / 2 / 0 / 0 / 1 / 1 / 0 |
| 15–19 | 4 | 64 | 4 | 2 / 2 / 2 / 0 / 0 / 1 / 1 / 0 |
| 20–24 | 4 | 64 | 4 | 1 / 2 / 2 / 0 / 0 / 1 / 1 / 1 |
| 25 onward | 4 | 64 | 4 | 1 / 2 / 2 / 0 / 0 / 1 / 1 / 1; diamonds spawn with four HP |

All weights are out of eight, before bomb-only spacing/cap restrictions. Enemy
speeds remain unchanged across these rows. Armor therefore retains about 205
updates between bomb range and contact, against a 30-update bomb cooldown.
The orange square has about 85 updates in bomb range and needs only one bomb.
Orange squares first appear in level 6, hexagons in level 8. These substitutions
retain the two bomb-only entries per eight-entry late-wave table; cap, quota,
spawn interval, and bomb cooldown are unchanged by the new variants. The level-20
row replaces one of the two standard triangle entries with a reinforced triangle.
The generator validates every cap as 1..4; `TrySpawn` independently enforces
`VALIDATED_ENEMY_CAP=4`. The loader uses those validated caps directly to save
ROM space for the late-level delay selection. After the completion clear, new
spawns use the next level's type mix and delay.

Store the displayed level as packed BCD `01..99`; increment with decimal mode
only for that operation, then clear it. After level 8, reuse its cap/delay row;
compare the displayed BCD level with the generated `LATE_SPAWN_LEVEL` to select
the shorter delay from level 10. Levels 8–9 keep eight updates between eligible
arrivals, allowing time to learn the hexagon before the pace changes. Quotas keep
growing through level 15 and then stay at 64. From `LATE_MIX_LEVEL=$20`, use type
offset 64 for the ninth row, without indexing beyond the eight cap/delay entries.
At spawn, compare diamond type and `REINFORCED_DIAMOND_LEVEL=$25` to choose
three or four HP. No health changes apply to other types.
Level 99 repeats indefinitely without wrapping or indexing beyond the tables.
The row's type offset is eight times its zero-based index, allowing a random
three-bit selection without a multiplication or indirect pointer at spawn time.

## Beam and enemy rendering

Use the ball for vertical/diagonal beams and the playfield for horizontal beams and bomb outlines, with player 0 for the turret and player 1 for enemies. Leave missiles disabled. Use the persistent level background except during cyan health-recovery flashes, yellow all-clear flashes, or higher-priority red player-hit feedback; use cycling rainbow colors for beam frames and fixed gold for ring frames. HUD graphics occupy a separate vertical region.

The beam uses eight fixed rays, one selected by the shot's latched direction.
Vertical and diagonal rays are one color clock wide; diagonal ball motion
advances at most one color clock each physical scanline. Horizontal rays retain
their two-scanline thickness and independently controlled playfield halves so a
right shot cannot create a left copy. Both kernels repeat turret/enemy graphics
across two scanlines per logical row. Each new shot selects the next bright hue
and starts brightness at 15; following updates count down through 1, then hide
the pattern. Holding or releasing the stick does not change that countdown.
Keep the shot's hue and direction fixed until another rearmed shot replaces it.
The [kernel notes](KERNEL_TIMING.md#effect-scheduling) document the shot-driven
decay and the legacy display ROM's release-driven version.
Set the color before the arena and keep it fixed across all rows; there is no
spatial gradient or separate glow layer.

Keep the turret visible every frame. Draw a visible beam fade on both frame phases normally. During a bomb, odd frames draw the ring and even frames draw the beam, giving each effect about 30 appearances per second without adding omissions to enemy graphics. Ring colors stay gold on both physical scanlines. Shot events, damage, and beam audio remain independent of this display phase. Use no transparency or trails.

Generate four ring sizes in the same radial geometry as the lanes, initially radii 6, 12, 18, and 24. Each lasts four updates, ensuring two visible ring frames regardless of the firing phase. The final outline marks the bomb's maximum radius. Treat the 16-update animation as feedback for immediate damage, not a persisting blast. Validate both beam/ring phases, neutral-stick bombs, every stage, and target visibility during the largest ring.

The generator encodes six playfield planes per pattern; ball-ray patterns have blank playfield data. The current geometry keeps left PF0 and right PF2 at zero, allowing four timed stream loads in the playfield kernel. Horizontal rays, neutral, and four rings share 14 unique 80-byte streams. Two additional packed motion streams serve all four diagonals; vertical rays reuse the zero stream. Pack three streams per page. Keep indexed streams within pages where the kernel assumes fixed load timing, or explicitly account for page crossings. Expanding the geometry into the constant-zero outer planes requires revising the playfield kernel.

The ball kernel strobes HMOVE at cycle 3 of every arena scanline. Clear all object motion registers in the separator so the turret and enemy stay fixed; write the ball's next motion at least 24 cycles after HMOVE. Store both physical lines' motion nibbles in one byte per logical row. Enable the ball only between the ray's generated row bounds, and disable it before the next HUD. The ball shares the playfield's color register, preserving the beam palette without changing sprite colors.

Each scanline still has its own write deadlines in a two-line kernel. Before accepting it, produce an instruction-cycle schedule covering both playfield halves, both player graphics, loop control, and horizontal positioning. No particular register schedule is considered proven by this specification.

### Initial two-enemy display

For the first kernel, position one enemy or burst graphic during blanking and draw it for the frame. When two objects are present, alternate them; when one is present, draw it every frame. Choose by greatest draw age with a stable slot-index tie-break so spawning/freeing slots cannot starve an enemy. Kills retain their draw age when switching to a burst. This avoids mid-arena repositioning in the first implementation.

At two enemies this targets one omitted frame between appearances, approximately 30 appearances per second per enemy. It must pass television readability testing; if it is too faint, improve reuse at separated heights before calling the baseline complete. Use software combat state even on omitted frames. Never let alternate-frame drawing cause alternate-frame damage.

### Four-enemy display

Gameplay uses fixed slot phases `(0,2)` and `(1,3)`. If one phase is empty,
draw the populated phase every frame. Sort a pair by Y, then switch Player 1's
sprite pointer and color after the upper sprite's eight-row window. During the
blank gap, move P1 by up to seven color clocks per logical row using HMOVE.
Player graphics are written once per logical row and retained on its second
scanline. Player 0 remains the turret. Both playfield and thin-beam kernels
retain their attack graphics while reusing P1. See [the cycle schedules](KERNEL_TIMING.md).

The spawner checks safety before admitting a paired enemy. With a cap of at
least three, even slots exclude E/W; odd slots admit new E/W entries only for
fast triangles. Vertical pairs occupy opposite halves. Generated type-pair
bounds use exact fixed-point movement, including diamond acceleration, to keep
one enemy at radius 24 or greater until the other reaches contact plus its full
18-update burst allowance. Bounds use both fractional endpoints. A horizontal
partner must be near enough to finish before its new vertical partner passes
radius 36; there is no far-horizontal placement case. This also handles slower
horizontal enemies in level 1. A burst partner defers placement.
Rejected arrangements retry after two updates. Killing early shortens existence
or freezes a sprite farther from the center, preserving the separation guarantee.

For every permitted lane/radius combination, the blank gap must fit all horizontal
movement, including opposing immunity offsets. The worst accepted near pair has
four blank logical rows. The tests reconstruct retained graphics, colors, and
HMOVE displacement, and require each live enemy/burst to appear at least every
other frame. Invalid debugger pairs set `FramePhase` bit 7 and safely omit the
second sprite; natural spawning must never reach that fallback. Bits 1–3 encode
the lower draw's slot plus one (zero for none); bit 0 remains the effect phase.

Four enemies can be admitted from level 2. Tests cover 625 four-target type
combinations under simultaneous beam/bomb use, both draw phases, horizontal
partners through death bursts, and natural spawning with no excess omissions.
Current headless Stella captures include four-target beam/ring/feedback scenes.
Live flicker/readability still needs playtesting; screenshots cannot certify it.
The normal X11 debugger-state pass remains available locally.

## HUD and sound

Display four score digits and five health marks above `LV01`, the current level.
The right half of the status row stays blank during play; numeric kills remaining
and bomb readiness are not displayed. All upper-HUD graphics are white. The title
uses `FIRE` in place of the level label. Game over retains the final score and
`LV` number and draws `OVER` on the right. Results reset only when a fresh fire
or RESET press starts a new run; held fire cannot skip the results.
A thin green progress bar fills left to right in eight steps below the arena;
a dim gray rail marks its full extent. Its fill is
`floor(8 * max(0, quota - remaining) / quota)`. The internal remaining count includes
future spawns and decreases only on kills. Advancement resets the fill for the next wave. Title/game-over
hide both the rail and fill; starting or restarting makes the bar visible.
This adds no pause or change to spawning.
Keep text compact; there are no menus, upgrade screens, or run statistics.
Health marks disappear as HP falls and return when a score bonus restores HP; the bomb retains its 30-update recharge.

Use two sound channels: one short beam-shot cue and one prioritized event cue
with a low-priority approach warning when idle.
Trigger the beam envelope once per shot, never continuously while held; stick
release does not need to cut off the short shot sound. Clear it on reset or
leaving play. Channel 1 priority, highest first, is game over, hexagon retaliation, player damage,
all-clear (full-health bonus or wave completion), health recovery, enemy destruction, nonlethal hit, ineffective attack, then bomb. Outcomes replace
the bomb sound when it hits a target, so rejection and successful damage remain
audible. A request of equal or higher priority restarts/replaces the current cue;
lower-priority requests are discarded without being queued. Resolve all slots
before selecting the cue, making priority independent of slot order. Multiple
same-update kills or contacts coalesce into one sound.

`config/audio.json` defines ascending-priority event IDs and envelope segments
`[updates, AUDC, AUDF, AUDV]`. Generated ROM tables use one sample index per
update and share identical register samples to save space. Each unique sample
uses two bytes: frequency, plus volume in the high nibble and waveform in the
low nibble. Playback unpacks the nibbles before writing the TIA registers. Bomb,
rejection, nonlethal hit, destruction, healing, clear, player damage, hexagon retaliation,
and game-over envelopes last 6, 8, 8, 12, 32, 32, 12, 12, and 36 updates respectively.
The nonlethal hit uses noise throughout, with a fixed frequency divider, a
sharp initial attack, and falling volume to suggest damage without a ricochet-like pitch slide;
the hexagon cue alternates buzzy pitches to distinguish it from ordinary damage.
Both are attack events: holds and fades cannot repeat them. A fresh matching
beam may restart the hexagon cue; a simultaneous lethal bomb prevents it.
The beam's existing five-update envelope remains independent. After the last
event sample, the next update can resume the approach warning or silence the
event channel if no eligible target remains. New-run initialization
clears the event ID, timer, and request; weapon cleanup on game over leaves its
four-note descending cue running. No cue repeats from a held input, a rejected
cooldown press, a cosmetic animation, or continued game-over state.
When no event envelope is playing or requested, scan all four slots
for the nearest active fast magenta triangle with integer radius at most 48.
Output the warning only in `PLAY`.
Use `depth = 48 - radius_hi`: waveform 4, frequency divider `4 + depth // 2`,
and volume `2 + depth // 8`. This gives a falling whistle that becomes louder
on approach. Values are generated from `config/audio.json`'s `fast_approach`
settings and checked against the TIA register ranges. Other types and inactive
bursts never trigger the warning. All combat cues preempt it; the beam's voice
remains independent. Resume at current proximity, without queuing or replaying
a warning envelope. Contact/removal and non-play modes stop the warning.

The scan uses only `Temp`, after spawning and quota checks finish; no persistent
RAM or per-enemy timer is added. The integer-radius buckets also make the cue
stable between fractional movement steps. When several magenta triangles are
present, one voice follows the closest rather than combining multiple whistles.

Tune timbre on hardware; music remains outside scope.

## RAM allocation

The current map uses the full available address range, with explicit guard and
stack space. Generate symbols and fail the build on overlap. Level state reuses
the diagnostic layout byte and the final two general reserves; future density
work must revise allocations or lifetimes before adding persistent state.

| Address range | Bytes | Allocation |
| --- | ---: | --- |
| `$80–$9F` | 32 | Four enemy slots in seven arrays; four shared secondary-draw bytes |
| `$A0–$AF` | 16 | BCD level number (diagnostic layout ID), frame counter, bomb count, mode, HP, two score bytes, spawn/break timer, square timer, RNG, active count, cap, movement enable, spawn interval, beam palette index, beam rearm latch |
| `$B0–$B7` | 8 | Direction, last direction, previous button/reset bits, beam enable, bomb cooldown, bomb-animation timer, bomb event, frame phase |
| `$B8–$BF` | 8 | Two HUD health masks, beam-shot timer, player-hit timer, event sound ID/timer/request, remaining kill quota |
| `$C0–$D7` | 24 | Renderer pointers, row bytes, draw/HUD state, and level type-table offset |
| `$D8–$E7` | 16 | Ten HUD score row bytes, four status-pointer bytes, reuse split row, general temporary; logic scratch aliases the HUD storage during overscan |
| `$E8–$EF` | 8 | Unallocated margin; guard pattern in debug builds |
| `$F0–$FF` | 16 | Stack reservation |
| Total | 128 | Includes stack and margin |

The 24 renderer bytes currently hold four two-byte playfield pointers, a two-byte sprite pointer, selected slot, HUD color, arena color, display-pattern ID, four beam visual bytes (fade timer, frozen hue, draw direction, draw color), a two-byte ball-motion pointer, two ball row bounds, a kernel selector, and the level type-table offset. The four former age bytes at `$98–$9B` hold the second draw descriptor; `$E6` holds the split row. Render selection finishes before HUD preparation overwrites its scratch. Scratch can be reused only across nonoverlapping lifetimes; record clobbered registers and scratch in each routine's header. ROM switching does not preserve a second copy of RAM.

During play and game over, the two HUD status pointers select ROM glyphs for the level's tens
and ones digits. After the top score row finishes, `PrepareProgress` reuses the
five right-score bytes as `HudProgress`, holding five playfield masks. A fixed
seven-line blank gap preserves the established HUD/arena positions. Status rows
follow at visible lines 19–28. The status scanline combines level digits through
`Temp` and draws either blank rows or `OVER` on the right. Only the title uses
the `FIRE` text pointers. X selects rows 0–4 (blank) or 5–9 (`OVER`) from two
page-safe ten-byte tables; it advances once per doubled font row, using no RAM.
Both level loading and progress preparation call `CalculateQuota`, preserving
X/Y and scratch. It caps at BCD `$15` before converting levels 10–14 to binary,
then uses two shifts and an offset for the four-per-level rule. Generation
rejects settings outside that compact routine's supported range. During progress
preparation, `ProgressQuota` temporarily uses the last right-score byte; the
final progress masks overwrite it after division. Three binary division steps
derive progress from this quota; values above quota clamp to empty. Bank 1 draws
the rail/fill on visible lines 190/191, after the arena. Footer entry clears both
sprites and the ball; outside play it clears all playfield registers for both
footer lines. The arena starts at visible line 30 (frame line 70).
Font tables pad only when an indexed read would cross a page. No new HUD RAM is allocated.
FIRE pointer high bytes share one constant; an assembler assertion requires
both text fragments to remain on the same page.

The generator shares identical subsequences and overlapping ends of renderer
setup, health, and progress tables: 296 logical lookup bytes occupy 254 ROM bytes.
Each original label aliases its contiguous slice, so the 6502 performs ordinary
indexed reads with no unpacking. Page-safe raster streams, sprite windows, and
fonts retain their separate placement constraints.

The game commits `PreviousButtons` before render preparation overwrites the sampled-input scratch with HUD rows. Movement/spawn scratch is also dead by then. Persistent health, score, timers, input history, enemy positions and beam state never alias those HUD buffers.

Initialize the stack at `$FF` and keep peak stack consumption within 16 bytes, including nested subroutines and any explicit pushes. Verify the high-water mark in the busiest frame. Increasing storage beyond four slots requires a revised map; it is not enabled by changing only a level row.

## ROM banks and module boundaries

F8 selects its lower and upper 4 KiB banks through cartridge hotspots `$1FF8` and `$1FF9`; the game can address their `$FFF8`/`$FFF9` mirrors. Stella's [F8 mapper implementation](https://github.com/stella-emu/stella/blob/master/src/emucore/CartF8.cxx) provides a reference for these selections.

| Bank | Contents |
| --- | --- |
| 0 | Reset/init, gameplay, audio, display/HUD preparation, pointer/type tables, HUD kernel and fonts |
| 1 | Frame synchronization, arena kernels, beam/ring streams, sprite atlas, reuse-motion tables |

Place matching bank-switch trampolines at `$FF80–$FFA9` in both banks, reserve `$FFF8–$FFF9` as hotspots, and put matching vectors at `$FFFA–$FFFF`. Both reset vectors enter a common stub that explicitly selects bank 0, so startup does not depend on the initial bank.

The seven stubs occupy `$FF80–$FFA9`. The playable ROM uses `$FFAA–$FFDB`
for the 50-byte level-ones font, `$FFDC–$FFED` for two nine-byte progress
tables, and `$FFEE–$FFF7` for ten digit offsets. These 78 bytes are identical in both bank tails, page-safe, and below
the hotspots. Structural checks verify their locations and exact generated data.

When both sound request and event countdown are zero, overscan uses `Temp`
after spawning to cache the nearest warning-eligible fast triangle. The beam
visual update and sync preserve it; the first VBLANK operation consumes it for
sound output before coordinate/render work reuses scratch. No persistent RAM
is added for the new enemies or sound scheduling.

Cross-bank transitions use explicit jump stubs whose next instructions are
identical at the same address in both banks. Do not use a normal cross-bank
`JSR`/`RTS` convention. Bank 1 starts synchronization and its blanking timer, then
jumps through `PrepareEntry` at `$FF92` to bank 0. Bank 0 prepares the HUD,
pointers, colors, and object positions, then jumps through `RenderEntry` at
`$FF98` back to bank 1 at `PrepareDone`. HUD drawing enters bank 0 through `HudEntry`
at `$FF9E`; separator line 29 returns through `ArenaEntry` at `$FFA4` to bank 1
(diagnostic: separator line 24). Overscan switches back
to bank 0. Moving the HUD frees space for the reuse kernel and motion tables. Pointer tables live with the code
that reads them and point into the bank containing the visible graphic data.

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
| `src/levels.asm` | Table loading and arena/effect reset for each level |
| `src/audio.asm` | Sound state and event priorities |
| `config/audio.json` | Prioritized event envelopes and TIA register segments |
| `src/render.asm`, `src/hud.asm`, `src/frame.asm`, `src/kernel.asm` | Bank-0 display preparation and positioning; bank-1 synchronization and timed screen output |
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
| Input | Each of eight center-to-direction flicks fires once. Holds and direct direction changes do not repeat. Actual center rearms; conflicting inputs do not. Startup/reset/transition holds cannot produce an accidental shot. Validate deliberate diagonal flicks on a real stick. |
| Shot fade | A shot starts bright and fades through the 15-update countdown while held or released. Its direction/hue stay fixed; a new rearmed shot replaces the fade. Reset clears it. Bomb animation and enemy scheduling continue. |
| Button edges | Held fire causes one bomb; cooldown presses do not queue; activation at `t+29` fails and a fresh press at `t+30` succeeds. Start/reset/transition inputs do not create accidental bombs. |
| Weapon/type matrix | Both triangle types take beam damage only; all three square types and hexagons take bomb damage only; diamonds accept either. Immune hits never reduce enemy health or award score. |
| Hexagon retaliation | Fresh matching beam costs one player HP; hold/fade/misses do not. A simultaneous in-range bomb kills first and prevents retaliation/contact. Beam retaliation plus surviving contact can cost two HP. Check every lane/slot, fatal damage, healing/clear priority, and busy updates with movement and due spawns. |
| Beam | Matching-lane triangles die on the shot event; wrong lanes survive; squares do not block the ray. Diamonds lose one health per shot, including ring frames; holding or entering the cosmetic fade cannot cause extra damage. Beam pattern crosses every variant's legal positions. |
| Bomb boundary | With zero movement, an eligible target at `24.00` takes one damage and at `24.01` takes none; square fill agrees. Triangles survive at either radius. Armor survives one bomb and dies to a second; the ring cannot hit again. |
| Resolution order | Same-frame beam+bomb can damage a diamond twice if eligible, but grants one kill per target. Lethal attacks prevent contact; a nonlethal hit does not. Multiple surviving contacts reduce player HP without underflow. |
| Contact damage | Small magenta triangles deal two player damage; other enemies deal one. Enemy health and contact damage remain independent. Test one HP, two HP, simultaneous contacts, and a lethal attack on the contact update. |
| Attack feedback | In-range immune hits flash yellow/orange and shake once per attack; real nonlethal hits flash white; kills show the burst. No immunity cue for misses, rejected bombs, holds, or cosmetic fades. Both draw phases show every stage. Actual damage wins over simultaneous immunity feedback. |
| Audio | Each accepted event produces the full configured TIA envelope, then silence; priority is independent of slot order. Beam remains independent of event cues. Higher/equal priority interrupts, lower priority never queues, multi-kills coalesce, game over finishes once, and reset/restart immediately clears both voices. |
| Player feedback | Damage starts a 12-update red background fade across HUD and arena, including fatal hits. Further hits still damage and restart it; reset clears it. Beam/ring/sprite output and frame timing remain correct throughout. |
| Level feedback | The next wave selects a persistent dark background after the clear celebration, preserving foreground colors. Check all eight colors with every enemy type and both effects, persistence, red-damage priority/restoration, game-over retention, restart/reset, debugger loads, and palette cycling across BCD levels 01–99. |
| Score milestone | Every crossed 1,000 points restores one HP below full health or clears surviving enemies at full health after nonfatal combat. Check exact/overshot thresholds, every cleared type, wave credit without points, old bursts, spawn deferral/resumption, multi-kills, simultaneous contacts, death priority, saturation, restart, distinct cyan/yellow flash and sound envelopes, and cue duration/priority. |
| Destruction burst | A scored kill draws all three stages at its final position, awards score once, and expires after 18 updates. Two bursts or a burst plus a live enemy each appear at least every other frame. A reserved burst slot cannot be reused early; reset clears all effects. |
| Movement | Fractional stepping, subtraction near zero, and every lane/radius mapping are correct. Diamond speed increases at each inward distance band and stays below the magenta triangle. No variant or burst leaves the arena. |
| Spawn limits | Never exceed active cap, duplicate a baseline lane, overwrite a live slot, or spin on failed placement. All squares and hexagons share the 72-update spacing and cap of one in wave 1, two thereafter. Fast squares enter at level 6 and hexagons at level 8 without changing spawn intervals. |
| Fairness | At each speed profile, measure the exact updates from bomb-range entry to contact. Armored squares allow two bombs plus reaction time. Mixed-speed arrivals retain usable bomb windows. |
| Progression | Quota crossing holds the full green bar, clears survivors without points, and plays 32 updates of yellow flashes and the clear sound before loading the next level. Nonfatal damage feedback finishes first; held inputs are consumed and HP/score are preserved. Multi-kills saturate the old quota. Death overrides advancement. Level 99 and score 9999 saturate safely. |
| Wave-progress HUD | Level digits and eight-step progress render at fixed scanline deadlines without affecting score, health, or arena. The lower-right HUD stays blank at every cooldown/quota value. Counts above quota show an empty bar. |
| Display | Turret stays steady; beam and bomb ring alternate without dropping shot events or their damage. Every active enemy appears at least every other frame. Test every ring stage on both press phases, neutral-stick bombs, same-height pairs, and center convergence. |
| Memory and ROM | Both possible startup banks reset correctly; bank stubs match; stack remains in its reservation; guard bytes remain intact; each bank fits. |
| Timing | All states use the intended frame/scanline counts. Worst-case bomb kills, score carry, failed spawns, transitions, and display schedules stay within measured budgets. |

Use small deterministic fixtures for logic failures, then a longer scripted stress run with repeated restarts, level transitions, and dense layouts. A hardware pass must cover a real joystick's diagonals, bomb responsiveness, flicker/readability on a television, and sound. Record emulator timing evidence separately from hardware observations.

## Implementation milestones

| Milestone | Deliverable | Exit criterion |
| --- | --- | --- |
| 0 | Pinned build, F8 startup/bank stubs, stable blank ROM | Correct image/vectors and stable frame from either initial bank |
| 1 | Turret, eight color-cycling beam patterns, one enemy graphic, expanding bomb outline | Cycle schedule and Stella measurements prove the core display and both effect phases |
| 2 | Input, two-enemy pool/display, movement, combat, HP, score, restart | Rule fixtures pass in the cartridge; two-enemy overlap remains readable |
| 3a | One beam shot per joystick flick, revised vulnerabilities, fast triangle, armored square, accelerating blue diamond | Shot input/fade, weapon matrix, movement, readability, and bomb fairness pass at the two-enemy cap |
| 3b | Level table, transitions, and combat cues implemented; balance playtest remains | Opening levels introduce variants gradually and are playable and fair; baseline hardware pass |
| 4 | Vertical sprite reuse and three-enemy scheduling | Three-enemy stress cases meet timing and omission limits; promote a later level to the validated cap |
| 5 | Four-enemy scheduling, wave-clear celebrations, and bottom progress bar implemented; balance playtest remains | Four-target CPU/geometry tests and current Stella stills pass; playtest sustained pressure and live readability |

Implement milestones in order. If milestone 1 fails, revise the kernel while keeping eight-way beam and button bomb behavior. If higher densities fail, adjust scheduling and spawn arrangements or keep the lower validated cap; do not restore removed visual effects to compensate. Charge bombs, trails, reflectors, shifters, XP, and upgrades remain outside this implementation.
