# Prototype kernel timing

This records the playable four-enemy variant prototype with flick-to-fire beams, levels, and
the separate static display-test ROM. CPU/register measurements come from the assembled F8 cartridges and the py65
harness. The reference quota-growth build has 81 Stella 6.0.2 screenshots captured
with SDL dummy video. Earlier references include 37 late-variant scenes and
32 four-target density captures. Each snapshot directory retains its ROM;
each sound capture below records the ROM hash it used.
The reinforced-enemy build adds 27 Stella captures of levels 20/25, both draw
phases on all eight backgrounds, and damage/color stages. Earlier screenshots
retain their original ROM hashes. Television readability and the full X11 debugger transcript
pass remain separate from those still-image checks.

## Frame layout

| Region | Scanlines | Work |
| --- | ---: | --- |
| VSYNC | 3 | Vertical synchronization |
| VBLANK | 37 | Sound output, HUD preparation, beam/ring pointers, enemy selection and positioning |
| Top HUD | 29 | Score/health and FIRE or LV01; final level plus OVER after death |
| Separator | 1 | Clear HUD graphics; prepare arena |
| Arena | 160 | 80 logical rows, each drawn twice |
| Footer | 2 | Wave-progress rail/fill during play and wave clears; blank on title/game over |
| Overscan | 30 | Input, movement, attacks, contacts, spawning, beam/fade, sound requests and approach lookup |
| Total | 262 | 19,912 CPU cycles at 76 cycles per line |

Earlier X11 Stella runs verified 19,912-cycle frames across effects and combat.
The current host harness checks this exact 262-line frame through scripted
survival, four-target combat, wave-clear transitions, HUD values, and boundary
fixtures. The diagnostic ROM retains its 24-line HUD and eight-line separator
and exercises all eleven static layouts. The playable arena starts at frame line
70; the diagnostic arena retains line 72. Both arenas remain 160 lines tall.
Both possible F8 startup banks enter the same reset path.

