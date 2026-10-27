; HUD row 0 is blank. Rows 1..23 are drawn here with independent PF halves.
HudLoop:
    IF DISPLAY_TEST
    sta WSYNC
    lda HudPlane0,y
    sta PF0               ; cycle 7
    lda HudPlane1,y
    sta PF1               ; cycle 14
    lda HudPlane2,y
    sta PF2               ; cycle 21
    nop
    nop
    nop
    nop
    nop                   ; cycle 31
    lda HudPlane3,y
    sta PF0               ; cycle 38
    lda HudPlane4,y
    sta PF1               ; cycle 45
    lda HudPlane5,y
    sta PF2               ; cycle 52
    iny
    cpy #24
    bne HudLoop
    ELSE
    sta WSYNC             ; blank HUD line 1
    ldy #0
    MAC SCORE_SCANLINE
    lda #COLOR_TURRET
    sta COLUPF            ; 5
    lda HudScoreLeft,y
    sta PF1               ; 12
    lda HudScoreRight,y
    sta PF2               ; 19
    REPEAT 9
    nop
    REPEND
    lda HudHealth1
    sta PF1               ; 43
    lda HudHealth2
    nop
    nop
    sta PF2               ; 53
    ENDM
ScoreHudLoop:
    sta WSYNC             ; lines 2..11, five doubled score/health rows
    SCORE_SCANLINE
    sta WSYNC
    SCORE_SCANLINE
    iny
    cpy #5
    bne ScoreHudLoop
    lda #0
    sta WSYNC             ; line 12
    sta PF1
    sta PF2
    sta WSYNC             ; line 13
    ldy #0
    MAC STATUS_SCANLINE
    lda #COLOR_TURRET
    sta COLUPF            ; 5
    lda (HudStatus1),y
    sta PF1               ; 13
    lda (HudStatus2),y
    sta PF2               ; 21
    lda BombHud1,y
    REPEAT 6
    nop
    REPEND
    sta PF1               ; 40
    lda HudColor
    nop
    sta COLUPF            ; 48, right half's bomb-ready color
    lda BombHud2,y
    sta PF2               ; 55
    ENDM
StatusHudLoop:
    sta WSYNC             ; lines 14..23, FIRE / PLAY / OVER and BOMB
    STATUS_SCANLINE
    sta WSYNC
    STATUS_SCANLINE
    iny
    cpy #5
    bne StatusHudLoop
    ENDIF
    ldx #8
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
    sta COLUBK
    sta HMCLR             ; well after blanking HMOVE; players stay stationary
    sta ENABL
    ldy #ARENA_ROWS-1      ; reverse indexing saves two loop cycles
    lda BallKernel
    bne ThinBeamLoop

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
