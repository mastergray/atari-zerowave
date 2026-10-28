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
    sta TIM64T
    jmp PrepareEntry
PrepareDone:
.wait:
    lda INTIM
    bne .wait
    sta WSYNC             ; blank line 36
    lda HudColor
    sta COLUPF
    lda #COLOR_BACKGROUND
    sta COLUBK
    lda #0
    sta PF0
    sta PF1
    sta PF2
    sta GRP0
    sta GRP1
    ldy #1
    sta WSYNC             ; first visible line (HUD padding row 0)
    sta VBLANK
    jmp HudLoop

