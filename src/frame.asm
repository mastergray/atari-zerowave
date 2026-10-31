; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Bank 1 owns television synchronization. WSYNC stalls the CPU until the next
; scanline; VSYNC marks the frame start, and VBLANK hides work between pictures.
; NTSC budget: 3 sync + 37 blank + 192 visible + 30 overscan = 262 scanlines.
; The visible gameplay area is 29 HUD + 1 separator + 160 arena + 2 footer.
; At 76 CPU cycles per line, changing these boundaries changes frame timing.

; Entry after overscan line-29 boundary. Sync begins at the next boundary.
FrameStart:
    SUBROUTINE
    lda #2
    sta WSYNC
    sta VSYNC
    sta WSYNC
    sta WSYNC
    sta WSYNC
    lda #0
    sta VSYNC
    lda #43
    ; Run preparation in bank 0 while the RIOT timer counts down, then return
    ; through RenderEntry. This wait absorbs preparation's variable work time;
    ; the timer value depends on the entry path and its partial first interval.
    sta TIM64T
    jmp PrepareEntry
PrepareDone:
.wait:
    lda INTIM
    bne .wait
    sta WSYNC             ; blank line 36
    IF DISPLAY_TEST
    lda HudColor
    ELSE
    lda #COLOR_TURRET
    ENDIF
    sta COLUPF
    IF DISPLAY_TEST
    lda #COLOR_BACKGROUND
    sta COLUBK
    ENDIF
    lda #0
    sta PF0
    sta PF1
    sta PF2
    sta GRP0
    sta GRP1
    ldy #1
    sta WSYNC             ; first visible line (HUD padding row 0)
    sta VBLANK
    ; HUD lives in bank 0; it jumps back through ArenaEntry for bank 1's arena.
    jmp HudEntry

