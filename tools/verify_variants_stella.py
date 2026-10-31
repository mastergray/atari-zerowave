#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 mastergray
# SPDX-License-Identifier: GPL-3.0-only

"""Capture late enemy silhouettes, beam retaliation, and bomb-first resolution."""
import json

from check_rom import symbols
from stella_session import ROOT, run_stella


def main():
    sym = symbols()
    palette = json.loads((ROOT / 'config/tuning.json').read_text())['level_background_colors']
    commands, labels, advances, expected = [], [], [], {}
    fields = ('GameMode', 'Health', 'ScoreLo', 'ScoreHi', 'ActiveCount',
              'EnemyHealth', 'EnemyVisual', 'PlayerHitTimer', 'EventSoundId')

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

    def enemy(slot, kind, lane, radius):
        for name, value in (('EnemyFlags', 0x80 | kind << 4 | lane),
                            ('EnemyHealth', 3 if kind == 2 else 1),
                            ('EnemyRadiusHi', radius), ('EnemyRadiusLo', 0), ('EnemyVisual', 0)):
            poke(name, value, slot)

    frame(5)
    commands.append('joy0fire #0')
    frame(2)
    commands.append('joy0fire #1')
    # Four silhouettes over both sprite phases, including orange against brown
    # and cyan against teal. Two positions are sampled for square fill/range.
    for level in range(1, len(palette) + 1):
        poke('LevelNumber', level)
        poke('GameMode', 3)
        poke('SpawnTimer', 1)
        frame(2)
        poke('MovementEnabled', 0)
        poke('SpawnTimer', 255)
        poke('KillsRemaining', 255)
        for radius in (40, 24):
            for slot, kind, lane in ((0, 6, 0), (1, 7, 1), (2, 2, 4), (3, 1, 5)):
                enemy(slot, kind, lane, radius)
            frame(2)
            capture(f'palette-{level}-radius-{radius}-a', ActiveCount=4, Health=5)
            frame()
            capture(f'palette-{level}-radius-{radius}-b', ActiveCount=4, Health=5)

    poke('LevelNumber', 8)
    poke('GameMode', 3)
    poke('SpawnTimer', 1)
    frame(2)
    poke('MovementEnabled', 0)
    poke('SpawnTimer', 255)
    poke('KillsRemaining', 255)
    enemy(0, 7, 0, 24)
    frame(2)
    capture('hexagon-before', Health=5, EnemyHealth=1)
    commands.append('joy0up #0')
    frame(2)
    capture('hexagon-retaliation', Health=4, EnemyHealth=1, EventSoundId=sym['SFX_HEX_REJECT'])
    frame(20)
    capture('hexagon-held-beam-expired', Health=4, EnemyHealth=1, EnemyVisual=0, PlayerHitTimer=0)
    commands.append('joy0up #1')
    frame()
    commands.extend(['joy0up #0', 'joy0fire #0'])
    frame(2)
    capture('bomb-before-beam', Health=4, EnemyHealth=0, ActiveCount=0, ScoreLo=0x60,
            EventSoundId=sym['SFX_KILL'])
    frame(6)
    capture('hexagon-destroyed', Health=4, EnemyHealth=0, ActiveCount=0, ScoreLo=0x60)

    run, values, snapshots, transcript = run_stella('atari-zerowave', commands, labels, advances)
    columns = {name: values('*' + name) for name in fields}
    assert all(len(column) == len(labels) for column in columns.values())
    states = {label: {name: columns[name][i] for name in fields} for i, label in enumerate(labels)}
    for label, state in expected.items():
        assert all(states[label][name] == value for name, value in state.items()), (label, states[label], state)
    report = dict(directory=str(run.relative_to(ROOT)), session=transcript.name,
                  snapshots=dict(zip(labels, [p.name for p in snapshots])), states=states,
                  frame_lines=262, cycles_per_frame=19912)
    (run.parent / 'latest-variants.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Stella variant checks passed; {len(snapshots)} captures in {run}')


if __name__ == '__main__':
    main()
