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
    sta SWACNT
    lda #$a5
    ldx #7
.guards:
    sta GuardStart,x
    dex
    bpl .guards
    jsr LoadFixture
    jsr SampleInput
    lda CurrentButtons
    sta PreviousButtons
    jsr UpdateBeamVisual
    lda #2
    sta VBLANK
    jmp DisplayEntry

; Entry: overscan line 0, cycle 13. Exit: bank 1 at line 29, then sync line 30.
; RIOT's first decrement is immediate; 34 leaves the line-29 WSYNC window.
GameFrame:
    SUBROUTINE
    lda #34
    sta TIM64T
    jsr UpdatePrototype
LogicDone:
.wait:
    lda INTIM
    bne .wait
    sta WSYNC
    jmp DisplayEntry

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
    ; Minimal attack feedback; no music/event queue.
    lda #4
    sta AUDC0
    lda #8
    sta AUDF0
    lda BeamEnabled
    asl
    sta AUDV0
    lda #8
    sta AUDC1
    sta AUDF1
    ; Keep the short noise envelope independent of the longer ring animation.
    lda BombTimer
    sec
    sbc #(BOMB_ANIMATION_FRAMES-BOMB_SOUND_FRAMES)
    bcs .bombVolume
    lda #0
.bombVolume:
    sta AUDV1
    rts

; Visual state only: active beam stays bright; neutral stops gameplay/audio now
; while the last direction fades. A/X clobbered, no scratch, under 60 cycles.
; Laser Blast's decay is a low-nibble countdown 15..1, then hidden at zero.
; TIA ignores color bit 0, so brightness steps are 14,14,12,12,...,2,2,0.
UpdateBeamVisual:
    SUBROUTINE
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
.dark:
    lda #0
    sta BeamDrawColor
    lda #$ff
    sta BeamDrawDirection
    rts

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
