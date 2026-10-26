PYTHON ?= python3
DASM ?= .tools/dasm-src/src/dasm
STELLA ?= stella
ROM := build/atari-zerowave.bin
GENERATED := build/generated/assets.stamp
SOURCE := $(wildcard src/*.asm src/*.inc) vendor/dasm/vcs.h

.PHONY: all bootstrap check test run debug stella-check clean
all: $(ROM)

bootstrap:
	$(PYTHON) tools/bootstrap.py

$(GENERATED): tools/generate_assets.py config/tuning.json config/fixtures.json
	$(PYTHON) tools/generate_assets.py

$(ROM): $(SOURCE) $(GENERATED)
	@test -x "$(DASM)" || { echo "DASM missing: run make bootstrap or set DASM=/path/to/dasm"; exit 1; }
	$(DASM) src/main.asm -Isrc -Ivendor/dasm -Ibuild/generated -f3 -o$(ROM) -lbuild/atari-zerowave.lst -sbuild/atari-zerowave.sym
	$(PYTHON) tools/check_rom.py

check: all
	$(PYTHON) tools/check_rom.py
	$(PYTHON) -m unittest discover -s tests -v

test: check

run: all
	$(STELLA) -type F8 -format NTSC -lc JOYSTICK -rc JOYSTICK -tv.phosphor byrom -pp NO $(ROM)

debug: all
	$(STELLA) -debug -type F8 -format NTSC -lc JOYSTICK $(ROM)

stella-check: all
	$(PYTHON) tools/verify_stella.py

clean:
	$(PYTHON) -c 'import pathlib, shutil; p=pathlib.Path("build"); shutil.rmtree(p) if p.is_dir() else None'
