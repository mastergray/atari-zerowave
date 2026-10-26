#!/usr/bin/env python3
"""Build a pinned assembler and obtain the test CPU locally, without system changes."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DEPENDENCIES = (
    ("dasm-src", "https://github.com/dasm-assembler/dasm.git", "2.20.14.1", "09270863f5f70e5200c30d2778f654ff7a40adba"),
    ("py65", "https://github.com/mnaberez/py65.git", "1.2.0", "9455a5c70e059cd1263982051e392a8ac25c3e6a"),
)


def main():
    for name, url, tag, revision in DEPENDENCIES:
        destination = ROOT / ".tools" / name
        if not destination.exists():
            subprocess.run(["git", "clone", "--depth", "1", "--branch", tag, url, str(destination)], check=True)
        actual = subprocess.check_output(["git", "-C", str(destination), "rev-parse", "HEAD"], text=True).strip()
        if actual != revision:
            raise SystemExit(f"Refusing to use {destination}: expected {revision}, found {actual}")
    subprocess.run(["make", "-C", str(ROOT / ".tools/dasm-src/src")], check=True)
    print("Pinned DASM and py65 are ready in .tools/.")


if __name__ == "__main__":
    main()
