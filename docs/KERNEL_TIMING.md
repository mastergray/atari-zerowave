# Prototype kernel timing

This records the playable three-enemy variant prototype with flick-to-fire beams, levels, and
the separate static display-test ROM. CPU/register measurements come from the assembled F8 cartridges and the py65
harness. The new density kernel also has 22 inspected Stella 6.0.2 captures taken with
SDL dummy video. Television readability and the full X11 debugger transcript
pass remain separate from those still-image checks.

## Frame layout

| Region | Scanlines | Work |
| --- | ---: | --- |
| VSYNC | 3 | Vertical synchronization |
| VBLANK | 37 | HUD preparation, beam/ring pointers, enemy selection and positioning |
| HUD | 24 | Four score digits, five health marks, FIRE/LV 01..99/OVER and BOMB |
| Separator | 8 | Clear HUD graphics; prepare arena |
| Arena | 160 | 80 logical rows, each drawn twice |
| Overscan | 30 | Input, movement, attacks, contacts, spawning, beam/fade and sound |
| Total | 262 | 19,912 CPU cycles at 76 cycles per line |

Stella's `_cycleslo` increases by 19,912 per frame across direction changes,
all animation frames, combat, spawning, start/restart, level transitions, and cooldown waits.
The host harness checks 262-line frames through a scripted survival run and
boundary fixtures. The diagnostic ROM also exercises all eleven static layouts.
Both possible F8 startup banks enter the same reset path.

