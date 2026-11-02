#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 mastergray
# SPDX-License-Identifier: GPL-3.0-only

"""Capture reinforced enemies, damage feedback and the gold-to-blue shell."""
import json

from check_rom import symbols
from stella_session import ROOT, run_stella


def main():
    sym = symbols()
    palette = json.loads((ROOT / 'config/tuning.json').read_text())['level_background_colors']
    commands, labels, advances, expected = [], [], [], {}
    fields = ('LevelNumber', 'Health', 'ScoreLo', 'ScoreHi', 'ActiveCount',
              'EnemyHealth', 'EnemyVisual', 'EventSoundId')

    def poke(name, value, slot=0):
        commands.append(f'ram ${sym[name] + slot:04x} #{value}')

    def frame(count=1):
        commands.extend([f'frame #{count}', 'print _cycleslo'])
        advances.append(count)

    def capture(label, **state):
        labels.append(label)
        expected[label] = state
        commands.extend(f'print *{name}' for name in fields)
        commands.append('savesnap')

    def load(level):
        commands.extend(['joy0up #1', 'joy0fire #1'])
        poke('LevelNumber', int(str(level), 16))
        poke('GameMode', 3)
        poke('KillsRemaining', 1)
        poke('SpawnTimer', 1)
        poke('MovementEnabled', 0)
        frame()
        poke('SpawnTimer', 255)
        poke('KillsRemaining', 255)
        poke('ScoreHi', 0)
        poke('ScoreLo', 0)

    def enemy(slot, kind, lane, radius, hp):
        for name, value in (('EnemyFlags', 0x80 | kind << 4 | lane),
                            ('EnemyHealth', hp), ('EnemyRadiusHi', radius),
                            ('EnemyRadiusLo', 0), ('EnemyVisual', 0)):
            poke(name, value, slot)

    frame(5)
    commands.append('joy0fire #0')
    frame(2)
    commands.append('joy0fire #1')
    for index, color in enumerate(palette, 1):
        load(25)
        poke('LevelBackground', color)
        for slot, kind, lane, radius, hp in ((0, 2, 0, 40, 4), (1, 3, 1, 40, 2),
                                             (2, 2, 4, 24, 3), (3, 7, 5, 24, 1)):
            enemy(slot, kind, lane, radius, hp)
        frame(2)
        capture(f'palette-{index}-a', ActiveCount=4, Health=5, EnemyHealth=4)
        frame()
        capture(f'palette-{index}-b', ActiveCount=4, Health=5, EnemyHealth=4)

    load(20)
    enemy(0, 3, 0, 20, 2)
    frame(2)
    capture('triangle-intact', LevelNumber=0x20, EnemyHealth=2, ScoreLo=0)
    commands.append('joy0fire #0')
    frame()
    capture('triangle-bomb-rejected', EnemyHealth=2, EventSoundId=sym['SFX_IMMUNE'])
    commands.append('joy0fire #1')
    frame(20)
    commands.append('joy0up #0')
    frame()
    capture('triangle-first-hit', EnemyHealth=1, ScoreLo=0, EventSoundId=sym['SFX_HIT'])
    frame(17)
    capture('triangle-held-shot', EnemyHealth=1, EnemyVisual=0, ScoreLo=0)
    commands.append('joy0up #1')
    frame()
    commands.append('joy0up #0')
    frame()
    capture('triangle-destroyed', EnemyHealth=0, ActiveCount=0, ScoreLo=0x30)

    load(25)
    enemy(0, 2, 0, 20, 4)
    frame(2)
    capture('diamond-gold', LevelNumber=0x25, EnemyHealth=4, ScoreLo=0)
    commands.append('joy0up #0')
    frame()
    capture('diamond-first-hit', EnemyHealth=3, EventSoundId=sym['SFX_HIT'])
    frame(7)
    capture('diamond-blue', EnemyHealth=3, EnemyVisual=0)
    commands.append('joy0up #1')
    frame()
    commands.append('joy0fire #0')
    frame()
    capture('diamond-bomb-hit', EnemyHealth=2, ScoreLo=0)
    commands.append('joy0fire #1')
    frame()
    commands.append('joy0up #0')
    frame()
    capture('diamond-third-hit', EnemyHealth=1, ScoreLo=0)
    commands.append('joy0up #1')
    frame()
    commands.append('joy0up #0')
    frame()
    capture('diamond-destroyed', EnemyHealth=0, ActiveCount=0, ScoreLo=0x40, Health=5)

    run, values, snapshots, transcript = run_stella('atari-zerowave', commands, labels, advances)
    columns = {name: values('*' + name) for name in fields}
    assert all(len(column) == len(labels) for column in columns.values())
    states = {label: {name: columns[name][i] for name in fields} for i, label in enumerate(labels)}
    for label, state in expected.items():
        assert all(states[label][name] == value for name, value in state.items()), (label, states[label], state)
    report = dict(directory=str(run.relative_to(ROOT)), session=transcript.name,
                  snapshots=dict(zip(labels, [p.name for p in snapshots])), states=states,
                  frame_lines=262, cycles_per_frame=19912)
    (run.parent / 'latest-reinforced.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Stella reinforced-enemy checks passed; {len(snapshots)} captures in {run}')


if __name__ == '__main__':
    main()
