import importlib.util
import json
from pathlib import Path
import unittest

from rom_machine import Machine, ROOT

spec = importlib.util.spec_from_file_location("assets", ROOT / "tools/generate_assets.py")
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)


class AssetTests(unittest.TestCase):
    def test_every_lane_center_is_covered(self):
        tuning = assets.load_config()
        for lane in range(8):
            rows = assets.beam_rows(lane, tuning)
            ball = assets.ball_beam(lane, tuning)
            for radius in range(tuning["contact_radius"], tuning["spawn_radius"] + 1):
                x, y = assets.center(lane, radius, tuning)
                if ball["enabled"]:
                    # Rounding a thin ray and a sprite's center separately can
                    # differ by one clock, still inside the enemy silhouette.
                    self.assertTrue(any(p is not None and abs(p - x) <= 1
                                        for p in ball["pixels"][y * 2:y * 2 + 2]), (lane, radius))
                else:
                    pixel = assets.encode_row({x // 4})
                    self.assertTrue(all((a & b) == b for a, b in zip(rows[y], pixel)), (lane, radius))
                self.assertGreaterEqual(x - 4, 0)
                self.assertLess(x + 3, 160)
                self.assertGreaterEqual(y - 2, 0)
                self.assertLess(y + 1, 80)

    def test_neutral_is_blank(self):
        self.assertFalse(any(any(row) for row in assets.beam_rows(8, assets.load_config())))

    def test_directional_rays_do_not_mirror(self):
        tuning = assets.load_config()
        for lane in (1, 2, 3):
            self.assertFalse(any(any(row[:3]) for row in assets.beam_rows(lane, tuning)))
        for lane in (5, 6, 7):
            self.assertFalse(any(any(row[3:]) for row in assets.beam_rows(lane, tuning)))
        for lane in (0, 1, 3, 4, 5, 7):
            pixels = [x for x in assets.ball_beam(lane, tuning)["pixels"] if x is not None]
            if lane in (1, 3):
                self.assertTrue(all(x > tuning["center_x"] for x in pixels))
            elif lane in (5, 7):
                self.assertTrue(all(x < tuning["center_x"] for x in pixels))
            else:
                self.assertEqual(set(pixels), {tuning["center_x"]})
            self.assertTrue(all(abs(a - b) <= 1 for a, b in zip(pixels, pixels[1:])))

    def test_rings_expand_to_bomb_range_and_keep_a_hollow_center(self):
        tuning = assets.load_config()
        bounds = []
        radii = assets.bomb_radii(tuning)
        self.assertEqual(radii[-1], tuning["bomb_radius"])
        for radius in radii:
            rows = assets.ring_rows(radius, tuning)
            occupied_y = [y for y, row in enumerate(rows) if any(row)]
            bounds.append((min(occupied_y), max(occupied_y)))
            for lane in range(8):
                x, y = assets.center(lane, radius, tuning)
                pixel = assets.encode_row({x // 4})
                self.assertTrue(all((a & b) == b for a, b in zip(rows[y], pixel)))
            center = assets.encode_row({tuning["center_x"] // 4})
            self.assertFalse(any(a & b for a, b in zip(rows[tuning["center_y"]], center)))
            self.assertTrue(all(row[0] == row[5] == 0 for row in rows))
        self.assertTrue(all(a[0] > b[0] and a[1] < b[1] for a, b in zip(bounds, bounds[1:])))


class CartridgeTests(unittest.TestCase):
    def machine(self, bank=1):
        machine = Machine(bank)
        machine.boot()
        return machine

    def test_both_startup_banks_and_ram_guards(self):
        for bank in (0, 1):
            machine = self.machine(bank)
            for _ in range(4):
                self.assertEqual(machine.frame(), 262 * 76)
                self.assertEqual(machine.value("BeamDrawDirection"), 255)
                self.assertEqual(machine.value("BeamFadeTimer"), 0)
            self.assertEqual(machine.bus.ram[0x68:0x70], bytes([0xa5] * 8))
            self.assertGreaterEqual(machine.min_sp, 0xef)

    def test_all_input_combinations(self):
        machine = self.machine()
        expected = {0: 255, 1: 0, 9: 1, 8: 2, 10: 3, 2: 4, 6: 5, 4: 6, 5: 7}
        for raw in range(16):
            normalized = raw
            if raw & 3 == 3:
                normalized &= ~3
            if raw & 12 == 12:
                normalized &= ~12
            self.assertEqual(machine.frame(raw), 262 * 76)
            self.assertEqual(machine.value("Direction"), expected[normalized])
            self.assertEqual(machine.value("BeamEnabled"), int(normalized != 0))

    def test_bomb_edge_cooldown_and_simultaneous_beam(self):
        machine = self.machine()
        machine.frame(9, fire=True)
        self.assertEqual(machine.value("BombCount"), 1)
        self.assertEqual(machine.value("BombCooldown"), 60)
        self.assertEqual(machine.value("BombTimer"), 16)
        self.assertEqual(machine.value("Direction"), 1)
        for _ in range(90):
            self.assertEqual(machine.frame(9, fire=True), 262 * 76)
        self.assertEqual(machine.value("BombCount"), 1)
        machine.frame(fire=False)
        machine.frame(fire=True)
        self.assertEqual(machine.value("BombCount"), 2)
        machine.frame(fire=False)
        for _ in range(57):
            machine.frame()
        machine.frame(fire=True)  # t+59: rejected
        self.assertEqual(machine.value("BombCount"), 2)
        machine.frame(fire=True)  # t+60: held, not queued
        self.assertEqual(machine.value("BombCount"), 2)
        machine.frame(fire=False)
        machine.frame(fire=True)
        self.assertEqual(machine.value("BombCount"), 3)

    def test_exact_cooldown_boundary(self):
        machine = self.machine()
        machine.frame(fire=True)
        for _ in range(59):
            machine.frame(fire=False)
        machine.frame(fire=True)
        self.assertEqual(machine.value("BombCount"), 2)

    def test_reset_with_fire_does_not_bomb(self):
        machine = self.machine()
        machine.frame(fire=True, reset=True)
        self.assertEqual(machine.value("BombCount"), 0)
        self.assertEqual(machine.value("BombTimer"), 0)
        machine.frame(fire=True)
        self.assertEqual(machine.value("BombCount"), 0)
        machine.frame()
        machine.frame(fire=True)
        self.assertEqual(machine.value("BombCount"), 1)
        machine.frame(reset=True)
        self.assertEqual(machine.value("BombTimer"), 0)
        self.assertLessEqual(machine.value("DisplayPattern"), 8)

    def test_select_cycles_fixtures_and_two_enemy_fairness(self):
        machine = self.machine()
        fixtures = json.loads((ROOT / "config/fixtures.json").read_text())
        for layout, fixture in enumerate(fixtures):
            self.assertEqual(machine.value("LayoutId"), layout)
            selected = []
            for _ in range(6):
                self.assertEqual(machine.frame(direction_mask=1), 262 * 76)
                selected.append(machine.value("SelectedSlot"))
                for slot in range(len(fixture["enemies"])):
                    self.assertLessEqual(machine.value("EnemyAge", slot), 1)
            if len(fixture["enemies"]) == 2:
                self.assertEqual(set(selected), {0, 1})
                self.assertTrue(all(a != b for a, b in zip(selected, selected[1:])))
            machine.frame(select=True)
            machine.frame(select=True)
            machine.frame(select=False)
        self.assertEqual(machine.value("LayoutId"), 0)

    def test_no_enemies_is_safe(self):
        machine = self.machine()
        for slot in range(4):
            machine.poke("EnemyFlags", 0, slot)
        self.assertEqual(machine.frame(), 262 * 76)
        self.assertEqual(machine.value("SelectedSlot"), 255)

    def test_arena_register_deadlines(self):
        machine = self.machine()
        machine.bus.events.clear()
        machine.frame(direction_mask=9, fire=True)
        origin = machine.bus.vsync_edges[-1] // 76 * 76
        expected = [(3, 0x0d), (11, 0x0e), (19, 0x1c), (27, 0x0f),
                    (34, 0x1b), (42, 0x0d), (50, 0x0e), (53, 0x0f)]
        for line in range(72, 232):
            writes = [(cycle % 76, register) for cycle, register, _ in machine.bus.events
                      if (cycle - origin) // 76 == line and register in (0x0d, 0x0e, 0x0f, 0x1b, 0x1c)]
            self.assertEqual(writes, expected, line)

    def assert_rendered_pattern(self, machine, pattern):
        """Check actual TIA data and deadlines for all 160 lines of this frame."""
        manifest = json.loads((ROOT / "build/generated/manifest.json").read_text())
        rows = manifest["patterns"][pattern]
        ball = manifest["ball_patterns"][pattern]
        origin = machine.bus.vsync_edges[-1] // 76 * 76
        if ball["enabled"]:
            self.assert_ball_pattern(machine, ball, origin)
            return
        self.assertEqual(machine.value("BallKernel"), 0)
        self.assertEqual(machine.bus.tia[0x1f], 0)  # no residual ball on ring/neutral frames
        scanlines = [[] for _ in range(160)]
        for cycle, register, value in machine.bus.events:
            line = (cycle - origin) // 76 - 72
            if 0 <= line < 160 and register in (0x0d, 0x0e, 0x0f):
                scanlines[line].append((cycle % 76, register, value))
        schedule = [(3, 0x0d), (11, 0x0e), (27, 0x0f), (42, 0x0d), (50, 0x0e), (53, 0x0f)]
        for line, writes in enumerate(scanlines):
            self.assertEqual(writes, [(cycle, register, value) for (cycle, register), value
                                     in zip(schedule, rows[line // 2])], (pattern, line))

    def assert_ball_pattern(self, machine, ball, origin):
        self.assertEqual(machine.value("BallKernel"), 1)
        self.assertEqual(machine.bus.tia[0x0a] & 0x30, 0)  # one color-clock width
        x, motion, enabled = ball["initial_x"], 0, 0
        stationary = None
        lines = [[] for _ in range(160)]
        for cycle, register, value in machine.bus.events:
            line = (cycle - origin) // 76 - 72
            if 0 <= line < 160:
                lines[line].append((cycle % 76, register, value))
            elif 0 <= cycle - origin < 72 * 76 and register == 0x2b:
                stationary = True  # separator clears all five motion registers
            elif stationary and register in (0x20, 0x21, 0x24):
                stationary = False
        self.assertTrue(stationary, "Clear motion before strobing HMOVE throughout the arena")
        for line, writes in enumerate(lines):
            moves = 0
            for cycle, register, value in writes:
                self.assertNotIn(register, (0x0d, 0x0e, 0x0f, 0x20, 0x21))
                if register == 0x2a:
                    self.assertEqual(cycle, 3)
                    delta = motion >> 4
                    x -= delta if delta < 8 else delta - 16
                    moves += 1
                elif register == 0x24:
                    self.assertGreaterEqual(cycle - 3, 24)
                    motion = value
                elif register == 0x1f:
                    enabled = value & 2
                    if line != 159:
                        self.assertLessEqual(cycle, 21)
            self.assertEqual(moves, 1)
            self.assertEqual(x if enabled else None, ball["pixels"][line], line)
        self.assertEqual(machine.bus.tia[0x1f], 0)

    def test_beam_has_no_blank_frames_or_disabled_input_or_sound(self):
        machine = self.machine()
        for direction, mask in enumerate((1, 9, 8, 10, 2, 6, 4, 5)):
            patterns = []
            for _ in range(2):
                machine.bus.events.clear()
                self.assertEqual(machine.frame(mask), 262 * 76)
                pattern = machine.value("DisplayPattern")
                patterns.append(pattern)
                self.assertEqual(machine.value("BeamEnabled"), int(mask != 0))
                self.assertEqual(machine.bus.tia[0x19], 2 if mask else 0)
                self.assert_rendered_pattern(machine, pattern)
            self.assertEqual(patterns, [direction, direction])

    def test_release_fades_last_direction_and_hue_for_fifteen_frames(self):
        for direction, mask in enumerate((1, 9, 8, 10, 2, 6, 4, 5)):
            machine = self.machine()
            machine.poke("FrameCounter", direction * 4)
            machine.frame(mask)
            hue = machine.value("ArenaColor") & 0xf0
            self.assertEqual(machine.value("BeamFadeTimer"), 15)
            for level in range(15, 0, -1):
                machine.bus.events.clear()
                self.assertEqual(machine.frame(), 262 * 76)
                self.assertEqual(machine.value("Direction"), 255)
                self.assertEqual(machine.value("BeamEnabled"), 0)
                self.assertEqual(machine.bus.tia[0x19], 0)
                self.assertEqual(machine.value("BeamFadeTimer"), level - 1)
                self.assertEqual(machine.value("DisplayPattern"), direction)
                self.assertEqual(machine.value("ArenaColor"), hue | level)
                self.assert_rendered_pattern(machine, direction)
                self.assert_arena_colors_and_sprites(machine)
            for _ in range(3):
                machine.frame()
                self.assertEqual(machine.value("DisplayPattern"), 8)
                self.assertEqual(machine.value("BeamDrawDirection"), 255)
                self.assertEqual(machine.value("ArenaColor"), 0)

    def test_reaim_and_reset_cancel_fading_without_trails(self):
        machine = self.machine()
        machine.frame(9)
        for _ in range(5):
            machine.frame()
        self.assertEqual(machine.value("ArenaColor") & 15, 11)
        machine.frame(4)
        self.assertEqual(machine.value("BeamEnabled"), 1)
        self.assertEqual(machine.value("DisplayPattern"), 6)
        self.assertEqual(machine.value("ArenaColor") & 15, 14)
        self.assertEqual(machine.value("BeamFadeTimer"), 15)
        machine.frame(15)  # opposing axes cancel, initiating the same release fade
        self.assertEqual(machine.value("BeamEnabled"), 0)
        self.assertEqual(machine.value("DisplayPattern"), 6)
        machine.frame(reset=True)
        self.assertEqual(machine.value("BeamFadeTimer"), 0)
        self.assertEqual(machine.value("DisplayPattern"), 8)
        machine.frame()
        self.assertEqual(machine.value("DisplayPattern"), 8)

    def test_bomb_and_two_enemies_continue_during_release_fade(self):
        machine = self.machine()
        for _ in range(8):
            machine.frame(select=True)
            machine.frame()
        machine.frame(8)
        hue = machine.value("ArenaColor") & 0xf0
        selected = []
        for elapsed in range(18):
            machine.bus.events.clear()
            self.assertEqual(machine.frame(fire=True), 262 * 76)
            self.assertEqual(machine.value("BeamEnabled"), 0)
            self.assertEqual(machine.value("BombCount"), 1)
            self.assertEqual(machine.value("BeamFadeTimer"), max(0, 14 - elapsed))
            if machine.value("FramePhase") and elapsed < 16:
                self.assertEqual(machine.value("DisplayPattern"), 9 + elapsed // 4)
                self.assertEqual(machine.value("ArenaColor"), 46)
            else:
                self.assertEqual(machine.value("DisplayPattern"), 2 if elapsed < 15 else 8)
                self.assertEqual(machine.value("ArenaColor"), hue | (15 - elapsed) if elapsed < 15 else 0)
            selected.append(machine.value("SelectedSlot"))
            self.assert_rendered_pattern(machine, machine.value("DisplayPattern"))
        self.assertTrue(all(a != b for a, b in zip(selected, selected[1:])))

    def test_beam_changes_color_over_time_but_stays_uniform_within_each_frame(self):
        machine = self.machine()
        tuning = assets.load_config()
        seen_colors = set()
        # Every hue, both frame phases, and a counter rollover.
        machine.poke("FrameCounter", 248)
        for _ in range(40):
            machine.bus.events.clear()
            self.assertEqual(machine.frame(9), 262 * 76)
            color = machine.value("ArenaColor")
            phase = (machine.value("FrameCounter") >> 2) & 7
            self.assertEqual(color, tuning["beam_colors"][phase])
            seen_colors.add(color)
            self.assert_arena_colors_and_sprites(machine)
        self.assertEqual(seen_colors, set(tuning["beam_colors"]))

    def assert_arena_colors_and_sprites(self, machine):
        origin = machine.bus.vsync_edges[-1] // 76 * 76
        selected = machine.value("SelectedSlot")
        ball_kernel = machine.value("BallKernel")
        top = machine.value("EnemyY", selected) if selected != 255 else 0
        kind = machine.value("EnemyFlags", selected) if selected != 255 else 0
        shape = [0x18, 0x3c, 0x7e, 0xff]
        if kind & 0x40:
            shape = [0x7e] * 4 if machine.value("EnemyRadiusHi", selected) <= 24 else [0x7e, 0x42, 0x42, 0x7e]
        writes = []
        color = None
        for cycle, register, value in machine.bus.events:
            line = (cycle - origin) // 76 - 72
            if register == 0x08:
                # The only arena color setup happens before its first scanline.
                self.assertFalse(0 <= line < 160, "Unexpected scanline color gradient")
                color = value
            if not 0 <= line < 160 or register not in (0x1b, 0x1c):
                continue
            self.assertEqual(color, machine.value("ArenaColor"))
            row = line // 2
            if register == 0x1b:
                expected = [0x18, 0x3c, 0x7e, 0x3c][row - 38] if 38 <= row < 42 else 0
                self.assertEqual(value, expected)
                if ball_kernel:
                    self.assertLessEqual(cycle % 76, 36)
                else:
                    self.assertEqual(cycle % 76, 34)
            else:
                expected = shape[row - top] if selected != 255 and top <= row < top + 4 else 0
                self.assertEqual(value, expected)
                if ball_kernel:
                    self.assertLessEqual(cycle % 76, 29)
                else:
                    self.assertEqual(cycle % 76, 19)
            writes.append(register)
        self.assertEqual(len(writes), 160 * 2)

    def test_every_ring_and_beam_phase_preserves_two_enemy_schedule(self):
        # A press on either parity must show each ring twice, not skip a stage.
        for offset in (0, 1):
            machine = self.machine()
            for _ in range(8):
                machine.frame(select=True)
                machine.frame()
            for _ in range(offset):
                machine.frame()
            rings, selected = [], []
            for elapsed in range(17):
                mask = (1, 9, 8, 10, 2, 6, 4, 5)[elapsed % 8]
                machine.bus.events.clear()
                self.assertEqual(machine.frame(mask, fire=True), 262 * 76)
                self.assertEqual(machine.value("BombEvent"), int(elapsed == 0))
                self.assertEqual(machine.value("BombTimer"), max(0, 16 - elapsed))
                self.assertEqual(machine.bus.tia[0x1a], max(0, 6 - elapsed))
                self.assertEqual(machine.value("BeamEnabled"), 1)
                pattern = machine.value("DisplayPattern")
                if machine.value("FramePhase") and elapsed < 16:
                    self.assertEqual(pattern, 9 + elapsed // 4)
                    rings.append(pattern)
                else:
                    self.assertEqual(pattern, elapsed % 8)
                self.assert_rendered_pattern(machine, pattern)
                self.assert_arena_colors_and_sprites(machine)
                selected.append(machine.value("SelectedSlot"))
                self.assertEqual(machine.bus.tia[0x09], 0)  # no arena background flash
            self.assertEqual(rings, [9, 9, 10, 10, 11, 11, 12, 12])
            self.assertEqual(set(selected), {0, 1})
            self.assertTrue(all(a != b for a, b in zip(selected, selected[1:])))
            self.assertEqual(machine.bus.ram[0x68:0x70], bytes([0xa5] * 8))
            self.assertGreaterEqual(machine.min_sp, 0xef)

    def test_bomb_animates_without_a_beam(self):
        machine = self.machine()
        for elapsed in range(16):
            machine.frame(fire=True)
            self.assertEqual(machine.value("BeamEnabled"), 0)
            expected = 9 + elapsed // 4 if machine.value("FramePhase") else 8
            self.assertEqual(machine.value("DisplayPattern"), expected)

    def test_positioning_loop_does_not_cross_page(self):
        machine = self.machine()
        address = machine.sym["PositionPlayer"]
        # SEC; STA WSYNC; SBC #15; BCS back. Branch must cost exactly 3 cycles.
        loop, branch_end = address + 3, address + 7
        self.assertEqual(loop >> 8, branch_end >> 8)


if __name__ == "__main__":
    unittest.main()
