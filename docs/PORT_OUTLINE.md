# Zero Swarm → Atari 2600: cuts for a playable version

Reviewed 2026-10-26 against `../res`, commit `fb68a689d3fa6346696dd2310e5dd3d167c065a1`. The combat prototype now permits three enemies from level 2; [kernel measurements](KERNEL_TIMING.md) record its timing and remaining limits.

The [implementation specification](IMPLEMENTATION_SPEC.md) defines the native code architecture, game rules, level data, resource budgets, and acceptance tests for this baseline.

## Agreed prototype baseline

Build a small, single-screen survival game: a stationary turret fires one beam shot when the joystick is pushed from center into one of eight directions, and the button detonates a fixed-strength local bomb. Center the stick again before each new beam shot. Enemies approach along those same eight directions. Start with triangles and squares, then add the agreed speed/armor variants and blue diamond described below. Keep health, score, and level progression. Prove the game with two active enemies first, then introduce more simultaneous enemies in later levels as rendering tests establish capacity.

**The largest cuts should be swarm density, freedom of movement, and visual effects.** Those cuts preserve the user's two essential actions: aim/fire with the stick and bomb with the button.

The scope below targets a stock Atari 2600 and one standard joystick. The user has accepted this reduced feature set as the test baseline, with increasing enemy counts in later levels as an explicit goal. Two active enemies is the starting cap, not the intended permanent limit. Exact level thresholds and the final enemy cap remain to be tested.

The accepted effects use a thin beam and a four-step expanding bomb outline.
They alternate display frames while the bomb animates, preserving attack events
and the existing enemy schedule. The ring is cosmetic; bomb damage remains
immediate and limited to a fixed radius. Under the revised controls, each beam
shot starts bright and fades automatically over about 15 updates, even while
the stick remains held. Its direction and hue stay fixed during the fade;
successive shots use the bright palette. Damage occurs once when the shot fires.
A fresh center-to-direction movement fires again and replaces the old fade.
There are no stacked gradient lines or automatic repeat shots.

## What to cut, and what replaces it

| Cut from the proposed port | Keep instead | Why make this cut? |
| --- | --- | --- |
| Smooth 360° mouse aiming and mouse-controlled beam length | Eight directions, one fixed reach clipped to the arena | Matches the joystick and makes aiming and hit tests predictable. |
| Smoothly rotating beam and player polygon | Eight fixed thin rays and a small stationary turret symbol | Vertical/diagonal rays use the one-color-clock ball; horizontal rays retain their two-scanline playfield shape. Diagonals still follow the pixel grid. |
| Free-moving enemies anywhere in the arena | Eight straight approach lanes aligned with the beam | No targets between firing directions; one shared movement rule and simple hit tests. Free-moving enemies are not implemented in the source yet. |
| A large simultaneous swarm from the outset | **Two active enemies for the prototype and opening levels**, with higher caps in later levels after validation | Reduces initial display conflicts and flicker while leaving a clear path to denser encounters. Two is a starting choice, not an Atari hardware maximum. |
| Sweeping filled sectors, lingering trails, transparency, and accumulated effects | One beam shot, with a short automatic cosmetic fade | Removes overlapping graphics and direction history without sacrificing directional firing. |
| Hold-to-charge bomb, growing charge circle, and compression animation | One bomb strength, fired on button press | Simplifies input and keeps the bomb immediate. Charging is technically plausible, but unnecessary for the first game. |
| The 24-ring bomb sequence and smooth circular outlines | One coarse outline expanding through four sizes, a noise burst, and immediate local damage | Precomputed outlines share alternate frames with the beam; no accumulated rings or trails. |
| Shifters, reflectors, reflected shots, and free movement | Triangles, squares, and a blue diamond sharing straight approach lanes, with type-specific speed and health | Keeps weapon choice and enemy variety without extra projectiles or movement off the firing lanes. Shifters and reflectors are only design intentions in the checkout. |
| XP, weapon upgrades, per-type statistics, reports, and elaborate screens | Score, five health marks, bomb-ready indicator, and game over | Focuses the game on survival. These systems are scope cuts, not claims that counters or menus are impossible on Atari. |
| Music and decorative background animation | Brief attack, hit, and death sounds on a plain arena | Attack, rejection, hit, destruction, player-damage, and game-over cues are implemented. Music remains outside scope. |

