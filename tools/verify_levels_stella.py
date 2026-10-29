#!/usr/bin/env python3
"""Check level boundaries and the numeric HUD in the real Stella cartridge."""
import json

from check_rom import symbols
from stella_session import ROOT, run_stella


def main():
    sym = symbols()
    commands, labels, advances, expected = [], [], [], {}
    fields = ("GameMode", "LevelNumber", "KillsRemaining", "SpawnTimer", "Health",
              "ScoreLo", "ActiveCount", "BeamEvent", "BombEvent", "LevelTypeOffset")

    def poke(name, value, slot=0):
        commands.append(f"ram ${sym[name] + slot:04x} #{value}")

    def frame(count=1):
        commands.extend([f"frame #{count}", "print _cycleslo"])
        advances.append(count)

    def capture(label, **state):
        labels.append(label)
        expected[label] = state
        commands.extend(f"print *{name}" for name in fields)
        commands.append("savesnap")

    frame(5)
    commands.append("joy0fire #0")
    frame(2)
    commands.append("joy0fire #1")
    frame()
    poke("MovementEnabled", 0)
    poke("SpawnTimer", 255)
    capture("level-01", GameMode=1, LevelNumber=1, KillsRemaining=8)
    poke("KillsRemaining", 1)
    poke("Health", 3)
    poke("EnemyFlags", 0x82)
    poke("EnemyHealth", 1)
    poke("EnemyRadiusHi", 40)
    poke("EnemyRadiusLo", 0)
    frame(2)
    commands.append("joy0right #0")
    frame(2)
    capture("quota-cleared-burst", GameMode=1, LevelNumber=1, KillsRemaining=0, ScoreLo=0x10)
    # Displayed burst finishes at 18; wait one more frame to draw the new HUD.
    frame(18)
    capture("break-02", GameMode=3, LevelNumber=2, KillsRemaining=0, SpawnTimer=59, Health=3)
    commands.append("joy0fire #0")
    frame(58)
    capture("break-last-update", GameMode=3, SpawnTimer=1, ActiveCount=0, BeamEvent=0, BombEvent=0)
    frame()
    capture("level-02-entry", GameMode=1, LevelNumber=2, KillsRemaining=10, SpawnTimer=60,
            Health=3, ScoreLo=0x10, ActiveCount=0, BeamEvent=0, BombEvent=0, LevelTypeOffset=8)
    frame(2)
    capture("held-after-break", GameMode=1, BeamEvent=0, BombEvent=0)
    commands.extend(["joy0right #1", "joy0fire #1"])
    frame()
    commands.extend(["joy0right #0", "joy0fire #0"])
    frame(2)
    capture("fresh-attacks", GameMode=1)
    commands.extend(["joy0right #1", "joy0fire #1"])
    # Last-row reuse and decimal carry, with a completed picture of every HUD.
    for old, next_level, name in ((3, 4, "04"), (8, 9, "09"), (9, 0x10, "10"), (0x98, 0x99, "99"), (0x99, 0x99, "99-repeat")):
        poke("LevelNumber", old)
        poke("KillsRemaining", 0)
        poke("SpawnTimer", 255)
        frame(2)
        capture(f"break-{name}", GameMode=3, LevelNumber=next_level, SpawnTimer=59)
        frame(60)
        capture(f"level-{name}", GameMode=1, LevelNumber=next_level,
                LevelTypeOffset=24 if next_level == 4 else 56, Health=3, ScoreLo=0x10)
    # Death beats a completed quota, then RESET must restore level 1.
    poke("KillsRemaining", 0)
    poke("Health", 1)
    poke("EnemyFlags", 0xc6)
    poke("EnemyHealth", 1)
    poke("EnemyRadiusHi", 8)
    frame(2)
    capture("death-before-advance", GameMode=2, LevelNumber=0x99, Health=0)
    commands.extend(["ram SWBCNT #1", "ram SWCHB $FE"])
    frame(2)
    capture("reset-level-01", GameMode=1, LevelNumber=1, KillsRemaining=8, Health=5, ScoreLo=0)

    run, values, snapshots, transcript = run_stella("atari-zerowave", commands, labels, advances)
    columns = {name: values("*" + name) for name in fields}
    assert all(len(column) == len(labels) for column in columns.values())
    states = {label: {name: columns[name][i] for name in fields} for i, label in enumerate(labels)}
    for label, state in expected.items():
        assert all(states[label][name] == value for name, value in state.items()), (label, states[label], state)
    report = dict(directory=str(run.relative_to(ROOT)), session=transcript.name,
                  snapshots=dict(zip(labels, [p.name for p in snapshots])), states=states,
                  frame_lines=262, cycles_per_frame=19912)
    (run.parent / "latest-levels.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Stella level checks passed; {len(snapshots)} captures in {run}")


if __name__ == "__main__":
    main()
