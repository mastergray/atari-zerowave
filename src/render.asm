; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Rendering preparation translates game state into a scanline schedule. The
; visible kernels cannot afford gameplay decisions: give them row pointers,
; colors, initial object positions and the row where P1 changes to enemy two.
; Arena row pointers address bank 1 data, even though setup executes in bank 0.
;
; Hardware roles: P0 = turret; P1 = up to two enemies per frame; ball = thin
; vertical/diagonal beam; playfield = horizontal beam or bomb outline. Alternate
; frame pairs cover all four slots, and odd bomb frames substitute the ring.

; VBLANK setup runs in bank 0, with explicit bank jumps on entry/exit.
; Update audio first: it consumes overscan scratch and selects the envelope
; whose timer also drives bonus flashes. Then finish coordinates, HUD and TIA
; positioning before RenderEntry waits for the fixed visible-picture boundary.
PrepareFrame:
    IF DISPLAY_TEST = 0
    jsr UpdateAudio       ; same update's events, before bonus-flash color selection
    ldx #0
.coordinate:
    ; Live enemies use their new radius; scored kills get one final position.
    ; Other inactive bursts retain their previous coordinates without moving.
    lda EnemyFlags,x
    bmi .liveCoordinate
    and #$40              ; newly scored burst: finish position, then clear marker
    beq .nextCoordinate
    jsr PositionEnemy
    lda #0
    sta EnemyFlags,x
    jmp .nextCoordinate
.liveCoordinate:
    jsr PositionEnemy     ; all live/newly scored coordinates update after combat
.nextCoordinate:
    inx
    cpx #MAX_ENEMIES
    bne .coordinate
    ENDIF
    jsr PrepareRender
    jmp RenderEntry

; Prepare playfield, ball-motion and enemy pointers; A/X/Y clobbered.
; Display alternation never changes BeamEnabled or the one-update BombEvent.
; Gameplay uses two stable phases with vertical reuse; diagnostics use draw ages.
PrepareRender:
    SUBROUTINE
    IF DISPLAY_TEST = 0
    ; Background priority: player damage, then healing/all-clear flash, then
    ; the persistent level palette. Sound runs first, so this uses its updated
    ; timer; bit 3 alternates eight-update flash and normal-background periods.
    ldy PlayerHitTimer
    bne .damageBackground
    ldx #COLOR_HEALTH_BONUS
    lda EventSoundId
    cmp #SFX_HEAL
    beq .bonusFlash
    cmp #SFX_CLEAR
    bne .levelBackground
    ldx #COLOR_CLEAR_BONUS
.bonusFlash:
    lda EventSoundTimer
    and #8                ; two eight-update flashes in either 32-update bonus cue
    beq .levelBackground
    txa
    bne .backgroundReady
.levelBackground:
    lda LevelBackground
    jmp .backgroundReady
.damageBackground:
    lda PlayerHitColorByTimer,y
.backgroundReady:
    sta COLUBK            ; one background color for the whole visible picture
    ENDIF
    lda FrameCounter
    and #1
    sta FramePhase
    lda BeamDrawColor     ; uniform fixed-hue shot fade (legacy held color in diagnostics)
    sta ArenaColor
    ; Effects share display resources, not combat state. Beam and ring take
    ; turns when a bomb is active; attack events were already resolved in logic.
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
    ; Patterns 0..7 = lanes, 8 = blank, 9..12 = expanding ring stages.
    ; Generated parallel tables supply both the thin-ball bounds/motion and
    ; four playfield streams. All indexed row reads must remain on one page.
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
    IF DISPLAY_TEST
    lda #COLOR_READY
    ldx BombCooldown
    beq .ready
    lda #COLOR_WAITING
.ready:
    sta HudColor
    ENDIF
    IF DISPLAY_TEST
    ; Diagnostic fixtures select the drawable slot with the oldest draw age.
    ; Gameplay uses stable pairs instead (reuse_render.asm), without these ages.
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
    ldy EnemyVisual,x
    lda EnemyFlags,x
    bmi .liveEnemy
    lda BurstColorByTimer,y
    sta COLUP1
    lda BurstSpriteByTimer,y
    tay
    jmp .graphic
.liveEnemy:
    and #TYPE_MASK
    lsr
    lsr
    lsr
    lsr
    tay
    lda TypeColor,y
    sta COLUP1
    lda TypeSprite,y
    tay
    cpy #2                ; only square graphics 2..5 have an outline/fill pair
    bcc .feedback
    cpy #6                ; diamond and shared hexagon/flash shape stay filled
    bcs .feedback
    lda EnemyHealth,x
    cmp #1
    bne .range
    ldy #2                ; one-health square, including damaged armor
.range:
    lda EnemyRadiusHi,x
    cmp #BOMB_RADIUS
    bcc .filled
    bne .feedback
    lda EnemyRadiusLo,x
    bne .feedback
.filled:
    iny                   ; ready shape follows outlined shape in atlas
