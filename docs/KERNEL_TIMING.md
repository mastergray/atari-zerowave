# Prototype kernel timing

This records the controls/display prototype, corresponding to implementation
milestones 0 and 1. Measurements were taken from the assembled F8 ROM with the
py65 harness and Stella 6.0.2. They do not certify television readability or
unfinished combat paths.

## Frame layout

| Region | Scanlines | Work |
| --- | ---: | --- |
| VSYNC | 3 | Vertical synchronization |
| VBLANK | 37 | Beam/ring pointers, enemy selection and positioning |
| HUD | 24 | TEST/BOMB labels and cooldown color |
| Separator | 8 | Clear HUD graphics; prepare arena |
| Arena | 160 | 80 logical rows, each drawn twice |
| Overscan | 30 | Sample input, update bomb state, select fixtures and sound |
| Total | 262 | 19,912 CPU cycles at 76 cycles per line |

Stella's `_cycleslo` increases by 19,912 per frame across direction changes,
all animation frames, fixture loads, and cooldown waits.
The host harness checks 262-line frames through button/cooldown tests and all
eleven layouts. Both possible F8 startup banks enter the same reset path.

The RIOT timer starts with a partial first interval: its first decrement occurs
after one CPU cycle. With this entry path, `TIM64T=43` during blanking and `34`
during overscan leave the polling loop in the intended final WSYNC window.
These constants depend on instruction placement and entry timing. A full-interval
timer model incorrectly accepted a 260-line earlier build; the harness now
models the behavior in [Stella's RIOT implementation](https://github.com/stella-emu/stella/blob/6.0.2/src/emucore/M6532.cxx).

## Arena scanline schedule

The following are CPU cycles at instruction completion, counted from WSYNC
release. Both physical scanlines of each logical row use the same schedule.
The playfield is in normal, unreflected mode, with independent writes for its
left and right halves.

| Cycle | Register | Value |
| ---: | --- | --- |
| 5 | PF0 | Zero for left edge |
| 13 | PF1 | Left beam/ring stream |
| 21 | GRP1 | Selected enemy row |
| 29 | PF2 | Left beam/ring stream |
| 36 | GRP0 | Turret row |
| 44 | PF0 | Right beam/ring stream |
| 52 | PF1 | Right beam/ring stream |
| 57 | PF2 | Zero for right edge |

The first line then reaches WSYNC at cycle 60. The second line increments Y,
compares it with 80, branches, and reaches WSYNC by cycle 67. The last row
enters overscan instead. Indexed streams never cross a page during the kernel.
The tests check all eight register deadlines on all 160 arena lines.

Generated rays occupy playfield columns 9 through 31; the rings fit inside that
span. Left PF0 and right PF2
are therefore constant zero, allowing four varying streams instead of six.
Deduplication reduces the eight directions, neutral, and four rings to 22 shared
80-byte streams (the beams alone need thirteen). Packing three streams per
256-byte page saves alignment space without introducing page-crossing loads.
If the arena geometry expands into those outer columns, the
generator fails; changing the timed kernel is required.

Enemy GRP1 is ready before the leftmost legal sprite pixel. The turret stays at
horizontal left edge 76 and logical top row 38. Sprite positioning runs entirely
in blanking, followed by HMOVE. `PositionPlayer` deliberately aligns its subtract/
branch loop within one page and uses a five-cycle absolute indexed HMP store.
Changing either changes horizontal placement; Stella inspection confirmed both
players at the intended positions after correcting these details.

## Effect scheduling

`FrameCounter & 1` selects the display phase. Even frames show the selected beam,
or blank for neutral. Odd frames show a bomb ring when `BombTimer` is nonzero,
or blank otherwise. Pattern IDs 0–7 are directions, 8 is blank, and 9–12 are
the four rings. `DisplayPattern` records the prepared frame for debugger checks.

The ring radii are 6, 12, 18, and 24 in the shared game geometry. Each stage lasts
four updates, giving two visible appearances per stage regardless of the press
phase. The animation lasts 16 updates. A gold playfield color distinguishes the
ring from the cyan beam; the arena background stays black. The outline replaces
the previous size, so no filled disk or trail accumulates.

This is display-only scheduling: `BeamEnabled` and the beam sound remain active
while a direction is held, even on its omitted frames. `BombEvent` pulses once
on acceptance for future immediate damage; it is not repeated for ring stages.
The bomb sound decays over six updates independently of the longer animation.
Cooldown remains 60 updates. No damage rules are implemented in this prototype.

The ring uses the existing kernel and player graphics are written on both
phases. Enemy draw ages do not depend on effect phase, so two enemies still
appear every other frame. No extra flicker phase is added for enemies.

## Space and update budgets

| Resource | Current measurement |
| --- | --- |
| Bank 0 end / room before trampoline | `$F195` / 3,563 bytes |
| Bank 1 end / room before trampoline | `$FE78` / 264 bytes |
| Cartridge | 8,192 bytes, identical bank tails and vectors |
| RAM | Fixed 128-byte map, including reserves and stack |
| Stack | Four bytes observed; 16 reserved |
| Guard | Eight bytes at `$E8–$EF`, intact in tested runs |
| Update cost | 190–576 cycles from `GameFrame` to `LogicDone` |
| Render preparation done | 698–850 cycles from VSYNC line start |

The cost samples cover 374 frames: all 16 direction combinations with button up/
down in all eleven layouts, plus SELECT edges. They include fixture loads but
exclude future movement, combat, score, and spawning. Re-measure after adding
those paths. The renderer bank's 264-byte remaining space requires budgeting
coordinate and future HUD tables; raw per-lane X/Y arrays will not fit unchanged.
Future coordinate data may need compression or relocation to the logic bank.

## Display limits and evidence

The turret uses player 0. Player 1 draws one enemy per frame, selected by greatest
draw age with a stable slot-index tie break. One target is visible every frame;
two targets alternate without starvation. Four slots are reserved, but the
prototype supports only two active targets. Cycling three or four targets through
this same whole-frame slot would exceed the accepted omission limit.

`make stella-check` records both phases of same-height, center-convergence, and
separated-height pairs. Its SELECT fixture injection temporarily drives only the
RIOT port-B SELECT bit; the ROM still performs its normal switch sampling and
edge detection. The command transcript documents that setup. Debugger `frame`
stops at VSYNC, so animation captures wait for a complete newly drawn frame.

The Stella snapshots cover both phases of all eight rays, neutral, every bomb
animation frame, and target placement during the largest ring. Visual inspection
confirmed the expanding outline and both target phases. Real hardware
flicker and audio remain untested. Advancing
to three enemies requires vertical sprite reuse and new timing/visibility
measurements, as described in [the implementation specification](IMPLEMENTATION_SPEC.md).
