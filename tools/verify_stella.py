#!/usr/bin/env python3
"""Run deterministic display scenarios in Stella's real TIA implementation.

Run with a display, or: xvfb-run -a python3 tools/verify_stella.py
Collected emulator state and captures are stored under build/stella/.
"""
from pathlib import Path
import argparse
import json
import os
import re
import shutil
import subprocess
import time

from x11_input import Keyboard

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=45)
    args = parser.parse_args()
    if not os.environ.get("DISPLAY"):
        raise SystemExit("Use xvfb-run -a python3 tools/verify_stella.py, or run inside a graphical session")
    out = ROOT / "build/stella"
    out.mkdir(parents=True, exist_ok=True)
    # Isolate each run so old captures cannot make a failed run look successful.
    run = out / time.strftime("%Y%m%d-%H%M%S")
    run.mkdir()
    rom = run / "prototype.bin"
    shutil.copyfile(ROOT / "build/atari-zerowave.bin", rom)
    shutil.copyfile(ROOT / "build/atari-zerowave.sym", rom.with_suffix(".sym"))
    marker = f"print #{int(time.time()) % 10000000}"
    commands = ["base dec", marker]
    labels, advances = [], []

    def frame(count=1):
        commands.extend([f"frame #{count}", "print _cycleslo"])
        advances.append(count)

    def capture(label):
        # DisplayPattern still describes the completed frame at the VSYNC stop;
        # gameplay counters already describe the next frame's update.
        commands.extend(["print *DisplayPattern", "print *ArenaColor", "savesnap"])
        labels.append(label)

    frame(5)
    capture("neutral")
    directions = [("N", ["up"]), ("NE", ["up", "right"]), ("E", ["right"]), ("SE", ["down", "right"]),
                  ("S", ["down"]), ("SW", ["down", "left"]), ("W", ["left"]), ("NW", ["up", "left"])]
    for name, held in directions:
        for direction in ("up", "down", "left", "right"):
            # Debugger commands set electrical pin levels: zero is pressed.
            commands.append(f"joy0{direction} #{int(direction not in held)}")
        frame(2)
        commands.append("print *Direction")
        capture(f"{name}-0")
        frame()
        capture(f"{name}-1")
    commands.append("joy0fire #0")
    frame()
    commands.extend(["print *BombCount", "print *BombCooldown"])
    # Capture all 16 completed animation frames, including interleaved beams.
    for elapsed in range(16):
        frame()
        capture(f"bomb-{elapsed:02}")
    frame(49)
    commands.extend(["print *BombCount", "print *BombCooldown", "joy0fire #1"])
    frame()
    # Stella 6 has no SELECT debugger command. Drive just port B's SELECT bit
    # as an output in this test; the ROM still samples SWCHB and detects edges.
    commands.append("ram SWBCNT #2")
    for _ in range(8):
        commands.append("ram SWCHB $FD")
        frame()
        commands.append("ram SWCHB $FF")
        frame()
    for layout in ("same-height", "near-turret", "north-south"):
        if layout != "same-height":
            commands.append("ram SWCHB $FD")
            frame()
            commands.append("ram SWCHB $FF")
            frame()
        commands.extend(["print *LayoutId", "joy0fire #0"])
        frame()
        commands.append("print *BombCount")
        frame(13)  # largest ring, with both enemy phases across the next two captures
        commands.append("print *SelectedSlot")
        capture(f"{layout}-0")
        frame()
        commands.append("print *SelectedSlot")
        capture(f"{layout}-1")
        commands.append("joy0fire #1")
        frame(48)  # release and recover before the next layout's bomb
    commands.extend(["ram SWBCNT #0", "print _fcount"])
    (run / "commands.script").write_text("\n".join(commands) + "\n")
    # Stella 6 runs autoexec before the debugger display is fully initialized.
    # Send commands after its window opens instead of trusting startup snapshots.
    environment = os.environ.copy()
    environment["XDG_CONFIG_HOME"] = str(run / "config") + "/"
    (run / "config/stella").mkdir(parents=True)
    sessions = []
    with (run / "emulator.log").open("w") as log:
        process = subprocess.Popen([
            "stella", "-video", "software", "-audio.enabled", "0",
            "-type", "F8", "-format", "NTSC", "-debug", "-dbg.res", "1100x800",
            "-ss1x", "1", "-sssingle", "0", "-snapsavedir", str(run),
            "-statedir", str(run), "-cfgdir", str(run), "-nvramdir", str(run),
            "-plr.bankrandom", "0", "-dev.bankrandom", "0", "-pp", "NO", str(rom),
        ], cwd=run, env=environment, stdout=log, stderr=subprocess.STDOUT)
        try:
            time.sleep(1)
            keyboard = Keyboard()
            # Stella 6's saveses corrupts output after its prompt buffer wraps.
            # Save and clear short chunks without changing emulation state.
            for start in range(0, len(commands), 60):
                for command in commands[start:start + 60]:
                    keyboard.command(command)
                previous_sessions = set(Path.home().glob("session_*.txt"))
                keyboard.command(marker)
                keyboard.command("saveses")
                deadline = time.monotonic() + args.timeout
                while time.monotonic() < deadline:
                    # Stella 6 writes saveses to its default home save directory.
                    # Collect only a new session containing this run's marker.
                    candidates = set(Path.home().glob("session_*.txt")) - previous_sessions
                    owned = [p for p in candidates if marker.encode() in p.read_bytes()]
                    if owned:
                        for candidate in owned:
                            destination = run / candidate.name
                            shutil.move(str(candidate), str(destination))
                            sessions.append(destination)
                        break
                    if process.poll() is not None:
                        raise RuntimeError(f"Stella exited ({process.returncode}); see {run / 'emulator.log'}")
                    time.sleep(0.1)
                else:
                    raise RuntimeError(f"Stella did not finish its debugger script; see {run}")
                keyboard.command("cls")
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    snapshots = sorted(run.glob("*.png"))
    if len(snapshots) != len(labels):
        raise RuntimeError(f"Expected {len(labels)} TIA snapshots; got {len(snapshots)} in {run}")
    session = "\n".join(p.read_text(errors="replace") for p in sessions)
    transcript = run / "session.txt"
    transcript.write_text(session)
    if any(error in session for error in ("Unknown command", "No such command", "Invalid")):
        raise RuntimeError(f"Debugger script error in {transcript}")
    def values(expression):
        pattern = re.escape("> print " + expression) + r"\n[^\n]* #([0-9]+)"
        return [int(value) for value in re.findall(pattern, session)]
    assert values("*Direction") == list(range(8)), values("*Direction")
    assert values("*BombCount") == [1, 1, 2, 3, 4], values("*BombCount")
    assert values("*BombCooldown") == [60, 0], values("*BombCooldown")
    assert values("*LayoutId") == [8, 9, 10], values("*LayoutId")
    slots = values("*SelectedSlot")
    assert len(slots) == 6 and all(set(slots[i:i + 2]) == {0, 1} for i in (0, 2, 4)), slots
    patterns = values("*DisplayPattern")
    assert len(patterns) == len(labels) and patterns[0] == 8, patterns
    colors = values("*ArenaColor")
    assert len(colors) == len(labels), colors
    for direction in range(8):
        start = 1 + direction * 2
        assert patterns[start:start + 2] == [direction, direction], patterns
        assert sorted(color & 15 for color in colors[start:start + 2]) == [10, 14], colors
    bomb_patterns = patterns[17:33]
    assert [p for p in bomb_patterns if p >= 9] == [9, 9, 10, 10, 11, 11, 12, 12], bomb_patterns
    assert bomb_patterns.count(7) == 8, bomb_patterns
    for i in (33, 35, 37):
        assert sorted(patterns[i:i + 2]) == [7, 12], patterns
    assert all(color == 46 for pattern, color in zip(patterns, colors) if pattern >= 9), colors
    cycles = values("_cycleslo")
    assert len(cycles) == len(advances), (cycles, advances)
    assert all(b - a == count * 262 * 76 for a, b, count in zip(cycles, cycles[1:], advances[1:])), cycles
    report = {"directory": str(run.relative_to(ROOT)), "snapshots": dict(zip(labels, [p.name for p in snapshots])), "session": transcript.name,
              "frame_lines": 262, "cycles_per_frame": 262 * 76, "direction_ids": values("*Direction"),
              "bomb_count_after_held_button": values("*BombCount")[1],
              "display_patterns": dict(zip(labels, patterns)), "arena_colors": dict(zip(labels, colors))}
    (out / "latest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Stella executed the scenarios and captured {len(snapshots)} TIA images in {run}")
    print(f"Debugger results: {transcript}")


if __name__ == "__main__":
    main()
