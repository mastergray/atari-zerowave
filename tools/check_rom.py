#!/usr/bin/env python3
"""Structural checks on the actual DASM image and symbol file."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def symbols(path=None):
    result = {}
    for line in (path or ROOT / "build/atari-zerowave.sym").read_text().splitlines():
        match = re.match(r"^(\S+)\s+([0-9a-fA-F]{4})\s", line)
        if match:
            result[match[1]] = int(match[2], 16)
    return result


def check():
    rom = (ROOT / "build/atari-zerowave.bin").read_bytes()
    sym = symbols()
    assert len(rom) == 8192, "Wrong F8 image size"
    assert rom[0xf80:0x1000] == rom[0x1f80:0x2000], "Bank stubs/vectors differ"
    assert rom[0xffa:0x1000] == b"\x80\xff" * 3, "Invalid vectors"
    assert sym["RamEnd"] == 0x100 and sym["StackBottom"] == 0xf0
    assert sym["GuardStart"] == 0xe8 and sym["EnemyFlags"] == 0x80
    for bank in (0, 1):
        assert sym[f"Bank{bank}End"] <= 0xff80, "Bank overflows trampoline area"
    for name, address in sym.items():
        if name.startswith(("PlayfieldStream", "BeamMotionStream")) or name == "TurretRows":
            assert (address & 255) + 79 < 256, f"Page crossing: {name}"
        elif name.startswith("HudPlane"):
            assert (address & 255) + 23 < 256, f"Page crossing: {name}"
        elif name.startswith("Sprite"):
            assert address & 255 == 0, f"Unaligned sprite: {name}"
    manifest = json.loads((ROOT / "build/generated/manifest.json").read_text())
    report = {
        "rom_bytes": len(rom), "sha256": hashlib.sha256(rom).hexdigest(),
        "assembler_pin": "DASM 2.20.14.1", "enemy_slots": 4,
        "prototype_display_cap": 2,
        "bank_bytes_before_tail": [sym[f"Bank{bank}End"] - 0xf000 for bank in (0, 1)],
        "bank_headroom_before_tail": [0xff80 - sym[f"Bank{bank}End"] for bank in (0, 1)],
        "beam_streams": manifest["unique_beam_streams"],
        "playfield_streams": manifest["unique_playfield_streams"],
        "raster_streams": manifest["unique_raster_streams"],
        "vertical_diagonal_beam_width_clocks": 1,
        "beam_release_fade_updates": manifest["tuning"]["beam_fade_start"],
        "bomb_radii": manifest["bomb_radii"],
        "bomb_animation_frames": manifest["bomb_animation_frames"],
        "reference_commit": "fb68a689d3fa6346696dd2310e5dd3d167c065a1",
    }
    (ROOT / "build/build-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"F8 ROM: {len(rom)} bytes; bank headroom {report['bank_headroom_before_tail']}; RAM map and page-safe streams checked.")


if __name__ == "__main__":
    check()
