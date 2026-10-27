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
    jsr PrepareRender
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

; Prepare playfield, ball-motion and enemy pointers; A/X/Y clobbered.
; Display alternation never changes BeamEnabled or the one-update BombEvent.
; Age selection is independent of slot parity, so a freed slot cannot starve another.
PrepareRender:
    SUBROUTINE
    IF DISPLAY_TEST = 0
    jsr PrepareHud
    ENDIF
    lda FrameCounter
    and #1
    sta FramePhase
    lda BeamDrawColor     ; uniform held color or fixed-hue release fade
    sta ArenaColor
    lda FramePhase
    beq .beamFrame
    ldx BombTimer
    bne .effectFrame
.beamFrame:
    ldy BeamDrawDirection
    cpy #8
    bcc .patternReady
    ldy #8                ; neutral
    bne .patternReady
.effectFrame:
    lda BombPatternByTimer,x
    tay
    lda #COLOR_BOMB
    sta ArenaColor
.patternReady:
    sty DisplayPattern
    lda BallKernelByPattern,y
    sta BallKernel
    lda BallMinY,y
    sta BeamMinY
    lda BallMaxY,y
    sta BeamMaxY
    lda BallMotionLo,y
    sta BeamMotion
    lda BallMotionHi,y
    sta BeamMotion+1
    lda PatternLeft1Lo,y
    sta BeamLeft1
    lda PatternLeft1Hi,y
    sta BeamLeft1+1
    lda PatternLeft2Lo,y
    sta BeamLeft2
    lda PatternLeft2Hi,y
    sta BeamLeft2+1
    lda PatternRight0Lo,y
    sta BeamRight0
    lda PatternRight0Hi,y
    sta BeamRight0+1
    lda PatternRight1Lo,y
    sta BeamRight1
    lda PatternRight1Hi,y
    sta BeamRight1+1
    lda #COLOR_READY
    ldx BombCooldown
    beq .ready
    lda #COLOR_WAITING
.ready:
    sta HudColor
    lda #$ff
    sta SelectedSlot
    lda #0
    sta BestAge
    ldx #0
.choose:
    lda EnemyFlags,x
    bmi .drawable
    lda EnemyVisual,x
    beq .next
.drawable:
    lda EnemyAge,x
    cmp #$ff
    beq .ageReady
    inc EnemyAge,x
.ageReady:
    lda EnemyAge,x
    cmp BestAge
    bcc .next
    beq .next
    sta BestAge
    stx SelectedSlot
.next:
    inx
    cpx #4
    bne .choose
    ldx SelectedSlot
    cpx #$ff
    beq .noEnemy
    lda #0
    sta EnemyAge,x
    lda EnemyY,x
    clc
    adc #4                ; reversed row index: top maps to sprite byte 83
    sta EnemySprite       ; all sprite streams begin on a page boundary
    lda EnemyVisual,x
    beq .liveEnemy
    tay
    lda EnemySprite
    clc
    adc #(<BurstFlash+2)  ; 8-row burst centered over the old 4-row enemy
    sta EnemySprite
    lda BurstSpriteByTimer,y
    sta EnemySprite+1
    lda BurstColorByTimer,y
    sta COLUP1
    jmp .triangle
.liveEnemy:
    lda #>SpriteTriangle
    sta EnemySprite+1
    lda #COLOR_TRIANGLE
    sta COLUP1
    lda EnemyFlags,x
    and #$40
    beq .triangle
    lda #>SpriteSquare
    sta EnemySprite+1
    lda #COLOR_SQUARE
    sta COLUP1
    lda EnemyRadiusHi,x
    cmp #BOMB_RADIUS
    bcc .filled
    bne .triangle
    lda EnemyRadiusLo,x
    bne .triangle
.filled:
    lda #>SpriteSquareReady
    sta EnemySprite+1
.triangle:
    lda EnemyX,x
    jmp .positionEnemy
.noEnemy:
    lda #<SpriteTriangle  ; first 80 rows are zero
    sta EnemySprite
    lda #>SpriteTriangle
    sta EnemySprite+1
    lda #76
.positionEnemy:
    ldx #1
    jsr PositionPlayer
    lda #76
    ldx #0
    jsr PositionPlayer
    ldy DisplayPattern
    lda BallInitialX,y
    ldx #4               ; same positioning registers, indexed to HMBL/RESBL
    jsr PositionPlayer
    sta WSYNC
    sta HMOVE
    lda #COLOR_TURRET
    sta COLUP0
    rts

; Standard coarse/fine positioning during blanking.
; A = left edge (0..159), X = object (player 0/1 or ball 4); A clobbered, <= 2 lines.
    align 16
PositionPlayer:
    SUBROUTINE
    sec
    sta WSYNC
.divide:
    sbc #15
    bcs .divide
    eor #7
    asl
    asl
    asl
    asl
    sta.w HMP0,x          ; intentional 5-cycle absolute indexed store
    sta RESP0,x
    rts
