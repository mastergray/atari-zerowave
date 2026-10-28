import unittest
import json

from rom_machine import Machine, ROOT
import test_prototype as prototype

assets = prototype.assets

MASKS = (1, 9, 8, 10, 2, 6, 4, 5)


class CombatTests(unittest.TestCase):
    assert_rendered_pattern = prototype.CartridgeTests.assert_rendered_pattern
    assert_ball_pattern = prototype.CartridgeTests.assert_ball_pattern
    assert_arena_colors_and_sprites = prototype.CartridgeTests.assert_arena_colors_and_sprites

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
        return m

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
            self.assertEqual(m.value("SpawnTimer"), 90)
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
        for _ in range(59):
            self.frame(m, fire=True)
            self.assertEqual(m.value("EnemyHealth"), 1)
        self.frame(m)
        self.frame(m, fire=True)
        self.assertEqual(m.value("EnemyFlags"), 0)
        self.assertEqual(self.score(m), 50)

    def test_bomb_boundary_and_no_feedback_for_out_of_range_variants(self):
        for kind in (0, 1, 2, 4, 5):
            m = self.game()
            self.enemy(m, 0, 2, 24, kind=kind)
            self.enemy(m, 1, 6, 24, fraction=1, kind=kind)
            before = m.value("EnemyHealth")
            self.frame(m, fire=True)
            self.assertEqual(m.value("EnemyHealth"), before - (kind in (2, 4, 5)))
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
        for _ in range(59):
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
        for kind in (0, 1, 2, 4, 5):
            for lane, mask in enumerate(MASKS):
                m = self.game()
                self.enemy(m, 0, lane, 63, kind=kind)
                self.enemy(m, 1, (lane + 4) % 8, 24, kind=5)
                for feedback in (0, 6, 134):
                    m.poke("EnemyVisual", feedback)
                    for _ in range(2):
                        self.frame(m)
                        self.assert_arena_colors_and_sprites(m)
                        self.assertLessEqual(m.value("EnemyAge", 1), 1)

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
            self.assertLessEqual(len(active), 2)
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
        for _ in range(58):
            self.frame(m, select=True)
        self.frame(m, fire=True)  # t+59: too early
        self.assertEqual(m.value("BombCount"), 1)
        self.frame(m)  # t+60, no fresh press
        self.frame(m, fire=True)
        self.assertEqual(m.value("BombCount"), 2)
        self.assertEqual(m.value("LayoutId"), 0)
        self.assertEqual(m.value("ActiveCount"), 0)
        m = self.game()
        self.frame(m, fire=True)
        for _ in range(59):
            self.frame(m)
        self.frame(m, fire=True)  # t+60: accepted
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
            self.assertLessEqual(m.value("EnemyAge", 1), 1)
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

    def test_scripted_survival_keeps_two_enemies_visible_and_timing_stable(self):
        m = self.game(False)
        kinds, awards = set(), set()
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
            self.assertLessEqual(len(active), 2)
            self.assertEqual(len({m.value("EnemyFlags", s) & 7 for s in active}), len(active))
            for slot in active:
                self.assertLessEqual(m.value("EnemyAge", slot), 1)
                self.assertTrue(0 <= m.value("EnemyX", slot) <= 152)
                self.assertTrue(0 <= m.value("EnemyY", slot) <= 76)
            self.assertLessEqual(sum(bool(m.value("EnemyFlags", s) & 0x40) for s in active), 1)
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


if __name__ == "__main__":
    unittest.main()
