# Prototype kernel timing

This records the playable two-enemy combat prototype through milestone 2 and
the separate static display-test ROM. Measurements were taken from the assembled
F8 cartridges with the py65 harness and Stella 6.0.2. They do not certify
television readability or the future level and larger-enemy-count paths.

## Frame layout

| Region | Scanlines | Work |
| --- | ---: | --- |
| VSYNC | 3 | Vertical synchronization |
| VBLANK | 37 | HUD preparation, beam/ring pointers, enemy selection and positioning |
| HUD | 24 | Four score digits, five health marks, FIRE/PLAY/OVER and BOMB |
| Separator | 8 | Clear HUD graphics; prepare arena |
| Arena | 160 | 80 logical rows, each drawn twice |
| Overscan | 30 | Input, movement, attacks, contacts, spawning, beam/fade and sound |
| Total | 262 | 19,912 CPU cycles at 76 cycles per line |

Stella's `_cycleslo` increases by 19,912 per frame across direction changes,
all animation frames, combat, spawning, start/restart, and cooldown waits.
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
left and health marks on the right; lines 14–23 display FIRE, PLAY or OVER on
the left and the colored BOMB label on the right. Each font row lasts two lines.
The diagnostic ROM retains its TEST/BOMB header.

| Region | Left PF1 / PF2 completion | Right PF1 / PF2 completion | Color |
| --- | --- | --- | --- |
| Score and health | Cycles 12 / 19 | Cycles 43 / 53 | White at cycle 5 |
| Status and bomb | Cycles 13 / 21 | Cycles 40 / 55 | White at 5, bomb-ready color at 48 |

PF0 remains clear. Render preparation converts packed BCD into ten score-row
bytes and selects two status pointers. These occupy `$D8–$E5` only during
display; input and spawn scratch can reuse them during overscan after the last
visible line. The input history is committed before HUD preparation overwrites
the samples. Health masks use two previously reserved audio bytes.

## Arena scanline schedule

The following are CPU cycles at instruction completion, counted from WSYNC
release, for the playfield kernel (left/right rays, rings, and blank frames).
Both physical scanlines of each logical row use the same graphics-write schedule
and the same color.
The playfield is in normal, unreflected mode, with independent writes for its
left and right halves.

| Cycle | Register | Value |
| ---: | --- | --- |
| 3 | PF0 | Zero for left edge |
| 11 | PF1 | Left beam/ring stream |
| 19 | GRP1 | Selected enemy row |
| 27 | PF2 | Left beam/ring stream |
| 34 | GRP0 | Turret row |
| 42 | PF0 | Right beam/ring stream |
| 50 | PF1 | Right beam/ring stream |
| 53 | PF2 | Zero for right edge |

The first line then reaches WSYNC at cycle 56. The second line decrements Y,
branches, and reaches WSYNC by cycle 61 (62 if the branch crosses a page).
The last row enters overscan instead. X stays zero, allowing three-cycle STX
instructions for constant-zero PF writes. Reverse row indexing removes the
separate row-limit comparison. Playfield,
turret, and sprite data are stored in reverse row order to preserve their screen
positions. Indexed streams never cross a page during the kernel.

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
horizontal left edge 76 and logical top row 38. Sprite positioning runs entirely
in blanking, followed by HMOVE. `PositionPlayer` deliberately aligns its subtract/
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
| GRP1 | 22, 27, or 28 | 11 |
| GRP0 | 29, 34, or 35 | 18 |
| HMBL | 37, 42, or 43 | 34 |

