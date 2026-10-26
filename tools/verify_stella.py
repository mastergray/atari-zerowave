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
    commands = ["base dec", marker, "frame #5", "print _fcount", "print _scan", "print _cycleslo", "savesnap"]
    directions = [("N", ["up"]), ("NE", ["up", "right"]), ("E", ["right"]), ("SE", ["down", "right"]),
                  ("S", ["down"]), ("SW", ["down", "left"]), ("W", ["left"]), ("NW", ["up", "left"])]
    for _, held in directions:
        for direction in ("up", "down", "left", "right"):
            # Debugger commands set electrical pin levels: zero is pressed.
            commands.append(f"joy0{direction} #{int(direction not in held)}")
        commands.extend(["frame #2", "print *Direction", "print _cycleslo", "savesnap"])
    # frame stops at the next VSYNC, before that frame is drawn. One additional
    # frame makes the new flash visible in the completed framebuffer snapshot.
    commands.extend(["joy0fire #0", "frame #1", "print *BombCount", "print *BombCooldown", "frame #1", "savesnap",
                     "frame #64", "print *BombCount", "print *BombCooldown", "joy0fire #1", "frame #1"])
    # Stella 6 has no SELECT debugger command. Drive just port B's SELECT bit
    # as an output in this test; the ROM still samples SWCHB and detects edges.
    commands.append("ram SWBCNT #2")
    for _ in range(8):
        commands.extend(["ram SWCHB $FD", "frame #1", "ram SWCHB $FF", "frame #1"])
    commands.extend(["print *LayoutId", "frame #1", "print *SelectedSlot", "savesnap",
                     "frame #1", "print *SelectedSlot", "savesnap", "print _cycleslo"])
    for _ in range(2):
        commands.extend(["ram SWCHB $FD", "frame #1", "ram SWCHB $FF", "frame #1", "print *LayoutId",
                         "frame #1", "savesnap", "frame #1", "savesnap"])
    commands.extend(["ram SWBCNT #0", "print _fcount", "saveses"])
    labels = ["neutral"] + [name for name, _ in directions] + ["bomb"]
    labels += [f"{layout}-{phase}" for layout in ("same-height", "near-turret", "north-south") for phase in (0, 1)]
    (run / "commands.script").write_text("\n".join(commands) + "\n")
    # Stella 6 runs autoexec before the debugger display is fully initialized.
    # Send commands after its window opens instead of trusting startup snapshots.
    environment = os.environ.copy()
    environment["XDG_CONFIG_HOME"] = str(run / "config") + "/"
    (run / "config/stella").mkdir(parents=True)
    previous_sessions = set(Path.home().glob("session_*.txt"))
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
            for command in commands:
                keyboard.command(command)
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                # Stella 6 writes saveses to its default home save directory.
                # Relocate only a new session containing this run's unique marker.
                sessions = []
                for candidate in set(Path.home().glob("session_*.txt")) - previous_sessions:
                    if marker in candidate.read_text():
                        destination = run / candidate.name
                        candidate.rename(destination)
                        sessions.append(destination)
                if sessions:
                    break
                if process.poll() is not None:
                    raise RuntimeError(f"Stella exited ({process.returncode}); see {run / 'emulator.log'}")
                time.sleep(0.1)
            else:
                raise RuntimeError(f"Stella did not finish its debugger script; see {run}")
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
    session = sessions[0].read_text()
    if any(error in session for error in ("Unknown command", "No such command", "Invalid")):
        raise RuntimeError(f"Debugger script error in {sessions[0]}")
    def values(expression):
        pattern = re.escape("> print " + expression) + r"\n[^\n]* #([0-9]+)"
        return [int(value) for value in re.findall(pattern, session)]
    assert values("*Direction") == list(range(8)), values("*Direction")
    assert values("*BombCount") == [1, 1], values("*BombCount")
    assert values("*BombCooldown") == [60, 0], values("*BombCooldown")
    assert values("*LayoutId") == [8, 9, 10], values("*LayoutId")
    assert set(values("*SelectedSlot")) == {0, 1}, values("*SelectedSlot")
    cycles = values("_cycleslo")
    # Eight directions, each advanced by exactly two stable frames.
    assert len(cycles) == 10, cycles
    assert all(b - a == 2 * 262 * 76 for a, b in zip(cycles[:8], cycles[1:9])), cycles
    report = {"directory": str(run.relative_to(ROOT)), "snapshots": dict(zip(labels, [p.name for p in snapshots])), "session": sessions[0].name,
              "frame_lines": 262, "cycles_per_frame": 262 * 76, "direction_ids": values("*Direction"),
              "bomb_count_after_held_button": values("*BombCount")[-1]}
    (out / "latest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Stella executed the scenarios and captured {len(snapshots)} TIA images in {run}")
    print(f"Debugger results: {sessions[0]}")


if __name__ == "__main__":
    main()
