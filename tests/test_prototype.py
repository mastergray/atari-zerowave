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
            for radius in range(tuning["contact_radius"], tuning["spawn_radius"] + 1):
                x, y = assets.center(lane, radius, tuning)
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
        self.assertEqual(machine.value("BombFlash"), 6)
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
        machine.frame(fire=True)
        self.assertEqual(machine.value("BombCount"), 0)
        machine.frame()
        machine.frame(fire=True)
        self.assertEqual(machine.value("BombCount"), 1)

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
        expected = [(5, 0x0d), (13, 0x0e), (21, 0x1c), (29, 0x0f),
                    (36, 0x1b), (44, 0x0d), (52, 0x0e), (57, 0x0f)]
        for line in range(72, 232):
            writes = [(cycle % 76, register) for cycle, register, _ in machine.bus.events
                      if (cycle - origin) // 76 == line and register in (0x0d, 0x0e, 0x0f, 0x1b, 0x1c)]
            self.assertEqual(writes, expected, line)

    def test_positioning_loop_does_not_cross_page(self):
        machine = self.machine()
        address = machine.sym["PositionPlayer"]
        # SEC; STA WSYNC; SBC #15; BCS back. Branch must cost exactly 3 cycles.
        loop, branch_end = address + 3, address + 7
        self.assertEqual(loop >> 8, branch_end >> 8)


if __name__ == "__main__":
    unittest.main()