The controller requires discrete aiming, and the original visual presentation needs substantial reduction. Removing charge, upgrades, or advanced enemy behaviors is a recommendation to contain scope and display demands; their absence is not individually required by the hardware.

## What playing this version would feel like

The player stays in the center. A triangle approaches from the upper left; flicking the stick upper left fires a beam and destroys it. The player centers the stick to prepare another shot. A square approaches from the right; the player lets it enter the bomb's local range and presses the button. The bomb goes off immediately. Another enemy arrives from a different direction, and the cycle accelerates as the score rises.

Target rules, including the enemy revision agreed on 2026-10-27; numerical tuning remains provisional:

- Push from center into any of eight directions to fire once. Holding a direction does not repeat. Return to center before another shot; moving directly between directions does not fire or redirect the existing shot. The shot fades automatically after firing, independent of release.
- All triangles take beam damage only; bombs cannot damage them. All squares take bomb damage only; the beam cannot damage them. Blue diamonds take damage from either attack.
- Bombs deal one damage to each eligible enemy inside a fixed radius around the player. One-health targets die; tougher targets retain their remaining health. The expanding ring does not apply extra hits.
- Press the button once to detonate; holding it does not repeat. Use a short cooldown, initially around one second, and an obvious ready indicator. This cooldown is a new balancing proposal.
- Beam shots and bombs can be triggered together. The shot's graphic alternates with the expanding ring, but its one damage event is processed even on a ring display frame.
- An enemy reaching the center is removed and costs one player health point, except the small magenta triangle, which deals two. Start at five HP, matching the source's initial value; health cannot fall below zero.
- Kills increase score and advance a level's kill quota. Begin with a two-enemy cap; later levels can raise that cap, shorten spawn delays, or increase approach speed within tested limits. At zero HP, show game over; RESET starts again.

Early challenge comes from switching direction and timing the bomb. Later levels should add crowd management through higher simultaneous enemy counts. The compromise is a measured, bounded swarm rather than unrestricted density.

Bomb range must be understandable before pressing the button: fill the square's silhouette when it enters bomb range, and let the final ring size show that same boundary after firing. Keep both cues consistent with the actual hit test. Spawn timing must also leave a reasonable response window; do not routinely schedule bomb-only enemies so that surviving requires a bomb still on cooldown.

These are adaptation rules, not behavior recovered from a completed original game.

## Agreed enemy variants

| Enemy | Appearance | Damage accepted | Health | Movement |
| --- | --- | --- | --- | --- |
| Standard triangle | Existing green triangle | Beam only | 1 | Standard approach speed |
| Fast triangle | Smaller, magenta triangle | Beam only | 1 | Fastest enemy, including compared with the diamond near the turret |
| Standard square | Existing pink square | Bomb only | 1 | Steady approach speed |
| Armored square | Larger square with a visible damaged state | Bomb only | 2 | Slow enough to allow two separate bombs before contact |
| Blue diamond | Blue diamond silhouette | Beam and bomb | 3 initially; tunable | Accelerates as distance to the turret decreases; capped below the fast triangle |

The small magenta triangle still has only one health and dies to one beam hit,
but deals two damage to the player on contact. All other types deal one contact
damage, regardless of their own remaining health.

The armored square takes one damage per detonation and remains immune to beam
shots. A nonlethal hit changes its appearance; only the
final hit awards score and plays the destruction burst.

The diamond takes one damage per beam shot or bomb. Multiple beam hits require
separate joystick flicks, each with a return to center; there is no automatic
beam damage interval. Exact diamond health, speed bands, new score awards, and
spawn weights need playtesting. The weapon vulnerabilities, magenta triangle's
one health, top speed, and double contact damage, and distance-based diamond
acceleration are fixed design requirements.

Attack feedback: the wrong weapon triggers an 18-update bright yellow/orange
flash with a small sideways shake, while keeping the enemy silhouette visible.
A successful nonlethal hit uses a six-update white flash; a kill uses the
existing expanding destruction burst. A beam shot on a square triggers the
immunity cue once; an in-range bomb on a
triangle triggers it once per detonation. Holding the stick, cosmetic fades,
misses, and out-of-range bombs do not trigger the immunity cue. Pulse color and
duration need visual playtesting.

