PYTHON ?= python3
DASM ?= .tools/dasm-src/src/dasm
STELLA ?= stella
STELLA_AUDIO ?= -audio.enabled 1
ROM := build/atari-zerowave.bin
DISPLAY_ROM := build/atari-zerowave-display.bin
GENERATED := build/generated/assets.stamp
SOURCE := $(wildcard src/*.asm src/*.inc) vendor/dasm/vcs.h

.PHONY: all bootstrap check test run run-display debug stella-check clean
all: $(ROM) $(DISPLAY_ROM)

bootstrap:
	$(PYTHON) tools/bootstrap.py

$(GENERATED): tools/generate_assets.py config/tuning.json config/fixtures.json config/audio.json
	$(PYTHON) tools/generate_assets.py

$(ROM): $(SOURCE) $(GENERATED)
	@test -x "$(DASM)" || { echo "DASM missing: run make bootstrap or set DASM=/path/to/dasm"; exit 1; }
	$(DASM) src/main.asm -Isrc -Ivendor/dasm -Ibuild/generated -f3 -o$(ROM) -lbuild/atari-zerowave.lst -sbuild/atari-zerowave.sym
	$(PYTHON) tools/check_rom.py

$(DISPLAY_ROM): $(SOURCE) $(GENERATED)
	$(DASM) src/main.asm -DDISPLAY_TEST=1 -Isrc -Ivendor/dasm -Ibuild/generated -f3 -o$(DISPLAY_ROM) -lbuild/atari-zerowave-display.lst -sbuild/atari-zerowave-display.sym
	$(PYTHON) tools/check_rom.py --display

check: all
	$(PYTHON) tools/check_rom.py
	$(PYTHON) tools/check_rom.py --display
	$(PYTHON) -m unittest discover -s tests -v

test: check

run: all
	$(STELLA) $(STELLA_AUDIO) -type F8 -format NTSC -lc JOYSTICK -rc JOYSTICK -tv.phosphor byrom -pp NO $(ROM)

debug: all
	$(STELLA) $(STELLA_AUDIO) -debug -type F8 -format NTSC -lc JOYSTICK $(ROM)

run-display: $(DISPLAY_ROM)
	$(STELLA) $(STELLA_AUDIO) -type F8 -format NTSC -lc JOYSTICK -pp NO $(DISPLAY_ROM)

stella-check: all
	$(PYTHON) tools/verify_stella.py
	$(PYTHON) tools/verify_combat_stella.py

clean:
	$(PYTHON) -c 'import pathlib, shutil; p=pathlib.Path("build"); shutil.rmtree(p) if p.is_dir() else None'
