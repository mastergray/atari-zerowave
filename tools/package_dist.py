#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 mastergray
# SPDX-License-Identifier: GPL-3.0-only

"""Package corresponding source from the working tree, including local changes."""
from pathlib import Path
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]

# Explicit source/documentation patterns avoid collecting build outputs, local
# toolchains, reference checkouts, Git history, caches, or machine configuration.
ROOT_FILES = ("LICENSE", "NOTICE", "README.md", "Makefile", ".gitignore")
SOURCE_PATTERNS = (
    "src/*.asm", "src/*.inc", "config/*.json", "tools/*.py", "tests/*.py",
    "docs/*.md", "docs/screenshots/*.png",
    "vendor/dasm/LICENSE", "vendor/dasm/README.md", "vendor/dasm/vcs.h",
)


def main():
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    sources = {ROOT / name for name in ROOT_FILES}
    for pattern in SOURCE_PATTERNS:
        sources.update(ROOT.glob(pattern))
    archive = destination / "zerowave-source.tar.gz"
    pending = archive.with_suffix(archive.suffix + ".tmp")
    try:
        with tarfile.open(pending, "w:gz") as bundle:
            for path in sorted(sources):
                if path.is_symlink() or not path.is_file():
                    raise ValueError(f"Expected a regular source file: {path}")
                relative = path.relative_to(ROOT)
                bundle.add(path, arcname=f"zerowave-source/{relative}", recursive=False)
        pending.replace(archive)
    finally:
        pending.unlink(missing_ok=True)
    for name in ("LICENSE", "NOTICE"):
        shutil.copyfile(ROOT / name, destination / name)
    print(f"Packaged {len(sources)} source files and GPL notices in dist/.")


if __name__ == "__main__":
    main()
