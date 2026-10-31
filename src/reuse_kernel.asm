; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Player 1 is reused for a second, vertically separated enemy. Between the
; sprites, bounded HMOVE steps reposition it without interrupting beam/ring data.
; Only the first physical line writes player graphics; TIA retains both rows.
    MAC REUSE_CONTROL
    SUBROUTINE
    cpy ReuseRow
    beq .reuse
    bcs .rowDone
    ldx NextDelta
    lda ReuseMotion,x
    sta HMP1
    lda ReuseRemainder,x
    sta NextDelta
    ldx #0
.rowDone:
    dey
    jmp {1}
.reuse:
    lda NextSprite
    sta EnemySprite
    lda NextSprite+1
    sta EnemySprite+1
    lda NextColor
    sta COLUP1
    jmp .rowDone
    ENDM

    MAC REUSE_PF_FIRST
    sta HMOVE             ; 3: player movement in blanking
    stx PF0               ; 6
    lda (BeamLeft1),y
    sta PF1               ; 14
    lda (EnemySprite),y
    sta GRP1              ; 22
    lda (BeamLeft2),y
    sta PF2               ; 30
    lda TurretRows,y
    sta GRP0              ; 37
    lda (BeamRight0),y
    sta PF0               ; 45
    lda (BeamRight1),y
    sta PF1               ; 53
    stx PF2               ; 56
    ENDM

    MAC REUSE_PF_SECOND
    stx PF0               ; 3
    lda (BeamLeft1),y
    sta PF1               ; 11
    lda (BeamLeft2),y
    sta PF2               ; 19
    lda (BeamRight0),y
    nop
    sta PF0               ; 29: left PF0 has finished
    lda (BeamRight1),y
    cpy ReuseRow           ; useful work while left PF1 finishes
    sta PF1               ; 40; comparison flags feed the row control below
    ENDM

ArenaLoop:
    sta WSYNC
    REUSE_PF_FIRST
    tya
    beq ArenaLastPair
    ldx NextDelta
    lda ReuseMotion,x
    sta Temp              ; prefetch motion while preserving the visible row
    ldx #0
    sta WSYNC
    REUSE_PF_SECOND
    beq PFReuse
    bcs PFStatic
    lda Temp
    sta HMP1              ; 50; applied only on the next first scanline
    stx PF2               ; 53, after left PF2 has finished
    ldx NextDelta
    lda ReuseRemainder,x
    sta NextDelta
    ldx #0
PFRowDone:
    dey
    jmp ArenaLoop         ; WSYNC completes by cycle 75 on every path
PFStatic:
    nop
    stx PF2               ; 50
    jmp PFRowDone
PFReuse:
    lda NextColor
    sta COLUP1
    stx PF2               ; 52, sprite is blank throughout this row
    lda NextSprite
    sta EnemySprite
    lda NextSprite+1
    sta EnemySprite+1
    jmp PFRowDone
ArenaLastPair:
    sta WSYNC
    REUSE_PF_SECOND
    nop
    nop
    nop
    nop
    stx PF2
    jmp ArenaDone

ThinBeamLoop:
    sta WSYNC
    sta HMOVE
    lda #0
    cpy BeamMinY
    bcc ThinBeamEnableReady
    cpy BeamMaxY
    bcs ThinBeamEnableReady
    lda #2
ThinBeamEnableReady:
    sta ENABL
    lda (EnemySprite),y
    sta GRP1
    lda TurretRows,y
    sta GRP0
    lda (BeamMotion),y
    sta HMBL
    stx HMP1
    cpy #0
    beq ThinBeamLastPair
    sta WSYNC
    sta HMOVE
    lda (BeamMotion),y
    asl
    asl
    asl
    asl
    nop
    nop
    nop
    nop                   ; motion writes must follow HMOVE by at least 24 cycles
    sta HMBL
    REUSE_CONTROL ThinBeamLoop
ThinBeamLastPair:
    sta WSYNC
    sta HMOVE
    lda (BeamMotion),y
    asl
    asl
    asl
    asl
    nop
    nop
    nop
    nop                   ; motion writes must follow HMOVE by at least 24 cycles
    sta HMBL
ArenaDone:
    lda GameMode
    and #1                ; PLAY or LEVEL_BREAK; hide both bar rows otherwise
    bne ProgressFooter
    lda #0
    sta WSYNC             ; visible line 190: empty footer on title/game over
    sta PF0
    sta PF1
    sta PF2
    sta ENABL
    sta GRP0
    sta GRP1
    sta WSYNC             ; visible line 191
    jmp FooterDone
ProgressFooter:
    lda #0
    sta WSYNC             ; visible line 190: full wave rail
    sta PF0               ; 3
    sta ENABL             ; 6
    sta GRP0              ; 9
    sta GRP1              ; 12
    lda #$04
    sta COLUPF            ; 17, dim gray rail
    lda #$ff
    sta PF1               ; 22
    sta PF2               ; 25
    lda #$f0
    sta PF0               ; 30, left PF0 has finished
    REPEAT 12
    nop
    REPEND
    lda #$0f
    sta PF2               ; 59, right end of the rail
    sta WSYNC             ; visible line 191: green completed portion
    lda #0
    sta PF0               ; 5
    lda #COLOR_READY
    sta COLUPF            ; 10
    lda HudProgress
    sta PF1               ; 16
    lda HudProgress+1
    sta PF2               ; 22
    REPEAT 6
    nop
    REPEND
    lda HudProgress+2
    sta PF0               ; 40
    lda HudProgress+3
    sta PF1               ; 46
    lda HudProgress+4
    sta PF2               ; 52
FooterDone:
    lda #2
    sta WSYNC
    sta VBLANK
    jmp LogicEntry
