# Atari ZeroWave

A native Atari 2600 prototype of the stationary-turret game described in
[the port outline](docs/PORT_OUTLINE.md) and [implementation spec](docs/IMPLEMENTATION_SPEC.md).
The cartridge targets NTSC, uses ordinary 8 KiB F8 banking, and needs no extra RAM.

The current build is a playable two-enemy combat prototype: approaching triangles
and squares, beam and bomb kills, five health points, a four-digit score, and
start/game-over/restart screens. It uses fixed opening difficulty; levels and
higher enemy counts come next. The approved thin beam, color cycle, release fade,
and expanding bomb ring are retained.

## Build and run

Prerequisites: Git, Make, a C compiler, Python 3, and Stella. The optional automated
Stella check also needs Linux/X11, Xvfb, xauth, libX11, and libXtst.

```sh
make bootstrap  # Fetch pinned DASM 2.20.14.1 and py65 1.2.0 into .tools/
make check      # Generate assets, assemble, and test the actual ROM
make run        # Open Stella with NTSC/F8 and joystick settings
```

The ROM is `build/atari-zerowave.bin`; symbols, assembly listing, and a checksum/
bank-usage report are alongside it. `make debug` opens Stella's debugger.
`make clean` removes generated output and captures under `build/`. Tool downloads
stay in `.tools/`; nothing is installed globally. A separately installed assembler
can be selected with `make DASM=/path/to/dasm`.

Make is optional for launching an existing ROM: open the `.bin` in Stella or run
`stella build/atari-zerowave.bin`. `make run` also rebuilds it when sources change.

## Controls

Use a joystick in the left port. These are Stella's default keyboard bindings;
custom mappings can be changed in its input settings.

| Control | Stella key | Prototype behavior |
| --- | --- | --- |
| Joystick direction | Arrow keys; combine two for diagonals | Hold to fire a solid color-cycling beam; release to fade |
| Joystick button | Space | Start/restart; during play, bomb on a fresh press if ready |
| SELECT | F1 | No effect in the playable ROM |
| RESET | F2 | Start a fresh run with five HP and zero score |

Press Space at `FIRE` to start. The upper-left number is your score; the five
white marks on the right are health. Green triangles die to a beam on their
approach lane and award 10 points. Pink squares require a bomb and award 25.
A square fills in when it enters bomb range. Each enemy reaching the turret
costs one health point. At zero health, `OVER` appears and the final score stays
visible; release and press Space again, or use F2, to restart.

Enemies approach along eight lanes, with at most two active and no duplicate
lanes. The first spawn arrives about 1.5 seconds after starting. Movement and
spawn settings stay fixed throughout this milestone; score saturates at 9999.

