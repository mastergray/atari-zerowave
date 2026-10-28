    processor 6502
    IFNCONST DISPLAY_TEST
DISPLAY_TEST = 0
    ENDIF
    include "vcs.h"
    include "ram.inc"
    include "tuning.inc"
    include "constants.inc"

; Every bank has matching jump trampolines and vectors. No cross-bank returns.
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
    ENDM
ResetEntry   = $ff80
DisplayEntry = $ff86
LogicEntry   = $ff8c
PrepareEntry = $ff92
RenderEntry  = $ff98

    SEG ROM
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
Bank0End = *
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

    ORG $1000
    RORG $f000
    include "frame.asm"
    include "kernel.asm"
    include "graphics.inc"
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
