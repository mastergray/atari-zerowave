#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 mastergray
# SPDX-License-Identifier: GPL-3.0-only

"""Exercise the playable cartridge in Stella, including natural spawns and combat."""
import argparse
import json

from check_rom import symbols
from stella_session import ROOT, run_stella


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=45)
    args = parser.parse_args()
    sym = symbols()
    commands, labels, advances = [], [], []
    fields = ("GameMode", "Health", "ScoreHi", "ScoreLo", "ActiveCount", "BombCount",
              "BombCooldown", "EnemyFlags", "EnemyRadiusHi", "EnemyRadiusLo", "BeamEnabled",
              "EnemyVisual", "EnemyHealth", "SelectedSlot", "BeamArmed", "BeamDrawDirection", "BeamDrawColor",
              "PlayerHitTimer", "EventSoundId", "EventSoundTimer")

    def frame(count=1):
        commands.extend([f"frame #{count}", "print _cycleslo"])
        advances.append(count)

    def capture(label):
        commands.extend(f"print *{name}" for name in fields)
        commands.append("savesnap")
        labels.append(label)

    def poke(name, value, slot=0):
        commands.append(f"ram ${sym[name] + slot:04x} #{value}")

    frame(5)
    capture("ready")
    commands.append("joy0fire #0")
    frame(2)
    capture("start-held")
    commands.append("joy0fire #1")
    frame(90)
    capture("approach-early")
    frame(90)
    capture("two-enemies-0")
    frame()
    capture("two-enemies-1")
    commands.append("joy0right #0")
    frame(2)
    capture("beam-kill")

    # Deterministic boundary fixtures; enemy positioning, damage and HUD still
    # run through the cartridge. Natural movement/spawning was exercised above.
    poke("MovementEnabled", 0)
    poke("SpawnTimer", 255)
    poke("SpawnInterval", 255)
    for slot in range(4):
        poke("EnemyFlags", 0, slot)
        poke("EnemyVisual", 0, slot)
    poke("EnemyFlags", 0xc2)
    poke("EnemyHealth", 1)
    poke("EnemyRadiusHi", 24)
    poke("EnemyRadiusLo", 1)
    frame(2)
    capture("square-outside")
    commands.append("joy0fire #0")
    frame(2)
    capture("bomb-outside-0")
    frame()
    capture("bomb-outside-1")
    poke("EnemyRadiusLo", 0)
    frame(60)
    capture("square-inside-held")
    commands.append("joy0fire #1")
    frame()
    commands.append("joy0fire #0")
    frame(2)
    capture("bomb-kill-0")
    frame()
    capture("bomb-kill-1")
    commands.append("joy0right #1")
    poke("Health", 1)
    for slot, lane in enumerate((0, 4)):
        poke("EnemyFlags", 0xc0 | lane, slot)
        poke("EnemyHealth", 1, slot)
        poke("EnemyVisual", 0, slot)
        poke("EnemyRadiusHi", 8, slot)
        poke("EnemyRadiusLo", 0, slot)
    frame(2)
    capture("game-over")
    frame(10)
    capture("game-over-held")
    commands.append("joy0fire #1")
    frame()
    commands.append("joy0fire #0")
    frame(2)
    capture("restart-held")
    frame(3)
    commands.extend(["ram SWBCNT #1", "ram SWCHB $FE"])
    frame(2)
    capture("reset-held")
    commands.extend(["ram SWCHB $FF", "ram SWBCNT #0"])
    poke("ScoreHi", 0x12)
    poke("ScoreLo", 0x34)
    poke("Health", 3)
    frame(2)
    capture("hud-1234")
    poke("ScoreHi", 0x98)
    poke("ScoreLo", 0x76)
    poke("Health", 1)
    frame(2)
    capture("hud-9876")

    # Capture both object phases in each of the three burst stages. The RAM
    # timer at VSYNC is one update ahead of the completed picture, hence 17/16,
    # 11/10 and 5/4 represent displayed timers 18/17, 12/11 and 6/5.
    commands.extend(["joy0fire #1", "ram SWBCNT #1", "ram SWCHB $FE"])
    frame()
    commands.extend(["ram SWCHB $FF", "ram SWBCNT #0"])
    frame()
    poke("MovementEnabled", 0)
    poke("SpawnTimer", 255)
    poke("SpawnInterval", 255)

    def burst_fixture(radius, bomb=False):
        for slot, flags in enumerate((0xc2 if bomb else 0x82, 0xc6)):
            poke("EnemyFlags", flags, slot)
            poke("EnemyHealth", 1, slot)
            poke("EnemyRadiusHi", radius, slot)
            poke("EnemyRadiusLo", 0, slot)
            poke("EnemyVisual", 0, slot)
            poke("EnemyAge", 0, slot)
        frame(2)

    def burst_captures(prefix):
        frame()  # attack accepted; completed picture is still pre-attack
        for stage in range(3):
            frame(1 if stage == 0 else 5)
            capture(f"{prefix}-{stage}-0")
            frame()
            capture(f"{prefix}-{stage}-1")
        frame(5)
        capture(f"{prefix}-finished")

    burst_fixture(40)
    capture("burst-beam-before")
    commands.append("joy0right #0")
    burst_captures("burst-beam")
    commands.extend(["joy0right #1", "joy0up #0"])
    burst_fixture(20, bomb=True)
    capture("burst-bomb-before")
    commands.append("joy0fire #0")
    burst_captures("burst-bomb")

    # Variant portraits and complete manual-shot/armor/immunity interactions.
    def fresh():
        commands.extend(["joy0up #1", "joy0down #1", "joy0left #1", "joy0right #1", "joy0fire #1",
                         "ram SWBCNT #1", "ram SWCHB $FE"])
        frame(2)
        commands.extend(["ram SWCHB $FF", "ram SWBCNT #0"])
        frame()
        poke("MovementEnabled", 0)
        poke("SpawnTimer", 255)
        poke("SpawnInterval", 255)

    def target(kind, radius=40):
        poke("EnemyFlags", 0x82 | (kind << 4))
        poke("EnemyHealth", {0: 1, 1: 1, 2: 3, 4: 1, 5: 2}[kind])
        poke("EnemyRadiusHi", radius)
        poke("EnemyRadiusLo", 0)
        poke("EnemyVisual", 0)
        frame(2)

    for kind, name in ((0, "triangle"), (1, "fast"), (2, "diamond"), (4, "square"), (5, "armor")):
        fresh()
        target(kind)
        capture(f"variant-{name}")
        if kind in (4, 5):
            poke("EnemyRadiusHi", 20)
            frame(2)
            capture(f"variant-{name}-in-range")

    fresh()
    target(2)
    commands.append("joy0right #0")
    frame(2)
    capture("diamond-shot-1")
    frame(6)
    capture("diamond-shot-fading")
    frame(10)
    capture("diamond-held-dark")
    commands.extend(["joy0right #1", "joy0up #0"])
    frame(2)
    capture("diamond-direct-turn")
    commands.append("joy0up #1")
    frame()
    commands.append("joy0right #0")
    frame(2)
    capture("diamond-shot-2")
    commands.append("joy0right #1")
    frame()
    commands.append("joy0right #0")
    frame(2)
    capture("diamond-shot-3")

    fresh()
    target(4, 20)
    commands.append("joy0right #0")
    frame(2)
    capture("immune-square")
    frame(6)
    capture("immune-square-orange")
    frame(6)
    capture("immune-square-yellow")
    frame(6)
    capture("immune-square-expired-held")

    fresh()
    target(1, 20)
    commands.append("joy0fire #0")
    frame(2)
    capture("immune-triangle-0")
    frame()
    capture("immune-triangle-1")
    frame(18)
    capture("immune-triangle-expired")

    fresh()
    target(5, 20)
    commands.extend(["joy0fire #0", "joy0right #0"])
    frame(2)
    capture("armor-hit-1")
    frame(8)
    capture("armor-damaged")
    commands.append("joy0fire #1")
    frame()
    commands.append("joy0fire #0")
    frame(2)
    capture("armor-rejected-bomb")
    frame(60)
    capture("armor-held-bomb")
    commands.append("joy0fire #1")
    frame()
    commands.append("joy0fire #0")
    frame(2)
    capture("armor-hit-2")

    fresh()
    poke("Health", 3)
    target(1, 8)
    capture("fast-contact")
    for stage in range(1, 4):
        frame(3)
        capture(f"player-hit-fade-{stage}")
    frame(3)
    capture("player-hit-finished")
    target(1, 8)
    capture("fast-contact-game-over")
    frame(12)
    capture("player-hit-game-over-finished")

    fresh()
    target(1, 8)
    capture("player-hit-before-reset")
    fresh()
    capture("player-hit-reset")

    run, values, snapshots, transcript = run_stella("atari-zerowave", commands, labels, advances, args.timeout)
    columns = {name: values("*" + name) for name in fields}
    assert all(len(v) == len(labels) for v in columns.values()), columns
    states = {label: {name: columns[name][i] for name in fields} for i, label in enumerate(labels)}

    def expect(label, **expected):
        assert all(states[label][name] == value for name, value in expected.items()), (label, states[label], expected)

    expect("ready", GameMode=0, Health=5, ActiveCount=0, BombCount=0, BeamEnabled=0)
    expect("start-held", GameMode=1, BombCount=0, ActiveCount=0)
    expect("approach-early", ActiveCount=1, EnemyFlags=0x82)
    expect("two-enemies-0", ActiveCount=2)
    assert states["approach-early"]["EnemyRadiusHi"] > states["two-enemies-0"]["EnemyRadiusHi"]
    expect("beam-kill", ScoreLo=0x10, ActiveCount=1)
    expect("square-outside", EnemyFlags=0xc2, EnemyRadiusLo=1, ScoreLo=0x10)
    for label in ("bomb-outside-0", "bomb-outside-1", "square-inside-held"):
        expect(label, EnemyFlags=0xc2, BombCount=1, ScoreLo=0x10)
    expect("square-inside-held", BombCooldown=0, EnemyRadiusLo=0)
    for label in ("bomb-kill-0", "bomb-kill-1"):
        expect(label, ActiveCount=0, ScoreLo=0x35, BombCount=2)
    for label in ("game-over", "game-over-held"):
        expect(label, GameMode=2, Health=0, ScoreLo=0x35, BeamEnabled=0)
    for label in ("restart-held", "reset-held"):
        expect(label, GameMode=1, Health=5, ScoreHi=0, ScoreLo=0, ActiveCount=0, BombCount=0)
    expect("hud-1234", ScoreHi=0x12, ScoreLo=0x34, Health=3)
    expect("hud-9876", ScoreHi=0x98, ScoreLo=0x76, Health=1)
    for prefix, active, score in (("burst-beam", 1, 0x10), ("burst-bomb", 0, 0x60)):
        for stage in range(3):
            selected = []
            for phase in (0, 1):
                label = f"{prefix}-{stage}-{phase}"
                expect(label, EnemyFlags=0, EnemyVisual=17 - stage * 6 - phase,
                       ActiveCount=active, ScoreLo=score, Health=5)
                selected.append(states[label]["SelectedSlot"])
            assert set(selected) == {0, 1}, (prefix, stage, selected)
        expect(f"{prefix}-finished", EnemyVisual=0, SelectedSlot=1 if active else 255, ScoreLo=score)
    expect("diamond-shot-1", EnemyHealth=2, ScoreLo=0, BeamEnabled=0)
    expect("diamond-shot-fading", EnemyHealth=2, BeamDrawDirection=2)
    expect("diamond-held-dark", EnemyHealth=2, BeamDrawDirection=255, BeamDrawColor=0)
    expect("diamond-direct-turn", EnemyHealth=2, BeamEnabled=0, BeamDrawDirection=255)
    expect("diamond-shot-2", EnemyHealth=1, ScoreLo=0)
    expect("diamond-shot-3", EnemyHealth=0, EnemyFlags=0, ScoreLo=0x40)
    expect("immune-square", EnemyHealth=1, EnemyVisual=17, ScoreLo=0)
    expect("immune-square-orange", EnemyHealth=1, EnemyVisual=11, ScoreLo=0)
    expect("immune-square-yellow", EnemyHealth=1, EnemyVisual=5, ScoreLo=0)
    expect("immune-square-expired-held", EnemyHealth=1, EnemyVisual=0, ScoreLo=0)
    expect("immune-triangle-0", EnemyHealth=1, EnemyVisual=17, ScoreLo=0)
    expect("immune-triangle-1", EnemyHealth=1, EnemyVisual=16, ScoreLo=0)
    expect("immune-triangle-expired", EnemyHealth=1, EnemyVisual=0, ScoreLo=0)
    expect("armor-hit-1", EnemyHealth=1, EnemyVisual=133, ScoreLo=0)
    for label in ("armor-damaged", "armor-rejected-bomb", "armor-held-bomb"):
        expect(label, EnemyHealth=1, EnemyVisual=0, ScoreLo=0, BombCount=1)
    expect("armor-hit-2", EnemyHealth=0, EnemyFlags=0, ScoreLo=0x50, BombCount=2)
    expect("fast-contact", Health=1, EnemyFlags=0, ScoreLo=0, PlayerHitTimer=11)
    for stage in range(1, 4):
        expect(f"player-hit-fade-{stage}", Health=1, PlayerHitTimer=11 - stage * 3)
    expect("player-hit-finished", Health=1, PlayerHitTimer=0)
    expect("fast-contact-game-over", Health=0, GameMode=2, ScoreLo=0, PlayerHitTimer=11)
    expect("player-hit-game-over-finished", Health=0, GameMode=2, PlayerHitTimer=0)
    expect("player-hit-before-reset", Health=3, PlayerHitTimer=11)
    expect("player-hit-reset", Health=5, PlayerHitTimer=0)
    for label, sound_id, timer in (
        ("ready", 0, 0), ("start-held", 0, 0),
        ("diamond-shot-1", 3, 4), ("diamond-shot-fading", 0, 0),
        ("diamond-shot-2", 3, 4), ("diamond-shot-3", 4, 10),
        ("immune-square", 2, 6), ("immune-square-expired-held", 0, 0),
        ("immune-triangle-0", 2, 6), ("immune-triangle-1", 2, 5),
        ("armor-hit-1", 3, 4), ("armor-rejected-bomb", 0, 0),
        ("armor-hit-2", 4, 10), ("fast-contact", 5, 10),
        ("player-hit-finished", 0, 0), ("fast-contact-game-over", 6, 34),
        ("player-hit-game-over-finished", 6, 22), ("player-hit-reset", 0, 0),
    ):
        expect(label, EventSoundId=sound_id, EventSoundTimer=timer)
    report = dict(directory=str(run.relative_to(ROOT)), session=transcript.name,
                  snapshots=dict(zip(labels, [p.name for p in snapshots])), states=states,
                  frame_lines=262, cycles_per_frame=19912)
    (run.parent / "latest-combat.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Stella combat checks passed; {len(snapshots)} captures in {run}")


if __name__ == "__main__":
    main()
