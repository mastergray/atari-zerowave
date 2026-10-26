; HUD row 0 is blank. Rows 1..23 are drawn here with independent PF halves.
HudLoop:
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
    ldy #ARENA_ROWS-1      ; reverse indexing saves two loop cycles

; Four varying PF streams serve both rays and rings: neither reaches columns
; 0..3 or 32..39. Sprite writes precede their earliest possible pixels.
; X is zero after the separator loop. Reuse it for constant-zero PF writes.
; Completion cycles: PF0=3, PF1=11, GRP1=19, PF2=27, GRP0=34,
; PF0=42, PF1=50, PF2=53. Color changes at cycle 66, past the ray's right edge,
; preparing the next physical line. One bright core line, one colored glow line.
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
    lda (GlowColor),y      ; 58
    bit Temp              ; 61; timing only, value/flags unused
    nop                   ; 63
    sta COLUPF            ; 66: second physical line uses the glow color
    sta WSYNC
    ARENA_SCANLINE
    lda ArenaColor        ; 56
    nop                   ; 58
    nop                   ; 60
    bit Temp              ; 63
    sta COLUPF            ; 66: next row starts with its bright core
    dey                   ; 68
    bpl ArenaLoop         ; 71; next WSYNC completes at 74
    lda #2
    sta WSYNC             ; first overscan line
    sta VBLANK
    jmp LogicEntry