The RIOT timer starts with a partial first interval: its first decrement occurs
after one CPU cycle. With this entry path, `TIM64T=43` during blanking and `34`
during overscan leave the polling loop in the intended final WSYNC window.
These constants depend on instruction placement and entry timing. A full-interval
timer model incorrectly accepted a 260-line earlier build; the harness now
models the behavior in [Stella's RIOT implementation](https://github.com/stella-emu/stella/blob/6.0.2/src/emucore/M6532.cxx).

## Playable HUD

HUD lines 0–1 and 12–13 are blank. Lines 2–11 display four score digits on the
left and health marks on the right; lines 14–23 display FIRE, LV 01..99 or OVER on
the left and the colored BOMB label on the right. Each font row lasts two lines.
The diagnostic ROM retains its TEST/BOMB header.

| Region | Left PF1 / PF2 completion | Right PF1 / PF2 completion | Color |
| --- | --- | --- | --- |
| Score and health | Cycles 12 / 19 | Cycles 43 / 53 | White at cycle 5 |
| Title/game-over and bomb | Cycles 13 / 21 | Cycles 40 / 55 | White at 5, bomb-ready color at 48 |
| Level and bomb | Cycles 12 / 31 | Cycles 40 / 55 | White at 5, bomb-ready color at 48 |

PF0 remains clear. Render preparation converts packed BCD into ten score-row
bytes and selects two status pointers. These occupy `$D8–$E5` only during
display; input and spawn scratch can reuse them during overscan after the last
visible line. The input history is committed before HUD preparation overwrites
the samples. Health masks use two previously reserved audio bytes.

For play and level breaks, the status pointers select the level's tens and ones
glyphs in two page-safe 50-byte ROM tables. A separate status scanline combines
these through `Temp`, whose render-selection lifetime has finished, and draws
the fixed `LV` label. PF2 completes at cycle 31, before its left-half display
begins. Both digits remain visible every frame; the HUD still takes 24 lines.

## Arena scanline schedule

The gameplay kernel uses these instruction-completion cycles after WSYNC:

| Register | First physical line | Second physical line |
| --- | ---: | ---: |
| HMOVE | 3 | No strobe |
| PF0 left | 6 | 3 |
| PF1 left | 14 | 11 |
| GRP1 | 22 | Retained |
| PF2 left | 30 | 19 |
| GRP0 | 37 | Retained |
| PF0 right | 45 | 29 |
| PF1 right | 53 | 40 |
| PF2 right | 56 | 50–53, according to reuse path |

Only the first line writes player graphics; TIA holds those values on the second.
The freed cycles switch the second sprite's pointer/color and update its horizontal
motion during blank rows. The first line prefetches the motion byte; the second
line applies it and looks up the remaining displacement. The tightest paths reach
WSYNC at cycle 75. Two page-aligned 256-byte tables avoid variable indexed-load
costs. Right-half PF writes stay late enough to preserve the left half's pixels.
The row-zero exit is separate so loop control cannot spill into an extra scanline.

The diagnostic kernel retains its original per-line schedule: PF0/1 at 3/11,
GRP1 at 19, PF2 at 27, GRP0 at 34, then right PF0/1/2 at 42/50/53. It does not
reuse sprites within a frame. Both ROMs retain the 160-line arena.

COLUPF is set during the separator and remains fixed throughout the entire arena.
The whole beam changes color together between frames, with no scanline gradient
or separate glow layer. Tests reject any color write during the arena and check
the upright player graphics on all 160 lines. Horizontal rays remain two
physical lines tall. Vertical and diagonal rays use the separate ball kernel
below to reach one-color-clock width.

Generated rays occupy playfield columns 9 through 31; the rings fit inside that
span. Left PF0 and right PF2
are therefore constant zero, allowing four varying streams instead of six.
Deduplication reduces the horizontal directions, neutral, and four rings to 14
shared 80-byte streams (the horizontal beams alone need five). Two additional
motion streams serve all diagonal rays. Packing three streams per
256-byte page saves alignment space without introducing page-crossing loads.
If the arena geometry expands into those outer columns, the
generator fails; changing the timed kernel is required.

Enemy GRP1 is ready before the leftmost legal sprite pixel. The turret stays at
horizontal left edge 76 and logical top row 38. Initial sprite positioning runs in blanking, followed by HMOVE. The playable
kernel then repositions P1 between a pair of separated sprite windows. `PositionPlayer` deliberately aligns its subtract/
branch loop within one page and uses a five-cycle absolute indexed HMP store.
Changing either changes horizontal placement; Stella inspection confirmed both
players at the intended positions after correcting these details.

### Thin-beam scanlines

The ball draws N, NE, SE, S, SW, and NW at one color clock wide. Each diagonal
moves by zero or one color clock per physical scanline, keeping the ray connected.
Its initial X and visible row bounds come from the same lane geometry as enemy
positions. Opposite diagonals share slopes; each 80-byte motion stream packs
the moves for both physical scanlines into its high and low nibbles.

| Register | First line completion cycle | Second line completion cycle |
| --- | ---: | ---: |
| HMOVE | 3 | 3 |
| ENABL | 14, 19, or 20 according to row bounds | Held from first line |
| GRP1 | 22, 27, or 28 | Retained |
| GRP0 | 29, 34, or 35 | Retained |
| HMBL | 37, 42, or 43 | 27 |

The second line also performs sprite reuse work within its 76-cycle budget. The final line disables ENABL before entering overscan. The playfield
stays blank throughout this kernel. HMCLR in the separator stops player motion
before the repeated HMOVE strobes. Ball-motion writes occur more than 24 cycles
after HMOVE, following the timing requirement in Atari's
[Stella Programmer's Guide](https://www.atariage.com/2600/programming/2600_101/docs/stella.html).
Early HMOVE also blanks the leftmost eight color clocks; these lie in the empty
black arena margin. Gameplay writes each sprite row once and holds it for the second physical line.
HMP1 clears on the first line after HMOVE so P1 moves only once per logical row;
the second line prepares its next step. The diagnostic kernel still writes both
sprite rows on each line and writes its second HMBL at cycle 34.

## Effect scheduling

`FrameCounter & 1` selects the display phase. Normally both phases show the
selected shot fade (legacy held beam in the diagnostic ROM), otherwise blank. During bombs, odd frames show a ring and
even frames show the beam. Pattern IDs 0–7 are directions, 8 is blank, and 9–12 are
the four rings. `DisplayPattern` records the prepared frame for debugger checks.

The ring radii are 6, 12, 18, and 24 in the shared game geometry. Each stage lasts
four updates, giving two visible appearances per stage regardless of the press
phase. The animation lasts 16 updates. Both physical ring lines keep the same
gold color; the arena background is normally black, with a red fade on player damage. The outline replaces
the previous size, so no filled disk or trail accumulates.

The playable ROM emits one `BeamEvent` when the stick moves from center into a
valid direction. `BeamArmed` is cleared by the shot and rearmed only when all
four physical direction bits are released. Holding, directly changing direction,
or supplying conflicting inputs cannot create repeat shots. Input history and
the rearm latch are maintained across title, reset, and game over.

A shot selects the next hue from `beam_colors`, latches its direction, and starts
brightness at 15. Subsequent updates count through 1, then hide it, whether the
stick is held or released. TIA ignores bit 0, so the effective luminances are
`14,14,12,12,10,10,8,8,6,6,4,4,2,2,0`. The final zero-luminance hue may still be
visible; the next update removes the pattern. The timer advances on ring frames.
A fresh rearmed shot replaces any remaining fade. No phosphor setting is needed.

This decay comes from Dennis Debro's
[Laser Blast disassembly](https://github.com/DNSDEBRO/Disassemblies/blob/a74a6312bac5ae28eacb423303bf55db30ad33d1/Atari2600/Laser%20Blast/laser_blast.asm):
`CheckForActionButton` initializes the player's laser to `COLOR_LEADSHIP + 15`,
the overscan update decrements its low nibble once per frame, and the kernel
hides it at zero. Our current adaptation starts decay on the joystick shot.
The diagnostic ROM retains the earlier held color cycle and release-driven fade.

Four renderer bytes store `BeamFadeTimer`, `BeamFadeHue`, `BeamDrawDirection`,
and `BeamDrawColor`. `BeamEvent` aliases `BeamEnabled` in gameplay and lasts one
update only; combat uses it and `LastDirection`, never the cosmetic fade.
The five-update shot sound has its own timer in a former audio reserve byte.

`BombEvent` also pulses once for immediate damage, independent of ring display
phases. Bomb sound lasts six updates, its ring 16, and its cooldown 30. A bomb
damages squares and diamonds, while triangles show vivid yellow/orange immunity feedback.
The beam damages triangles and diamonds; squares show the same immunity feedback. A combined
hit on a diamond can deal two damage but awards score only once on death.
Bomb damage and square fill both compare the full 8.8 radius: `24.00` is inside,
`24.01` is outside.

The ring uses the playfield kernel and player graphics are written on both
phases. Fixed slot phases keep every live enemy/burst visible at least every other
frame, including a third target. No extra flicker phase is added for enemies.

Scored kills retain their last position for an 18-update sprite burst. The three
stages last six updates each: white flash, gold sparks, and dim red embers. The
active flag clears and score applies immediately. `EnemyVisual` holds the timer;
the renderer schedules a nonzero timer alongside live enemies using the same
slot-phase rule. Thus two bomb kills each receive three appearances per stage.
Timers advance in game over too; reset clears the entire slot pool.

`ScanEnemies` counts live enemies separately from drawable objects, using the
existing `Temp` scratch byte for the latter. Bursts reserve their old slots.
A due spawn waits if the combined enemy/burst count reaches the level's cap, keeping the
one-omitted-frame limit for survivors. No extra persistent RAM is allocated.

Live enemies reuse `EnemyVisual` for feedback: bit 7 marks a six-update white
successful hit. Immunity uses 18 updates split into three six-update stages,
with colors `$1E`, `$2E`, `$1E` and horizontal draw offsets -2, +2, 0 color clocks.
Each stage gives either sprite phase three appearances. The shake affects only
TIA positioning; cached coordinates and damage geometry remain unchanged.
The low seven bits hold the timer. On death it becomes the destruction timer;
no extra per-enemy storage is needed. `EnemyHealth` reuses the old unused phase array.
The damaged armored square uses the smaller normal square graphic, with its
own type/score retained. Range-fill selection remains independent of feedback.

Ten eight-row sprite windows share five pages, two shapes per page. Labels sit
at offsets 0 and 88; graphics at 80..87 and 168..175, sharing blank padding.
The pointer is `label + EnemyY + 6`, giving a top row of `EnemyY - 2`.
All 80 reads stay on-page for the legal positions and cannot reach another
shape. Standard enemy shapes retain their original four rows inside that window.

Display setup and HUD preparation now run in bank 0. After VSYNC, bank 1 starts
the blanking timer and jumps through `PrepareEntry` ($FF92) to bank 0; it returns
through `RenderEntry` ($FF98) at `PrepareDone`. Pointer/type tables live in bank 0,
the sprite atlas, raster streams, motion tables, and arena kernels live in bank 1.
HUD drawing/fonts now live in bank 0: `HudEntry` ($FF9E) switches there after
blanking, and `ArenaEntry` ($FFA4) switches back during the first separator line.
The seven bank stubs are byte-identical in both tails.

Player contact starts a 12-update background flash. `PlayerHitTimer` uses one
former audio reserve byte; it advances before combat and also during game over.
The shades `$48`, `$46`, `$44`, `$42` each last three updates, then return to black.
Render preparation writes COLUBK during blanking, before the HUD; neither the
frame setup nor the separator overwrites it in the playable ROM. All 192 visible
lines therefore share the same background color. HMCLR and ENABL still receive
zero in the separator. The diagnostic ROM retains its black background writes.
New contacts restart the timer without reducing further contact damage. Reset
clears it, while game-over weapon cleanup leaves the fatal-hit flash visible.

## Combat audio

`src/audio.asm` updates both TIA voices during overscan. Channel 0 retains the
five-update beam tone. Channel 1 plays generated per-update control, frequency,
and volume tables from `config/audio.json`. Empty bombs, rejection, nonlethal hits,
destruction, player hits, and game over last 6/8/6/12/12/36 updates respectively.
Game over has highest priority, followed by player hit, destruction, nonlethal
hit, rejection, and bomb. Requests are coalesced before playback; higher/equal
priority replaces a running envelope, while lower-priority events are discarded.

Event ID, remaining updates, and this-update request use three former reserve
bytes at `$BC–$BE`; `$BF` now holds the level kill quota. Sound timers never drive damage or
visuals. Fatal-hit cleanup stops the beam but lets the game-over tone finish;
reset/restart clears both voices. The separate display ROM keeps its original
audio behavior. Tests check exact TIA register envelopes, silence after expiry,
slot-order-independent priority, preemption/retriggering, coalesced kills,
rejected attacks, and game-over/reset behavior.

A separate Stella 6.0.2 capture through SDL's disk audio backend records all
seven cues from the playable ROM, using actual beam/bomb inputs or contact
fixtures. All seven produce nonzero PCM, stay below clipping, and return to
silence. `build/audio-captures/report.json` records the ROM hash and WAV paths;
the capture script and isolated settings are retained alongside it. This checks
emulated audio output, not the user's speaker routing or real Atari sound.

## Level progression

`LevelNumber` aliases diagnostic `LayoutId` at `$A0`, `KillsRemaining` uses `$BF`,
and the eight-entry type-row offset uses former render reserve `$D7`. The spawn
countdown doubles as the 60-update break timer. These lifetimes leave the guard
and stack untouched. The level number uses BCD, saturates at 99, and maps every
level above eight to the final table row.

Quota exhaustion prevents spawning in the same update, but all slots still
resolve damage/contact and receive score. Death wins over level completion.
Advancement waits for both live targets and destruction bursts to finish, then
shows the next level for 60 updates. Loading resets the arena and combat effects,
retains HP/score/RNG/input history, and consumes that update without spawning or
attacking. All rows retain the tested type speeds. Level 1 caps at two; later rows cap at
three and use shorter intervals (60 updates in level 2, down to 42 in level 7).

## Space and update budgets

| Resource | Current measurement |
| --- | --- |
| Bank 0 end / room before trampoline | `$FE72` / 270 bytes |
| Bank 1 end / room before trampoline | `$FF00` / 128 bytes |
| Cartridge | 8,192 bytes, identical bank tails and vectors |
| RAM | Fixed 128-byte map, including reserves and stack |
| Stack | Eight bytes observed; 16 reserved |
| Guard | Eight bytes at `$E8–$EF`, intact in tested runs |
| Update cost | 334–1,777 cycles from `GameFrame` to `LogicDone` |
| Render preparation done | 1,468–1,848 cycles from VSYNC line start |

The combat suite records 11,255 frame samples in `build/combat-timing.json`,
including a survival run of at least 1,400 frames across all five types, movement/attack/contact boundaries, scoring,
spawning, immunity/hit feedback, destruction bursts, HUD values, and restart.
A second natural run completes the first four levels with all variants seen and
no player damage. Fixtures check quotas, exact breaks, carry/saturation at levels
09/10/99, per-row spawning, input history, and death/reset priority.
Tests enforce the 2,000-cycle update and
2,400-cycle preparation limits. The static diagnostic build has 1,256 bytes free
in bank 0 and 896 in bank 1.

Four 64-byte magnitude tables live in bank 0. Cardinal/diagonal signs reconstruct
all eight lanes there; cached sprite coordinates cross into the render bank.
The four former EnemyAge bytes now hold the lower sprite pointer, remaining X
displacement, and color. `$E6` stores the reuse row. `FramePhase` bit 0 selects
the effect phase, bits 1–3 encode the lower slot plus one, and bit 7 flags an
invalid debugger pair. HUD scratch is generated only after render selection.

## Display limits and evidence

The turret uses player 0. Player 1 draws a vertically separated pair on one
phase and the remaining enemy on the other. Phases belong to slots `(0,2)` and
`(1,3)`, with an empty phase borrowing the populated phase. Four slots remain
allocated, but the gameplay cap is three.

The even pair uses upper/lower lanes; E/W remain available to the singleton.
The spawner checks an entire remaining approach, using generated bounds for all
25 type pairs and both fractional endpoints. One enemy must stay at radius 24
or greater until the other could reach contact plus 18 burst updates. This also
handles early kills, which freeze the sprite farther out and shorten its life.
Unsafe arrangements defer eight updates. One bomb-only target remains the limit.

At the tightest accepted diagonal separation, four logical rows are blank.
That fits three seven-clock moves plus pointer-switch overhead, including the
largest immunity-shake difference. Tests exhaust every legal lane/radius pair's
space requirement, reconstruct actual sprite rows and HMOVE positions, exercise
all beam/ring patterns on both paired phases, and check natural three-enemy
visibility through repeated center arrivals. Additional fixtures exercise all
125 three-target type combinations under simultaneous beam/bomb damage.
`build/density-timing.json` records another 3,815 frames, including the busy
three-target cases that reach the combined timing maxima above.

`make stella-check` runs both ROMs. The diagnostic pass records both phases of same-height, center-convergence, and
separated-height pairs. Its SELECT fixture injection temporarily drives only the
RIOT port-B SELECT bit; the ROM still performs its normal switch sampling and
edge detection. The command transcript documents that setup. Short log chunks
avoid Stella 6's corrupt session export after its prompt history wraps; they
are combined into `session.txt`. A shared lock serializes verification jobs,
because Stella 6 exports sessions into the user's home directory with names
that can collide within the same second. Each job uses its own XDG configuration
directory, so muting visual tests does not change normal Stella settings. Debugger `frame`
stops at VSYNC, so animation captures wait for a complete newly drawn frame.

The 56 diagnostic Stella snapshots cover both phases of all eight rays, neutral, every bomb
animation frame, target placement during the largest ring, and the complete
release fade. Pixel comparisons found left/right rays, neutral, and all eleven
ring captures identical to the previous release-fade build. Both phases of all
six thin directions match their generated paths: one color clock per scanline,
with sprite pixels preserved. The NW ray occupies 92 screenshot pixels, down
from 464, and retains one uniform hue during its fade. Cartridge tests also
check ball-motion timing, clearing player motion, release in all eight directions
and hues, re-aiming, reset, and fading during bombs with two enemies.
The playable pass adds 68 snapshots of natural spawns/movement, both phases of a
two-enemy scene, triangle kills, square immunity, bomb-radius boundaries,
game-over/restart, representative HUD values, and every burst stage alongside
a surviving enemy or a second burst. Additional captures show all variants,
a diamond defeated by three flicks, a held dark beam, yellow/orange immunity shakes,
white successful hits, armor loss/two-bomb kills, double contact damage, and
every red-flash stage through game over and reset.
Its debugger state confirms
score awards, event sound selection/countdown, and start/reset input handling. It uses explicit RAM fixtures only
for boundary cases, after first exercising natural spawning and movement.
The level pass adds 19 snapshots covering the last kill/burst, the upcoming-level
HUD, the exact break boundary, held/fresh controls, levels 04/09/10/99, final-row
reuse, fatal contacts, and reset to 01. Its states and captures are indexed by
`build/stella/latest-levels.json`.
The added density pass (`tools/verify_density_stella.py`) captures natural level-2
crowding, both paired phases, tight diagonal separation, beam/ring reuse,
immunity, and bursts. Its 22 snapshots are indexed by `latest-density.json` when
run successfully. X11 was unavailable in this session, so a delayed debugger
script with SDL dummy video produced the same 22 screenshots instead. These
were inspected for natural three-target visibility, both directions of P1 reuse,
beam/ring continuity, immunity offsets, bursts, and HUD placement. The capture
script, SDL input injector source, ROM, and images are retained under
`build/stella/headless-density-20261028-203725`; the index is
`build/stella/latest-headless-density.json`. This capture has no debugger
state/timing transcript; timing and state assertions above come from py65.
The normal X11 verification scripts remain available for a local full pass.
Real hardware flicker and audio remain untested. Four-enemy rendering requires
further measurements, as described in [the implementation specification](IMPLEMENTATION_SPEC.md).
