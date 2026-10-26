# Atari ZeroWave

A native Atari 2600 prototype of the stationary-turret game described in
[the port outline](docs/PORT_OUTLINE.md) and [implementation spec](docs/IMPLEMENTATION_SPEC.md).
The cartridge targets NTSC, uses ordinary 8 KiB F8 banking, and needs no extra RAM.

The current build implements the first controls/display milestone: a centered
turret, eight-way continuous beam, button-triggered bomb flash and sound,
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

## Controls

Use a joystick in the left port. These are Stella's default keyboard bindings;
custom mappings can be changed in its input settings.

| Control | Stella key | Prototype behavior |
| --- | --- | --- |
| Joystick direction | Arrow keys; combine two for diagonals | Fire a beam continuously; release to stop |
| Joystick button | Space | Bomb flash and sound on a fresh press, if ready |
| SELECT | F1 | Advance to the next static test layout |
| RESET | F2 | Return to the first layout and clear bomb state |

The `BOMB` label is green when ready and amber during the 60-update cooldown.
Holding the button produces one bomb; pressing during cooldown does not queue
another. The beam stays on during the six-update flash. RESET with fire held
does not trigger a bomb.

SELECT cycles through N, NE, E, SE, S, SW, W, and NW single-target layouts, then
east/west at the same height, two diagonals near the turret, and a north/south pair.
Triangles are green. Squares are pink and fill in when inside bomb range. The SE
layout demonstrates this cue. These are visual fixtures: firing does not remove
them. Two-target layouts alternate one enemy per frame, so each appears at about
30 Hz while the beam and turret remain present every frame.

## Validation and development

`make check` runs 12 tests covering generated geometry, all joystick combinations,
button edges and exact cooldown boundaries, both startup banks, stack/guard
integrity, fixed frame lengths, kernel write deadlines, and display fairness.
The CPU tests execute the assembled cartridge using py65 and a limited VCS bus;
they do not simulate TIA pixels.

```sh
xvfb-run -a make stella-check
```

This runs the ROM in an isolated Stella window, checks input/bomb state and
262-line timing, and saves 16 TIA snapshots: neutral, all eight directions, bomb,
and both phases of the three overlap layouts. Results are indexed by
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