The second line reaches WSYNC by cycle 43, including the loop branch's page
crossing. The final line disables ENABL before entering overscan. The playfield
stays blank throughout this kernel. HMCLR in the separator stops player motion
before the repeated HMOVE strobes. Ball-motion writes occur more than 24 cycles
after HMOVE, following the timing requirement in Atari's
[Stella Programmer's Guide](https://www.atariage.com/2600/programming/2600_101/docs/stella.html).
Early HMOVE also blanks the leftmost eight color clocks; these lie in the empty
black arena margin. Both sprites still update every physical line.

## Effect scheduling

`FrameCounter & 1` selects the display phase. Normally both phases show the
selected beam or its release afterglow, otherwise blank. During bombs, odd frames show a ring and
even frames show the beam. Pattern IDs 0–7 are directions, 8 is blank, and 9–12 are
the four rings. `DisplayPattern` records the prepared frame for debugger checks.

The ring radii are 6, 12, 18, and 24 in the shared game geometry. Each stage lasts
four updates, giving two visible appearances per stage regardless of the press
phase. The animation lasts 16 updates. Both physical ring lines keep the same
gold color; the arena background stays black. The outline replaces
the previous size, so no filled disk or trail accumulates.

While held, the entire beam cycles through eight colors at one palette step per
four frames, all at luminance 14. The palette is `beam_colors` in
`config/tuning.json`; it lives in bank 0 so the update can preserve its hue on
release. The appearance is drawn by the ROM and does not require Stella phosphor
blending.

Release freezes the last direction and hue, then draws brightness values 15
through 1 over 15 updates before hiding the beam. TIA ignores color bit 0, giving
effective luminances `14,14,12,12,10,10,8,8,6,6,4,4,2,2,0`. Luminance zero can
still be a dark colored pixel; the next update removes the pattern entirely.
The timer advances even during ring frames. New directional input immediately
replaces the fade with a bright beam, and reset clears the afterglow.

This cadence comes from Dennis Debro's
[Laser Blast disassembly](https://github.com/DNSDEBRO/Disassemblies/blob/a74a6312bac5ae28eacb423303bf55db30ad33d1/Atari2600/Laser%20Blast/laser_blast.asm):
`CheckForActionButton` initializes the player's laser to `COLOR_LEADSHIP + 15`,
the overscan update decrements its low nibble once per frame, and the kernel
disables it at zero. Our adaptation starts that decay on joystick release and
retains the selected rainbow hue. The original uses a missile graphic; our
eight-way implementation uses the ball and horizontal playfield rays.

Four renderer bytes store `BeamFadeTimer`, `BeamFadeHue`, `BeamDrawDirection`,
and `BeamDrawColor`. `Direction` and `BeamEnabled` still become neutral/zero
immediately on release, and the beam sound stops. Combat uses those input fields,
never the cosmetic draw direction. The render bank consumes the
prepared color and direction for either arena kernel.

This is display-only scheduling: `BeamEnabled` and the beam sound remain active
while a direction is held, even on its omitted frames. `BombEvent` pulses once
on acceptance for immediate damage; it is not repeated for ring stages.
The bomb sound decays over six updates independently of the longer animation.
Cooldown remains 60 updates. Bomb damage and the square fill cue both compare
the full 8.8 radius: `24.00` is inside, `24.01` is outside.

The ring uses the playfield kernel and player graphics are written on both
phases. Enemy draw ages do not depend on effect phase, so two enemies still
appear every other frame. No extra flicker phase is added for enemies.

## Space and update budgets

| Resource | Current measurement |
| --- | --- |
| Bank 0 end / room before trampoline | `$F530` / 2,640 bytes |
| Bank 1 end / room before trampoline | `$FD6D` / 531 bytes |
| Cartridge | 8,192 bytes, identical bank tails and vectors |
| RAM | Fixed 128-byte map, including reserves and stack |
| Stack | Six bytes observed; 16 reserved |
| Guard | Eight bytes at `$E8–$EF`, intact in tested runs |
| Update cost | 250–1,097 cycles from `GameFrame` to `LogicDone` |
| Render preparation done | 1,382–1,534 cycles from VSYNC line start |

The combat suite records 1,848 frame samples in `build/combat-timing.json`,
including a 1,400-frame survival run, movement/attack/contact boundaries, scoring,
spawning, HUD values, and restart. Tests enforce the 2,000-cycle update and
2,400-cycle preparation limits. The static diagnostic build has 2,644 bytes free
in bank 0 and 776 in bank 1.

Four 64-byte magnitude tables live in bank 0. Cardinal/diagonal signs reconstruct
all eight lanes there; cached sprite coordinates cross into the render bank.
This preserves its remaining space for later HUD/display work. Level state,
new audio envelopes and sprite reuse still require fresh RAM/timing budgets.

## Display limits and evidence

The turret uses player 0. Player 1 draws one enemy per frame, selected by greatest
draw age with a stable slot-index tie break. One target is visible every frame;
two targets alternate without starvation. Four slots are reserved, but the
prototype supports only two active targets. Cycling three or four targets through
this same whole-frame slot would exceed the accepted omission limit.

`make stella-check` runs both ROMs. The diagnostic pass records both phases of same-height, center-convergence, and
separated-height pairs. Its SELECT fixture injection temporarily drives only the
RIOT port-B SELECT bit; the ROM still performs its normal switch sampling and
edge detection. The command transcript documents that setup. Short log chunks
avoid Stella 6's corrupt session export after its prompt history wraps; they
are combined into `session.txt`. Debugger `frame`
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
The playable pass adds 18 snapshots of natural spawns/movement, both phases of a
two-enemy scene, triangle kills, square immunity, bomb-radius boundaries,
game-over/restart and representative HUD values. Its debugger state confirms
score awards and start/reset input handling. It uses explicit RAM fixtures only
for boundary cases, after first exercising natural spawning and movement.
Real hardware
flicker and audio remain untested. Advancing
to three enemies requires vertical sprite reuse and new timing/visibility
measurements, as described in [the implementation specification](IMPLEMENTATION_SPEC.md).
