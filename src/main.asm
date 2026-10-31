; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Cartridge entry point and memory layout. DASM emits two 4 KiB banks into an
; 8 KiB F8 ROM; both banks appear to the CPU at $F000..$FFFF. ORG selects the
; position in the ROM file, while RORG selects the address used by the CPU.
;
; Reading guide:
;   game.asm -> play.asm/input.asm: frame update and controls
;   enemies.asm/combat.asm/levels.asm: movement, attacks and wave progression
;   render.asm/hud.asm: turn game state into pointers and display bytes
;   frame.asm/hud_kernel.asm/kernel.asm: timed writes that draw the picture
;   ram.inc: shared state, including scratch bytes reused between frame phases
; Generated includes come from tools/generate_assets.py and config/*.json.
; DISPLAY_TEST=1 builds static display fixtures instead of the playable game.
;
; One gameplay frame: overscan updates -> VSYNC -> VBLANK preparation -> HUD
; -> arena/footer -> overscan. See docs/KERNEL_TIMING.md for scanline budgets.

    processor 6502
    IFNCONST DISPLAY_TEST
DISPLAY_TEST = 0
    ENDIF
    include "vcs.h"
    include "ram.inc"
    include "tuning.inc"
    include "constants.inc"

; Every bank has matching jump trampolines and vectors. No cross-bank returns.
; BIT reads an F8 hotspot ($FFF8 = bank 0, $FFF9 = bank 1). That changes the
; bank immediately, so the following JMP must exist at the same address in
; both banks. Use these entries with JMP; ordinary JSR/RTS stays within a bank.
    MAC COMMON_BANK_TAIL
    .byte $2c,$f8,$ff       ; ResetEntry: BIT $FFF8
    jmp Reset
    .byte $2c,$f9,$ff       ; DisplayEntry: BIT $FFF9
    jmp FrameStart
    .byte $2c,$f8,$ff       ; LogicEntry: BIT $FFF8
    jmp GameFrame
    .byte $2c,$f8,$ff       ; PrepareEntry: BIT $FFF8
    jmp PrepareFrame
    .byte $2c,$f9,$ff       ; RenderEntry: BIT $FFF9
    jmp PrepareDone
    .byte $2c,$f8,$ff       ; HudEntry: BIT $FFF8
    jmp HudLoop
    .byte $2c,$f9,$ff       ; ArenaEntry: BIT $FFF9
    jmp ArenaFrameStart
    IF DISPLAY_TEST = 0
    include "shared_hud.inc" ; page-safe font/progress data in matching tails
    ENDIF
    IF * > $fff8
        ERR
    ENDIF
    ENDM
ResetEntry   = $ff80
DisplayEntry = $ff86
LogicEntry   = $ff8c
PrepareEntry = $ff92
RenderEntry  = $ff98
HudEntry     = $ff9e
ArenaEntry   = $ffa4
LevelDigitOnes = $ffaa
ProgressRight1 = $ffdc
ProgressRight2 = $ffe5
DigitOffsets = $ffee

    SEG ROM
; Bank 0 holds the game rules, display preparation and top HUD kernel.
    ORG $0000
    RORG $f000
    include "game.asm"
    include "audio.asm"
    include "input.asm"
    include "play.asm"
    include "levels.asm"
    include "enemies.asm"
    include "combat.asm"
    include "render.asm"
    include "hud_kernel.asm"
    IF DISPLAY_TEST = 0
    include "hud.asm"
    ENDIF
    include "fixtures.inc"
    include "movement.inc"
    include "enemy_types.inc"
    include "levels.inc"
    IF DISPLAY_TEST = 0
    include "audio.inc"
    ENDIF
    include "render_tables.inc"
    include "hud_graphics.inc"
Bank0End = *
; Keep code/data below the shared tail; this assertion catches bank overflow.
    IF Bank0End > $ff80
        ERR
    ENDIF
    ORG $0f80
    RORG $ff80
    COMMON_BANK_TAIL
    ORG $0ff8
    RORG $fff8
    .byte 0,0
    .word ResetEntry,ResetEntry,ResetEntry

; Bank 1 holds frame synchronization, arena kernels and large graphics tables.
    ORG $1000
    RORG $f000
    include "frame.asm"
    include "kernel.asm"
    include "graphics.inc"
    IF DISPLAY_TEST = 0
    include "reuse_motion.inc"
    ENDIF
Bank1End = *
    IF Bank1End > $ff80
        ERR
    ENDIF
    ORG $1f80
    RORG $ff80
    COMMON_BANK_TAIL
    ORG $1ff8
    RORG $fff8
    .byte 0,0
    .word ResetEntry,ResetEntry,ResetEntry