Player damage flashes the background red behind both the HUD and arena, fading
to black over 12 updates. This also plays on fatal damage; reset clears it.
The visual effect does not pause movement or prevent further contact damage.

Introduce variants while retaining the validated two-enemy display cap, then
use the level table to introduce them gradually. Increasing the number of enemy
types is separate from increasing the number visible at once.

## Increasing enemy counts in later levels

The progression goal is more enemies on screen, while retaining the same beam and bomb controls. Introduce the agreed variants before increasing simultaneous enemy counts; shifters and reflectors remain outside scope.

- Opening levels use a cap of two active enemies, giving the player time to learn direction changes and bomb range.
- After the baseline works, test three active enemies, then four. Each count is a validation target, not a promised capability or a fixed level assignment.
- Promote a higher cap into the level progression only when worst-case overlap remains readable, frame timing stays stable, and controls and hit detection remain reliable.
- Keep enemy cap, spawn interval, approach speed, enemy mix, and kill quota in a small level table. Avoid increasing all difficulty settings at once; tune the first level with each new cap separately.
- Once the tested display limit is reached, further levels can vary timing, speed, and enemy mix without exceeding that limit. Preserve enough time for bomb-only enemies to be handled with the cooldown.

Implement enemy storage and update loops as a fixed-size pool with a level-specific active cap. Keep the compiled pool capacity separate from the current level cap, so increasing a tested limit does not require rewriting two hard-coded enemy cases. Size the pool to the RAM budget of each build; this does not assume unlimited spare slots.

## Why enemy count and effects are the expensive parts