The `BOMB` label is green when ready and amber during the 60-update cooldown.
Holding the button produces one bomb; pressing during cooldown does not queue
another. The gold bomb outline expands through four sizes over 16 updates
(about a quarter-second), ending at the bomb's range. During that animation,
ring and beam frames alternate. Outside bombs the beam stays visible every frame.
The entire beam uses one bright color at a time, cycling through eight colors
at one step per four updates. There are no stacked gradient lines or separate
glow stripes. Its input and sound remain active throughout while a direction is
held. Releasing the stick stops firing and sound immediately, while the last beam
holds its hue and dims over 15 frames (about a quarter-second). This uses
[Laser Blast's brightness countdown](docs/KERNEL_TIMING.md#effect-scheduling).
Re-aiming immediately replaces the afterglow with a bright beam in the new
direction. The afterglow deals no damage. Starting or resetting with fire held
does not trigger a bomb; release the button before bombing.

Vertical and diagonal beams use the TIA ball at one color clock wide. Diagonals
advance at most one color clock per physical scanline, giving a connected thin
line. Left/right beams retain their existing two-scanline thickness and reach.
Both techniques use the same color cycle and release fade.

Bomb damage happens once, immediately on the accepted press, within a fixed
radius. The expanding ring is visual feedback; an enemy entering it afterward
survives. Beam damage continues while held, including ring display frames.

Destroyed enemies leave a short burst at the hit position: a white flash, gold
sparks, then dim red embers over 18 updates (about 0.3 seconds). Kills and score
apply immediately. A burst temporarily occupies the old sprite slot, so a new
spawn may wait for it to finish when both display slots are occupied.

For this playtest, check whether triangles are easy to hit, the square's fill cue
gives enough warning, the bomb feels responsive, and two approaching enemies
remain readable. Let enemies through once to check health loss and restart.

## Static display test

`make all` also builds `build/atari-zerowave-display.bin`. Open it with
`make run-display` to revisit the earlier visual fixtures without combat.

In that ROM, SELECT cycles through N, NE, E, SE, S, SW, W, and NW single-target layouts, then
east/west at the same height, two diagonals near the turret, and a north/south pair.
Triangles are green. Squares are pink and fill in when inside bomb range. The SE
layout demonstrates this cue. These are visual fixtures: firing does not remove
them. Two-target layouts alternate one enemy per frame, so each appears at about
30 Hz. The turret remains present every frame. The beam appears at 60 Hz normally;
during bombs, beam and ring each appear at about 30 Hz. Bombs do not reduce enemy
appearances further.

## Validation and development

`make check` runs 41 tests covering generated geometry, all joystick combinations,
button edges and exact cooldown boundaries, both startup banks, stack/guard
integrity, fixed frame lengths, kernel write deadlines, and display fairness.
Tests check every animation stage for presses on either frame phase, actual
playfield data, ball motion/enable timing, uniform beam color, sprite rows, every palette phase,
continuous beam state, and the separate short sound envelope. Release tests cover
all eight directions and hues, the exact fade countdown, immediate sound cutoff,
re-aiming, reset, and simultaneous bombing with two enemies.
Combat checks cover all lane/radius coordinates, fixed-point boundaries, attack
priority, BCD score carries/saturation, start/reset input edges, spawn limits,
square spacing, HUD digits/health, and a 1,400-frame scripted survival run.
Burst checks cover all eight hit directions, every animation stage, double bomb
kills, surviving-enemy visibility, spawn deferral, expiry, and reset/game over.
`build/combat-timing.json` records the measured update/prepare costs and stack use.
The CPU tests execute the assembled cartridge using py65 and a limited VCS bus;
they do not simulate TIA pixels.

```sh
xvfb-run -a make stella-check
```

This runs both ROMs in isolated Stella windows and checks 262-line timing.
The display ROM saves 56 TIA snapshots: neutral, both phases of all eight
directions, all 16 bomb frames, and both phases of the three overlap layouts
during the largest ring, plus the last held beam, all 15 release frames, and the
cleared frame. Results are indexed by
`build/stella/latest.json`. The playable ROM adds 34 captures of natural movement,
two-enemy drawing, kills, exact bomb-range boundaries, game over/restart, and HUD
values, plus both phases of every destruction-burst stage, indexed by
`build/stella/latest-combat.json`. Validated with Stella 6.0.2. See
[kernel timing notes](docs/KERNEL_TIMING.md) for the measured budgets and limits.
Television flicker, real joystick diagonals, and sound still need a hardware pass.

Assembly lives in `src/`; `config/` contains tuning and static fixtures;
`tools/generate_assets.py` produces the shared graphics tables. The independent
Godot reference checkout in `res/` is ignored by this repository.

Next is combat playtesting, followed by the level table, level transitions, and
additional hit/death sounds. Keep the two-enemy cap until the later sprite reuse
work establishes a readable schedule for three or four enemies.

## Local repository

The branch is `main`, with repository-local identity
`mastergray <me@mastergray.com>`. No remote is configured. When a personal GitHub
repository is created, use the `github-mastergray` SSH alias. The initial commit
records the agreed port outline and implementation specification.
