# SPDX-FileCopyrightText: 2026 mastergray
# SPDX-License-Identifier: GPL-3.0-only

import math
import itertools
import json
import unittest
from rom_machine import Machine, ROOT
from render_checks import assert_sprites, drawn_slots, assets
import test_prototype as prototype


class DensityTests(unittest.TestCase):
    assert_rendered_pattern = prototype.CartridgeTests.assert_rendered_pattern
    assert_ball_pattern = prototype.CartridgeTests.assert_ball_pattern

    @classmethod
    def setUpClass(cls):
        cls.timings = []

    @classmethod
    def tearDownClass(cls):
        if cls.timings:
            (ROOT / 'build/density-timing.json').write_text(json.dumps(dict(
                frames=len(cls.timings), logic_cycles=[min(t[0] for t in cls.timings), max(t[0] for t in cls.timings)],
                prepare_cycles=[min(t[1] for t in cls.timings), max(t[1] for t in cls.timings)],
                cycles_per_frame=19912), indent=2) + '\n')

    def game(self):
        m = Machine()
        m.boot()
        m.frame(reset=True)
        m.poke('LevelNumber', 2)
        m.poke('GameMode', 3)
        m.poke('SpawnTimer', 1)
        m.frame()
        return m

    def frame(self, m, *args, **kwargs):
        m.bus.events.clear()
        self.assertEqual(m.frame(*args, **kwargs), 262 * 76)
        self.assertLess(m.checkpoints[-1][0], 2000)
        prepare = m.checkpoints[-1][1] - m.bus.vsync_edges[-1] // 76 * 76
        self.assertLess(prepare, 2400)
        self.timings.append((m.checkpoints[-1][0], prepare))
        self.assertEqual(m.bus.ram[0x68:0x70], bytes([0xa5] * 8))
        self.assertGreaterEqual(m.min_sp, 0xef)
        self.assertFalse(m.value('FramePhase') & 0x80, 'Unsafe pair reached renderer')
        assert_sprites(self, m)
        self.assert_rendered_pattern(m, m.value('DisplayPattern'))

    def enemy(self, m, slot, lane, radius, kind=2):
        m.poke('EnemyFlags', 0x80 | kind << 4 | lane, slot)
        m.poke('EnemyRadiusHi', radius, slot)
        m.poke('EnemyRadiusLo', 0, slot)
        m.poke('EnemyHealth', 3 if kind == 2 else 1, slot)
        m.poke('EnemyVisual', 0, slot)

    def test_geometry_has_enough_blank_rows_for_every_allowed_pair_and_shake(self):
        tuning = assets.load_config()
        for upper in (0, 1, 7):
            for lower in (3, 4, 5):
                for r1 in range(8, 64):
                    for r2 in range(8, 64):
                        if max(r1, r2) < tuning['pair_safe_radius']:
                            continue
                        x1, y1 = assets.center(upper, r1, tuning)
                        x2, y2 = assets.center(lower, r2, tuning)
                        blank_rows = y2 - y1 - 8
                        self.assertGreaterEqual(blank_rows, math.ceil((abs(x2 - x1) + 4) / 7) + 1,
                                                (upper, lower, r1, r2))

    def test_pair_movement_both_directions_and_all_effects(self):
        m = self.game()
        m.poke('MovementEnabled', 0)
        for upper in (0, 1, 7):
            for lower in (3, 4, 5):
                for radii in ((9, 24), (24, 9), (63, 24), (24, 63)):
                    for parity in (0, 1):
                        for slot in range(4):
                            m.poke('EnemyFlags', 0, slot)
                            m.poke('EnemyVisual', 0, slot)
                        # Reverse slot ordering on the odd phase to exercise sorting.
                        self.enemy(m, parity if parity == 0 else parity + 2, upper, radii[0])
                        self.enemy(m, parity + 2 if parity == 0 else parity, lower, radii[1])
                        self.enemy(m, 1 - parity, 6, 40)
                        for effect in range(24):
                            m.poke('SpawnTimer', 255)
                            m.poke('FrameCounter', 1 - parity)
                            m.poke('BeamArmed', 0)  # inject visuals, avoid damaging the fixture
                            m.poke('BeamDrawDirection', effect % 8)
                            m.poke('BeamFadeTimer', 15)
                            m.poke('BombTimer', 25 - effect if effect >= 8 else 0)
                            self.frame(m, 8)
                            self.assertEqual(set(drawn_slots(m)), {parity, parity + 2})

    def test_immunity_and_bursts_preserve_paired_sprite_colors_and_positions(self):
        m = self.game()
        m.poke('MovementEnabled', 0)
        self.enemy(m, 0, 7, 24, kind=4)
        self.enemy(m, 1, 2, 30)
        self.enemy(m, 2, 3, 9)
        for elapsed in range(19):
            m.poke('SpawnTimer', 255)
            self.frame(m, 5)
        self.assertEqual(m.value('EnemyHealth'), 1)
        # Two simultaneous bursts retain both descriptors without changing positions.
        for slot in (0, 2):
            m.poke('EnemyFlags', 0, slot)
            m.poke('EnemyVisual', 18, slot)
        seen = set()
        for elapsed in range(18):
            m.poke('SpawnTimer', 255)
            self.frame(m)
            seen.update(drawn_slots(m))
        self.assertEqual(seen, {0, 1, 2})

    def test_later_levels_reach_four_and_never_hide_an_enemy_for_two_frames(self):
        for level, expected in ((2, {0, 1, 4}), (6, {6}), (8, {6, 7})):
            m = self.game()
            m.poke('LevelNumber', level)
            m.poke('GameMode', 3)
            m.poke('SpawnTimer', 1)
            self.frame(m)
            peak, first_four, previous = 0, None, set()
            last_draw, kinds = {}, set()
            for frame in range(1800):
                m.poke('Health', 5)  # keep observing unattended arrivals after contacts
                self.frame(m)
                live = {s for s in range(4) if m.value('EnemyFlags', s) & 0x80 or m.value('EnemyVisual', s)}
                for s in live - previous:
                    last_draw[s] = frame - 1
                for s in drawn_slots(m):
                    last_draw[s] = frame
                for s in live:
                    self.assertLessEqual(frame - last_draw[s], 1)
                self.assertLessEqual(len(live), 4)
                peak = max(peak, len(live))
                if len(live) == 4 and first_four is None:
                    first_four = frame + 1
                previous = live
                kinds.update((m.value('EnemyFlags', s) >> 4) & 7 for s in live)
                self.assertLessEqual(sum(bool(m.value('EnemyFlags', s) & 0x40) for s in live), 2)
            self.assertEqual(peak, 4)
            self.assertLessEqual(first_four, 120)  # within two seconds of entering the level

            self.assertTrue(expected <= kinds, (level, kinds))

    def test_pair_boundaries_account_for_every_type_fraction_and_death_animation(self):
        tuning = assets.load_config()
        early, late = assets.pair_limits(tuning)
        kinds = [t['id'] for t in tuning['enemy_types']]
        full = tuning['spawn_radius'] * 256
        contact = tuning['contact_radius'] * 256
        safe = tuning['pair_safe_radius'] * 256 - 1
        for old in kinds:
            for new in kinds:
                index = old * 8 + new
                for hi in range(8, 64):
                    for fraction in (0, 255):
                        if hi < early[index] or hi >= late[index]:
                            radius = hi * 256 + fraction
                            self.assertTrue(
                                assets.travel_frames(old, radius, contact, tuning) + 18 < assets.travel_frames(new, full, safe, tuning)
                                or assets.travel_frames(new, full, contact, tuning) + 18 < assets.travel_frames(old, radius, safe, tuning))

    def test_four_target_combat_all_type_combinations_fits_frame_budget(self):
        for kinds in itertools.product((0, 1, 2, 4, 5, 6, 7), repeat=4):
            m = self.game()
            m.poke('MovementEnabled', 0)
            m.poke('SpawnTimer', 255)
            for slot, lane, radius, kind in zip((0, 1, 2, 3), (7, 0, 3, 4), (24, 24, 9, 9), kinds):
                self.enemy(m, slot, lane, radius, kind)
                m.poke('EnemyHealth', 2 if kind == 5 else 3 if kind == 2 else 1, slot)
            self.frame(m, 5, fire=True)
            self.frame(m, 5, fire=True)
            self.assertEqual(m.value('Health'), 5)

    def test_approach_audio_and_dense_render_share_vblank_budget(self):
        for radii in itertools.permutations((24, 32, 40, 48)):
            for lanes in ((7, 0, 3, 4), (0, 7, 4, 3)):
                for fire_beam in (False, True):
                    m = self.game()
                    m.poke('MovementEnabled', 0)
                    m.poke('SpawnTimer', 255)
                    for slot, lane, radius in zip(range(4), lanes, radii):
                        self.enemy(m, slot, lane, radius, kind=1)
                        if radius == 24:
                            m.poke('EnemyVisual', 8, slot)  # immunity outlasts its sound
                    self.frame(m, 8 if fire_beam else 0)  # empty east lane, independent shot voice
                    self.frame(m, 8 if fire_beam else 0)
                    self.assertEqual(m.value('EventSoundId'), 0)
                    self.assertGreater(m.bus.tia[0x1a], 0)

    def test_horizontal_partners_remain_drawable_through_approach_and_bursts(self):
        tuning = assets.load_config()
        early, _ = assets.pair_limits(dict(tuning, pair_safe_radius=36))
        kinds = {t['id']: t for t in tuning['enemy_types']}
        contact = tuning['contact_radius'] * 256
        def path(kind, radius):
            result = []
            while radius > contact:
                result.append(radius // 256)
                speed = kinds[kind]['speed']
                if kind == 2:
                    if radius // 256 < 24:
                        speed = tuning['diamond_near_speed']
                    elif radius // 256 < 40:
                        speed = tuning['diamond_mid_speed']
                radius -= speed
            return result
        vertical = {kind: path(kind, 63 * 256) for kind in kinds}
        dx = [assets.center(2, r, tuning)[0] - 80 for r in range(64)]
        diag = [assets.center(3, r, tuning) for r in range(64)]
        for old in kinds:
            for new in kinds:
                for radius in range(9, min(64, early[old * 8 + new])):
                    horizontal = path(old, radius * 256 + 255)
                    for t, old_radius in enumerate(horizontal):
                        # Killing now freezes X for the full burst while the
                        # vertical enemy continues to the smallest safe gap.
                        self.assertLess(t + 18, len(vertical[new]))
                        new_radius = vertical[new][t + 18]
                        x, y = diag[new_radius]
                        blank = y - 40 - 8
                        needed = math.ceil((dx[old_radius] + x - 80 + 4) / 7) + 1
                        self.assertGreaterEqual(blank, needed, (old, new, radius, t))

    def test_fast_horizontal_spawns_keep_both_east_and_west_available(self):
        m = self.game()
        m.poke('MovementEnabled', 0)
        seen = set()
        for seed in range(1, 256):
            for slot in range(4):
                m.poke('EnemyFlags', 0, slot)
                m.poke('EnemyVisual', 0, slot)
            self.enemy(m, 0, 0, 63, kind=0)
            m.poke('RandomState', seed)
            m.poke('SpawnTimer', 1)
            self.frame(m)
            flags = m.value('EnemyFlags', 1)
            if flags & 7 in (2, 6):
                self.assertEqual(flags & 0xf0, 0x90)
                seen.add(flags & 7)
        self.assertEqual(seen, {2, 6})
