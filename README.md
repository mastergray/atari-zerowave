# Atari ZeroWave

A native Atari 2600 prototype of the stationary-turret game described in
[the port outline](docs/PORT_OUTLINE.md) and [implementation spec](docs/IMPLEMENTATION_SPEC.md).
The cartridge targets NTSC, uses ordinary 8 KiB F8 banking, and needs no extra RAM.

The current build implements the first controls/display milestone: a centered
turret, eight-way color-cycling beam, button-triggered expanding bomb ring and sound,
one-second bomb cooldown, and eleven static enemy layouts. Enemies do not move
or take damage yet. Health, score, levels, and title/game-over screens come later.

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
| Joystick button | Space | Expanding bomb ring and sound on a fresh press, if ready |
| SELECT | F1 | Advance to the next static test layout |
| RESET | F2 | Return to the first layout and clear bomb state and beam afterglow |

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
direction. RESET with fire held does not trigger a bomb.

Vertical and diagonal beams use the TIA ball at one color clock wide. Diagonals
advance at most one color clock per physical scanline, giving a connected thin
line. Left/right beams retain their existing two-scanline thickness and reach.
Both techniques use the same color cycle and release fade.

Try releasing each direction, re-aiming during the fade, and bombing while the
beam fades. Check
whether the expanding ring is easy to see and whether the beam remains
easy to aim. The ring is visual feedback for the planned immediate, fixed-radius
damage; it does not introduce a moving damage front or a lingering blast.

SELECT cycles through N, NE, E, SE, S, SW, W, and NW single-target layouts, then
east/west at the same height, two diagonals near the turret, and a north/south pair.
Triangles are green. Squares are pink and fill in when inside bomb range. The SE
layout demonstrates this cue. These are visual fixtures: firing does not remove
them. Two-target layouts alternate one enemy per frame, so each appears at about
30 Hz. The turret remains present every frame. The beam appears at 60 Hz normally;
during bombs, beam and ring each appear at about 30 Hz. Bombs do not reduce enemy
appearances further.

## Validation and development

`make check` runs 20 tests covering generated geometry, all joystick combinations,
button edges and exact cooldown boundaries, both startup banks, stack/guard
integrity, fixed frame lengths, kernel write deadlines, and display fairness.
Tests check every animation stage for presses on either frame phase, actual
playfield data, ball motion/enable timing, uniform beam color, sprite rows, every palette phase,
continuous beam state, and the separate short sound envelope. Release tests cover
all eight directions and hues, the exact fade countdown, immediate sound cutoff,
re-aiming, reset, and simultaneous bombing with two enemies.
The CPU tests execute the assembled cartridge using py65 and a limited VCS bus;
they do not simulate TIA pixels.

```sh
xvfb-run -a make stella-check
```

This runs the ROM in an isolated Stella window, checks input/bomb state and
262-line timing, and saves 56 TIA snapshots: neutral, both phases of all eight
directions, all 16 bomb frames, and both phases of the three overlap layouts
during the largest ring, plus the last held beam, all 15 release frames, and the
cleared frame. Results are indexed by
`build/stella/latest.json`. Validated with Stella 6.0.2. See
[kernel timing notes](docs/KERNEL_TIMING.md) for the measured budgets and limits.
Television flicker, real joystick diagonals, and sound still need a hardware pass.

Assembly lives in `src/`; `config/` contains tuning and static fixtures;
`tools/generate_assets.py` produces the shared graphics tables. The independent
Godot reference checkout in `res/` is ignored by this repository.

Next is milestone 2: radial enemy movement, beam/bomb hit rules, contact damage,
health, score, and restart. Keep the two-enemy cap while testing combat; later
three- and four-enemy levels require the sprite reuse work specified in the plan.

## Local repository

The branch is `main`, with repository-local identity
`mastergray <me@mastergray.com>`. No remote is configured. When a personal GitHub
repository is created, use the `github-mastergray` SSH alias. The initial commit
records the agreed port outline and implementation specification.
