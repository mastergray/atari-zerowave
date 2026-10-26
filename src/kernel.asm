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
    lda #COLOR_BEAM
    sta COLUPF
    lda ArenaBackground
    sta COLUBK
    ldy #0

; Four varying PF streams suffice because the ray never reaches columns 0..3
; or 32..39. Sprite writes precede their earliest possible horizontal pixels.
; Completion cycles from each WSYNC: PF0=5, PF1=13, GRP1=21, PF2=29,
; GRP0=36, PF0=44, PF1=52, PF2=57. Second line repeats the same logical row.
    MAC ARENA_SCANLINE
    lda #0
    sta PF0
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
    lda #0
    sta PF2
    ENDM
ArenaLoop:
    sta WSYNC
    ARENA_SCANLINE
    sta WSYNC
    ARENA_SCANLINE
    iny
    cpy #ARENA_ROWS
    bne ArenaLoop
    lda #2
    sta WSYNC             ; first overscan line
    sta VBLANK
    jmp LogicEntry
