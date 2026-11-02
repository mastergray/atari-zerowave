# SPDX-FileCopyrightText: 2026 mastergray
# SPDX-License-Identifier: GPL-3.0-only

"""Reconstruct retained TIA sprite rows and P1 motion from real ROM writes."""
import test_prototype as prototype
assets = prototype.assets


def drawn_slots(m):
    first = m.value('SelectedSlot')
    second = (m.value('FramePhase') >> 1) & 7
    return ([] if first == 255 else [first]) + ([second - 1] if second else [])


def sprite(m, slot):
    tuning = assets.load_config()
    flags, timer = m.value('EnemyFlags', slot), m.value('EnemyVisual', slot)
    kind = next(t for t in tuning['enemy_types'] if t['id'] == ((flags >> 4) & 7))
    graphic, color = kind['sprite'], kind['color']
    reinforced = assets.load_levels()['reinforced_diamond']
    if kind['id'] == 2 and m.value('EnemyHealth', slot) >= reinforced['health']:
        color = reinforced['color']
    x = m.value('EnemyX', slot)
    if flags & 0x40 and kind['id'] != 7:
        if m.value('EnemyHealth', slot) == 1:
            graphic = 2
        graphic += m.value('EnemyRadiusHi', slot) * 256 + m.value('EnemyRadiusLo', slot) <= 24 * 256
    if timer:
        if not flags & 0x80:
            stage = (18 - timer) // 6
            graphic, color = 7 + stage, tuning['enemy_burst_colors'][stage]
        elif timer & 0x80:
            color = tuning['colors']['hit']
        else:
            stage = (18 - timer) // 6
            color = tuning['colors']['immune_accent' if stage == 1 else 'immune']
            x += (-2, 2, 0)[stage]
    return m.value('EnemyY', slot) - 2, x, assets.SPRITES[graphic][1], color


def assert_sprites(test, m):
    origin = m.bus.vsync_edges[-1] // 76 * 76
    shapes = [sprite(m, slot) for slot in drawn_slots(m)]
    x = shapes[0][1] if shapes else 76
    motion, grp0, grp1, color, arena_color = 0, 0, 0, 0, 0
    lines = [[] for _ in range(160)]
    for cycle, register, value in m.bus.events:
        line = (cycle - origin) // 76 - m.sym["ARENA_START_LINE"]
        if line < 0:
            if register == 0x11:
                x = 3 * (cycle % 76) - 63
            elif register == 0x21:
                motion = value
            elif register == 0x2a:
                nibble = motion >> 4
                x -= nibble if nibble < 8 else nibble - 16
            elif register == 0x2b:
                motion = 0
            elif register == 0x07:
                color = value
            if register == 0x08:
                arena_color = value
        elif line < 160:
            lines[line].append((cycle % 76, register, value))
    sprite_writes = 0
    for line, writes in enumerate(lines):
        row = line // 2
        for cycle, register, value in writes:
            test.assertNotIn(register, (0x08, 0x20, 0x10, 0x11), 'No arena color/position reset or turret motion')
            if register == 0x2a:
                test.assertEqual(cycle, 3)
                nibble = motion >> 4
                x -= nibble if nibble < 8 else nibble - 16
            elif register == 0x21:
                test.assertGreaterEqual(cycle, 27, 'Motion written too soon after HMOVE')
                motion = value
            elif register == 0x07:
                test.assertEqual(grp1, 0, 'Color changes only in the blank gap')
                color = value
            elif register in (0x1b, 0x1c):
                test.assertEqual(line % 2, 0)
                sprite_writes += 1
                if register == 0x1b:
                    grp0 = value
                    test.assertLessEqual(cycle, 37)
                else:
                    grp1 = value
                    test.assertLessEqual(cycle, 28)
        test.assertEqual(arena_color, m.value('ArenaColor'))
        test.assertEqual(grp0, [0x18, 0x3c, 0x7e, 0x3c][row - 38] if 38 <= row < 42 else 0)
        expected = [(shape[row - top], xpos, tint) for top, xpos, shape, tint in shapes if top <= row < top + 8]
        test.assertLessEqual(len(expected), 1)
        test.assertEqual(grp1, expected[0][0] if expected else 0, (line, drawn_slots(m)))
        if grp1:
            test.assertEqual((x, color), expected[0][1:], (line, drawn_slots(m)))
    test.assertEqual(sprite_writes, 160)