.feedback:
    lda EnemyVisual,x
    beq .graphic
    bmi .hit
    sty Temp
    tay
    lda ImmuneColorByTimer,y
    ldy Temp
    jmp .color
.hit:
    lda #COLOR_HIT
.color:
    sta COLUP1
.graphic:
    lda GraphicHi,y
    sta EnemySprite+1
    lda EnemyY,x
    clc
    adc #6                ; eight-row window centered at old EnemyY+2
    adc GraphicLo,y       ; labels are at offsets 0 or 88, no carry
    sta EnemySprite
    lda EnemyX,x
    ldy EnemyFlags,x
    bpl .positionEnemy
    ldy EnemyVisual,x
    beq .positionEnemy
    bmi .positionEnemy
    clc
    adc ImmuneOffsetByTimer,y ; cosmetic shake; collision position never moves
    jmp .positionEnemy
.noEnemy:
    lda #<SpriteTriangle  ; first 80 rows are zero
    sta EnemySprite
    lda #>SpriteTriangle
    sta EnemySprite+1
    lda #76
    ELSE
    include "reuse_render.asm"
    ENDIF
.positionEnemy:
    IF DISPLAY_TEST = 0
    ; A holds the upper enemy's X. Keep it on the stack while PrepareHud uses
    ; the shared scratch bytes that just held pair-selection intermediates.
    pha
    jsr PrepareHud
    pla
    ENDIF
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
; Each subtract/branch iteration delays RESP by 15 color clocks. The remainder
; becomes a signed fine-motion nibble for the later HMOVE. Alignment and the
; forced absolute HMP store are timing requirements, not space optimizations.
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

    IF DISPLAY_TEST = 0
; X = drawable slot. Return A = display X (including cosmetic immunity shake),
; NextSprite = padded row pointer, NextColor = color. Preserve X; clobber A/Y/Temp.
; Square sprites have adjacent outline/filled versions: fill means bomb range,
; while the base shape reflects remaining armor. Feedback changes only visuals.
PrepareEnemyGraphic:
    SUBROUTINE
    ldy EnemyVisual,x
    lda EnemyFlags,x
    bmi .liveEnemy
    lda BurstColorByTimer,y
    sta NextColor
    lda BurstSpriteByTimer,y
    tay
    jmp .graphic
.liveEnemy:
    and #TYPE_MASK
    lsr
    lsr
    lsr
    lsr
    tay
    lda TypeColor,y
    sta NextColor
    lda TypeSprite,y
    tay
    cpy #2                ; only square graphics 2..5 have an outline/fill pair
    bcc .feedback
    cpy #6                ; diamond and shared hexagon/flash shape stay filled
    bcs .feedback
    lda EnemyHealth,x
    cmp #1
    bne .range
    ldy #2                ; one-health square, including damaged armor
.range:
    lda EnemyRadiusHi,x
    cmp #BOMB_RADIUS
    bcc .filled
    bne .feedback
    lda EnemyRadiusLo,x
    bne .feedback
.filled:
    iny                   ; ready shape follows outlined shape in atlas
.feedback:
    lda EnemyVisual,x
    beq .graphic
    bmi .hit
    sty Temp
    tay
    lda ImmuneColorByTimer,y
    ldy Temp
    jmp .color
.hit:
    lda #COLOR_HIT
.color:
    sta NextColor
.graphic:
    ; The kernel counts Y from 79 down to 0. Each shape has 80 leading zero
    ; bytes plus eight reversed rows; offsetting the pointer by EnemyY+6 places
    ; that window vertically without an in-kernel bounds test. The generator
    ; packs two shapes per page and pads them so all 80 reads have fixed timing.
    lda GraphicHi,y
    sta NextSprite+1
    lda EnemyY,x
    clc
    adc #6                ; eight-row window centered at old EnemyY+2
    adc GraphicLo,y       ; labels are at offsets 0 or 88, no carry
    sta NextSprite
    lda EnemyX,x
    ldy EnemyFlags,x
    bpl .return
    ldy EnemyVisual,x
    beq .return
    bmi .return
    clc
    adc ImmuneOffsetByTimer,y ; cosmetic shake; collision position never moves
.return:
    rts
    ENDIF

    IF DISPLAY_TEST = 0
; X = phase 0/1; inspect slots X and X+2. SelectedSlot/SecondSlot start at $ff.
; Live sprites and inactive bursts are drawable; leave absent outputs at $ff.
; Clobber A/X only, so the caller can sort a chosen pair by vertical position.
ChooseRenderPair:
    SUBROUTINE
    lda EnemyFlags,x
    bmi .first
    lda EnemyVisual,x
    beq .second
.first:
    stx SelectedSlot
.second:
    inx
    inx
    lda EnemyFlags,x
    bmi .drawable
    lda EnemyVisual,x
    beq .done
.drawable:
    lda SelectedSlot
    cmp #$ff
    bne .pair
    stx SelectedSlot
    rts
.pair:
    stx SecondSlot
.done:
    rts
    ENDIF
