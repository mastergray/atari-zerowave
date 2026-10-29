; Stable phases pair slots 0/2 and 1/3. Empty phases borrow the other phase.
; The spawner guarantees separation for each pair's entire remaining life.
    lda #0
    sta ReuseRow
    sta NextDelta
    lda #$ff
    sta SelectedSlot
    sta SecondSlot
    ldx FramePhase
    jsr ChooseRenderPair
    lda SelectedSlot
    cmp #$ff
    bne .chosen
    lda FramePhase
    eor #1
    tax
    jsr ChooseRenderPair
.chosen:
    ldx SelectedSlot
    cpx #$ff
    beq .empty
    ldy SecondSlot
    cpy #$ff
    beq .firstGraphic
    lda EnemyY,x
    cmp EnemyY,y
    bcc .ordered
    stx SecondSlot
    sty SelectedSlot
    ldx SelectedSlot
    ldy SecondSlot
.ordered:
    lda EnemyY,y
    sec
    sbc EnemyY,x
    cmp #12
    bcs .firstGraphic
    ; Invalid debugger fixtures degrade safely; natural spawning never does.
    lda FramePhase
    ora #$80
    sta FramePhase
    lda #$ff
    sta SecondSlot
.firstGraphic:
    jsr PrepareEnemyGraphic
    sta FirstDrawX
    lda NextSprite
    sta EnemySprite
    lda NextSprite+1
    sta EnemySprite+1
    lda NextColor
    sta COLUP1
    ldx SecondSlot
    cpx #$ff
    beq .single
    jsr PrepareEnemyGraphic
    sec
    sbc FirstDrawX
    sta NextDelta
    inx
    txa
    asl
    ora FramePhase
    sta FramePhase
    ldx SelectedSlot
    lda #73
    sec
    sbc EnemyY,x
    sta ReuseRow
.single:
    lda FirstDrawX
    jmp .positionEnemy
.empty:
    lda #<SpriteTriangle
    sta EnemySprite
    lda #>SpriteTriangle
    sta EnemySprite+1
    lda #76
    jmp .positionEnemy
