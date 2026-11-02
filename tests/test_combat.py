# SPDX-FileCopyrightText: 2026 mastergray
# SPDX-License-Identifier: GPL-3.0-only

import unittest
import json

from rom_machine import Machine, ROOT
import test_prototype as prototype
from render_checks import assert_sprites

assets = prototype.assets

MASKS = (1, 9, 8, 10, 2, 6, 4, 5)


class CombatTests(unittest.TestCase):
    assert_rendered_pattern = prototype.CartridgeTests.assert_rendered_pattern
    assert_ball_pattern = prototype.CartridgeTests.assert_ball_pattern
    assert_arena_colors_and_sprites = assert_sprites

    @classmethod
    def setUpClass(cls):
        cls.timings = []
        cls.stack_bytes = 0

    @classmethod
    def tearDownClass(cls):
        report = dict(frames=len(cls.timings), logic_cycles=[min(t[0] for t in cls.timings), max(t[0] for t in cls.timings)],
                      prepare_cycles=[min(t[1] for t in cls.timings), max(t[1] for t in cls.timings)],
                      stack_bytes=cls.stack_bytes, cycles_per_frame=19912)
        (ROOT / "build/combat-timing.json").write_text(json.dumps(report, indent=2) + "\n")

    def game(self, frozen=True):
        m = Machine()
        m.boot()
        self.frame(m, reset=True)
        if frozen:
            m.poke("MovementEnabled", 0)
            m.poke("SpawnTimer", 255)
            m.poke("KillsRemaining", 255)  # isolate combat fixtures from level completion
        return m

    def finish_wave(self, m, mask=0, **buttons):
        for elapsed in range(46):
            if m.value("GameMode") != 3:
                return elapsed
            self.frame(m, mask, **buttons)
        self.fail("Wave clear did not finish")

    def frame(self, m, mask=0, **buttons):
        m.bus.events.clear()
        self.assertEqual(m.frame(mask, **buttons), 262 * 76)
        self.assertLess(m.checkpoints[-1][0], 2000)
        prepare = m.checkpoints[-1][1] - m.bus.vsync_edges[-1] // 76 * 76
        self.assertLess(prepare, 2400)
        self.timings.append((m.checkpoints[-1][0], prepare))
        type(self).stack_bytes = max(self.stack_bytes, 255 - m.min_sp)
        self.assertEqual(m.bus.ram[0x68:0x70], bytes([0xa5] * 8))
        self.assertGreaterEqual(m.min_sp, 0xef)
        self.assertFalse(m.cpu.p & 8, "Decimal mode leaked out of score routine")

    def enemy(self, m, slot, lane, radius, square=False, fraction=0, kind=None, health=None):
        kind = (4 if square else 0) if kind is None else kind
        definition = next(t for t in assets.load_config()["enemy_types"] if t["id"] == kind)
        m.poke("EnemyFlags", 0x80 | (kind << 4) | lane, slot)
        m.poke("EnemyHealth", definition["health"] if health is None else health, slot)
        m.poke("EnemyRadiusHi", radius, slot)
        m.poke("EnemyRadiusLo", fraction, slot)
        m.poke("EnemyAge", 0, slot)
        m.poke("EnemyVisual", 0, slot)

    def score(self, m):
        hi, lo = m.value("ScoreHi"), m.value("ScoreLo")
        return (hi >> 4) * 1000 + (hi & 15) * 100 + (lo >> 4) * 10 + (lo & 15)

    def set_score(self, m, score):
        m.poke("ScoreHi", (score // 1000) * 16 + score // 100 % 10)
        m.poke("ScoreLo", (score // 10 % 10) * 16 + score % 10)

    def test_score_healing_crosses_each_thousand_exactly_once_with_health_cap(self):
        for threshold in range(1000, 10000, 1000):
            for hp in (1, 4, 5):
                m = self.game()
                m.poke("Health", hp)
                self.set_score(m, threshold - 20)
                self.enemy(m, 0, 2, 40)
                self.frame(m, 8)
                self.assertEqual(m.value("Health"), hp)  # ten points short
                self.frame(m)
                self.enemy(m, 0, 2, 40)
                self.frame(m, 8)
                self.assertEqual(self.score(m), threshold)
                self.assertEqual(m.value("Health"), min(hp + 1, 5))
                self.assert_sound(m, "heal" if hp < 5 else "clear")
                self.frame(m)
                m.poke("Health", 3)
                self.enemy(m, 0, 2, 40)
                self.frame(m, 8)
                self.assertEqual(m.value("Health"), 3)  # no repeat or banked full-HP reward
        for kind in range(8):
            m = self.game()
            m.poke("Health", 2)
            self.set_score(m, 995)
            self.enemy(m, 0, 2, 20, kind=kind, health=1)
            self.frame(m, 8, fire=kind in (4, 5, 6, 7))
            self.assertGreater(self.score(m), 1000)  # crossings need not land exactly
            self.assertEqual(m.value("Health"), 3)
            self.assert_sound(m, "heal")

    def test_score_healing_multikills_and_contacts_are_order_independent(self):
        m = self.game()
        m.poke("Health", 2)
        self.set_score(m, 950)
        for slot, lane in enumerate((0, 1, 4, 5)):
            self.enemy(m, slot, lane, 20, kind=4)
        self.frame(m, fire=True)
        self.assertEqual((self.score(m), m.value("Health")), (1050, 3))
        self.assert_sound(m, "heal")
        for hp in (1, 2, 5):
            for order in (False, True):
                m = self.game()
                m.poke("Health", hp)
                m.poke("KillsRemaining", 1)
                self.set_score(m, 990)
                self.enemy(m, int(order), 2, 40)
                self.enemy(m, int(not order), 6, 8)
                self.enemy(m, 2, 4, 40, kind=2)
                self.frame(m, 8)
                self.assertEqual(self.score(m), 1000)
                self.assertEqual(m.value("Health"), hp if hp > 1 else 0)
                self.assertEqual(m.value("GameMode"), 3 if hp > 1 else 2)
                self.assertEqual(m.value("LevelNumber"), 1)
                self.assert_sound(m, "player_hit" if hp > 1 else "death")
                self.assert_background(m, 0x48)
                self.assertEqual(m.value("EnemyFlags", 2), 0xa4)  # healing back to five must not also clear

    def test_full_health_bonus_clears_every_type_with_bursts_and_no_extra_score(self):
        for kind in range(8):
            m = self.game()
            m.poke("KillsRemaining", 10)
            self.set_score(m, 990)
            for slot, lane in enumerate((0, 1, 4, 5)):
                self.enemy(m, slot, lane, 40, kind=0 if slot == 0 else kind)
            self.frame(m)  # populate the positions the player last saw
            positions = [(m.value("EnemyX", i), m.value("EnemyY", i)) for i in range(4)]
            for elapsed in range(19):
                self.frame(m, 1)
                self.assertEqual((m.value("Health"), self.score(m), m.value("ActiveCount")), (5, 1000, 0))
                self.assertEqual(m.value("KillsRemaining"), 6)
                for slot in range(4):
                    self.assertEqual((m.value("EnemyFlags", slot), m.value("EnemyHealth", slot)), (0, 0))
                    self.assertEqual(m.value("EnemyVisual", slot), max(0, 18 - elapsed))
                    self.assertEqual((m.value("EnemyX", slot), m.value("EnemyY", slot)), positions[slot])
                self.assert_sound(m, "clear", elapsed)
                self.assert_arena_colors_and_sprites(m)
                self.assert_rendered_pattern(m, m.value("DisplayPattern"))
            self.enemy(m, 1, 6, 40, kind=2)
            self.frame(m, 1)  # held input/chime do not repeat the clear
            self.assertEqual((m.value("EnemyFlags", 1), m.value("EnemyHealth", 1)), (0xa6, 3))

    def test_full_health_clear_preserves_old_bursts_and_advances_quota_before_respawn(self):
        for quota in (1, 4):
            m = self.game()
            m.poke("KillsRemaining", quota)
            self.set_score(m, 990)
            for slot, lane, kind in ((0, 0, 0), (1, 1, 5), (2, 4, 2)):
                self.enemy(m, slot, lane, 40, kind=kind)
            m.poke("EnemyVisual", 12, 3)
            m.poke("EnemyX", 40, 3)
            m.poke("EnemyY", 65, 3)
            self.frame(m)
            m.poke("SpawnTimer", 1)
            m.poke("BombCooldown", 7)
            m.poke("BombTimer", 6)
            self.frame(m, 1)
            self.assertEqual((m.value("SpawnTimer"), m.value("BombCooldown"), m.value("BombTimer")), (0 if quota == 1 else 24, 6, 5))
            self.assertEqual((m.value("EnemyVisual", 3), m.value("EnemyX", 3), m.value("EnemyY", 3)), (10, 40, 65))
            self.assertEqual((self.score(m), m.value("ActiveCount")), (1000, 0))
            self.assertEqual((m.value("LevelNumber"), m.value("KillsRemaining")), (1, 0) if quota == 1 else (1, 1))
            if quota == 1:
                self.assertEqual(self.finish_wave(m, 1), 33)
                self.assertEqual((m.value("LevelNumber"), m.value("KillsRemaining")), (2, 12))
            for _ in range(m.value("SpawnInterval") - 1):
                self.frame(m, 1)
                self.assertEqual(m.value("ActiveCount"), 0)
                self.assertEqual(m.value("BeamEvent"), 0)
            self.frame(m, 1)
            self.assertEqual(m.value("ActiveCount"), 1)
            self.assertEqual(self.score(m), 1000)

    def test_full_health_clear_timing_with_movement_bomb_and_level_rollover(self):
        for kind in range(8):
            for level in (0x09, 0x99):
                for radius in (20, 40):
                    for quota in (1, 8):
                        m = self.game(False)
                        m.poke("LevelNumber", level)
                        m.poke("KillsRemaining", quota)
                        m.poke("SpawnTimer", 255)
                        self.set_score(m, 990)
                        for slot, lane in enumerate((0, 1, 4, 5)):
                            self.enemy(m, slot, lane, radius, kind=0 if slot == 0 else kind)
                        self.frame(m)
                        m.poke("SpawnTimer", 1)
                        self.frame(m, 1, fire=True)
                        self.assertEqual((m.value("ActiveCount"), m.value("Health")), (0, 5))
                        self.assertTrue(all(m.value("EnemyFlags", slot) == 0 for slot in range(4)))
                        extra = {4: 25, 6: 35, 7: 60}.get(kind, 0) * 3 if radius == 20 else 0
                        self.assertEqual(self.score(m), 1000 + extra)
                        self.assertEqual(m.value("LevelNumber"), level)
                        self.assertEqual(m.value("GameMode"), 3 if quota == 1 else 1)
                        self.assert_sound(m, "clear")
                        self.assert_arena_colors_and_sprites(m)
                        self.assert_rendered_pattern(m, m.value("DisplayPattern"))

    def test_clear_bonus_has_yellow_flashes_and_distinct_sound_with_damage_priority(self):
        self.assertNotEqual(self.sound_sequence("clear"), self.sound_sequence("heal"))
        palette = assets.load_config()["level_background_colors"]
        for level in range(1, 9):
            m = self.game()
            m.poke("LevelNumber", level)
            m.poke("GameMode", 3)
            m.poke("SpawnTimer", 1)
            self.frame(m)
            m.poke("KillsRemaining", 255)
            self.set_score(m, 990)
            self.enemy(m, 0, 2, 40)
            self.enemy(m, 1, 6, 40, kind=2)
            for elapsed in range(34):
                m.poke("SpawnTimer", 255)  # isolate the cue from replacement spawns
                self.frame(m, 8)
                self.assertEqual((m.value("Health"), self.score(m), m.value("ActiveCount")), (5, 1000, 0))
                if elapsed < 32:
                    self.assert_sound(m, "clear", elapsed)
                else:
                    self.assertEqual((m.value("EventSoundId"), m.bus.tia[0x1a]), (0, 0))
                self.assert_background(m, 0x1a if elapsed < 8 or 16 <= elapsed < 24 else palette[level - 1])
                self.assert_rendered_pattern(m, m.value("DisplayPattern"))
        for action in ("hit", "death", "reset"):
            m = self.game()
            self.set_score(m, 990)
            self.enemy(m, 0, 2, 40)
            self.frame(m, 8)
            self.assert_sound(m, "clear")
            self.assert_background(m, 0x1a)
            if action == "death":
                m.poke("Health", 1)
            self.enemy(m, 1, 6, 8)
            self.frame(m, reset=action == "reset")
            if action == "reset":
                self.assertEqual((m.value("EventSoundId"), m.bus.tia[0x19], m.bus.tia[0x1a]), (0, 0, 0))
                self.assert_background(m, 0)
            else:
                self.assert_sound(m, "death" if action == "death" else "player_hit")
                self.assert_background(m, 0x48)
                for _ in range(12):
                    self.frame(m)
                self.assert_background(m, 0)  # interrupted yellow flashes do not resume

    def test_healing_flash_sound_and_attacks_preserve_each_level_background(self):
        palette = assets.load_config()["level_background_colors"]
        for old_level in range(1, 9):
            m = self.game()
            m.poke("LevelNumber", old_level)
            m.poke("GameMode", 3)
            m.poke("SpawnTimer", 1)
            self.frame(m)
            m.poke("SpawnTimer", 255)
            m.poke("KillsRemaining", 255)
            m.poke("Health", 3)
            self.set_score(m, 990)
            self.enemy(m, 0, 2, 40)
            self.enemy(m, 1, 6, 40, kind=2)
            for elapsed in range(33):
                self.frame(m, 8, fire=True)
                self.assertEqual((m.value("Health"), self.score(m)), (4, 1000))
                self.assertEqual(m.value("LevelNumber"), old_level)
                if elapsed < 32:
                    self.assert_sound(m, "heal", elapsed)
                else:
                    self.assertEqual((m.value("EventSoundId"), m.bus.tia[0x1a]), (0, 0))
                self.assert_background(m, 0xba if elapsed in (*range(8), *range(16, 24)) else palette[(old_level - 1) % 8])
                self.assert_arena_colors_and_sprites(m)
                self.assert_rendered_pattern(m, m.value("DisplayPattern"))

    def test_healing_cue_retriggers_yields_to_damage_and_clears_on_reset(self):
        m = self.game()
        m.poke("Health", 2)
        self.set_score(m, 990)
        self.enemy(m, 0, 2, 40)
        self.enemy(m, 1, 6, 40, kind=1)  # warning returns when the chime ends
        self.frame(m, 8)
        self.assert_sound(m, "heal")
        self.frame(m)
        self.enemy(m, 0, 2, 40)
        self.frame(m, 8)
        self.assert_sound(m, "heal", 2)  # ordinary kill cannot interrupt or restart it
        self.frame(m)
        self.set_score(m, 1990)
        self.enemy(m, 0, 2, 40)
        self.frame(m, 8)
        self.assertEqual(m.value("Health"), 4)
        self.assert_sound(m, "heal")
        for elapsed in range(1, 32):
            self.frame(m)
            self.assert_sound(m, "heal", elapsed)
        self.frame(m)
        self.assert_approach(m)
        for action in ("hit", "death", "reset"):
            m = self.game()
            m.poke("Health", 2)
            self.set_score(m, 990)
            self.enemy(m, 0, 2, 40)
            self.frame(m, 8)
            self.assert_sound(m, "heal")
            if action == "death":
                m.poke("Health", 1)
            self.enemy(m, 1, 6, 8)
            self.frame(m, reset=action == "reset")
            if action == "reset":
                self.assertEqual((m.value("Health"), self.score(m), m.value("EventSoundId")), (5, 0, 0))
                self.assert_background(m, 0)
                self.assertEqual((m.bus.tia[0x19], m.bus.tia[0x1a]), (0, 0))
            else:
                self.assert_sound(m, "death" if action == "death" else "player_hit")
                self.assert_background(m, 0x48)

    def test_score_healing_does_not_repeat_at_saturation_and_rearms_on_restart(self):
        m = self.game()
        m.poke("Health", 2)
        self.set_score(m, 9980)
        for _ in range(5):
            self.enemy(m, 0, 2, 40)
            self.frame(m, 8)
            self.frame(m)
            self.assertEqual(m.value("Health"), 2)
        self.assertEqual(self.score(m), 9999)
        m.poke("Health", 1)
        self.enemy(m, 0, 6, 8)
        self.frame(m)
        self.assertEqual(m.value("GameMode"), 2)
        self.frame(m, fire=True)
        self.frame(m)
        m.poke("Health", 2)
        self.set_score(m, 990)
        self.enemy(m, 0, 2, 40)
        self.frame(m, 8)
        self.assertEqual((self.score(m), m.value("Health")), (1000, 3))
        self.assert_sound(m, "heal")

    def test_power_on_waits_for_a_fresh_start_from_either_bank(self):
        for bank in (0, 1):
            m = Machine(bank)
            m.bus.fire = 0  # held across power-on
            m.boot()
            for _ in range(4):
                self.frame(m, 8, fire=True)
                self.assertEqual(m.value("GameMode"), 0)
                self.assertEqual(m.value("BeamEnabled"), 0)
                self.assertEqual(m.value("ActiveCount"), 0)
            self.frame(m)
            self.frame(m, 8, fire=True)
            self.assertEqual(m.value("GameMode"), 1)
            self.assertEqual(m.value("Health"), 5)
            self.assertEqual(m.value("BombCount"), 0)
            self.assertEqual(m.value("BeamEnabled"), 0)
            self.assertEqual(m.value("SpawnTimer"), 24)
            self.frame(m, 8, fire=True)
            self.assertEqual(m.value("BeamEvent"), 0)
            self.assertEqual(m.value("BombCount"), 0)
            self.frame(m)
            self.frame(m, 8)
            self.assertEqual(m.value("BeamEvent"), 1)

    def test_beam_pierces_triangles_but_not_squares_or_other_lanes(self):
        for lane, mask in enumerate(MASKS):
            m = self.game()
            self.enemy(m, 0, lane, 45, square=True)
            self.enemy(m, 1, lane, 55)
            self.frame(m, mask)
            self.assertEqual(m.value("EnemyFlags", 0), 0xc0 | lane)
            self.assertEqual(m.value("EnemyFlags", 1), 0)
            self.assertEqual(self.score(m), 10)
            self.enemy(m, 1, (lane + 1) & 7, 50)
            self.frame(m, mask)
            self.assertTrue(m.value("EnemyFlags", 1) & 0x80)
        m = self.game()
        for slot in (0, 1):
            self.enemy(m, slot, 2, 40 + slot * 10)
        self.frame(m, 8)
        self.assertEqual(m.value("ActiveCount"), 0)
        self.assertEqual(self.score(m), 20)

    def test_release_afterglow_does_not_damage(self):
        m = self.game()
        self.frame(m, 9)
        self.enemy(m, 0, 1, 40)
        for _ in range(15):
            self.frame(m)
            self.assertEqual(self.score(m), 0)
            self.assertTrue(m.value("EnemyFlags") & 0x80)
        self.frame(m, 9)
        self.assertEqual(self.score(m), 10)

    def test_flick_shot_latches_direction_and_requires_actual_center(self):
        for lane, mask in enumerate(MASKS):
            m = self.game()
            self.enemy(m, 0, lane, 40, kind=2)
            self.frame(m, mask)
            self.assertEqual(m.value("EnemyHealth"), 2)
            self.assertEqual(m.value("BeamEvent"), 1)
            for other in (mask, MASKS[(lane + 1) % 8], 3, 12, 15, mask):
                self.frame(m, other)
                self.assertEqual(m.value("BeamEvent"), 0)
                self.assertEqual(m.value("EnemyHealth"), 2)
                self.assertEqual(m.value("LastDirection"), lane)
                self.assertEqual(m.value("BeamDrawDirection"), lane)
            self.frame(m)
            self.frame(m, mask)
            self.assertEqual(m.value("EnemyHealth"), 1)
            self.frame(m)
            self.frame(m, mask)
            self.assertEqual(m.value("EnemyFlags"), 0)
            self.assertEqual(self.score(m), 40)

    def test_all_input_combinations_shoot_once_and_invalid_inputs_do_not_rearm(self):
        decode = (255, 0, 4, 255, 6, 7, 5, 6, 2, 1, 3, 2, 255, 0, 4, 255)
        for mask, direction in enumerate(decode):
            m = self.game()
            self.frame(m, mask)
            self.assertEqual(m.value("Direction"), direction)
            self.assertEqual(m.value("BeamEvent"), int(direction != 255))
            self.frame(m, mask)
            self.assertEqual(m.value("BeamEvent"), 0)

    def test_shot_fades_while_held_or_released_with_single_sound_envelope(self):
        tuning = assets.load_config()
        for release in (False, True):
            for lane, mask in enumerate(MASKS):
                m = self.game()
                for hue_index, hue in enumerate(tuning["beam_colors"]):
                    for elapsed in range(17):
                        self.frame(m, mask if elapsed == 0 or not release else 0)
                        self.assertEqual(m.value("BeamEvent"), int(elapsed == 0))
                        self.assertEqual(m.value("BeamDrawDirection"), lane if elapsed < 15 else 255)
                        self.assertEqual(m.value("BeamDrawColor"), (hue & 240) | (15 - elapsed) if elapsed < 15 else 0)
                        self.assertEqual(m.bus.tia[0x19], max(0, tuning["beam_sound_frames"] - elapsed))
                        self.assert_rendered_pattern(m, m.value("DisplayPattern"))
                    self.frame(m)  # rearm, including after a held fade
                self.assertEqual(m.value("BeamPalette"), 0)

    def test_weapon_matrix_and_feedback_expiry_for_every_type(self):
        for kind in assets.load_config()["enemy_types"]:
            for weapon in (1, 2):
                m = self.game()
                self.enemy(m, 0, 2, 20, kind=kind["id"])
                self.frame(m, 8 if weapon == 1 else 0, fire=weapon == 2)
                damaged = bool(kind["weapons"] & weapon)
                hp = kind["health"] - damaged
                self.assertEqual(m.value("EnemyHealth"), hp)
                self.assertEqual(m.value("EnemyFlags") != 0, hp > 0)
                self.assertEqual(self.score(m), kind["score"] if hp == 0 else 0)
                self.assertEqual(m.value("EnemyVisual"), 18 if hp == 0 else 134 if damaged else 18)
                for _ in range(6 if damaged else 18):
                    self.assert_arena_colors_and_sprites(m)
                    self.frame(m, 8 if weapon == 1 else 0, fire=weapon == 2)
                    self.assertEqual(m.value("EnemyHealth"), hp)
                if hp:
                    self.assertEqual(m.value("EnemyVisual"), 0)
                    self.assert_arena_colors_and_sprites(m)

    def test_reinforced_spawns_begin_at_twenty_and_twenty_five(self):
        definitions = {t['id']: t for t in assets.load_config()['enemy_types']}
        for level in (19, 20, 24, 25, 99):
            with self.subTest(level=level):
                m = self.game()
                m.poke('LevelNumber', int(str(level), 16))
                m.poke('GameMode', 3)
                m.poke('SpawnTimer', 1)
                self.frame(m)
                seen = set()
                for _ in range(128):
                    for slot in range(4):
                        m.poke('EnemyFlags', 0, slot)
                        m.poke('EnemyVisual', 0, slot)
                    m.poke('SpawnTimer', 1)
                    m.poke('SquareTimer', 0)
                    self.frame(m)
                    kind = (m.value('EnemyFlags') >> 4) & 7
                    seen.add(kind)
                    hp = 4 if kind == 2 and level >= 25 else definitions[kind]['health']
                    self.assertEqual(m.value('EnemyHealth'), hp)
                    self.assertEqual(m.value('SpawnTimer'), 4)
                    self.assert_arena_colors_and_sprites(m)
                self.assertEqual(seen, {0, 1, 2, 6, 7} | ({3} if level >= 20 else set()))

    def test_reinforced_triangle_needs_two_flicks_and_rejects_bombs(self):
        for lane, mask in enumerate(MASKS):
            m = self.game()
            self.enemy(m, 0, lane, 20, kind=3)
            self.frame(m, fire=True)
            self.assertEqual(m.value('EnemyHealth'), 2)
            self.assertEqual(m.value('EnemyVisual'), 18)
            self.assertEqual(m.value('EventSoundId'), m.sym['SFX_IMMUNE'])
            self.frame(m, mask)
            self.assertEqual(m.value('EnemyHealth'), 1)
            self.assertEqual(m.value('EnemyVisual'), 0x80 | 6)
            self.assertEqual(m.value('EventSoundId'), m.sym['SFX_HIT'])
            for _ in range(16):
                self.frame(m, mask)
                self.assertEqual((m.value('EnemyHealth'), self.score(m)), (1, 0))
                self.assert_arena_colors_and_sprites(m)
            self.frame(m)
            self.frame(m, mask)
            self.assertEqual((m.value('EnemyFlags'), m.value('EnemyVisual')), (0, 18))
            self.assertEqual((self.score(m), m.value('KillsRemaining'), m.value('Health')), (30, 254, 5))
            self.assertEqual(m.value('EventSoundId'), m.sym['SFX_KILL'])
        for hp, expected_health, expected_score in ((2, 4, 0), (1, 5, 30)):
            m = self.game()
            self.enemy(m, 0, 2, 8, kind=3, health=hp)
            self.frame(m, 8)
            self.assertEqual((m.value('Health'), self.score(m)), (expected_health, expected_score))

    def test_reinforced_diamond_takes_four_hits_and_loses_gold_shell(self):
        for attacks in (('beam',) * 4, ('bomb',) * 4, ('beam', 'bomb', 'beam', 'bomb')):
            m = self.game()
            self.enemy(m, 0, 2, 20, kind=2, health=4)
            self.frame(m)
            self.assertEqual(m.bus.tia[0x07], 0x1e)
            self.assert_arena_colors_and_sprites(m)
            for damage, attack in enumerate(attacks, 1):
                self.frame(m)  # release/rearm before every distinct attack
                m.poke('BombCooldown', 0)  # cooldown has separate exact-boundary tests
                mask, bomb = (8, False) if attack == 'beam' else (0, True)
                self.frame(m, mask, fire=bomb)
                self.assertEqual(m.value('EnemyHealth'), 4 - damage)
                self.assertEqual(self.score(m), 40 if damage == 4 else 0)
                self.assertEqual(m.value('KillsRemaining'), 254 if damage == 4 else 255)
                for _ in range(6):
                    self.frame(m, mask, fire=bomb)
                    self.assertEqual(m.value('EnemyHealth'), 4 - damage)
                    self.assert_arena_colors_and_sprites(m)
                if damage < 4:
                    self.assertEqual(m.bus.tia[0x07], 0x8e)
            self.assertEqual(m.value('Health'), 5)

    def test_reinforced_colors_and_feedback_on_every_background(self):
        for background in assets.load_config()['level_background_colors']:
            m = self.game()
            m.poke('LevelBackground', background)
            for slot, kind, lane, radius in ((0, 2, 0, 40), (1, 3, 1, 40),
                                              (2, 2, 4, 24), (3, 7, 5, 24)):
                self.enemy(m, slot, lane, radius, kind=kind, health=4 if kind == 2 else None)
            for _ in range(2):
                self.frame(m)
                self.assert_arena_colors_and_sprites(m)
            self.frame(m, 1)  # first diamond sheds its shell; lower one stays gold
            for _ in range(8):
                self.frame(m, 1)
                self.assert_arena_colors_and_sprites(m)
                self.assertEqual((m.value('EnemyHealth', 0), m.value('EnemyHealth', 2)), (3, 4))

    def test_hexagon_retaliates_once_per_fresh_matching_beam(self):
        for slot in range(4):
            for lane, mask in enumerate(MASKS):
                m = self.game()
                self.enemy(m, slot, lane, 40, kind=7)
                self.frame(m, MASKS[(lane + 1) % 8])
                self.assertEqual(m.value("Health"), 5)
                self.assertEqual(m.value("EnemyVisual", slot), 0)
                self.frame(m)
                self.frame(m, mask)
                self.assertEqual((m.value("Health"), m.value("EnemyHealth", slot)), (4, 1))
                self.assertEqual(m.value("EnemyVisual", slot), 18)
                self.assertEqual(self.score(m), 0)
                self.assert_background(m, 0x48)
                self.assert_sound(m, "hex_reject")
                for _ in range(20):
                    self.frame(m, mask)
                    self.assertEqual(m.value("Health"), 4)
                    self.assert_arena_colors_and_sprites(m)
                self.frame(m)  # centering rearms, including while the beam fades
                self.frame(m, mask)
                self.assertEqual(m.value("Health"), 3)

    def test_hexagon_bomb_precedes_retaliation_and_contact(self):
        for radius, fraction in ((8, 0), (24, 0), (24, 1), (40, 0)):
            for hp in (1, 5):
                m = self.game()
                m.poke("Health", hp)
                self.enemy(m, 0, 2, radius, fraction=fraction, kind=7)
                self.frame(m, 8, fire=True)
                killed = radius * 256 + fraction <= 24 * 256
                self.assertEqual(m.value("Health"), hp if killed else hp - 1)
                self.assertEqual(m.value("EnemyHealth"), 0 if killed else 1)
                self.assertEqual(self.score(m), 60 if killed else 0)
                self.assert_sound(m, "kill" if killed else "death" if hp == 1 else "hex_reject")
        for hp in (1, 2, 5):
            for beam in (False, True):
                m = self.game()
                m.poke("Health", hp)
                self.enemy(m, 0, 2, 8, kind=7)
                self.frame(m, 8 if beam else 0)
                expected = max(0, hp - 1 - beam)
                self.assertEqual(m.value("Health"), expected)
                self.assertEqual(m.value("EnemyFlags"), 0)
                self.assertEqual(m.value("GameMode"), 1 if expected else 2)
                self.assertEqual(self.score(m), 0)

    def test_hexagon_retaliation_death_beats_healing_and_wave_advance(self):
        for hp in (1, 4, 5):
            for reverse in (False, True):
                m = self.game()
                self.set_score(m, 990)
                m.poke("Health", hp)
                m.poke("KillsRemaining", 1)
                self.enemy(m, int(reverse), 2, 40, kind=0)
                self.enemy(m, int(not reverse), 2, 24, kind=7)
                self.frame(m, 8)
                self.assertEqual(self.score(m), 1000)
                self.assertEqual(m.value("Health"), hp if hp > 1 else 0)
                self.assertEqual(m.value("LevelNumber"), 1)
                self.assertEqual(m.value("EnemyHealth", int(not reverse)), 1)
                self.assert_sound(m, "hex_reject" if hp > 1 else "death")

    def test_hexagon_busy_update_with_movement_score_and_due_spawn(self):
        for hex_slot in range(4):
            for kind in range(8):
                for radius in (8, 20, 40):
                    for quota in (1, 8):
                        with self.subTest(hex_slot=hex_slot, kind=kind, radius=radius, quota=quota):
                            m = self.game(False)
                            m.poke("LevelNumber", 9)
                            m.poke("GameMode", 3)
                            m.poke("SpawnTimer", 1)
                            self.frame(m)
                            m.poke("KillsRemaining", quota)
                            m.poke("SpawnTimer", 1)
                            self.set_score(m, 990)
                            self.enemy(m, hex_slot, 0, 40, kind=7)
                            self.enemy(m, hex_slot ^ 2, 4, radius, kind=kind)
                            slots = [s for s in range(4) if s % 2 != hex_slot % 2]
                            # Opposite lanes per display pair. Triangle moves exactly
                            # onto the bomb boundary; fast triangle contacts this update.
                            self.enemy(m, slots[0], 1, 24, fraction=32, kind=0)
                            self.enemy(m, slots[1], 5, 8, kind=1)
                            self.frame(m, 1, fire=True)
                            self.assertEqual(m.value("EnemyHealth", hex_slot), 1)
                            self.assertLess(m.value("Health"), 5)
                            self.assert_background(m, 0x48)
                            self.assert_sound(m, "hex_reject" if m.value("Health") else "death")
                            self.assertFalse(m.value("FramePhase") & 0x80)
                            self.assert_arena_colors_and_sprites(m)

    def sound_sequence(self, name):
        sound = next(s for s in assets.load_sounds() if s["name"] == name)
        return [(control, frequency, volume) for frames, control, frequency, volume in sound["segments"]
                for _ in range(frames)]

    def assert_sound(self, m, name, elapsed=0):
        sequence = self.sound_sequence(name)
        self.assertEqual(m.value("EventSoundId"), m.sym["SFX_" + name.upper()])
        self.assertEqual(tuple(m.bus.tia[r] for r in (0x16, 0x18, 0x1a)), sequence[elapsed])
        self.assertEqual(m.value("EventSoundTimer"), len(sequence) - elapsed - 1)

    def assert_approach(self, m):
        cue = assets.load_audio()["fast_approach"]
        radii = [m.value("EnemyRadiusHi", slot) for slot in range(4)
                 if m.value("EnemyFlags", slot) & 0xf0 == 0x90]
        radius = min(radii, default=255)
        self.assertEqual(m.value("EventSoundId"), 0)
        self.assertEqual(m.value("EventSoundTimer"), 0)
        if m.value("GameMode") != 1 or radius > cue["radius"]:
            self.assertEqual(m.bus.tia[0x1a], 0)
        else:
            depth = cue["radius"] - radius
            self.assertEqual(tuple(m.bus.tia[r] for r in (0x16, 0x18, 0x1a)),
                             (cue["control"], cue["frequency_start"] + depth // 2,
                              cue["volume_start"] + depth // 8))

    def test_approach_warning_only_for_live_magenta_triangles_in_range(self):
        for slot in range(4):
            for kind in range(8):
                m = self.game()
                for radius in (63, 49, 48, 24, 9):
                    self.enemy(m, slot, 2, radius, kind=kind)
                    self.frame(m)
                    self.assert_approach(m)
                m.poke("EnemyFlags", 0, slot)
                m.poke("EnemyVisual", 18, slot)
                self.frame(m)
                self.assert_approach(m)  # a destruction burst must never whistle

    def test_approach_warning_tracks_nearest_fast_triangle_independent_of_slot(self):
        for slots in ((0, 1), (1, 0), (2, 3), (3, 2)):
            m = self.game()
            self.enemy(m, slots[0], 0, 48, kind=1)
            self.enemy(m, slots[1], 4, 20, kind=1)
            self.frame(m)
            self.assert_approach(m)
            # Removing the closest threat resumes at the survivor's current range.
            m.poke("EnemyFlags", 0, slots[1])
            self.frame(m)
            self.assert_approach(m)
            self.assertEqual(m.bus.tia[0x18], assets.load_audio()["fast_approach"]["frequency_start"])
            self.frame(m, 8)  # independent beam on an empty lane
            self.assertEqual(m.bus.tia[0x19], 5)
            self.assert_approach(m)

    def test_approach_warning_yields_to_every_combat_cue_and_resumes_at_current_distance(self):
        for name in ("bomb", "immune", "hit", "kill", "player_hit", "hex_reject", "death"):
            m = self.game()
            self.enemy(m, 0, 6, 40, kind=1)
            self.frame(m)
            self.assert_approach(m)
            if name in ("immune", "hit", "kill", "hex_reject"):
                self.enemy(m, 1, 2, 40, kind={"immune": 4, "hit": 2, "kill": 0, "hex_reject": 7}[name])
            elif name in ("player_hit", "death"):
                m.poke("Health", 1 if name == "death" else 5)
                self.enemy(m, 1, 2, 8)
            for elapsed in range(len(self.sound_sequence(name))):
                self.frame(m, 8 if name in ("immune", "hit", "kill", "hex_reject") else 0, fire=name == "bomb")
                self.assert_sound(m, name, elapsed)
                m.poke("EnemyRadiusHi", 20, 0)  # approach continues while warning is masked
            self.frame(m)
            self.assert_approach(m)
            if name != "death":
                self.assertGreater(m.bus.tia[0x1a], 0)

    def test_approach_warning_stops_on_kill_contact_reset_and_outside_play(self):
        for outcome in ("kill", "contact", "reset"):
            m = self.game()
            self.enemy(m, 0, 2, 20, kind=1)
            self.frame(m)
            self.assert_approach(m)
            if outcome == "contact":
                m.poke("EnemyRadiusHi", 8)
            self.frame(m, 8 if outcome == "kill" else 0, reset=outcome == "reset")
            for _ in range(18):
                self.frame(m)
            self.assert_approach(m)
            self.assertEqual(m.bus.tia[0x1a], 0)
        for mode in (0, 2, 3):
            m = self.game()
            self.enemy(m, 0, 2, 20, kind=1)
            self.frame(m)
            m.poke("GameMode", mode)
            self.frame(m)
            self.assert_approach(m)
            self.assertEqual(m.bus.tia[0x1a], 0)

    def test_natural_fast_approach_descends_and_grows_louder_until_contact(self):
        m = self.game()
        m.poke("MovementEnabled", 1)
        self.enemy(m, 0, 2, 63, kind=1)
        audible = []
        for _ in range(176):
            self.frame(m)
            if m.value("EnemyFlags") & 0x80:
                self.assert_approach(m)
                if m.bus.tia[0x1a]:
                    audible.append((m.bus.tia[0x18], m.bus.tia[0x1a]))
            else:
                self.assert_sound(m, "player_hit")
                break
        self.assertEqual(m.value("Health"), 3)
        self.assertGreater(len(audible), 120)
        self.assertEqual(audible[0], (4, 2))
        self.assertEqual(audible[-1], (24, 7))
        self.assertTrue(all(a[0] <= b[0] and a[1] <= b[1] for a, b in zip(audible, audible[1:])))

    def test_audio_envelopes_follow_real_combat_and_finish_in_silence(self):
        for name in ("bomb", "immune", "hit", "kill", "player_hit", "hex_reject", "death"):
            with self.subTest(sound=name):
                m = self.game()
                if name in ("immune", "hit", "kill", "hex_reject"):
                    self.enemy(m, 0, 2, 40, kind={"immune": 4, "hit": 2, "kill": 0, "hex_reject": 7}[name])
                elif name in ("player_hit", "death"):
                    m.poke("Health", 1 if name == "death" else 5)
                    self.enemy(m, 0, 6, 8)
                for elapsed in range(len(self.sound_sequence(name))):
                    self.frame(m, 8, fire=name == "bomb")
                    self.assert_sound(m, name, elapsed)
                    self.assertEqual(m.bus.tia[0x19], 0 if name == "death" else max(0, 5 - elapsed))
                for _ in range(3):
                    self.frame(m, 8, fire=name == "bomb")
                    self.assertEqual(m.value("EventSoundId"), 0)
                    self.assertEqual(m.bus.tia[0x1a], 0)

    def test_audio_same_update_priority_does_not_depend_on_enemy_order(self):
        # Each fixture is (kind, lane, radius); actual outcomes drive requests.
        cases = [
            ([(4, 2, 40), (2, 2, 40)], False, 5, "hit"),
            ([(4, 2, 40), (0, 2, 40)], False, 5, "kill"),
            ([(5, 6, 20), (4, 0, 20)], True, 5, "kill"),
            ([(4, 6, 8), (0, 2, 40)], False, 5, "player_hit"),
            ([(4, 6, 8), (0, 2, 40)], False, 1, "death"),
            ([(7, 2, 40), (2, 2, 40)], False, 5, "hex_reject"),
            ([(7, 2, 40), (0, 2, 40)], False, 5, "hex_reject"),
            ([(7, 2, 40), (4, 6, 8)], False, 5, "hex_reject"),
            ([(7, 2, 40), (4, 6, 8)], False, 1, "death"),
        ]
        for targets, bomb, health, sound in cases:
            for order in (targets, targets[::-1]):
                m = self.game()
                m.poke("Health", health)
                for slot, (kind, lane, radius) in enumerate(order):
                    self.enemy(m, slot, lane, radius, kind=kind)
                self.frame(m, 8, fire=bomb)
                self.assert_sound(m, sound)
        # Bomb damage wins over simultaneous beam immunity on the same target.
        m = self.game()
        self.enemy(m, 0, 2, 20, kind=5)
        self.frame(m, 8, fire=True)
        self.assert_sound(m, "hit")
        # Bombing a triangle must make the rejection audible, not just detonate.
        m = self.game()
        self.enemy(m, 0, 2, 20)
        self.frame(m, fire=True)
        self.assert_sound(m, "immune")

    def test_audio_preemption_retrigger_and_dropped_events_are_not_queued(self):
        m = self.game()
        self.frame(m, fire=True)
        self.assert_sound(m, "bomb")
        self.enemy(m, 0, 2, 40, kind=2)
        self.frame(m, 8)
        self.assert_sound(m, "hit")
        self.frame(m)  # rearm
        self.frame(m, 8)
        self.assert_sound(m, "hit")  # equal-priority hit restarts its envelope
        self.frame(m)
        self.frame(m, 8)
        self.assert_sound(m, "kill")
        self.enemy(m, 1, 6, 8)
        self.frame(m)
        self.assert_sound(m, "player_hit")
        self.enemy(m, 1, 2, 40, kind=4)
        self.frame(m, 8)  # lower priority immunity dropped; beam still audible
        self.assert_sound(m, "player_hit", 1)
        self.assertEqual(m.bus.tia[0x19], 5)
        for elapsed in range(2, len(self.sound_sequence("player_hit"))):
            self.frame(m, 8)
            self.assert_sound(m, "player_hit", elapsed)
        self.frame(m, 8)
        self.assertEqual(m.bus.tia[0x1a], 0, "Dropped immunity must not play later")
        self.frame(m)
        self.frame(m, 8)
        self.assert_sound(m, "immune")

    def test_hexagon_audio_interrupts_retriggers_and_clears_without_false_cues(self):
        self.assertEqual(len(self.sound_sequence("hit")), 8)
        self.assertEqual(len(self.sound_sequence("hex_reject")), 12)
        for other in ("immune", "hit", "player_hit", "kill"):
            self.assertNotEqual(self.sound_sequence("hex_reject"), self.sound_sequence(other))
        for prior in ("bomb", "immune", "hit", "kill", "heal", "clear", "player_hit"):
            m = self.game()
            m.poke("EventSoundId", m.sym["SFX_" + prior.upper()])
            m.poke("EventSoundTimer", len(self.sound_sequence(prior)))
            self.enemy(m, 0, 2, 40, kind=7)
            self.frame(m, 8)
            self.assert_sound(m, "hex_reject")
            self.assertEqual(m.value("Health"), 4)
            self.frame(m)
            self.frame(m, 8)
            self.assert_sound(m, "hex_reject")  # fresh shot restarts the cue
            self.assertEqual(m.value("Health"), 3)
            self.enemy(m, 1, 6, 8)
            self.frame(m, 8)
            self.assert_sound(m, "hex_reject", 1)  # ordinary contact cannot mask it
            self.frame(m, 8, reset=True)
            self.assertEqual((m.value("EventSoundId"), m.value("EventSoundTimer")), (0, 0))
            self.assertEqual((m.bus.tia[0x19], m.bus.tia[0x1a]), (0, 0))
        m = self.game()
        self.enemy(m, 0, 2, 40, kind=7)
        self.frame(m, 4)  # missed lane makes only the independent beam sound
        self.assertEqual(m.value("EventSoundId"), 0)
        self.frame(m, fire=True)  # out-of-range bomb does not provoke retaliation
        self.assert_sound(m, "bomb")
        self.assertEqual(m.value("Health"), 5)

    def test_audio_multikills_and_contacts_coalesce_without_replaying(self):
        for kind, radius, bomb, sound, health in [(4, 20, True, "kill", 5), (1, 8, False, "player_hit", 1)]:
            m = self.game()
            for slot, lane in enumerate((0, 4)):
                self.enemy(m, slot, lane, radius, kind=kind)
            self.frame(m, fire=bomb)
            self.assert_sound(m, sound)
            self.assertEqual(m.value("Health"), health)
            for elapsed in range(1, len(self.sound_sequence(sound))):
                self.frame(m, fire=bomb)
                self.assert_sound(m, sound, elapsed)
            self.frame(m, fire=bomb)
            self.assertEqual(m.bus.tia[0x1a], 0)

    def test_audio_no_false_hit_cues_or_queued_bombs(self):
        m = self.game()
        self.enemy(m, 0, 6, 24, fraction=1, kind=4)
        self.frame(m, 8, fire=True)  # wrong lane, outside radius: only weapons
        self.assert_sound(m, "bomb")
        for elapsed in range(1, 6):
            self.frame(m, 8)
            self.assert_sound(m, "bomb", elapsed)
        self.frame(m, 8, fire=True)  # cooldown rejects a fresh bomb press
        self.assertEqual(m.bus.tia[0x1a], 0)
        self.assertEqual(m.value("SoundRequest"), 0)
        for _ in range(60):
            self.frame(m, 8, fire=True)  # no repetition or delayed queue
            self.assertEqual(m.bus.tia[0x1a], 0)
        self.assertEqual(m.value("BombCount"), 1)
        # A shot that prevents a contact emits destruction, not player damage.
        m = self.game()
        self.enemy(m, 0, 2, 8)
        self.frame(m, 8)
        self.assert_sound(m, "kill")
        self.assertEqual(m.value("Health"), 5)

    def test_audio_reset_and_restart_interrupt_every_voice(self):
        for death in (False, True):
            for reset in (False, True) if death else (True,):
                m = self.game()
                if death:
                    m.poke("Health", 1)
                    self.enemy(m, 0, 6, 8)
                self.frame(m, 8, fire=not death)
                self.assert_sound(m, "death" if death else "bomb")
                self.frame(m, 8, reset=reset, fire=True)
                self.assertEqual(m.value("GameMode"), 1)
                self.assertEqual(m.value("BombCount"), 0)
                for name in ("ShotSoundTimer", "EventSoundTimer", "EventSoundId", "SoundRequest"):
                    self.assertEqual(m.value(name), 0)
                self.assertEqual((m.bus.tia[0x19], m.bus.tia[0x1a]), (0, 0))
                self.frame(m, 8, fire=True)
                self.assertEqual((m.bus.tia[0x19], m.bus.tia[0x1a]), (0, 0))

    def test_diamond_combined_attacks_and_feedback_priority(self):
        for hp in (1, 2, 3):
            m = self.game()
            self.enemy(m, 0, 2, 20, kind=2, health=hp)
            self.frame(m, 8, fire=True)
            self.assertEqual(m.value("EnemyHealth"), max(0, hp - 2))
            self.assertEqual(self.score(m), 40 if hp <= 2 else 0)
            self.assertEqual(m.value("EnemyVisual"), 18 if hp <= 2 else 134)
            self.assert_arena_colors_and_sprites(m)
        m = self.game()
        self.enemy(m, 0, 2, 20, kind=5)
        self.frame(m, 8, fire=True)
        self.assertEqual(m.value("EnemyHealth"), 1)
        self.assertEqual(m.value("EnemyVisual"), 134, "Real bomb damage wins over beam immunity")
        self.assert_arena_colors_and_sprites(m)

    def test_armored_square_two_separate_bombs_and_visible_armor_loss(self):
        m = self.game()
        self.enemy(m, 0, 2, 24, kind=5)
        self.frame(m)
        self.assert_arena_colors_and_sprites(m)
        self.frame(m, fire=True)
        self.assertEqual(m.value("EnemyHealth"), 1)
        self.assertEqual(self.score(m), 0)
        self.assert_arena_colors_and_sprites(m)
        for _ in range(29):
            self.frame(m, fire=True)
            self.assertEqual(m.value("EnemyHealth"), 1)
        self.frame(m)
        self.frame(m, fire=True)
        self.assertEqual(m.value("EnemyFlags"), 0)
        self.assertEqual(self.score(m), 50)

    def test_bomb_boundary_and_no_feedback_for_out_of_range_variants(self):
        for kind in range(8):
            m = self.game()
            self.enemy(m, 0, 2, 24, kind=kind)
            self.enemy(m, 1, 6, 24, fraction=1, kind=kind)
            before = m.value("EnemyHealth")
            self.frame(m, fire=True)
            self.assertEqual(m.value("EnemyHealth"), before - (kind in (2, 4, 5, 6, 7)))
            self.assertEqual(m.value("EnemyHealth", 1), before)
            self.assertEqual(m.value("EnemyVisual", 1), 0)
            self.assert_arena_colors_and_sprites(m)

    def test_type_speeds_acceleration_boundaries_and_armor_bomb_window(self):
        tuning = assets.load_config()
        for kind in tuning["enemy_types"]:
            for radius in (63, 41, 40, 39, 25, 24, 23, 9):
                m = self.game(False)
                m.poke("SpawnTimer", 255)
                self.enemy(m, 0, 2, radius, kind=kind["id"])
                speed = kind["speed"]
                if kind["id"] == 2:
                    speed = 64 if radius < 24 else 48 if radius < 40 else 32
                self.frame(m)
                self.assertEqual(m.value("EnemyRadiusHi") * 256 + m.value("EnemyRadiusLo"), radius * 256 - speed)
                self.assert_arena_colors_and_sprites(m)
        m = self.game(False)
        m.poke("SpawnTimer", 255)
        self.enemy(m, 0, 2, 24, kind=5)
        # Give the player half a second to react, then the full recharge period.
        for _ in range(30):
            self.frame(m)
        self.frame(m, fire=True)
        for _ in range(29):
            self.frame(m)
        self.frame(m, fire=True)
        self.assertEqual(self.score(m), 50)
        self.assertEqual(m.value("Health"), 5)

    def test_fast_triangle_double_contact_damage_saturates_and_can_be_prevented(self):
        for hp in (1, 2, 3, 5):
            m = self.game()
            m.poke("Health", hp)
            self.enemy(m, 0, 2, 8, kind=1)
            self.frame(m, fire=True)  # bomb cannot rescue the player from a triangle
            self.assertEqual(m.value("Health"), max(0, hp - 2))
            self.assertEqual(m.value("EnemyVisual"), 0)
            self.assertEqual(self.score(m), 0)
        m = self.game()
        self.enemy(m, 0, 2, 8, kind=1)
        self.frame(m, 8)
        self.assertEqual(m.value("Health"), 5)
        self.assertEqual(self.score(m), 20)
        m = self.game()
        self.enemy(m, 0, 2, 8, kind=2)
        self.frame(m, 8)
        self.assertEqual(m.value("Health"), 4, "Nonlethal beam hit does not prevent contact")
        self.assertEqual(self.score(m), 0)

    def test_all_variant_silhouettes_and_feedback_with_survivor_on_both_phases(self):
        for kind in range(8):
            for lane, mask in enumerate(MASKS):
                m = self.game()
                self.enemy(m, 0, lane, 63, kind=kind)
                self.enemy(m, 1, (lane + 4) % 8, 24, kind=5)
                for feedback in (0, 6, 134):
                    m.poke("EnemyVisual", feedback)
                    for _ in range(2):
                        self.frame(m)
                        self.assert_arena_colors_and_sprites(m)
                        self.assertFalse(m.value("FramePhase") & 0x80)

    def test_immunity_feedback_lasts_three_stages_without_moving_combat_position(self):
        for phase in (0, 1):
            m = self.game()
            m.poke("FrameCounter", phase)
            self.enemy(m, 0, 2, 20, kind=4)
            self.enemy(m, 1, 6, 40, kind=2)
            appearances = [[], [], []]
            for elapsed in range(19):
                self.frame(m, 8)
                self.assertEqual(m.value("EnemyVisual"), max(0, 18 - elapsed))
                self.assertEqual(m.value("EnemyHealth"), 1)
                self.assertEqual(self.score(m), 0)
                x, y = assets.center(2, 20, assets.load_config())
                self.assertEqual((m.value("EnemyX"), m.value("EnemyY")), (x - 4, y - 2))
                self.assert_arena_colors_and_sprites(m)
                if elapsed < 18:
                    appearances[elapsed // 6].append(m.value("SelectedSlot"))
                    if m.value("SelectedSlot") == 0:
                        self.assertEqual(m.bus.tia[0x07], (30, 46, 30)[elapsed // 6])
            self.assertTrue(all(slots.count(0) == slots.count(1) == 3 for slots in appearances))

    def assert_background(self, m, expected):
        origin = m.bus.vsync_edges[-1] // 76 * 76
        writes = [(cycle, value) for cycle, register, value in m.bus.events if register == 0x09]
        self.assertEqual([value for _, value in writes], [expected])
        self.assertLess(writes[0][0] - origin, 40 * 76, "Background must be set before the HUD")
        self.assertEqual(m.bus.tia[0x09], expected)

    def test_player_damage_flashes_whole_picture_and_expires_after_game_over(self):
        for hp in (1, 5):
            m = self.game()
            m.poke("Health", hp)
            self.enemy(m, 0, 0, 8)
            self.enemy(m, 1, 2, 40, kind=2)
            for elapsed in range(13):
                self.frame(m)
                self.assertEqual(m.value("PlayerHitTimer"), max(0, 12 - elapsed))
                self.assertEqual(m.value("Health"), hp - 1)
                self.assertEqual(m.value("GameMode"), 2 if hp == 1 else 1)
                self.assert_background(m, (72, 70, 68, 66)[elapsed // 3] if elapsed < 12 else 0)
                self.assert_arena_colors_and_sprites(m)

    def test_player_flash_retrigger_reset_and_simultaneous_contacts(self):
        m = self.game()
        self.enemy(m, 0, 0, 8)
        self.frame(m)
        for _ in range(6):
            self.frame(m)
        self.enemy(m, 0, 0, 8, kind=1)
        self.frame(m)
        self.assertEqual(m.value("Health"), 2)
        self.assertEqual(m.value("PlayerHitTimer"), 12)
        self.assert_background(m, 72)
        self.frame(m, reset=True)
        self.assertEqual(m.value("PlayerHitTimer"), 0)
        self.assert_background(m, 0)
        self.enemy(m, 0, 0, 8, kind=1)
        self.enemy(m, 1, 4, 8, kind=1)
        self.frame(m)
        self.assertEqual(m.value("Health"), 1)
        self.assertEqual(m.value("PlayerHitTimer"), 12)
        self.assert_background(m, 72)

    def test_damage_flash_coexists_with_beam_bomb_and_does_not_grant_invulnerability(self):
        m = self.game()
        self.enemy(m, 0, 0, 8)
        self.enemy(m, 1, 2, 20, kind=5)
        for elapsed in range(13):
            self.frame(m, 8, fire=True)
            self.assertEqual(m.value("Health"), 4)
            self.assertEqual(m.value("EnemyHealth", 1), 1)
            self.assert_background(m, (72, 70, 68, 66)[elapsed // 3] if elapsed < 12 else 0)
            self.assert_rendered_pattern(m, m.value("DisplayPattern"))
            self.assert_arena_colors_and_sprites(m)
        self.frame(m, reset=True)
        self.enemy(m, 0, 2, 8)
        self.frame(m, 8)
        self.assertEqual(m.value("Health"), 5, "A lethal shot prevents contact and the player flash")
        self.assertEqual(m.value("PlayerHitTimer"), 0)
        self.assert_background(m, 0)

    def test_bomb_fixed_point_boundary_and_fill_cue(self):
        for square in (True,):
            m = self.game()
            self.enemy(m, 0, 2, 24, square=square)
            self.enemy(m, 1, 6, 24, square=square, fraction=1)
            self.frame(m, fire=True)
            self.assertEqual(m.value("EnemyFlags", 0), 0)
            self.assertTrue(m.value("EnemyFlags", 1) & 0x80)
            self.assertEqual(self.score(m), 25 if square else 10)
            if square:
                if m.value("SelectedSlot") != 1:
                    self.frame(m, fire=True)
                self.assertEqual(m.value("SelectedSlot"), 1)
                self.assertEqual(m.value("EnemySprite", 1), m.sym["SpriteSquare"] >> 8)
            m.poke("EnemyRadiusLo", 0, 1)
            self.frame(m, fire=True)
            self.assertTrue(m.value("EnemyFlags", 1) & 0x80, "Ring must not deal later damage")
            if square:
                if m.value("SelectedSlot") != 1:
                    self.frame(m, fire=True)
                self.assertEqual(m.value("SelectedSlot"), 1)
                self.assertEqual(m.value("EnemySprite", 1), m.sym["SpriteSquareReady"] >> 8)

    def test_bomb_and_beam_award_each_kill_once_before_contact(self):
        m = self.game()
        self.enemy(m, 0, 2, 8)
        self.enemy(m, 1, 6, 8, square=True)
        self.frame(m, 8, fire=True)
        self.assertEqual(self.score(m), 35)
        self.assertEqual(m.value("Health"), 5)
        self.assertEqual(m.value("ActiveCount"), 0)
        self.frame(m, 8, fire=True)
        self.assertEqual(self.score(m), 35)

    def test_contacts_saturate_health_and_keep_same_frame_kills(self):
        m = self.game()
        m.poke("Health", 1)
        for slot in (0, 1):
            self.enemy(m, slot, slot, 8, square=True)
        self.frame(m)
        self.assertEqual(m.value("Health"), 0)
        self.assertEqual(m.value("GameMode"), 2)
        self.assertEqual(self.score(m), 0)
        m = self.game()
        m.poke("Health", 1)
        self.enemy(m, 0, 0, 8, square=True)
        self.enemy(m, 1, 2, 40)
        self.frame(m, 8)
        self.assertEqual(m.value("GameMode"), 2)
        self.assertEqual(self.score(m), 10)
        self.assertEqual(m.value("BeamEnabled"), 0)

    def test_movement_borrow_saturation_and_exact_contact(self):
        m = self.game()
        m.poke("MovementEnabled", 32)
        self.enemy(m, 0, 2, 25, fraction=0, square=True)
        self.frame(m)
        self.assertEqual((m.value("EnemyRadiusHi"), m.value("EnemyRadiusLo")), (24, 224))
        self.enemy(m, 0, 2, 8, fraction=33, square=True)
        self.frame(m)
        self.assertTrue(m.value("EnemyFlags") & 0x80)
        self.assertEqual(m.value("Health"), 5)
        self.enemy(m, 0, 2, 8, fraction=32, square=True)
        self.frame(m)
        self.assertEqual(m.value("EnemyFlags"), 0)
        self.assertEqual(m.value("Health"), 4)
        self.enemy(m, 0, 2, 0, fraction=1, square=True)
        self.frame(m)
        self.assertEqual((m.value("EnemyRadiusHi"), m.value("EnemyRadiusLo")), (0, 0))

    def test_cartridge_positions_match_all_lanes_and_radii(self):
        m = self.game()
        tuning = assets.load_config()
        for lane in range(8):
            for radius in range(64):
                self.enemy(m, 3, lane, radius)
                m.cpu.x = 3
                m.call("PositionEnemy")
                x, y = assets.center(lane, radius, tuning)
                self.assertEqual((m.value("EnemyX", 3), m.value("EnemyY", 3)), (x - 4, y - 2))

    def test_bcd_score_carries_saturates_and_clears_decimal_mode(self):
        m = self.game()
        for start, award, expected in ((0, 10, 10), (75, 25, 100), (990, 25, 1015),
                                       (9975, 25, 9999), (9990, 10, 9999), (9999, 25, 9999)):
            m.poke("ScoreHi", int(f"{start:04}"[:2], 16))
            m.poke("ScoreLo", int(f"{start:04}"[2:], 16))
            m.cpu.a = 0x10 if award == 10 else 0x25
            m.call("AwardScore")
            self.assertEqual(self.score(m), expected)
            self.assertFalse(m.cpu.p & 8)

    def test_lfsr_visits_every_nonzero_state(self):
        m = self.game()
        seen = set()
        for _ in range(255):
            m.call("NextRandom")
            seen.add(m.value("RandomState"))
        self.assertEqual(seen, set(range(1, 256)))
        self.assertEqual(m.value("RandomState"), 0xa5)

    def test_spawns_do_not_move_or_die_in_their_creation_update(self):
        m = self.game(False)
        m.poke("SpawnTimer", 1)
        # Seed $a5 selects lane E for the first triangle.
        self.frame(m, 8)
        self.assertEqual(m.value("EnemyFlags"), 0x82)
        self.assertEqual((m.value("EnemyRadiusHi"), m.value("EnemyRadiusLo")), (63, 0))
        self.assertEqual(self.score(m), 0)
        self.frame(m, 8)  # held direction cannot hit the new spawn
        self.assertEqual(m.value("EnemyFlags"), 0x82)
        self.frame(m)
        self.frame(m, 8)
        self.assertEqual(m.value("EnemyFlags"), 0)
        self.assertEqual(self.score(m), 10)

    def test_spawn_cap_distinct_lanes_and_square_spacing(self):
        m = self.game()
        m.poke("SpawnTimer", 0)
        m.poke("SpawnInterval", 1)
        m.poke("ActiveCap", 4)  # storage capacity must not bypass display cap
        for _ in range(20):
            self.frame(m)
            active = [m.value("EnemyFlags", s) for s in range(4) if m.value("EnemyFlags", s) & 0x80]
            self.assertLessEqual(len(active), 4)
            self.assertEqual(len({v & 7 for v in active}), len(active))
        self.assertEqual(len(active), 2)
        squares = []
        for t in range(150):
            for slot in range(4):
                m.poke("EnemyFlags", 0, slot)
            self.frame(m)
            if m.value("EnemyFlags") & 0x40:
                squares.append(t)
        self.assertGreaterEqual(len(squares), 2)
        self.assertTrue(all(b - a >= 72 for a, b in zip(squares, squares[1:])))

    def test_square_cap_reserves_beam_slots_and_keeps_spawn_spacing(self):
        def next_random(value):
            return (value >> 1) ^ (0xb8 if value & 1 else 0)
        levels = assets.load_levels()["levels"]
        for kind, row_index in ((4, 2), (5, 2), (6, 7), (7, 7)):
            row = levels[row_index]
            seed = next(seed for seed in range(1, 256)
                        if row["types"][next_random(next_random(seed)) >> 5] == kind)
            for cap in (2, 4):
                for count in range(cap // 2 + 1):
                    for existing in (4, 5, 6, 7):
                        for gap in (0, 1):
                            m = self.game()
                            m.poke("LevelTypeOffset", row_index * 8)
                            m.poke("ActiveCap", cap)
                            for slot in range(count):
                                self.enemy(m, slot, slot, 9, kind=existing)
                            m.poke("SquareTimer", gap)
                            m.poke("SpawnTimer", 0)
                            m.poke("RandomState", seed)
                            m.call("ScanEnemies")
                            m.call("TrySpawn")
                            expected = kind if count < cap // 2 and gap == 0 else 0
                            self.assertTrue(m.value("EnemyFlags", count) & 0x80)
                            self.assertEqual((m.value("EnemyFlags", count) >> 4) & 7, expected,
                                             (cap, count, kind, existing, gap))
                            self.assertEqual(m.value("SquareTimer"), 72 if expected else gap)

    def test_two_armored_squares_can_be_bombed_twice_while_approaching(self):
        m = self.game()
        m.poke("MovementEnabled", 1)
        for slot, lane in enumerate((0, 4)):
            self.enemy(m, slot, lane, 24, kind=5)
        self.frame(m, fire=True)
        self.assertEqual([m.value("EnemyHealth", s) for s in (0, 1)], [1, 1])
        for _ in range(29):
            self.frame(m)
        self.frame(m, fire=True)
        self.assertEqual([m.value("EnemyFlags", s) for s in (0, 1)], [0, 0])
        self.assertEqual(self.score(m), 100)
        self.assertEqual(m.value("Health"), 5)
        self.assertEqual([m.value("EnemyVisual", s) for s in (0, 1)], [18, 18])

    def test_game_over_freezes_and_restart_consumes_button_edge(self):
        m = self.game()
        m.poke("Health", 1)
        m.poke("ScoreLo", 0x75)
        self.enemy(m, 0, 0, 8, square=True)
        self.frame(m)
        for _ in range(5):
            self.frame(m, 8)
            self.assertEqual(m.value("GameMode"), 2)
            self.assertEqual(self.score(m), 75)
            self.assertEqual(m.value("BeamEnabled"), 0)
        self.frame(m, 8, fire=True)
        self.assertEqual(m.value("GameMode"), 1)
        self.assertEqual(m.value("Health"), 5)
        self.assertEqual(self.score(m), 0)
        self.assertEqual(m.value("BombCount"), 0)
        self.frame(m, fire=True)
        self.assertEqual(m.value("BombCount"), 0)
        self.frame(m)
        self.frame(m, fire=True)
        self.assertEqual(m.value("BombCount"), 1)
        self.frame(m, fire=True, reset=True)
        self.assertEqual(m.value("BombCount"), 0)

    def test_combat_bomb_cooldown_is_exact_and_select_has_no_effect(self):
        m = self.game()
        self.frame(m, fire=True)
        for _ in range(28):
            self.frame(m, select=True)
        self.frame(m, fire=True)  # t+29: too early
        self.assertEqual(m.value("BombCount"), 1)
        self.frame(m)  # t+30, no fresh press
        self.frame(m, fire=True)
        self.assertEqual(m.value("BombCount"), 2)
        self.assertEqual(m.value("LevelNumber"), 1)
        self.assertEqual(m.value("ActiveCount"), 0)
        m = self.game()
        self.frame(m, fire=True)
        for _ in range(29):
            self.frame(m)
        self.frame(m, fire=True)  # t+30: accepted
        self.assertEqual(m.value("BombCount"), 2)

    def test_playable_rom_preserves_rays_fade_and_sprite_timing(self):
        m = self.game()
        for slot, lane in enumerate((0, 4)):
            self.enemy(m, slot, lane, 40, square=True)
        for mask in MASKS:
            self.frame(m)
            self.frame(m, mask)
            self.assert_rendered_pattern(m, m.value("DisplayPattern"))
            self.assert_arena_colors_and_sprites(m)
        for _ in range(17):
            self.frame(m, fire=True)
            self.assert_rendered_pattern(m, m.value("DisplayPattern"))
            self.assert_arena_colors_and_sprites(m)

    def test_hud_raster_displays_bcd_digits_and_health(self):
        m = self.game()
        for hp in range(6):
            for score in (0, 1, 1234, 9876, 9999):
                m.poke("GameMode", 1)
                m.poke("Health", hp)
                m.poke("ScoreHi", int(f"{score:04}"[:2], 16))
                m.poke("ScoreLo", int(f"{score:04}"[2:], 16))
                self.frame(m)
                origin = m.bus.vsync_edges[-1] // 76 * 76
                for line in range(10):
                    row = line // 2
                    cells = {4 + digit * 4 + bit for digit, value in enumerate(f"{score:04}")
                             for bit in range(3) if assets.DIGITS[int(value)][row] & (4 >> bit)}
                    cells.update(24 + i * 3 for i in range(hp))
                    planes = assets.encode_row(cells)
                    expected = [(12, 0x0e, planes[1]), (19, 0x0f, planes[2]),
                                (43, 0x0e, planes[4]), (53, 0x0f, planes[5])]
                    writes = [(cy % 76, reg, value) for cy, reg, value in m.bus.events
                              if (cy - origin) // 76 == 42 + line and reg in (0x0e, 0x0f)]
                    self.assertEqual(writes, expected, (score, hp, line))

    def test_beam_kill_burst_stays_at_hit_and_expires_without_repeated_damage(self):
        for lane, mask in enumerate(MASKS):
            m = self.game()
            self.enemy(m, 0, lane, 63)
            for elapsed in range(19):
                self.frame(m, mask)
                self.assertEqual(m.value("EnemyFlags"), 0)
                self.assertEqual(m.value("ActiveCount"), 0)
                self.assertEqual(m.value("EnemyVisual"), max(0, 18 - elapsed))
                self.assertEqual(self.score(m), 10)
                self.assertEqual(m.value("Health"), 5)
                x, y = assets.center(lane, 63, assets.load_config())
                self.assertEqual((m.value("EnemyX"), m.value("EnemyY")), (x - 4, y - 2))
                self.assertEqual(m.value("SelectedSlot"), 0 if elapsed < 18 else 255)
                self.assert_arena_colors_and_sprites(m)

    def test_double_bomb_kill_animates_both_slots_on_both_ring_phases(self):
        for phase in (0, 1):
            m = self.game()
            m.poke("FrameCounter", phase)
            self.enemy(m, 0, 2, 20, square=True)
            self.enemy(m, 1, 6, 24, square=True)
            drawn = [[], [], []]
            for elapsed in range(19):
                self.frame(m, 1, fire=True)
                self.assertEqual(self.score(m), 50)
                self.assertEqual(m.value("ActiveCount"), 0)
                self.assertEqual(m.value("EnemyVisual", 0), max(0, 18 - elapsed))
                self.assertEqual(m.value("EnemyVisual", 1), max(0, 18 - elapsed))
                self.assert_arena_colors_and_sprites(m)
                self.assert_rendered_pattern(m, m.value("DisplayPattern"))
                if elapsed < 18:
                    drawn[elapsed // 6].append(m.value("SelectedSlot"))
            self.assertTrue(all(slots.count(0) == slots.count(1) == 3 for slots in drawn))

    def test_burst_reserves_draw_capacity_until_expiry_and_preserves_survivor(self):
        m = self.game()
        m.poke("SpawnTimer", 0)
        self.enemy(m, 0, 2, 40)
        self.enemy(m, 1, 6, 45, square=True)
        for elapsed in range(18):
            self.frame(m, 8)
            self.assertEqual(m.value("ActiveCount"), 1)
            self.assertEqual(m.value("EnemyVisual"), 18 - elapsed)
            self.assertFalse(m.value("FramePhase") & 0x80)
            self.assertEqual(m.value("EnemyFlags", 1), 0xc6)
            self.assertFalse(any(m.value("EnemyFlags", s) for s in (2, 3)))
            self.assert_arena_colors_and_sprites(m)
        self.frame(m, 8)
        self.assertEqual(m.value("ActiveCount"), 2)
        self.assertEqual(m.value("EnemyVisual"), 0)
        self.assertTrue(m.value("EnemyFlags") & 0x80)
        self.assertEqual(m.value("EnemyRadiusHi"), 63)

    def test_game_over_finishes_bursts_and_reset_clears_them(self):
        m = self.game()
        m.poke("Health", 1)
        self.enemy(m, 0, 0, 8, square=True)
        self.enemy(m, 1, 2, 40)
        self.frame(m, 8)
        self.assertEqual(m.value("GameMode"), 2)
        self.assertEqual(m.value("EnemyVisual", 0), 0)  # contact is not a scored kill
        self.assertEqual(m.value("EnemyVisual", 1), 18)
        for elapsed in range(1, 19):
            self.frame(m)
            self.assertEqual(m.value("EnemyVisual", 1), 18 - elapsed)
            self.assertEqual(self.score(m), 10)
            self.assert_arena_colors_and_sprites(m)
        self.frame(m, reset=True)
        self.enemy(m, 0, 2, 40)
        self.frame(m, 8)
        self.assertEqual(m.value("EnemyVisual"), 18)
        self.frame(m, reset=True)
        self.assertEqual([m.value("EnemyVisual", s) for s in range(4)], [0] * 4)
        self.assertEqual(m.value("SelectedSlot"), 255)

    def test_scripted_survival_keeps_enemies_visible_and_timing_stable(self):
        m = self.game(False)
        m.poke("LevelNumber", 4)  # all types; progression is covered separately
        m.poke("GameMode", 3)
        m.poke("SpawnTimer", 1)
        self.frame(m)
        m.poke("KillsRemaining", 255)
        kinds, awards, square_pairs = set(), set(), set()
        previous_score = 0
        for elapsed in range(3000):
            active = [s for s in range(4) if m.value("EnemyFlags", s) & 0x80]
            mask = 0
            bomb = False
            for slot in active:
                flags = m.value("EnemyFlags", slot)
                kinds.add((flags >> 4) & 7)
                if flags & 0x40:
                    radius = m.value("EnemyRadiusHi", slot) * 256 + m.value("EnemyRadiusLo", slot)
                    bomb |= radius <= 24 * 256 and m.value("BombCooldown") == 0
                else:
                    if m.value("BeamArmed"):
                        mask = MASKS[flags & 7]
            self.frame(m, mask, fire=bomb)
            active = [s for s in range(4) if m.value("EnemyFlags", s) & 0x80]
            self.assertLessEqual(len(active), 4)
            self.assertEqual(len({m.value("EnemyFlags", s) & 7 for s in active}), len(active))
            for slot in active:
                self.assertFalse(m.value("FramePhase") & 0x80)
                self.assertTrue(0 <= m.value("EnemyX", slot) <= 152)
                self.assertTrue(0 <= m.value("EnemyY", slot) <= 76)
            self.assertLessEqual(sum(bool(m.value("EnemyFlags", s) & 0x40) for s in active),
                                 (m.value("ActiveCap") + 1) // 2)
            squares = tuple(sorted((m.value("EnemyFlags", s) >> 4) & 7
                                   for s in active if m.value("EnemyFlags", s) & 0x40))
            if len(squares) == 2:
                square_pairs.add(squares)
            score = self.score(m)
            if score > previous_score:
                awards.add(score - previous_score)
            previous_score = score
            if elapsed >= 1400 and kinds == {0, 1, 2, 4, 5} and {10, 20, 25, 40, 50} <= awards:
                break
        self.assertEqual(kinds, {0, 1, 2, 4, 5})
        self.assertTrue({10, 20, 25, 40, 50} <= awards)
        self.assertEqual(m.value("Health"), 5)
        self.assertEqual(m.value("GameMode"), 1)
        self.assertIn((4, 5), square_pairs, "Natural play must admit a square beside armor")

    def test_level_rows_load_preserving_run_state_and_reset_effects(self):
        config = assets.load_levels()
        levels = config["levels"]
        for number in range(1, 100):
            m = self.game()
            m.poke("LevelNumber", int(str(number), 16))
            m.poke("Health", 3)
            m.poke("ScoreHi", 0x12)
            m.poke("ScoreLo", 0x34)
            m.poke("RandomState", 0x51)
            m.poke("PreviousButtons", 128)
            m.poke("BeamArmed", 0)
            for name in ("BombCooldown", "BombTimer", "SquareTimer", "PlayerHitTimer", "BeamFadeTimer",
                         "ShotSoundTimer", "EventSoundId", "EventSoundTimer", "SoundRequest"):
                m.poke(name, 1)
            self.enemy(m, 0, 2, 30)
            m.call("LoadLevel")
            row = levels[min(number, len(levels)) - 1]
            interval = (config["late_spawn"]["interval"]
                        if number >= config["late_spawn"]["start_level"] else row["spawn_interval"])
            type_row = len(levels) if number >= config["late_mix"]["start_level"] else min(number, len(levels)) - 1
            self.assertEqual(m.value("LevelTypeOffset"), type_row * 8)
            self.assertEqual(m.value("KillsRemaining"), min(8 + 4 * (number - 1), 64))
            self.assertEqual(m.value("ActiveCap"), min(row["cap"], 4))
            self.assertEqual(m.value("SpawnInterval"), interval)
            self.assertEqual(m.value("SpawnTimer"), interval)
            self.assertEqual((m.value("Health"), self.score(m), m.value("RandomState")), (3, 1234, 0x51))
            self.assertEqual((m.value("PreviousButtons"), m.value("BeamArmed")), (128, 0))
            for name in ("BombCooldown", "BombTimer", "SquareTimer", "PlayerHitTimer", "BeamFadeTimer",
                         "ShotSoundTimer", "EventSoundId", "EventSoundTimer", "SoundRequest", "ActiveCount"):
                self.assertEqual(m.value(name), 0, name)
            self.assertEqual(bytes(m.bus.ram[:32]), bytes(32))

    def test_faster_spawns_start_at_level_ten_and_keep_the_final_mix(self):
        for level, delay in ((8, 8), (9, 8), (10, 4), (11, 4), (99, 4)):
            with self.subTest(level=level):
                m = self.game()
                m.poke("LevelNumber", int(str(level), 16))
                m.poke("GameMode", 3)
                m.poke("SpawnTimer", 1)
                self.frame(m)
                self.assertEqual(m.value("LevelTypeOffset"), (8 if level >= 20 else 7) * 8)
                self.assertEqual(m.value("ActiveCap"), 4)
                # Both the first arrival and a replacement must wait the exact
                # delay. Clear the previous slot to isolate cadence from spacing.
                for _ in range(2):
                    for slot in range(4):
                        m.poke("EnemyFlags", 0, slot)
                        m.poke("EnemyVisual", 0, slot)
                    for _ in range(delay - 1):
                        self.frame(m)
                        self.assertEqual(m.value("ActiveCount"), 0)
                    self.frame(m)
                    self.assertEqual(m.value("ActiveCount"), 1)
                    self.assertEqual(m.value("SpawnTimer"), delay)

    def test_level_quota_counts_kills_only_and_multi_kills_saturate(self):
        m = self.game()
        m.poke("KillsRemaining", 1)
        self.enemy(m, 0, 2, 20, kind=2)
        self.frame(m, 8)
        self.assertEqual(m.value("KillsRemaining"), 1)  # nonlethal damage
        self.frame(m)  # rearm before testing an ineffective shot
        self.enemy(m, 1, 6, 40, kind=4)
        self.frame(m, 4)
        self.assertEqual(m.value("KillsRemaining"), 1)
        m.poke("EnemyRadiusHi", 8, 1)
        self.frame(m)  # contact is not a kill
        self.assertEqual((m.value("KillsRemaining"), m.value("Health")), (1, 4))
        for slot, lane in enumerate((2, 6)):
            self.enemy(m, slot, lane, 20, kind=4)
        m.poke("SpawnTimer", 0)
        self.frame(m, fire=True)
        self.assertEqual(m.value("KillsRemaining"), 0)  # multiple kills saturate, no underflow
        self.assertEqual(self.score(m), 50)
        self.assertEqual(m.value("ActiveCount"), 0)
        self.assertEqual((m.value("GameMode"), m.value("LevelNumber")), (3, 1))
        self.finish_wave(m)
        m.poke("SpawnTimer", 255)
        for _ in range(17):
            self.frame(m)
            self.assertEqual(m.value("KillsRemaining"), 12)
            self.assertEqual(self.score(m), 50)

    def test_level_completion_shows_full_bar_then_clear_and_consumes_controls(self):
        for kind in range(8):
            m = self.game()
            m.poke("KillsRemaining", 1)
            m.poke("Health", 3)  # wave clear does not require full health
            self.enemy(m, 0, 2, 40)
            self.enemy(m, 1, 6, 40, kind=kind)
            self.frame(m)
            position = (m.value("EnemyX", 1), m.value("EnemyY", 1))
            self.frame(m, 8)
            self.assertEqual((m.value("GameMode"), m.value("LevelNumber"), m.value("KillsRemaining")), (3, 1, 0))
            self.assertEqual(m.value("ActiveCount"), 1)  # full bar precedes clearing
            self.assert_sound(m, "kill")
            for elapsed in range(32):
                self.frame(m, 8, fire=True)
                self.assertEqual((m.value("GameMode"), m.value("LevelNumber")), (3, 1))
                self.assertEqual((m.value("Health"), self.score(m), m.value("ActiveCount")), (3, 10, 0))
                self.assertEqual([m.value("HudProgress", i) for i in range(5)], [255, 255, 240, 255, 15])
                self.assertEqual((m.value("EnemyFlags", 1), m.value("EnemyHealth", 1)), (0, 0))
                self.assertEqual((m.value("EnemyX", 1), m.value("EnemyY", 1)), position)
                self.assertEqual(m.value("EnemyVisual", 1), max(0, 18 - elapsed))
                self.assertEqual((m.value("BeamEvent"), m.value("BombEvent"), m.bus.tia[0x19]), (0, 0, 0))
                self.assert_sound(m, "clear", elapsed)
                self.assert_background(m, 0x1a if elapsed < 8 or 16 <= elapsed < 24 else 0)
                self.assert_arena_colors_and_sprites(m)
            self.frame(m, 8, fire=True)
            self.assertEqual((m.value("GameMode"), m.value("LevelNumber"), m.value("KillsRemaining")), (1, 2, 12))
            self.assertEqual([m.value("HudProgress", i) for i in range(5)], [0] * 5)
            self.assertEqual((m.value("ActiveCap"), m.value("SpawnInterval"), m.value("SpawnTimer")), (4, 12, 12))
            self.assert_background(m, 0x90)
            self.assertEqual((m.value("EventSoundId"), m.bus.tia[0x1a]), (0, 0))
            self.frame(m, 8, fire=True)
            self.assertEqual((m.value("BeamEvent"), m.value("BombEvent")), (0, 0))
            self.frame(m)
            self.frame(m, 8, fire=True)
            self.assertEqual((m.value("BeamEvent"), m.value("BombEvent")), (1, 1))

    def test_level_clear_coincides_with_score_bonus_without_extra_rewards(self):
        for hp in (3, 5):
            m = self.game()
            m.poke("Health", hp)
            m.poke("KillsRemaining", 1)
            self.set_score(m, 990)
            self.enemy(m, 0, 2, 40)
            self.enemy(m, 1, 6, 40, kind=5)
            self.frame(m, 8)
            self.assert_sound(m, "heal" if hp < 5 else "clear")
            self.assertEqual((m.value("GameMode"), m.value("KillsRemaining")), (3, 0))
            self.frame(m)
            self.assert_sound(m, "clear")
            self.assert_background(m, 0x1a)
            self.assertEqual(m.value("ActiveCount"), 0)
            self.assertEqual(self.finish_wave(m), 32)
            self.assertEqual((m.value("Health"), self.score(m), m.value("LevelNumber")), (min(hp + 1, 5), 1000, 2))

    def test_level_background_preserves_all_enemy_colors_and_attack_effects(self):
        palette = (0x00, 0x90, 0xb0, 0x60, 0xd0, 0x20, 0x80, 0x02)
        for level in range(2, 10):
            for kind in range(8):
                m = self.game()
                m.poke("LevelNumber", level)
                m.poke("GameMode", 3)
                m.poke("SpawnTimer", 1)
                self.frame(m)
                m.poke("KillsRemaining", 255)
                m.poke("SpawnTimer", 255)
                self.enemy(m, 0, 2, 40)
                self.enemy(m, 1, 6, 40, kind=kind)
                for _ in range(40):  # outlast the former 36-update pulse
                    self.frame(m, 8, fire=True)
                    self.assertEqual(m.value("LevelBackground"), palette[(level - 1) % 8])
                    self.assert_background(m, palette[(level - 1) % 8])
                    self.assertEqual((m.value("Health"), self.score(m), m.value("LevelNumber")), (5, 10, level))
                    self.assertEqual(m.value("EnemyFlags", 1), 0x86 | kind << 4)
                    self.assert_arena_colors_and_sprites(m)
                    self.assert_rendered_pattern(m, m.value("DisplayPattern"))

    def test_level_background_returns_after_damage_before_clear_or_game_over(self):
        for hp in (1, 5):
            m = self.game()
            m.poke("LevelNumber", 2)
            m.poke("GameMode", 3)
            m.poke("SpawnTimer", 1)
            self.frame(m)
            m.poke("Health", hp)
            m.poke("KillsRemaining", 1)
            self.enemy(m, 0, 2, 40)
            self.enemy(m, 1, 6, 8)
            self.enemy(m, 2, 4, 40, kind=5)
            for elapsed in range(46):
                self.frame(m, 8)
                next_wave = hp > 1 and elapsed >= 44
                self.assertEqual(m.value("LevelNumber"), 3 if next_wave else 2)
                if elapsed < 12:
                    color = (0x48, 0x46, 0x44, 0x42)[elapsed // 3]
                    self.assertEqual(m.value("EnemyHealth", 2), 2)
                elif hp > 1 and elapsed < 44:
                    self.assert_sound(m, "clear", elapsed - 12)
                    color = 0x1a if 12 <= elapsed < 20 or 28 <= elapsed < 36 else 0x90
                    self.assertEqual(m.value("ActiveCount"), 0)
                else:
                    color = 0xb0 if next_wave else 0x90
                self.assert_background(m, color)
            self.frame(m, reset=(hp > 1), fire=(hp == 1))
            self.assertEqual((m.value("GameMode"), m.value("LevelNumber"), m.value("Health")), (1, 1, 5))
            self.assert_background(m, 0)

    def test_level_background_cycles_with_bcd_levels_and_resets_on_start(self):
        palette = (0x00, 0x90, 0xb0, 0x60, 0xd0, 0x20, 0x80, 0x02)
        m = Machine()
        m.boot()
        self.frame(m)
        self.assert_background(m, 0)
        self.frame(m, fire=True)
        self.assert_background(m, 0)
        for level in range(1, 100):
            bcd = (level // 10) * 16 + level % 10
            m.poke("LevelNumber", bcd)
            m.poke("GameMode", 3)
            m.poke("SpawnTimer", 1)
            self.frame(m)  # debugger loader must match actual advancement
            self.assertEqual(m.value("LevelNumber"), bcd)
            self.assertEqual(m.value("LevelBackground"), palette[(level - 1) % 8])
            self.assert_background(m, palette[(level - 1) % 8])
            m.poke("KillsRemaining", 0)
            self.frame(m)  # full bar before the celebration
            self.assertEqual(m.value("LevelNumber"), bcd)
            m.poke("SpawnTimer", 1)  # exercise the end of the already-tested countdown
            self.frame(m)
            next_level = min(level + 1, 99)
            self.assertEqual(m.value("LevelNumber"), (next_level // 10) * 16 + next_level % 10)
            self.assert_background(m, palette[(next_level - 1) % 8])
            self.assertEqual(m.value("ActiveCount"), 0)
        self.frame(m, reset=True)
        self.assert_background(m, 0)

    def test_level_death_beats_completion_and_contacts_do_not_advance_quota(self):
        for order in (False, True):
            m = self.game()
            m.poke("Health", 1)
            m.poke("KillsRemaining", 1)
            self.enemy(m, int(order), 2, 40)
            self.enemy(m, int(not order), 6, 8, kind=4)
            self.frame(m, 8)
            self.assertEqual((m.value("GameMode"), m.value("LevelNumber")), (2, 1))
            self.assertEqual((self.score(m), m.value("KillsRemaining")), (10, 0))
            self.assert_sound(m, "death")
            for _ in range(80):
                self.frame(m)
                self.assertEqual((m.value("GameMode"), m.value("LevelNumber")), (2, 1))
        m = self.game()
        m.poke("KillsRemaining", 1)
        self.enemy(m, 0, 6, 8)
        self.frame(m)
        self.assertEqual((m.value("KillsRemaining"), self.score(m), m.value("GameMode")), (1, 0, 1))
        m.poke("KillsRemaining", 0)
        self.enemy(m, 0, 6, 8)
        self.frame(m)
        self.assertEqual((m.value("Health"), m.value("GameMode"), m.value("LevelNumber")), (3, 3, 1))
        self.finish_wave(m)
        self.assertEqual(m.value("LevelNumber"), 2)

    def test_level_bcd_increment_saturation_and_reset_during_clear(self):
        for start, expected in ((1, 2), (8, 9), (9, 10), (14, 15), (15, 16), (19, 20), (24, 25), (98, 99), (99, 99)):
            m = self.game()
            m.poke("LevelNumber", int(str(start), 16))
            m.poke("KillsRemaining", 0)
            m.poke("Health", 3)
            m.poke("ScoreHi", 0x99)
            m.poke("ScoreLo", 0x99)
            self.frame(m)
            self.assertEqual(self.finish_wave(m), 33)
            self.assertEqual(m.value("LevelNumber"), int(str(expected), 16))
            self.assertEqual(m.value("KillsRemaining"), min(8 + 4 * (expected - 1), 64))
            delay = 4 if expected >= 10 else assets.load_levels()["levels"][min(expected - 1, 7)]["spawn_interval"]
            self.assertEqual((m.value("SpawnInterval"), m.value("SpawnTimer")), (delay, delay))
            for _ in range(60):
                self.frame(m)
            self.assertEqual(m.value("GameMode"), 1)
            self.assertEqual((m.value("Health"), self.score(m)), (3, 9999))
            self.assertEqual(m.value("LevelTypeOffset"), (8 if expected >= 20 else min(expected - 1, 7)) * 8)
        m.poke("KillsRemaining", 0)
        self.frame(m)
        self.frame(m, 8, fire=True, reset=True)
        self.assertEqual((m.value("GameMode"), m.value("LevelNumber"), m.value("KillsRemaining")), (1, 1, 8))
        self.assertEqual((m.value("Health"), self.score(m), m.value("RandomState")), (5, 0, 0xa5))
        self.assertEqual((m.value("BeamEvent"), m.value("BombEvent")), (0, 0))

    def test_level_hud_digits_and_blank_right_half_at_all_cooldowns(self):
        for level in (1, 9, 10, 19, 80, 99):
            for remaining in (0, 1, 8, 9, 10, 18, 42, 99, 100, 255):
                m = self.game()
                m.poke("GameMode", 3)  # inspect zero without advancing a live level
                m.poke("LevelNumber", int(str(level), 16))
                m.poke("KillsRemaining", remaining)
                m.poke("SpawnTimer", 60)
                m.poke("BombCooldown", 10 if remaining & 1 else 0)
                self.frame(m)
                origin = m.bus.vsync_edges[-1] // 76 * 76
                for line in range(10):
                    row = line // 2
                    cells = {4 + i * 4 + bit for i, letter in enumerate("LV")
                             for bit in range(3) if assets.FONT[letter][row] & (4 >> bit)}
                    cells.update(12 + i * 4 + bit for i, digit in enumerate(f"{level:02}")
                                 for bit in range(3) if assets.DIGITS[int(digit)][row] & (4 >> bit))
                    values = assets.encode_row(cells)
                    writes = [(cy % 76, reg, value) for cy, reg, value in m.bus.events
                              if (cy - origin) // 76 == 59 + line and reg in (0x0d, 0x0e, 0x0f, 0x08)]
                    self.assertEqual(writes, [(5,0x0d,0),(10,0x08,14),(17,0x0e,values[1]),(36,0x0f,values[2]),
                                              (41,0x0e,0),(50,0x0f,0)])
        for mode, word in ((0, "FIRE"), (2, "OVER")):
            m = self.game()
            m.poke("GameMode", mode)
            self.frame(m)
            origin = m.bus.vsync_edges[-1] // 76 * 76
            for line in range(10):
                row = line // 2
                cells = {4 + i * 4 + bit for i, letter in enumerate(word)
                         for bit in range(3) if assets.FONT[letter][row] & (4 >> bit)}
                values = assets.encode_row(cells)
                writes = [(cy % 76, reg, value) for cy, reg, value in m.bus.events
                          if (cy - origin) // 76 == 59 + line and reg in (0x0d, 0x0e, 0x0f, 0x08)]
                self.assertEqual(writes, [(5,0x08,14),(13,0x0e,values[1]),(21,0x0f,values[2]),
                                         (40,0x0e,0),(51,0x0f,0)])

    def test_wave_progress_bar_matches_quota_and_has_fixed_raster_deadlines(self):
        for number in (*range(1, 17), 19, 20, 99):
            quota = min(8 + 4 * (number - 1), 64)
            for remaining in (*range(quota + 2), 99, 255):
                m = self.game()
                m.poke("LevelNumber", int(str(number), 16))
                m.poke("GameMode", 3)
                m.poke("SpawnTimer", 1)
                self.frame(m)
                m.poke("GameMode", 3)  # hold zero for the full-bar boundary
                m.poke("SpawnTimer", 60)
                m.poke("KillsRemaining", remaining)
                self.frame(m)
                filled = max(0, quota - remaining) * 8 // quota
                planes = assets.encode_row(set(range(4, 4 + filled * 4)))
                expected = [planes[i] for i in (1, 2, 3, 4, 5)]
                self.assertEqual([m.value("HudProgress", i) for i in range(5)], expected)
                origin = m.bus.vsync_edges[-1] // 76 * 76
                writes = [(cy % 76, reg, value) for cy, reg, value in m.bus.events
                          if (cy - origin) // 76 == 231 and reg in (0x0d, 0x0e, 0x0f, 0x08)]
                self.assertEqual(writes, [(5, 0x0d, 0), (10, 0x08, 198), (16, 0x0e, planes[1]),
                                         (22, 0x0f, planes[2]), (40, 0x0d, planes[3]),
                                         (46, 0x0e, planes[4]), (52, 0x0f, planes[5])])
                self.assert_arena_colors_and_sprites(m)
                rail = [(cy % 76, reg, value) for cy, reg, value in m.bus.events
                        if (cy - origin) // 76 == 230 and reg in (0x0d, 0x0e, 0x0f, 0x08)]
                self.assertEqual(rail, [(3, 0x0d, 0), (17, 0x08, 4), (22, 0x0e, 255),
                                        (25, 0x0f, 255), (30, 0x0d, 240), (59, 0x0f, 15)])
        for mode in (0, 2):
            m = self.game()
            m.poke("GameMode", mode)
            m.poke("KillsRemaining", 1)
            self.frame(m)
            self.assertEqual([m.value("HudProgress", i) for i in range(5)], [0] * 5)

    def test_progress_footer_is_hidden_before_start_and_after_game_over(self):
        m = Machine()
        m.boot()
        self.assertEqual(m.sym["ARENA_START_LINE"], 70)
        def check_footer(visible):
            origin = m.bus.vsync_edges[-1] // 76 * 76
            writes = [(reg, value) for cy, reg, value in m.bus.events
                      if 230 <= (cy - origin) // 76 < 232]
            playfield = [value for reg, value in writes if reg in (0x0d, 0x0e, 0x0f)]
            self.assertEqual(any(playfield), visible)
            for reg in (0x1b, 0x1c, 0x1f):  # turret, enemy, and beam cleared before footer
                self.assertIn((reg, 0), writes)
            # The former bar rows now start the arena; the remaining separator is blank.
            self.assertFalse(any(value for cy, reg, value in m.bus.events
                                 if (cy - origin) // 76 == 69 and reg in (0x0d, 0x0e, 0x0f)))
        self.frame(m)
        self.assertEqual(m.value("GameMode"), 0)
        check_footer(False)
        self.frame(m, fire=True)
        self.assertEqual(m.value("GameMode"), 1)
        check_footer(True)
        m.poke("KillsRemaining", 4)
        self.frame(m)
        check_footer(True)
        m.poke("Health", 1)
        self.enemy(m, 0, 0, 8)
        self.frame(m)
        self.assertEqual(m.value("GameMode"), 2)
        check_footer(False)
        self.frame(m, reset=True)
        self.assertEqual(m.value("GameMode"), 1)
        self.assertEqual(m.value("KillsRemaining"), 8)
        check_footer(True)
        self.assertEqual([m.value("HudProgress", i) for i in range(5)], [0] * 5)

    def test_level_spawn_mixes_introduce_variants_in_order(self):
        levels = assets.load_levels()["levels"]
        self.assertEqual([row["spawn_interval"] for row in levels], [24, 12, 12, 10, 8, 8, 8, 8])
        for kind, first_level in ((6, 6), (7, 8)):
            self.assertEqual(next(i + 1 for i, row in enumerate(levels) if kind in row["types"]), first_level)
        for index, row in enumerate(assets.load_levels()["levels"]):
            m = self.game()
            m.poke("LevelNumber", index + 1)
            m.poke("GameMode", 3)
            m.poke("SpawnTimer", 1)
            self.frame(m)
            seen = set()
            for _ in range(128):
                for slot in range(4):
                    m.poke("EnemyFlags", 0, slot)
                    m.poke("EnemyVisual", 0, slot)
                m.poke("SpawnTimer", 1)
                m.poke("SquareTimer", 0)
                self.frame(m)
                self.assertEqual(m.value("ActiveCount"), 1)
                self.assertEqual(m.value("SpawnTimer"), row["spawn_interval"])
                seen.add((m.value("EnemyFlags") >> 4) & 7)
            self.assertEqual(seen, set(row["types"]))

    def test_level_natural_run_reaches_all_variants_without_damage(self):
        m = self.game(False)
        seen, levels = set(), set()
        for elapsed in range(10000):
            levels.add(m.value("LevelNumber"))
            mask, bomb = 0, False
            for slot in range(4):
                flags = m.value("EnemyFlags", slot)
                if not flags & 0x80:
                    continue
                seen.add((flags >> 4) & 7)
                if flags & 0x40:
                    radius = m.value("EnemyRadiusHi", slot) * 256 + m.value("EnemyRadiusLo", slot)
                    bomb |= radius <= 24 * 256 and m.value("BombCooldown") == 0
                elif m.value("BeamArmed"):
                    mask = MASKS[flags & 7]
            self.frame(m, mask, fire=bomb)
            self.assertEqual(m.value("Health"), 5)
            self.assertLessEqual(m.value("ActiveCount"), 4)
            if m.value("LevelNumber") >= 5 and seen == {0, 1, 2, 4, 5}:
                break
        self.assertTrue({1, 2, 3, 4} <= levels)
        self.assertEqual(seen, {0, 1, 2, 4, 5})
        self.assertGreaterEqual(m.value("LevelNumber"), 5)


if __name__ == "__main__":
    unittest.main()
