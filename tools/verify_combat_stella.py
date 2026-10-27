#!/usr/bin/env python3
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
              "BombCooldown", "EnemyFlags", "EnemyRadiusHi", "EnemyRadiusLo", "BeamEnabled")

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
    poke("EnemySpeed", 0)
    poke("SpawnTimer", 255)
    poke("SpawnInterval", 255)
    for slot in range(4):
        poke("EnemyFlags", 0, slot)
    poke("EnemyFlags", 0xc2)
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
    report = dict(directory=str(run.relative_to(ROOT)), session=transcript.name,
                  snapshots=dict(zip(labels, [p.name for p in snapshots])), states=states,
                  frame_lines=262, cycles_per_frame=19912)
    (run.parent / "latest-combat.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Stella combat checks passed; {len(snapshots)} captures in {run}")


if __name__ == "__main__":
    main()
