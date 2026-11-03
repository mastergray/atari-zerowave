; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Bank 0's timed top-HUD kernel. PF register rewrites split each scanline into
; independent left/right halves: score on the left, health on the right, then
; level or FIRE on a second row, with OVER beside the final level after death.
; Each font row is drawn twice for height.
; NOPs and repeated macros place writes at specific beam positions; shortening
; them would move or corrupt pixels even if the computed bytes stayed the same.

; HUD row 0 is blank. Draw rows 1..28 (diagnostic: 1..23) with independent halves.
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
    lda #7
    sta TIM64T            ; retain the HUD spacing while preparing the progress bar
    ; Score pixels are finished, so their right-hand buffer is now available
    ; for the footer masks. The timer keeps this variable work inside a fixed
    ; seven-line gap before the status row, preserving the arena's start time.
    jsr PrepareProgress
.waitProgress:
    lda INTIM
    bne .waitProgress
    sta WSYNC             ; line 18, last blank row before status line 19
    ldy #0
    ldx #0                ; right-hand rows 0..4 are blank during play/break
    lda GameMode
    beq StatusHudLoop
    cmp #MODE_GAME_OVER
    bne LevelHudLoop
    ldx #5                ; rows 5..9 spell OVER beside the retained final level
    bne LevelHudLoop
    MAC STATUS_SCANLINE
    lda #COLOR_TURRET
    sta COLUPF            ; 5
    lda (HudStatus1),y
    sta PF1               ; 13
    lda (HudStatus2),y
    sta PF2               ; 21
    lda #0
    REPEAT 7
    nop
    REPEND
    sta PF1               ; 40, clear right half
    REPEAT 4
    nop
    REPEND
    sta PF2               ; 51, after left PF2 finishes
    ENDM
StatusHudLoop:
    sta WSYNC             ; lines 19..28, FIRE on the title screen
    STATUS_SCANLINE
    sta WSYNC
    STATUS_SCANLINE
    iny
    cpy #5
    bne StatusHudLoop
    jmp HudStatusDone
    MAC LEVEL_SCANLINE
    lda #0
    sta PF0               ; 5, left margin
    lda #COLOR_TURRET
    sta COLUPF            ; 10
    lda LevelLabel,y
    sta PF1               ; 17, LV
    lda (HudStatus1),y
    sta Temp
    lda (HudStatus2),y
    ora Temp
    sta PF2               ; 36, level digits before left PF2 begins
    lda HudOverRight1,x
    sta PF1               ; 43, right half: blank during play, OVER after death
    lda HudOverRight2,x
    sta PF2               ; 50, after left PF2 finishes
    ENDM
LevelHudLoop:
    sta WSYNC             ; lines 19..28: LV nn, plus OVER on the right after death
    LEVEL_SCANLINE
    sta WSYNC
    LEVEL_SCANLINE
    inx
    iny
    cpy #5
    bne LevelHudLoop
HudStatusDone:
    ENDIF
    sta WSYNC             ; gameplay separator line 29; diagnostic separator 24
    lda #0
    IF DISPLAY_TEST
    sta PF0
    sta PF1
    sta PF2
    ENDIF
    jmp ArenaEntry
