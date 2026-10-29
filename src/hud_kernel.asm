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
    lda GameMode
    cmp #MODE_PLAY
    beq LevelHudLoop
    cmp #MODE_LEVEL_BREAK
    beq LevelHudLoop
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
    jmp HudStatusDone
    MAC LEVEL_SCANLINE
    lda #COLOR_TURRET
    sta COLUPF            ; 5
    lda LevelLabel,y
    sta PF1               ; 12, LV
    lda (HudStatus1),y
    sta Temp              ; tens digit; renderer scratch is finished
    lda (HudStatus2),y
    ora Temp
    sta PF2               ; 31, before left PF2 begins displaying
    lda BombHud1,y
    nop
    sta PF1               ; 40
    lda HudColor
    nop
    sta COLUPF            ; 48
    lda BombHud2,y
    sta PF2               ; 55
    ENDM
LevelHudLoop:
    sta WSYNC             ; lines 14..23: LV 01..99 and BOMB
    LEVEL_SCANLINE
    sta WSYNC
    LEVEL_SCANLINE
    iny
    cpy #5
    bne LevelHudLoop
HudStatusDone:
    ENDIF
    sta WSYNC             ; separator line 24, before switching back to bank 1
    lda #0
    sta PF0
    sta PF1
    sta PF2
    jmp ArenaEntry
