#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 mastergray
# SPDX-License-Identifier: GPL-3.0-only

"""Check wave clears, the level/progress HUD, and paired squares in Stella."""
import json

from check_rom import symbols
from generate_assets import level_quota
from stella_session import ROOT, run_stella


def main():
    sym = symbols()
    palette = json.loads((ROOT / 'config/tuning.json').read_text())['level_background_colors']
    commands, labels, advances, expected = [], [], [], {}
    fields = ('GameMode', 'LevelNumber', 'KillsRemaining', 'SpawnTimer', 'Health',
              'ScoreLo', 'ActiveCount', 'BeamEvent', 'BombEvent', 'LevelTypeOffset',
              'LevelBackground', 'PlayerHitTimer', 'ScoreHi', 'EventSoundId', 'EventSoundTimer')

    def poke(name, value, slot=0):
        commands.append(f'ram ${sym[name] + slot:04x} #{value}')

    def frame(count=1):
        commands.extend([f'frame #{count}', 'print _cycleslo'])
        advances.append(count)

    def capture(label, **state):
        if 'LevelNumber' in state:
            bcd = state['LevelNumber']
            decimal_level = (bcd >> 4) * 10 + (bcd & 15)
            state['LevelBackground'] = palette[(decimal_level - 1) % len(palette)]
        labels.append(label)
        expected[label] = state
        commands.extend(f'print *{name}' for name in fields)
        commands.append('savesnap')

    frame(5)
    capture('title-no-progress', GameMode=0)
    commands.append('joy0fire #0')
    frame(2)
    commands.append('joy0fire #1')
    poke('MovementEnabled', 0)
    poke('SpawnTimer', 255)
    capture('level-01', GameMode=1, LevelNumber=1, KillsRemaining=8)
    for remaining in (6, 4, 2):
        poke('KillsRemaining', remaining)
        frame(2)
        capture(f'wave-progress-{remaining}', KillsRemaining=remaining)
    poke('KillsRemaining', 1)
    poke('Health', 3)
    for slot, flags in ((0, 0x82), (1, 0xd7)):
        poke('EnemyFlags', flags, slot)
        poke('EnemyHealth', 1 if slot == 0 else 2, slot)
        poke('EnemyRadiusHi', 40, slot)
        poke('EnemyRadiusLo', 0, slot)
    frame(2)
    capture('one-kill-left', KillsRemaining=1, ActiveCount=2)
    commands.append('joy0right #0')
    frame(2)  # savesnap displays the completed picture, one update behind RAM
    capture('wave-complete-full-bar', GameMode=3, LevelNumber=1, KillsRemaining=0,
            Health=3, ScoreLo=0x10, ActiveCount=0)
    frame()
    capture('wave-clear-yellow-bursts', GameMode=3, LevelNumber=1, KillsRemaining=0,
            Health=3, ScoreLo=0x10, ActiveCount=0, EventSoundId=sym['SFX_CLEAR'])
    frame(4)
    capture('held-during-clear', GameMode=3, BeamEvent=0, BombEvent=0, ActiveCount=0)
    frame(4)
    capture('wave-clear-flash-gap', GameMode=3, KillsRemaining=0, ActiveCount=0)
    frame(8)
    capture('wave-clear-second-flash', GameMode=3, KillsRemaining=0, ActiveCount=0)
    frame(16)
    capture('level-02-after-clear', GameMode=1, LevelNumber=2, KillsRemaining=12,
            Health=3, ScoreLo=0x10, ActiveCount=0, LevelTypeOffset=8,
            EventSoundId=0, BeamEvent=0, BombEvent=0)
    commands.append('joy0right #1')
    frame()
    commands.extend(['joy0up #0', 'joy0fire #0'])
    frame(2)
    capture('fresh-attacks', GameMode=1, KillsRemaining=12)
    commands.extend(['joy0up #1', 'joy0fire #1'])
    for old, next_level, name in ((3, 4, '04'), (8, 9, '09'), (9, 0x10, '10'),
                                  (0x13, 0x14, '14'), (0x14, 0x15, '15'), (0x15, 0x16, '16'),
                                  (0x98, 0x99, '99'), (0x99, 0x99, '99-repeat')):
        poke('LevelNumber', old)
        poke('KillsRemaining', 0)
        poke('SpawnTimer', 255)
        frame(35)
        capture(f'level-{name}', GameMode=1, LevelNumber=next_level,
                LevelTypeOffset=24 if next_level == 4 else 56, Health=3, ScoreLo=0x10, ActiveCount=0,
                KillsRemaining=level_quota((next_level >> 4) * 10 + (next_level & 15)))
    for remaining in (9, 18, 42, 99):
        poke('KillsRemaining', remaining)
        poke('BombCooldown', 0 if remaining & 1 else 15)
        frame(2)
        capture(f'remaining-{remaining:02}', KillsRemaining=remaining)
    # Hold the completed bar during the wave-clear countdown.
    poke('GameMode', 3)
    poke('SpawnTimer', 60)
    poke('KillsRemaining', 0)
    frame(2)
    capture('remaining-00', KillsRemaining=0)
    poke('GameMode', 1)
    poke('KillsRemaining', 0)
    poke('Health', 1)
    poke('EnemyFlags', 0xc6)
    poke('EnemyHealth', 1)
    poke('EnemyRadiusHi', 8)
    frame(2)
    capture('death-before-advance', GameMode=2, LevelNumber=0x99, Health=0)
    commands.extend(['ram SWBCNT #1', 'ram SWCHB $FE'])
    frame(2)
    capture('reset-level-01', GameMode=1, LevelNumber=1, KillsRemaining=8, Health=5, ScoreLo=0)
    commands.append('ram SWCHB $FF')
    poke('LevelNumber', 3)
    poke('GameMode', 3)
    poke('SpawnTimer', 1)
    frame(2)
    poke('MovementEnabled', 0)
    poke('SpawnTimer', 255)
    for slot, lane, radius, kind in ((0, 0, 24, 4), (1, 1, 40, 1), (2, 4, 24, 5), (3, 5, 9, 0)):
        poke('EnemyFlags', 0x80 | kind << 4 | lane, slot)
        poke('EnemyHealth', 2 if kind == 5 else 1, slot)
        poke('EnemyRadiusHi', radius, slot)
        poke('EnemyRadiusLo', 0, slot)
    frame(2)
    capture('two-squares-a', ActiveCount=4)
    frame()
    capture('two-squares-b', ActiveCount=4)
    commands.append('joy0fire #0')
    frame(2)
    capture('two-squares-first-bomb-a', ActiveCount=3, KillsRemaining=15, ScoreLo=0x25)
    frame()
    capture('two-squares-first-bomb-b', ActiveCount=3, KillsRemaining=15, ScoreLo=0x25)

    # Compare all five silhouettes against each persistent level background.
    commands.append('joy0fire #1')
    for level, color in enumerate(palette, 1):
        poke('LevelNumber', level)
        poke('GameMode', 3)
        poke('SpawnTimer', 1)
        frame(2)
        poke('MovementEnabled', 0)
        poke('KillsRemaining', 255)
        poke('SpawnTimer', 255)
        for slot, lane, radius, kind in ((0, 0, 24, 2), (1, 1, 40, 1),
                                         (2, 4, 24, 0), (3, 5, 40, 4)):
            poke('EnemyFlags', 0x80 | kind << 4 | lane, slot)
            poke('EnemyHealth', 3 if kind == 2 else 1, slot)
            poke('EnemyRadiusHi', radius, slot)
            poke('EnemyRadiusLo', 0, slot)
            poke('EnemyVisual', 0, slot)
        frame(2)
        capture(f'palette-{level}-a', ActiveCount=4, LevelNumber=level, LevelBackground=color)
        frame()
        capture(f'palette-{level}-b', ActiveCount=4, LevelBackground=color)
        poke('EnemyFlags', 0xd5, 3)
        poke('EnemyHealth', 2, 3)
        frame()
        capture(f'palette-{level}-armor-a', ActiveCount=4, LevelBackground=color)
        frame()
        capture(f'palette-{level}-armor-b', ActiveCount=4, LevelBackground=color)
    frame(40)
    capture('level-background-persists', LevelBackground=palette[-1], PlayerHitTimer=0)
    poke('PlayerHitTimer', 12)
    frame(2)
    capture('level-background-damage-priority', ActiveCount=4, LevelBackground=palette[-1])
    frame(12)
    capture('level-background-after-damage', PlayerHitTimer=0, ActiveCount=4, LevelBackground=palette[-1])

    poke('LevelNumber', 3)
    poke('GameMode', 3)
    poke('SpawnTimer', 1)
    frame(2)
    poke('MovementEnabled', 0)
    poke('SpawnTimer', 255)
    poke('KillsRemaining', 255)
    poke('Health', 3)
    poke('ScoreHi', 0x09)
    poke('ScoreLo', 0x90)
    for slot, flags, hp in ((0, 0x82, 1), (1, 0xa6, 3)):
        poke('EnemyFlags', flags, slot)
        poke('EnemyHealth', hp, slot)
        poke('EnemyRadiusHi', 40, slot)
    frame(2)
    capture('health-bonus-before', Health=3, ScoreHi=0x09, ScoreLo=0x90)
    commands.append('joy0right #0')
    frame(2)
    capture('health-bonus-flash-1', Health=4, ScoreHi=0x10, ScoreLo=0, EventSoundId=sym['SFX_HEAL'])
    for label in ('health-bonus-gap', 'health-bonus-flash-2', 'health-bonus-background'):
        frame(8)
        capture(label, Health=4, EventSoundId=sym['SFX_HEAL'])
    frame(8)
    capture('health-bonus-finished', Health=4, EventSoundId=0, EventSoundTimer=0)
    for full in (True, False):
        commands.append('joy0right #1')
        frame()
        poke('Health', 5 if full else 3)
        poke('ScoreHi', 0x19 if full else 0x29)
        poke('ScoreLo', 0x90)
        poke('EnemyFlags', 0x82)
        poke('EnemyHealth', 1)
        poke('EnemyRadiusHi', 40)
        poke('EnemyVisual', 0)
        if full:
            for slot, flags, hp in ((1, 0xa7, 3), (2, 0xd4, 2), (3, 0x95, 1)):
                poke('EnemyFlags', flags, slot)
                poke('EnemyHealth', hp, slot)
                poke('EnemyRadiusHi', 40, slot)
                poke('EnemyRadiusLo', 0, slot)
                poke('EnemyVisual', 0, slot)
            frame(2)
            capture('full-health-clear-before-a', ActiveCount=4, Health=5)
            frame()
            capture('full-health-clear-before-b', ActiveCount=4, Health=5)
        else:
            poke('EnemyFlags', 0x84, 2)
            poke('EnemyHealth', 1, 2)
            poke('EnemyRadiusHi', 8, 2)
        commands.append('joy0right #0')
        frame(2)
        capture('health-bonus-full' if full else 'health-bonus-damage-priority',
                Health=5 if full else 3, ScoreHi=0x20 if full else 0x30, ScoreLo=0,
                EventSoundId=sym['SFX_CLEAR'] if full else sym['SFX_PLAYER_HIT'])
        if full:
            frame()
            capture('full-health-clear-bursts-b', Health=5, ActiveCount=0, ScoreHi=0x20, ScoreLo=0)
            frame(12)
            capture('full-health-clear-embers', Health=5, ActiveCount=0, ScoreHi=0x20, ScoreLo=0)
            frame(8)
            capture('full-health-clear-resumed', Health=5, ActiveCount=1, ScoreHi=0x20, ScoreLo=0)
            # Isolate the following simultaneous-hit fixture from the fresh spawn.
            for slot in range(4):
                poke('EnemyFlags', 0, slot)
                poke('EnemyVisual', 0, slot)
            poke('SpawnTimer', 255)
    commands.extend(['ram SWBCNT #1', 'ram SWCHB $FE'])
    frame(2)
    capture('health-bonus-reset', Health=5, ScoreHi=0, ScoreLo=0, LevelBackground=0, EventSoundId=0)

    run, values, snapshots, transcript = run_stella('atari-zerowave', commands, labels, advances)
    columns = {name: values('*' + name) for name in fields}
    assert all(len(column) == len(labels) for column in columns.values())
    states = {label: {name: columns[name][i] for name in fields} for i, label in enumerate(labels)}
    for label, state in expected.items():
        assert all(states[label][name] == value for name, value in state.items()), (label, states[label], state)
    report = dict(directory=str(run.relative_to(ROOT)), session=transcript.name,
                  snapshots=dict(zip(labels, [p.name for p in snapshots])), states=states,
                  frame_lines=262, cycles_per_frame=19912)
    (run.parent / 'latest-levels.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Stella level checks passed; {len(snapshots)} captures in {run}')


if __name__ == '__main__':
    main()
