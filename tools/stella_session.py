"""Shared X11/Stella debugger runner for display and combat scenarios."""
from pathlib import Path
import fcntl
import os
import re
import shutil
import subprocess
import time

from x11_input import Keyboard

ROOT = Path(__file__).resolve().parents[1]


def run_stella(stem, commands, labels, advances, timeout=45):
    # Stella 6 saves debugger sessions into HOME with second-resolution names.
    # Concurrent verification jobs can overwrite or collect each other's logs.
    out = ROOT / "build/stella"
    out.mkdir(parents=True, exist_ok=True)
    with (out / ".session.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _run_stella(stem, commands, labels, advances, timeout)


def _run_stella(stem, commands, labels, advances, timeout):
    if not os.environ.get("DISPLAY"):
        raise SystemExit("Use xvfb-run -a python3 tools/verify_stella.py, or run inside a graphical session")
    out = ROOT / "build/stella"
    out.mkdir(parents=True, exist_ok=True)
    # Isolate each run so old captures cannot make a failed run look successful.
    run = out / (time.strftime("%Y%m%d-%H%M%S") + "-" + stem)
    run.mkdir()
    rom = run / "prototype.bin"
    shutil.copyfile(ROOT / f"build/{stem}.bin", rom)
    shutil.copyfile(ROOT / f"build/{stem}.sym", rom.with_suffix(".sym"))
    marker = f"print #{int(time.time()) % 10000000}"
    commands = ["base dec", marker] + commands
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
                deadline = time.monotonic() + timeout
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
    cycles = values("_cycleslo")
    assert len(cycles) == len(advances), (cycles, advances)
    assert all(b - a == count * 262 * 76 for a, b, count in zip(cycles, cycles[1:], advances[1:])), cycles
    return run, values, snapshots, transcript
