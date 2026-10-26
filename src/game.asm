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
    lda BombFlash
    beq .noFlash
    dec BombFlash
.noFlash:
    jsr SampleInput
    lda PressedButtons
    and #1
    beq .notReset
    lda #0
    sta LayoutId
    sta BombCooldown
    sta BombFlash
    sta BombCount
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
    lda #BOMB_FLASH
    sta BombFlash
    lda #1
    sta BombEvent
    inc BombCount
.finish:
    lda CurrentButtons
    sta PreviousButtons
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
    lda BombFlash
    sta AUDV1
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
