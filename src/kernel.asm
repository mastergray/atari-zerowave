ArenaFrameStart:
    ldx #7
SeparatorLoop:
    sta WSYNC
    lda #0
    sta PF0
    sta PF1
    sta PF2
    dex
    bne SeparatorLoop
    lda ArenaColor
    sta COLUPF
    lda #COLOR_BACKGROUND
    IF DISPLAY_TEST
    sta COLUBK
    ENDIF
    sta HMCLR             ; well after blanking HMOVE; players stay stationary
    sta ENABL
    ldy #ARENA_ROWS-1      ; reverse indexing saves two loop cycles
    lda BallKernel
    beq .playfield
    jmp ThinBeamLoop
.playfield:

    IF DISPLAY_TEST
; Four varying PF streams serve both rays and rings: neither reaches columns
; 0..3 or 32..39. Sprite writes precede their earliest possible pixels.
; X is zero after the separator loop. Reuse it for constant-zero PF writes.
; Completion cycles: PF0=3, PF1=11, GRP1=19, PF2=27, GRP0=34,
; PF0=42, PF1=50, PF2=53. COLUPF stays fixed for the whole arena: the beam
; changes color between frames, with no stripes or scanline color gradient.
    MAC ARENA_SCANLINE
    stx PF0
    lda (BeamLeft1),y
    sta PF1
    lda (EnemySprite),y
    sta GRP1
    lda (BeamLeft2),y
    sta PF2
    lda TurretRows,y
    sta GRP0
    lda (BeamRight0),y
    sta PF0
    lda (BeamRight1),y
    sta PF1
    stx PF2
    ENDM
ArenaLoop:
    sta WSYNC
    ARENA_SCANLINE
    sta WSYNC
    ARENA_SCANLINE
    dey                   ; 55
    bpl ArenaLoop         ; 58; next WSYNC completes at 61
ArenaDone:
    lda #0
    sta ENABL
    lda #2
    sta WSYNC             ; first overscan line
    sta VBLANK
    jmp LogicEntry

; One-clock ball beam. The playfield stays clear; P0/P1 still draw every line.
; HMOVE at cycle 3, then HMBL no earlier than cycle 34 (>24 cycles later).
; Two packed motion nibbles advance the ball on individual physical lines.
ThinBeamLoop:
    sta WSYNC
    sta HMOVE             ; 3
    lda #0
    cpy BeamMinY
    bcc ThinBeamEnableReady
    cpy BeamMaxY
    bcs ThinBeamEnableReady
    lda #2
ThinBeamEnableReady:
    sta ENABL             ; <=20, before the leftmost beam pixel
    lda (EnemySprite),y
    sta GRP1              ; <=28, before the leftmost enemy
    lda TurretRows,y
    sta GRP0              ; <=35
    lda (BeamMotion),y
    sta HMBL              ; high nibble moves the second physical line
    sta WSYNC
    sta HMOVE             ; 3
    lda (EnemySprite),y
    sta GRP1              ; 11
    lda TurretRows,y
    sta GRP0              ; 18
    lda (BeamMotion),y
    asl
    asl
    asl
    asl
    sta HMBL              ; 34; low nibble moves the next row's first line
    dey
    bpl ThinBeamLoop
    jmp ArenaDone
    ELSE
    include "reuse_kernel.asm"
    ENDIF
