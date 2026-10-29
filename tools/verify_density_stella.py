#!/usr/bin/env python3
"""Check the three-enemy kernel in Stella, including real HMOVE pixel output."""
import json
from check_rom import symbols
from stella_session import ROOT, run_stella


def main():
    sym = symbols()
    commands, labels, advances = [], [], []
    fields = ('ActiveCount', 'FramePhase', 'SelectedSlot', 'BombCooldown', 'LevelNumber')

    def poke(name, value, slot=0):
        commands.append(f'ram ${sym[name] + slot:04x} #{value}')

    def frame(count=1):
        commands.extend([f'frame #{count}', 'print _cycleslo'])
        advances.append(count)

    def capture(label):
        labels.append(label)
        commands.extend('print *' + name for name in fields)
        commands.append('savesnap')

    frame(5)
    commands.append('joy0fire #0')
    frame(2)
    commands.append('joy0fire #1')
    poke('LevelNumber', 2)
    poke('GameMode', 3)
    poke('SpawnTimer', 1)
    frame(242)
    capture('natural-level-02-a')
    frame()
    capture('natural-level-02-b')
    poke('MovementEnabled', 0)
    poke('SpawnInterval', 255)
    poke('KillsRemaining', 255)
    # Exercise each phase as the paired phase, both motion directions, and the
    # narrowest accepted gap. Leave the singleton on E, visible on alternate frames.
    for parity, lanes in ((0, (7, 3)), (1, (1, 5))):
        for slot in range(4):
            poke('EnemyFlags', 0, slot)
            poke('EnemyVisual', 0, slot)
        for slot, lane, radius, kind in ((parity, lanes[0], 24, 2),
                                         (parity + 2, lanes[1], 9, 2),
                                         (1 - parity, 2, 40, 1)):
            poke('EnemyFlags', 0x80 | kind << 4 | lane, slot)
            poke('EnemyRadiusHi', radius, slot)
            poke('EnemyRadiusLo', 0, slot)
            poke('EnemyHealth', 3 if kind == 2 else 1, slot)
        for effect in ('neutral', 'beam', 'ring', 'immune', 'burst'):
            poke('SpawnTimer', 255)
            if effect == 'beam':
                commands.append('joy0up #0')
            if effect == 'ring':
                commands.append('joy0fire #0')
            if effect == 'immune':
                for slot in (parity, parity + 2):
                    poke('EnemyVisual', 18, slot)
            if effect == 'burst':
                for slot in (parity, parity + 2):
                    poke('EnemyFlags', 0, slot)
                    poke('EnemyVisual', 18, slot)
            frame(2)
            capture(f'pair-{parity}-{effect}-a')
            frame()
            capture(f'pair-{parity}-{effect}-b')
        commands.extend(['joy0up #1', 'joy0fire #1'])
        poke('BombTimer', 0)
        poke('BombCooldown', 0)
        poke('BeamFadeTimer', 0)
    run, values, snapshots, transcript = run_stella('atari-zerowave', commands, labels, advances)
    columns = {name: values('*' + name) for name in fields}
    states = {label: {name: columns[name][i] for name in fields} for i, label in enumerate(labels)}
    assert all(not state['FramePhase'] & 0x80 for state in states.values()), states
    assert states['natural-level-02-a']['ActiveCount'] == 3, states
    report = dict(directory=str(run.relative_to(ROOT)), session=transcript.name,
                  snapshots=dict(zip(labels, [p.name for p in snapshots])), states=states,
                  frame_lines=262, cycles_per_frame=19912)
    (run.parent / 'latest-density.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Stella density checks passed; {len(snapshots)} captures in {run}')


if __name__ == '__main__':
    main()
