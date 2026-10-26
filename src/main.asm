    processor 6502
    include "vcs.h"
    include "ram.inc"
    include "tuning.inc"

; Every bank has matching jump trampolines and vectors. No cross-bank returns.
    MAC COMMON_BANK_TAIL
    .byte $2c,$f8,$ff       ; ResetEntry: BIT $FFF8
    jmp Reset
    .byte $2c,$f9,$ff       ; DisplayEntry: BIT $FFF9
    jmp FrameStart
    .byte $2c,$f8,$ff       ; LogicEntry: BIT $FFF8
    jmp GameFrame
    ENDM
ResetEntry   = $ff80
DisplayEntry = $ff86
LogicEntry   = $ff8c

    SEG ROM
    ORG $0000
    RORG $f000
    include "game.asm"
    include "input.asm"
    include "fixtures.inc"
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
    include "render.asm"
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
