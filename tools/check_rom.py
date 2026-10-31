#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 mastergray
# SPDX-License-Identifier: GPL-3.0-only

"""Structural checks on the actual DASM image and symbol file."""
from pathlib import Path
import hashlib
import json
import re
import argparse

ROOT = Path(__file__).resolve().parents[1]


def symbols(path=None):
    result = {}
    for line in (path or ROOT / "build/atari-zerowave.sym").read_text().splitlines():
        match = re.match(r"^(\S+)\s+([0-9a-fA-F]{4})\s", line)
        if match:
            result[match[1]] = int(match[2], 16)
    return result


def check(display=False):
    stem = "atari-zerowave-display" if display else "atari-zerowave"
    rom = (ROOT / f"build/{stem}.bin").read_bytes()
    sym = symbols(ROOT / f"build/{stem}.sym")
    assert len(rom) == 8192, "Wrong F8 image size"
    assert rom[0xf80:0x1000] == rom[0x1f80:0x2000], "Bank stubs/vectors differ"
    assert rom[0xffa:0x1000] == b"\x80\xff" * 3, "Invalid vectors"
    if not display:
        assert sym["LevelDigitOnes"] == 0xffaa
        assert sym["ProgressRight1"] == 0xffdc and sym["ProgressRight2"] == 0xffe5
        shared = (ROOT / "build/generated/shared_hud.inc").read_text()
        data = bytes(int(value, 16) for value in re.findall(r"\$([0-9a-f]{2})", shared))
        assert sym["DigitOffsets"] == 0xffee
        assert len(data) == 78 and rom[0xfaa:0xff8] == data, "Shared HUD data misplaced"
    assert sym["RamEnd"] == 0x100 and sym["StackBottom"] == 0xf0
    assert sym["GuardStart"] == 0xe8 and sym["EnemyFlags"] == 0x80
    assert sym["ARENA_START_LINE"] == (72 if display else 70)
    for bank in (0, 1):
        assert sym[f"Bank{bank}End"] <= 0xff80, "Bank overflows trampoline area"
    for name, address in sym.items():
        if name.startswith(("PlayfieldStream", "BeamMotionStream")) or name == "TurretRows":
            assert (address & 255) + 79 < 256, f"Page crossing: {name}"
        elif name.startswith("HudPlane"):
            assert (address & 255) + 23 < 256, f"Page crossing: {name}"
        elif name.startswith("HudText"):
            assert (address & 255) + 4 < 256, f"Page crossing: {name}"
        elif name in ("DigitLeft", "DigitRight", "LevelDigitTens", "LevelDigitOnes"):
            assert (address & 255) + 49 < 256, f"Page crossing: {name}"
        elif name in ("ReuseMotion", "ReuseRemainder"):
            assert address & 255 == 0, f"Motion table must be page aligned: {name}"
        elif name == "LevelLabel":
            assert (address & 255) + 4 < 256, f"Page crossing: {name}"
        elif name.startswith("Sprite") or name in ("BurstFlash", "BurstSparks", "BurstEmbers"):
            assert address & 255 in (0, 88), f"Bad paired sprite offset: {name}"
            assert (address & 255) + 76 + 6 + 79 < 256, f"Sprite page crossing: {name}"
    manifest = json.loads((ROOT / "build/generated/manifest.json").read_text())
    report = {
        "rom_bytes": len(rom), "sha256": hashlib.sha256(rom).hexdigest(),
        "assembler_pin": "DASM 2.20.14.1", "enemy_slots": 4,
        "prototype_display_cap": 2 if display else 4, "display_test": display,
        "arena_first_frame_line": sym["ARENA_START_LINE"],
        "combat_difficulty": "static fixtures" if display else "table-driven waves with completion clears; cap of four with bounded vertical sprite reuse",
        "levels": None if display else manifest["levels"],
        "bank_bytes_before_tail": [sym[f"Bank{bank}End"] - 0xf000 for bank in (0, 1)],
        "bank_headroom_before_tail": [0xff80 - sym[f"Bank{bank}End"] for bank in (0, 1)],
        "beam_streams": manifest["unique_beam_streams"],
        "playfield_streams": manifest["unique_playfield_streams"],
        "raster_streams": manifest["unique_raster_streams"],
        "vertical_diagonal_beam_width_clocks": 1,
        "beam_release_fade_updates" if display else "beam_shot_fade_updates": manifest["tuning"]["beam_fade_start"],
        "beam_trigger": "held (legacy diagnostic)" if display else "center-to-direction flick",
        "enemy_types": manifest["tuning"]["enemy_types"],
        "enemy_burst_updates": sym["ENEMY_BURST_FRAMES"],
        "immunity_feedback_updates": sym["IMMUNE_FLASH_FRAMES"],
        "player_hit_flash_updates": sym["PLAYER_HIT_FRAMES"],
        "wave_completion": None if display else {"cue_updates": sym["LEVEL_BREAK_FRAMES"],
            "effect": "full green bar, survivor bursts, yellow flashes, clear sound",
            "requires_full_health": False, "extra_score": 0},
        "health_recovery": None if display else {"score_interval": 1000, "hp": 1,
            "hp_cap": sym["START_HP"], "cue_updates": 32,
            "at_full_hp": "clear surviving enemies; quota credit without extra score",
            "flash_color": manifest["tuning"]["colors"]["health_bonus"],
            "clear_flash_color": manifest["tuning"]["colors"]["clear_bonus"]},
        "level_background_colors": None if display else manifest["tuning"]["level_background_colors"],
        "audio": {"beam_updates": None if display else manifest["tuning"]["beam_sound_frames"],
                  "fast_approach": None if display else json.loads((ROOT / "config/audio.json").read_text())["fast_approach"],
                  "events": [] if display else [
                      {"name": sound["name"], "priority": index,
                       "updates": sum(segment[0] for segment in sound["segments"])}
                      for index, sound in enumerate(json.loads((ROOT / "config/audio.json").read_text())["sounds"], 1)]},
        "bomb_radii": manifest["bomb_radii"],
        "bomb_cooldown_updates": manifest["tuning"]["bomb_cooldown"],
        "bomb_animation_frames": manifest["bomb_animation_frames"],
        "reference_commit": "fb68a689d3fa6346696dd2310e5dd3d167c065a1",
    }
    report_name = "display-build-report.json" if display else "build-report.json"
    (ROOT / "build" / report_name).write_text(json.dumps(report, indent=2) + "\n")
    print(f"F8 ROM: {len(rom)} bytes; bank headroom {report['bank_headroom_before_tail']}; RAM map and page-safe streams checked.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--display", action="store_true")
    check(parser.parse_args().display)
