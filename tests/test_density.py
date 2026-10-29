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

    def test_level_two_reaches_three_and_never_hides_an_enemy_for_two_frames(self):
        m = self.game()
        peak, first_three, previous = 0, None, set()
        last_draw = {}
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
            self.assertLessEqual(len(live), 3)
            peak = max(peak, len(live))
            if len(live) == 3 and first_three is None:
                first_three = frame + 1
            previous = live
        self.assertEqual(peak, 3)
        self.assertLessEqual(first_three, 240)  # within four seconds of level 2

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

    def test_three_target_combat_all_type_combinations_fits_frame_budget(self):
        for kinds in itertools.product((0, 1, 2, 4, 5), repeat=3):
            m = self.game()
            m.poke('MovementEnabled', 0)
            m.poke('SpawnTimer', 255)
            for slot, lane, radius, kind in zip((0, 1, 2), (7, 2, 3), (24, 20, 9), kinds):
                self.enemy(m, slot, lane, radius, kind)
                m.poke('EnemyHealth', 2 if kind == 5 else 3 if kind == 2 else 1, slot)
            self.frame(m, 5, fire=True)
            self.frame(m, 5, fire=True)
            self.assertEqual(m.value('Health'), 5)