The RIOT timer starts with a partial first interval: its first decrement occurs
after one CPU cycle. With this entry path, `TIM64T=43` during blanking and `34`
during overscan leave the polling loop in the intended final WSYNC window.
These constants depend on instruction placement and entry timing. A full-interval
timer model incorrectly accepted a 260-line earlier build; the harness now
models the behavior in [Stella's RIOT implementation](https://github.com/stella-emu/stella/blob/6.0.2/src/emucore/M6532.cxx).

## Playable HUD

HUD lines 0–1 and 12–18 are blank. Lines 2–11 display four score digits on the
left and health marks on the right; lines 19–28 display FIRE on the title or
`LV01` during play. Game over keeps the final score and level, with `OVER` on
the right of the level. The right half is blank in other modes. Numeric
kills remaining and bomb readiness are no longer drawn; all top-HUD graphics stay white.
Each font row lasts two lines.
Visible line 29 clears the playfield and prepares the arena. Lines 30–189 draw
the arena, then lines 190/191 draw the dim full-width rail and green completed
portion. The bar spans playfield cells 4–35. Both sprites and the ball are cleared
on footer entry. Outside play and the completion sequence, the footer clears PF0/PF1/PF2 and stays blank;
the title and game-over screens show neither rail nor fill.
The diagnostic ROM retains its TEST/BOMB header.

| Region | Left PF1 / PF2 completion | Right PF1 / PF2 completion | Color |
| --- | --- | --- | --- |
| Score and health | Cycles 12 / 19 | Cycles 43 / 53 | White at cycle 5 |
| Title | Cycles 13 / 21 | Clear at cycles 40 / 51 | White at 5 |
| Level / game-over results | Cycles 17 / 36 | Blank or OVER at cycles 43 / 50 | White at 10 |
| Progress rail | Cycles 22 / 25 | PF1 retained / PF2 at 59 | Gray at 17; right PF0 at 30 |
| Progress fill | Cycles 16 / 22 | Cycles 46 / 52 | Green at 10; right PF0 at 40 |

PF0 is cleared at cycle 5 of each level line and stays blank across both halves.
Render preparation converts packed BCD into ten score-row
bytes and selects two status pointers. These occupy `$D8–$E5` only during
display; input and spawn scratch can reuse them during overscan after the last
visible line. The input history is committed before HUD preparation overwrites
the samples. Health masks use two previously reserved audio bytes.
FIRE pointers share one immediate high byte; assembly asserts that both text
fragments stay on the same page. Their low bytes are immediate constants.

For play, wave completion (mode 3), and game over, status pointers select the level's tens
and ones glyphs from page-safe 50-byte tables. The tens table aliases the score's
reversed digit font. The status scanline combines these through `Temp` and draws
the fixed `LV` label. PF2 completes at cycle 36, before its left-half display begins.
Two ten-byte tables provide blank rows 0–4 and OVER rows 5–9 on the right.
X selects the starting row by mode and advances once per doubled font row.
Page-safe absolute indexed loads preserve fixed four-cycle reads and need no RAM.

After the top score/health rows finish, `PrepareProgress` reuses five right-score
bytes as `HudProgress` playfield masks. The numeric remaining-count conversion,
glyphs, and bomb indicator graphics have been removed from the playable ROM.
Three binary division steps compute `floor(8 * completed / quota)`, clamping
over-quota debugger counts to empty. `TIM64T=7` and the following WSYNC keep the
preparation gap at seven scanlines, preserving the established layout. No RAM is
added. Font tables use page-safe packing rather than blanket alignment to recover
ROM space. Tests check every status write at its exact cycle for representative
levels, including 09/10/99, and require a blank right half across quota/cooldown
values and on the title. Game-over checks retain the final score/level past the
death cue, verify OVER's right-hand pixels, and exercise held fire, a fresh
restart, and RESET. Progress
tests cover every remaining count at each quota size, 99/255, and the exact bar
write schedule. Moving the bar to the footer shifts the arena up two scanlines,
preserving its size, the 192-line visible region, and the 262-line total frame.

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

The second line also performs sprite reuse work within its 76-cycle budget. Footer entry disables ENABL before drawing the bar and entering overscan. The playfield
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
gold color; the arena background holds its level color between cyan healing flashes, yellow all-clear flashes, and higher-priority red damage feedback. The outline replaces
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
damages squares, hexagons, and diamonds, while triangles show vivid yellow/orange immunity feedback.
The beam damages triangles and diamonds; squares show the same immunity feedback. A combined
hit on a diamond can deal two damage but awards score only once on death.
Bomb damage and square fill both compare the full 8.8 radius: `24.00` is inside,
`24.01` is outside.

A beam-immune hexagon sets `SFX_HEX_REJECT` and tail-calls `DamagePlayer` from
`ImmuneEnemy`, setting the existing player-hit timer. It receives no enemy damage.
This skips the lower-priority immunity sound and a redundant subroutine return.
`DamagePlayer` raises the sound request to `SFX_PLAYER_HIT` only if it would not
overwrite a hexagon cue from another slot. Death is requested after all slots
resolve and overrides both. Combat visits slots in descending order with a
shorter loop, keeping the additional sound selection inside the CPU budget.
The ordinary immunity
flash/shake still appears. Bomb kills skip the later beam/contact checks, so an
in-range bomb prevents retaliation in a simultaneous attack. No new timer or
per-enemy state is needed.

Movement checks the debug freeze flag once and visits slots with a descending
index. Gameplay sound output/envelope advancement runs first in VBLANK, before
bonus-flash color selection, leaving more overscan time for retaliation plus
contact, scoring, wave advancement, and spawning. If there is no requested or
active event sound, overscan precomputes the nearest fast triangle into `Temp`.
Beam visual work and synchronization preserve that scratch byte; VBLANK audio
consumes it before display preparation reuses it. The diagnostic ROM retains
overscan audio. Sound and visual envelopes still advance once per frame.

The ring uses the playfield kernel and player graphics are written on both
phases. Fixed slot phases keep every live enemy/burst visible at least every other
frame, including all four targets. No extra flicker phase is added for enemies.

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
The orange square reuses the normal square pair. The cyan hexagon shares
`BurstFlash` (graphic 7), widened to a flat-topped six-sided shape; its first
white destruction-flash silhouette changes accordingly. Hexagons bypass square
range-fill selection. The atlas remains ten windows with no extra sprite page.
The reinforced triangle shares the standard triangle window, colored violet.
A four-HP diamond uses gold until the first hit, then ordinary blue at three HP;
the existing white successful-hit flash overrides either base color. All other
types have less than four HP, which the generator validates.

Display setup and HUD preparation now run in bank 0. After VSYNC, bank 1 starts
the blanking timer and jumps through `PrepareEntry` ($FF92) to bank 0; it returns
through `RenderEntry` ($FF98) at `PrepareDone`. Pointer/type tables live in bank 0,
the sprite atlas, raster streams, motion tables, and arena kernels live in bank 1.
HUD drawing/fonts now live in bank 0: `HudEntry` ($FF9E) switches there after
blanking, and `ArenaEntry` ($FFA4) switches back on separator line 29
(diagnostic: separator line 24).
The seven bank stubs are byte-identical in both tails.
The following tail bytes also match: `$FFAA–$FFDB` holds the 50-byte level-ones
font, `$FFDC–$FFE4` holds `ProgressRight1`, and `$FFE5–$FFED` holds
`ProgressRight2`, and `$FFEE–$FFF7` holds ten `DigitOffsets` bytes. Moving these
78 bytes into matching bank tails and packing the score fonts between setup
tables makes room for wave completion without enlarging the cartridge. All indexed
reads stay on-page; assembly and structural checks keep the data below `$FFF8`.

Renderer setup, health masks, and the first three progress masks share repeated
subsequences and overlapping table ends. The generator emits 254 bytes for 296
logical lookup bytes, with each table name aliasing its contiguous slice. Raster
stream pointers use their known three-per-page offsets; sprite pointers use
their two-per-page offsets. No runtime unpacking is needed. Setup lookups may
cross pages within the measured blanking budget; timed raster streams, sprite
windows, fonts, and shared-tail reads retain their page constraints.

Player contact starts a 12-update background flash. `PlayerHitTimer` uses one
former audio reserve byte; it advances before combat and also during game over.
The shades `$48`, `$46`, `$44`, `$42` each last three updates, then restore the
current level background, including after fatal damage.
Render preparation writes COLUBK during blanking, before the HUD; neither the
frame setup nor the separator overwrites it in the playable ROM. All 192 visible
lines therefore share the same background color. HMCLR and ENABL still receive
zero in the separator. The diagnostic ROM retains its black background writes.
New contacts restart the timer without reducing further contact damage. Reset
clears it, while game-over weapon cleanup leaves the fatal-hit flash visible.

`ConfigureLevel` caches a persistent `LevelBackground` color from an eight-entry
table. Its index is `(decimal level - 1) % 8`: the low BCD nibble contributes the
ones, and twice the low two bits of the tens contributes the tens modulo eight.
This keeps the palette cycling across 09/10 and all later decimal boundaries,
independently of difficulty-row saturation. Level 99 keeps its color. Fresh starts
select level 1's black; game over retains the final level's color after the red
fade. Render preparation checks `PlayerHitTimer` first, so damage always wins.
`LevelBackground` aliases `HudColor`, whose bomb-readiness role is diagnostic-only.
Gameplay loads the white HUD color directly, so the palette uses no additional
RAM and does not add writes to the visible arena kernel.

Health recovery compares the thousands nibble of `ScoreHi` before and after
combat, using `HudScoreRight+4` as `ScoreBeforeCombat`. Positioning and slot
scanning preserve that scratch byte. After fatal-damage checks, a crossed
milestone adds one HP below the five-HP cap or clears all surviving active slots
at full health. Clearing sets enemy HP/flags to zero and starts 18-update bursts at
cached displayed positions, preserving preexisting bursts. It gives quota credit
without points and restarts the current spawn interval, preventing same-update
replacement. A post-bonus scan updates active/drawable counts before advancement
and spawning. Healing requests `SFX_HEAL`; full-health clearing requests
`SFX_CLEAR`. Saturating score at 9999 never retriggers a reward.
Each bonus cue lasts 32 updates. Bit 3 of its post-update timer selects cyan
`$BA` for healing or yellow `$1A` for clearing, producing 8 updates on, 8 off,
8 on, 8 off. Red damage feedback takes priority, and an
interrupted/discarded bonus cue is not queued. Wave completion requests its own
clear cue after red damage feedback, then loads the next level after it ends;
fresh starts clear all cues. No additional persistent RAM or bank switches are needed.

## Combat audio

`src/audio.asm` updates both TIA voices at the start of gameplay VBLANK. Channel 0 retains the
five-update beam tone. Channel 1 reads a per-update index into shared samples
from `config/audio.json`. Each unique sample uses a frequency byte and packed
control/volume byte; waveform occupies the low nibble and volume the high nibble.
Sample sharing and existing alignment padding accommodate the extra hexagon cue.
Bombs, rejection, nonlethal hits, destruction, healing, clear, player hits,
hexagon rejection, and game over last 6/8/8/12/32/32/12/12/36 updates respectively.
Nonlethal hits use noise throughout (`AUDC=8`, `AUDF=12`), with volume 12/9/6/2
lasting 1/2/2/3 updates. The sharp attack and quick fade replace the former
metallic tone steps, avoiding a pitch slide that suggested deflection;
hexagon retaliation uses four alternating buzzy pitch steps. Neither affects
damage, spawn pacing, or the existing visual-feedback timers.
Game over has highest priority, followed by hexagon rejection, player hit, clear, healing, destruction, nonlethal
hit, rejection, and bomb. Requests are coalesced before playback; higher/equal
priority replaces a running envelope, while lower-priority events are discarded.

Event ID, remaining updates, and this-update request use three former reserve
bytes at `$BC–$BE`; `$BF` now holds the level kill quota. Sound timers never drive damage. Each bonus cue shares its
event countdown with two cyan or yellow background flashes, avoiding another RAM byte. Fatal-hit cleanup stops the beam but lets the game-over tone finish;
reset/restart clears both voices. The separate display ROM keeps its original
audio behavior. Tests check exact TIA register envelopes, silence after expiry,
slot-order-independent priority, preemption/retriggering, coalesced kills,
rejected attacks, and game-over/reset behavior.

The idle event channel now follows the nearest active magenta triangle within
integer radius 48. Its pure-tone divider rises from 4 to 24 and volume from 2
to 7 during the final approach, producing a descending, strengthening whistle.
This is evaluated from live proximity after combat, so kills/contact stop it in
the same update, and an interrupted warning resumes at current range. All nine
event envelopes take priority; the independent beam voice is unchanged.
Only `Temp` is used, after its drawable-count lifetime has ended. The bounded
four-slot scan adds no persistent RAM and is skipped during event playback;
warning output is muted outside `PLAY`. Tests cover every type/slot, range boundaries, competing fast
triangles, each event priority, beam coexistence, reset/mode cleanup, and a full
natural fast-triangle approach ending in contact.

An earlier Stella 6.0.2 capture through SDL's disk audio backend records all
seven cues from the playable ROM, using actual beam/bomb inputs or contact
fixtures. All seven produce nonzero PCM, stay below clipping, and return to
silence. `build/audio-captures/report.json` records the ROM hash and WAV paths;
the capture script and isolated settings are retained alongside it. This checks
emulated audio output, not the user's speaker routing or real Atari sound.

The revised nonlethal-hit cue was captured separately from a beam hitting a
surviving diamond and a bomb hitting surviving armor; the hexagon cue was
captured from a fresh beam hit. The actual Stella SDL disk output contains
nonzero PCM below clipping and silent tails. Current capture indexes are
`build/audio-captures/latest-hit-beam-current.json`,
`build/audio-captures/latest-hit-bomb-current.json`, and
`build/audio-captures/latest-hex-reject-current.json`. Each records the ROM hash,
WAV path, peak level, and tail check; its capture script/settings are retained.

The preceding damage-impact retune changed nine bytes of audio sample data
only: assembly addresses, instructions, sound durations, and other cue
definitions matched its 104-test baseline. Nine existing audio/combat
checks passed against that retuned ROM, including the weapon matrix, cue envelopes,
priority, retriggering, expiry, and reset. Updated beam/diamond and bomb/armor
recordings verify nonzero, unclipped output and silent tails. Evidence is in
`build/damage-impact-validation.json`, with its targeted timings in
`build/damage-impact-timing.json`. The wave-clear build retains those sound
definitions and has its own full-suite measurements below.

The current healing cue is captured separately in
`build/audio-captures/latest-healing.json`, with its ROM hash, WAV, and retained
capture driver. A bomb kill crosses 1,000 points; Stella's actual disk output
has four rising notes near 991, 1314, 1960, and 2627 Hz, no clipping, and a silent
tail. A second current-ROM capture in `build/audio-captures/latest-clear.json`
records the full-health clear: its longer noise explosion decays without clipping
and returns to silence. Both complement the exact per-update register/envelope tests.

The approach-warning capture predates the density/HUD changes and uses a naturally moving magenta
triangle in headless Stella, followed by its contact cue. Analysis of the actual
SDL disk output measured a falling fundamental (about 2.6 kHz to 690 Hz over the
sampled approach) and increasing amplitude, no clipping, and a silent tail after
contact feedback. The WAV, command script, capture driver, and ROM hash are indexed
by `build/audio-captures/latest-fast-approach.json`. This verifies emulated output;
the final timbre and relative volume still benefit from listening during play.

## Level progression

`LevelNumber` aliases diagnostic `LayoutId` at `$A0`, `KillsRemaining` uses `$BF`,
and the eight-entry type-row offset uses former render reserve `$D7`.
`SpawnTimer` doubles as the completion countdown in mode 3, with zero meaning
that the clear is pending. These lifetimes leave the guard and stack untouched.
The BCD level saturates at 99 and maps levels above eight to the final cap/delay
row. From level 20, a ninth type-only row replaces one standard triangle entry
with type 3, the reinforced triangle. The quota grows separately: 8 on level 1, plus four each level, capped at
64 from level 15. Loading and HUD preparation share `CalculateQuota`; the old
eight-byte quota table is removed. The routine caps before the BCD-to-binary
conversion, so only levels 10–14 need the six-value correction. Its scratch-free
result becomes the remaining quota at load time and the HUD denominator during
progress preparation. `ProgressQuota` aliases the final right-score/progress
byte only after the score rows finish, adding no persistent RAM.

All slots resolve damage/contact and score milestones before checking the quota.
Death wins over completion. An alive player with zero quota enters mode 3 and
renders the completed level with a full green bar before clearing survivors.
The next update waits for any red damage feedback, then calls `ClearEnemyBonus`
for cached-position bursts without points, clears `ActiveCount`, requests the
32-update clear sound, and starts the countdown. No movement, attacks, contacts,
or spawns run during this sequence; old bursts and input history still update.
At countdown expiry, increment the level and call `LoadLevel`, retaining HP,
score, RNG, and input history, clearing weapons/slots, and restarting the new
wave's normal spawn interval. Level 99 repeats its final row and celebration.
Multi-kills saturate the old quota without credit toward the new quota.

For debugger fixtures, mode 3 with a positive quota and countdown still loads
the requested level without incrementing it. RESET works before or during the
celebration. Wave 1 retains a cap of two and a 24-update spawn interval; wave 2
has four and 12 updates, falling to eight updates at wave 5 and four updates
from wave 10 onward. Waves 8–9 retain the established pace when hexagons first
appear. The generator emits a separate BCD threshold and delay from `late_spawn`;
`late_mix` selects type offset 64 from level 20. `reinforced_diamond` supplies a
BCD level-25 threshold; the diamond spawn path uses the comparison's carry to
choose three or four HP. Type, speed, weapon rules, score, and RAM use stay the
same. The completion sequence does not require full health and does not
replace the separate 1,000-point rewards.

Actual Stella audio from a wave completed by a bomb at three HP and 25 points
is indexed by `build/audio-captures/latest-wave-clear.json`. It contains an
unclipped, decaying explosion and a silent tail, with the ROM hash and replay
script retained. Register tests assert the 32-update cue and yellow phases.

## Space and update budgets

| Resource | Current measurement |
| --- | --- |
| Bank 0 end / room before trampoline | `$FF7E` / 2 bytes |
| Bank 1 end / room before trampoline | `$FF00` / 128 bytes |
| Cartridge | 8,192 bytes, identical bank tails and vectors |
| RAM | Fixed 128-byte map, including reserves and stack |
| Stack | Eight bytes observed; 16 reserved |
| Guard | Eight bytes at `$E8–$EF`, intact in tested runs |
| Update cost | 288–1,889 cycles from `GameFrame` to `LogicDone` |
| Render preparation done | 1,620–2,380 cycles from VSYNC line start |

The suite contains 111 tests (82 combat and 29 density/diagnostic). Loading
checks cover all 99 displayed levels, including the shorter delay from level 10,
the type-row change at level 20, and reinforced diamond spawns from level 25;
progress rendering covers every supported quota, including 09/10, 14/15/16,
and the capped later levels. Current CPU/register and browser-cache validation
is recorded in `build/game-over-validation.json`, including the ROM hash,
suite results, and timing. The prior `build/reinforced-validation.json` retains
its ROM hashes and 27 Stella captures; those captures predate the game-over HUD
change. Previous evidence also remains in
`build/late-spawn-validation.json`, `build/wave-clear-validation.json`, and `build/quota-growth-validation.json`;
the latter retains the reference ROM and its 81 Stella screenshots.

The combat suite records 20,404 frame samples in `build/combat-timing.json`,
including a survival run of at least 1,400 frames across the five early types, movement/attack/contact boundaries, scoring,
spawning, immunity/hit feedback, destruction bursts, HUD values, and restart.
A second natural run completes the first four levels with all early variants seen and
no player damage. Fixtures check quotas, completion clears, carry/saturation at levels
09/10/19/20/24/25/99, per-row spawning, input history, and death/reset priority.
New fixtures test two fresh beam hits on violet triangles, bomb immunity,
four separate beam/bomb/mixed hits on reinforced diamonds, held-input rejection,
gold-to-blue appearance, feedback priority, and exact first/replacement delays.
Game-over fixtures retain scores and levels 09/25/99 for 60 updates while fire
is held, check the final level/OVER raster, and reset results only on a fresh
fire press or RESET. Existing score-raster checks also cover zero health.
The full-health-clear test includes 64 fixtures combining movement, both attacks,
all survivor types, a due spawn, and 09/10 or saturated-99 wave advancement.
Another 192 fixtures combine a hexagon in every slot with movement, a fresh
beam, bombs, other target types at contact/inside/outside bomb range, score
carry, wave advancement, and a due spawn. These stay within the update/preparation budgets, including normal scored
bursts positioned during blanking and bonus bursts retaining cached positions.
Tests enforce the 2,000-cycle update and
2,400-cycle preparation limits. The static diagnostic build has 1,064 bytes free
in bank 0 and 896 in bank 1.

Four 64-byte magnitude tables live in bank 0. Cardinal/diagonal signs reconstruct
all eight lanes there. Movement changes radii during overscan, then `PrepareFrame`
derives live coordinates during VBLANK before selecting sprites. Scored kills
clear the active bit but retain `$40 | lane` until `PrepareFrame` positions the
new burst at the exact hit radius and clears the marker. This moves coordinate
work out of crowded combat/bonus updates without changing the visible hit
position. Full-health bonus removals retain their last displayed coordinates
and need no positioning marker. Cached coordinates cross into the render bank.
The four former EnemyAge bytes now hold the lower sprite pointer, remaining X
displacement, and color. `$E6` stores the reuse row. `FramePhase` bit 0 selects
the effect phase, bits 1–3 encode the lower slot plus one, and bit 7 flags an
invalid debugger pair. HUD scratch is generated only after render selection.

## Display limits and evidence

The turret uses player 0. Player 1 draws up to two vertically separated enemies
per frame. Phases belong to slots `(0,2)` and `(1,3)`, with an empty phase borrowing
the populated phase. Four slots are allocated and validated for gameplay, without
adding a third flicker phase.

At caps of three or four, even slots use vertical/diagonal lanes; odd slots also
allow new E/W fast triangles. The spawner checks an entire remaining approach,
using generated bounds for all
49 type pairs and both fractional endpoints. One enemy must stay at radius 24
or greater until the other could reach contact plus 18 burst updates. This also
handles early kills, which freeze the sprite farther out and shorten its life.
Horizontal partners use a separate early-placement table: the new vertical enemy
must remain at radius 36 or greater until contact plus the full possible burst
of its horizontal partner. This covers every type carried from the opening level,
including slow armored debugger fixtures. A radius-32 bound failed the exhaustive
geometry check because fixed-point Y rounding left insufficient repositioning
time; the radius-36 bound passes. No new partner joins a burst. Unsafe arrangements
defer two updates. Bomb-only enemies are limited to one in wave 1 and two from
wave 2, with the same 72-update spacing shared by all squares and hexagons.
The normal/armored pair occurs in the natural survival test without losing
health; a separate fixture verifies two armored squares can take two ready
bombs while approaching. Both slots receive bomb damage in the same update.

At the tightest accepted diagonal separation, four logical rows are blank.
That fits three seven-clock moves plus pointer-switch overhead, including the
largest immunity-shake difference. Tests exhaust every legal lane/radius pair's
space requirement, reconstruct actual sprite rows and HMOVE positions, exercise
all beam/ring patterns on both paired phases, and check natural four-enemy
visibility through repeated center arrivals. Additional fixtures exercise all
4,096 four-target type combinations under simultaneous beam/bomb damage.
`build/density-timing.json` records the busy four-target cases, 96 idle-warning
layouts, and natural spawning: 1,800 updates each in levels 2, 6, and 8,
plus 2,400 each at levels 10, 20, and 25 to include the late variants in the seeded run.
Every live enemy remains visible at least every
other frame, and every level reaches four within 120 updates.

A deterministic October 28 comparison, before allowing paired squares, ran
900 frames at level 2 with health restored each update to keep both runs going.
It is recorded in `build/pressure-report.json`. With a scripted
defender, mean live population after a 120-frame warmup rose from 1.70 to 3.06;
the new run first reached four enemies at frame 48. With no attacks it averaged
3.99. This measures spawn pressure under two fixed behaviors, not human difficulty.

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
The updated level pass produces 81 snapshots covering the full green bar,
yellow explosion, flash gap, and cleared next level, the level/progress HUD, held/fresh controls, levels 04/09/10/99,
counts 00/09/18/42/99, quarter/half/three-quarter progress, final-row reuse, fatal
contacts, reset to 01, the hidden title/game-over footer, and both draw phases of a normal/armored pair before and
after a bomb. Additional captures show all five enemy variants against each of the eight
level colors, persistence, red damage overriding/restoring the background,
and a 0990-to-1000 health reward with both cyan flashes, a yellow full-health clear with all variants, burst stages, resumed spawning, and reset. Its normal
X11 state/capture index is `build/stella/latest-levels.json`.
The added density pass (`tools/verify_density_stella.py`) captures natural level-2
crowding, both paired phases, tight diagonal separation, beam/ring reuse,
immunity, and bursts. Its 32 snapshots include both phases of four-target neutral,
beam, ring, immunity, and burst fixtures. Its normal X11 index is `latest-density.json`.
X11 was unavailable in this session, so a delayed debugger script with SDL dummy
video produced 32 density screenshots on October 28 and 81 current wave screenshots plus 37 earlier variant screenshots
on October 30. Inspected examples cover four-target beam/ring/bursts, natural
crowding, bottom wave-progress fills, hidden title/game-over rails, counter reset,
paired squares taking a bomb, and enemy contrast throughout the background palette.
The 37 variant captures show orange-square outline/fill and cyan-hexagon
silhouettes beside diamonds and fast triangles on all eight backgrounds, red
beam-retaliation feedback, a held beam causing no further damage, and a
simultaneous bomb defeating the hexagon before it can retaliate.
The scripts, SDL input injector source, ROMs, and images are retained under
`build/stella/headless-four-density-20261028-214030` and
`build/stella/headless-four-levels-20261030-200220` and
`build/stella/headless-four-variants-20261030-200135`; their indexes are
`build/stella/latest-headless-four-density.json` and
`build/stella/latest-headless-four-levels.json` and
`build/stella/latest-headless-four-variants.json`. These captures have no debugger
state/timing transcript; current timing and state assertions come from py65.
The normal X11 verification scripts remain available for a local full pass.
The November 1 reinforced-enemy captures use the current ROM and are retained in
`build/stella/headless-four-reinforced-20261101-205500`, indexed by
`build/stella/latest-headless-four-reinforced.json`. Inspected images show violet
triangles against the level-20 plum background and gold diamonds becoming blue
after damage. The 27-image set also includes immunity, hit/kill stages, and both
draw phases on all eight backgrounds. Like the earlier dummy-video captures,
these verify appearance; CPU/register tests supply the state and timing checks.
Real hardware flicker and audio remain untested. Further density beyond four
requires a revised memory map and rendering plan, as described in
[the implementation specification](IMPLEMENTATION_SPEC.md).
