; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Build the top HUD's score/health rows and status pointers during VBLANK.
; Score and level are packed BCD, so each nibble already identifies a decimal
; glyph. DigitOffsets maps it to a five-row font; no division by ten is needed.

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
    cpy #MODE_PLAY
    beq .level
    cpy #MODE_LEVEL_BREAK
    beq .level
    ; FIRE/OVER glyphs share a page (asserted by the asset generator), so their
    ; two pointers need only one immediate high byte and separate low tables.
    lda #>HudText0Left1
    sta HudStatus1+1
    sta HudStatus2+1
    lda HudStatus1Lo,y
    sta HudStatus1
    lda HudStatus2Lo,y
    sta HudStatus2
    jmp .score
.level:
    lda LevelNumber
    lsr
    lsr
    lsr
    lsr
    tax
    lda DigitOffsets,x
    clc
    adc #<LevelDigitTens
    sta HudStatus1
    lda #>LevelDigitTens
    sta HudStatus1+1
    lda LevelNumber
    and #15
    tax
    lda DigitOffsets,x
    clc
    adc #<LevelDigitOnes
    sta HudStatus2
    lda #>LevelDigitOnes
    sta HudStatus2+1
.score:
    ; Compose two digits into each five-byte buffer. PF1 and PF2 draw their bits
    ; in opposite orders, so DigitLeft/DigitRight and the shifts differ. These
    ; are final register bytes, ready for the timing-critical SCORE_SCANLINE.
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

; Top score rows are finished. Reuse the five right-score bytes for the bar.
; Three binary division steps compute floor(8 * completed / quota).
; There are nine fill masks (0..8). Handle full completion separately; otherwise
; each shift doubles the remainder and each conditional subtraction yields the
; next quotient bit via carry/ROL. This avoids a general division routine.
; Odd mode numbers are PLAY/LEVEL_BREAK; other modes select the empty mask.
PrepareProgress:
    SUBROUTINE
    ldx #0
    stx Temp
    lda GameMode
    and #1
    beq .progressMasks
    jsr CalculateQuota
    sta ProgressQuota
    sec
    sbc KillsRemaining
    bcc .progressMasks    ; debugger counts beyond this wave show an empty bar
    ldx #8
    cmp ProgressQuota
    beq .progressMasks
    ldx #3
.progressBit:
    asl
    bcs .subtractQuota
    cmp ProgressQuota
    bcc .appendBit
.subtractQuota:
    sbc ProgressQuota
    sec
.appendBit:
    rol Temp
    dex
    bne .progressBit
    ldx Temp
.progressMasks:
    lda ProgressLeft1,x
    sta HudProgress
    lda ProgressLeft2,x
    sta HudProgress+1
    lda ProgressRight0,x
    sta HudProgress+2
    lda ProgressRight1,x
    sta HudProgress+3
    lda ProgressRight2,x
    sta HudProgress+4
    rts