The TIA supplies two player graphics, two missiles, a ball, and a coarse playfield. A conventional NTSC scanline gives the CPU 76 cycles. There is no framebuffer, and the console has 128 bytes of RAM shared with the stack. These constraints are documented in Atari's [Stella Programmer's Guide and TIA reference](https://alienbill.com/2600/101/docs/stella.html), reproduced in HTML.

For this design, one player graphic can show the turret and the other can show enemies. Reusing that enemy graphic at different heights is possible, but enemies sharing the same vertical region need special scheduling, another rendering technique, or alternating frames. Even two enemies need an overlap policy. An east/west pair beside the turret is a particularly useful stress test.

That is why the recommendation is to reduce simultaneous threats before promising a swarm. Start with two logical enemies, constrain spawn arrangements where needed, and verify whether any frame alternation is acceptable. Keep logical movement and damage independent of the display schedule. Do not silently hide an enemy that can still hurt the player.

The number of enemy *types* is much less concerning than many enemies visible *at once*. Additional silhouettes, vulnerability rules, and speed profiles provide variety while sharing the same lane coordinates and display schedule. Their graphics and state must still fit the measured ROM/RAM budgets.

A bomb's damage check can be small: compare each enemy's distance from the center against the blast radius. Its original visual effect is a separate, much larger requirement. The prototype retains one coarse animated outline while cutting the original overlapping ring sequence.

## The beam is the one rendering feature to protect

The renderer uses the one-color-clock ball for vertical and diagonal rays, repositioning it each scanline for diagonals. Horizontal rays use the playfield at two scanlines tall. Each ray has one uniform color that changes over time. During a bomb, alternate frames draw its expanding playfield outline. Draw the turret and enemies with player graphics. Keep the HUD in a separate strip and the arena background black.

The playfield is coarse and normally repeats or mirrors its two halves; independent halves need timed updates. A missile alone cannot be stretched into an arbitrary full-width horizontal ray. See the playfield and missile sections of the [Atari reference](https://alienbill.com/2600/101/docs/stella.html).

For this game, the proposed ray therefore needs a custom display kernel, meaning carefully timed code that draws each screen line. It must produce only the chosen direction, with no unintended mirrored shot. Store compact patterns in ROM and keep changing state small; do not allocate a screen-sized RAM buffer.

A stationary center, eight fixed rays, no trails, and four precomputed ring sizes make the kernel tractable. Frame alternation selects the appropriate ball or playfield kernel; both retain the same enemy schedule. The prototype's timing is recorded in the kernel notes. Television readability still needs testing.

Do not replace the beam with ordinary traveling bullets as an automatic optimization: each shot still spans its entire lane immediately. If drawing the ray proves troublesome, try coarser graphics and simpler enemy scheduling first.

## What the source contributes

The checkout is an attack-effects prototype. These source references distinguish actual behavior from planned features:

| Source | What is present |
| --- | --- |
| [Player.gd](../res/scripts/player/Player.gd) and [game_play.json](../res/data/game_play.json) | Mouse-aimed beam, sweep polygons, short-release bomb, hold charge, and animated bomb rings. The functions create visuals; they do not apply damage. |
| [ArenaLevel.tscn](../res/scenes/levels/ArenaLevel.tscn) and [project.godot](../res/project.godot) | A stationary player at the center of a 1280×720 viewport; left/right mouse attack inputs. |
| [game_state.json](../res/data/game_state.json) and [ArenaLevel.gd](../res/scripts/levels/ArenaLevel.gd) | Initial five HP, level/progress fields, and a HUD with placeholder wave counts. |
| [enemy_registry.json](../res/data/enemy_registry.json) and [difficulty_scaling.json](../res/data/difficulty_scaling.json) | Empty enemy definitions, difficulty tiers, and spawn weights. |
| [project.structure.md](../res/docs/project.structure.md) and [data.structure.md](../res/docs/data.structure.md) | Intended triangles, squares, shifters, reflectors, and progression systems; several listed scripts/scenes do not exist. |

The port reuses the attack concept and visual identity. Its enemy behavior, hit
detection, scoring, and game-over logic are new native code. Godot drawing, scene
management, and tween code are replaced by the cartridge's game loop and kernels.

## What to prove before expanding scope

1. **Core display:** centered turret, readable color-cycling beams in all eight directions, one enemy, and a button-triggered expanding bomb outline. Stable timing and responsive controls are the acceptance criteria.
2. **Small combat loop:** two active enemies, both enemy types, fixed bomb radius, cooldown, health, score, and restart. Test same-height enemies, diagonal changes, and simultaneous beam/bomb use.
3. **Variants, readability, and fairness:** verify one shot per joystick flick, the weapon/type matrix, small magenta triangles, two-bomb armor, diamond acceleration and separate shot damage, bomb-range cues, and spawn timing. Check frame timing and RAM/stack use in Stella, then test a real console and joystick.
4. **Later-level density:** stress-test three enemies, then four, including shared-height and center-convergence cases during beam/bomb use. Record the highest acceptable count, then use validated caps in the level table and playtest each transition.

If this version does not fit cleanly, cut in this order: decorative indicators and animation; arbitrary enemy overlap through stricter spawn spacing; then the active enemy count. A one-enemy version is a diagnostic fallback, not the intended finished game. Judge whether it can still produce enough challenge before accepting that reduction.

Preserve the eight-way beam and bomb button throughout those experiments. After testing the accepted ring/beam experiment and completing the reduced game, prioritize higher enemy counts for later levels before further visual effects. Charge bombs, sweep effects, shifters, reflectors, XP, and weapon upgrades remain outside the initial scope; level progression is included.

The playable prototype now implements all five variants, one beam shot per
joystick flick, automatic shot fades, the revised vulnerabilities, vivid immunity
and hit feedback, red player-damage flashes, attack/combat/game-over sounds,
health, score, destruction bursts, and restart. Eight difficulty rows introduce
the variants across the first four levels, then increase spawn frequency and
diamond weight. Kill quotas, one-second level breaks, and an `LV 01..99` HUD are
implemented, retaining health and score between levels. Level 1 allows two enemies;
level 2 onward allows three using vertical sprite reuse and approach-spacing
checks. Bomb recharge is 30 updates (about half a second). At most one bomb-only
enemy is active. CPU/register checks and 22 inspected headless Stella captures
cover the new density kernel. Level balancing, hardware readability, and
four-enemy layouts still need validation. The earlier static display fixtures and held-beam
behavior remain available in a separate diagnostic ROM.
