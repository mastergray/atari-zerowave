; Ten score row bytes, health masks and status pointers. Uses display-only
; scratch after input history is committed. A/X/Y clobbered, <700 cycles.
PrepareHud:
    SUBROUTINE
    ldx Health
    lda HealthMask1,x
    sta HudHealth1
    lda HealthMask2,x
    sta HudHealth2
    ldy GameMode
    lda HudStatus1Lo,y
    sta HudStatus1
    lda HudStatus1Hi,y
    sta HudStatus1+1
    lda HudStatus2Lo,y
    sta HudStatus2
    lda HudStatus2Hi,y
    sta HudStatus2+1
    lda ScoreHi
    lsr
    lsr
    lsr
    lsr
    tax
    lda DigitOffsets,x
    tax
    ldy #0
.thousands:
    lda DigitLeft,x
    sta HudScoreLeft,y
    inx
    iny
    cpy #5
    bne .thousands
    lda ScoreHi
    and #15
    tax
    lda DigitOffsets,x
    tax
    ldy #0
.hundreds:
    lda DigitLeft,x
    lsr
    lsr
    lsr
    lsr
    ora HudScoreLeft,y
    sta HudScoreLeft,y
    inx
    iny
    cpy #5
    bne .hundreds
    lda ScoreLo
    lsr
    lsr
    lsr
    lsr
    tax
    lda DigitOffsets,x
    tax
    ldy #0
.tens:
    lda DigitRight,x
    sta HudScoreRight,y
    inx
    iny
    cpy #5
    bne .tens
    lda ScoreLo
    and #15
    tax
    lda DigitOffsets,x
    tax
    ldy #0
.ones:
    lda DigitRight,x
    asl
    asl
    asl
    asl
    ora HudScoreRight,y
    sta HudScoreRight,y
    inx
    iny
    cpy #5
    bne .ones
    rts
