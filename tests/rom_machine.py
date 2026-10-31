# SPDX-FileCopyrightText: 2026 mastergray
# SPDX-License-Identifier: GPL-3.0-only

"""Execute the real cartridge on py65 with a small, explicitly limited VCS bus.

This harness checks CPU state, bank switching, and scanline write deadlines.
It does not emulate the TIA's pixel circuitry; Stella supplies the visual check.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools/py65"))
try:
    from py65.devices.mpu6502 import MPU
except ImportError as error:
    raise RuntimeError("Run make bootstrap to obtain the pinned py65 test CPU") from error
sys.path.insert(0, str(ROOT / "tools"))
from check_rom import symbols


class Bus:
    def __init__(self, rom, bank):
        self.rom, self.bank = rom, bank
        self.ram = bytearray([0x6d] * 128)
        self.tia = bytearray(64)
        self.joystick, self.switches, self.fire = 0xff, 0xff, 0x80
        self.cpu = None
        self.access_cycle = 0
        self.timer_start, self.timer_value = 0, 0
        self.wait = False
        self.events = []
        self.vsync_edges = []
        self.minimum_sp = 0xff

    def __getitem__(self, address):
        address &= 0x1fff
        if address & 0x1000:
            if address in (0x1ff8, 0x1ff9):
                self.bank = address - 0x1ff8
            return self.rom[self.bank * 4096 + (address & 0xfff)]
        if address & 0x80:
            if address & 0x200:
                register = address & 0x1f
                if register == 0:
                    return self.joystick
                if register == 2:
                    return self.switches
                if register == 4:
                    elapsed = max(0, self.access_cycle - self.timer_start)
                    # RIOT starts its prescaler at divider-1, so the first
                    # decrement occurs after one cycle, not after 64.
                    tick = (elapsed + 63) // 64
                    if tick <= self.timer_value:
                        return self.timer_value - tick
                    return (255 - (elapsed - (self.timer_value * 64 + 1))) & 255
                return 0
            return self.ram[address & 0x7f]
        return self.fire if address & 0xf == 0xc else 0

    def __setitem__(self, address, value):
        address &= 0x1fff
        value &= 255
        if address & 0x1000:
            if address in (0x1ff8, 0x1ff9):
                self.bank = address - 0x1ff8
            return
        if address & 0x80:
            if address & 0x200:
                if address & 0x1f == 0x16:
                    self.timer_start, self.timer_value = self.access_cycle, value
            else:
                self.ram[address & 0x7f] = value
            return
        register = address & 0x3f
        if register == 0 and value & 2 and not self.tia[0] & 2:
            self.vsync_edges.append(self.access_cycle)
        self.tia[register] = value
        self.events.append((self.access_cycle, register, value))
        if register == 2:
            self.wait = True


class Machine:
    def __init__(self, bank=1, diagnostic=False):
        self.diagnostic = diagnostic
        stem = "atari-zerowave-display" if diagnostic else "atari-zerowave"
        self.sym = symbols(ROOT / f"build/{stem}.sym")
        self.bus = Bus((ROOT / f"build/{stem}.bin").read_bytes(), bank)
        self.cpu = MPU(memory=self.bus, pc=None)
        self.bus.cpu = self.cpu
        self.min_sp = 0xff
        self.checkpoints = []

    def step(self):
        # All TIA/RIOT writes in this ROM use fixed-cycle stores. Attribute an
        # access to instruction completion; WSYNC then holds until a line edge.
        opcode = self.bus[self.cpu.pc]
        self.bus.access_cycle = self.cpu.processorCycles + self.cpu.cycletime[opcode]
        self.cpu.step()
        self.min_sp = min(self.min_sp, self.cpu.sp)
        if self.bus.wait:
            self.cpu.processorCycles = ((self.cpu.processorCycles + 75) // 76) * 76
            self.bus.wait = False

    def until(self, label, bank, limit=100000):
        for _ in range(limit):
            if self.cpu.pc == self.sym[label] and self.bus.bank == bank:
                return
            self.step()
        raise AssertionError(f"Did not reach {label}; PC={self.cpu.pc:04x}, bank={self.bus.bank}")

    def boot(self):
        self.until("GameFrame", 0)

    def frame(self, direction_mask=0, fire=False, reset=False, select=False):
        self.bus.joystick = 0xff ^ (direction_mask << 4)
        self.bus.fire = 0 if fire else 0x80
        self.bus.switches = 0xff ^ (int(reset) | (int(select) << 1))
        start = self.cpu.processorCycles
        self.step()
        self.until("LogicDone", 0)
        logic_cycles = self.cpu.processorCycles - start
        self.until("FrameStart", 1)
        self.step()
        self.until("PrepareDone", 1)
        prepare_cycle = self.cpu.processorCycles
        self.until("GameFrame", 0)
        self.checkpoints.append((logic_cycles, prepare_cycle))
        return self.cpu.processorCycles - start

    def value(self, name, index=0):
        return self.bus.ram[(self.sym[name] + index) & 0x7f]

    def poke(self, name, value, index=0):
        self.bus.ram[(self.sym[name] + index) & 0x7f] = value

    def call(self, label):
        """Execute a bank-0 routine directly, returning to the frame checkpoint."""
        assert self.bus.bank == 0 and self.cpu.pc == self.sym["GameFrame"]
        self.cpu.stPushWord(self.sym["GameFrame"] - 1)
        self.cpu.pc = self.sym[label]
        self.until("GameFrame", 0)
