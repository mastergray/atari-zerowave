; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Power-on initialization and the overscan half of the frame loop. Game rules
; run while the picture is blank, then wait out the remaining fixed frame time.
Reset:
    SUBROUTINE
    sei
    cld
    ldx #$ff
    txs
    lda #0
    ldx #$7f
.clearRam:
    sta $80,x
    dex
    bpl .clearRam
    ldx #$2c
.clearTia:
    sta $00,x
    dex
    bpl .clearTia
    sta SWACNT            ; all joystick port pins are inputs (direction = 0)
    lda #$a5
    ldx #7
.guards:
    sta GuardStart,x
    dex
    bpl .guards
    IF DISPLAY_TEST
    jsr LoadFixture
    ELSE
    jsr StartRun
    lda #MODE_TITLE
    sta GameMode
    ENDIF
    ; Treat held power-on buttons as history, not new presses on the next frame.
    jsr SampleInput
    lda CurrentButtons
    sta PreviousButtons
    IF DISPLAY_TEST
    jsr UpdateBeamVisual
    ELSE
    jsr ClearWeapons
    ENDIF
    lda #2
    sta VBLANK
    jmp DisplayEntry

; Entry: overscan line 0, cycle 13. Exit: bank 1 at line 29, then sync line 30.
; RIOT's first decrement is immediate; 34 leaves the line-29 WSYNC window.
; TIM64T counts in 64-cycle intervals. The timer absorbs variable logic time;
; logic must finish before this window, or polling would miss the frame deadline.
GameFrame:
    SUBROUTINE
    lda #34
    sta TIM64T
    IF DISPLAY_TEST
    jsr UpdatePrototype
    ELSE
    jsr UpdateGame
    ENDIF
LogicDone:
.wait:
    lda INTIM
    bne .wait
    sta WSYNC
    jmp DisplayEntry

    IF DISPLAY_TEST
; Frame update is bounded: no spawning/search or combat in this display build.
; A/X/Y and scratch clobbered; input history saved on every path.
UpdatePrototype:
    SUBROUTINE
    inc FrameCounter
    lda #0
    sta BombEvent
    lda BombCooldown
    beq .noCooldown
    dec BombCooldown
.noCooldown:
    lda BombTimer
    beq .noAnimation
    dec BombTimer
.noAnimation:
    jsr SampleInput
    lda PressedButtons
    and #1
    beq .notReset
    lda #0
    sta LayoutId
    sta BombCooldown
    sta BombTimer
    sta BombCount
    sta BeamFadeTimer
    jsr LoadFixture
    jmp .finish
.notReset:
    lda PressedButtons
    and #2
    beq .notSelect
    inc LayoutId
    lda LayoutId
    cmp #FIXTURE_COUNT
    bcc .load
    lda #0
    sta LayoutId
.load:
    jsr LoadFixture
.notSelect:
    lda PressedButtons
    and #$80
    beq .finish
    lda BombCooldown
    bne .finish
    lda #BOMB_COOLDOWN
    sta BombCooldown
    lda #BOMB_ANIMATION_FRAMES
    sta BombTimer
    lda #1
    sta BombEvent
    inc BombCount
.finish:
    lda CurrentButtons
    sta PreviousButtons
    jsr UpdateBeamVisual
    jmp UpdateAudio

    ENDIF

; Visual state only. Gameplay starts a fade on each shot; diagnostics retain
; the held/release experiment. A/X clobbered, no scratch, under 100 cycles.
; Laser Blast's decay is a low-nibble countdown 15..1, then hidden at zero.
; TIA ignores color bit 0, so brightness steps are 14,14,12,12,...,2,2,0.
; Color is hue in the high nibble and luminance in the low nibble. A fresh shot
; picks a hue, then fades without steering or further damage. Ring display frames
; still advance this timer, so alternating effects cannot prolong the attack.
UpdateBeamVisual:
    SUBROUTINE
    IF DISPLAY_TEST = 0
    lda BeamEvent
    beq .shotFade
    ldx BeamPalette
    lda BeamColors,x
    and #$f0
    sta BeamFadeHue
    inx
    txa
    and #7
    sta BeamPalette
    lda LastDirection
    sta BeamDrawDirection
    lda #BEAM_FADE_START
    sta BeamFadeTimer
.shotFade:
    lda BeamFadeTimer
    beq .dark
    ora BeamFadeHue
    sta BeamDrawColor
    dec BeamFadeTimer
    rts
    ELSE
    lda BeamEnabled
    beq .released
    lda #BEAM_FADE_START
    sta BeamFadeTimer
    lda Direction
    sta BeamDrawDirection
    lda FrameCounter
    lsr
    lsr
    and #7
    tax
    lda BeamColors,x
    sta BeamDrawColor
    and #$f0
    sta BeamFadeHue
    rts
.released:
    lda BeamFadeTimer
    beq .dark
    ora BeamFadeHue
    sta BeamDrawColor
    dec BeamFadeTimer
    lda LastDirection
    sta BeamDrawDirection
    rts
    ENDIF
.dark:
    lda #0
    sta BeamDrawColor
    lda #$ff
    sta BeamDrawDirection
    rts

    IF DISPLAY_TEST
; Select a deterministic static layout. Clobbers A/X/Y, no scratch.
; Clears all four slots; only the first two are populated in this prototype.
LoadFixture:
    SUBROUTINE
    lda #0
    ldx #31
.clear:
    sta EnemyFlags,x
    dex
    bpl .clear
    ldy LayoutId
    lda FixtureFlags0,y
    sta EnemyFlags
    lda FixtureRadius0,y
    sta EnemyRadiusHi
    lda FixtureX0,y
    sta EnemyX
    lda FixtureY0,y
    sta EnemyY
    lda FixtureFlags1,y
    sta EnemyFlags+1
    lda FixtureRadius1,y
    sta EnemyRadiusHi+1
    lda FixtureX1,y
    sta EnemyX+1
    lda FixtureY1,y
    sta EnemyY+1
    rts
    ENDIF
