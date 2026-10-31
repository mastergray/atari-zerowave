; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Stable phases pair slots 0/2 and 1/3. Empty phases borrow the other phase.
; The spawner guarantees separation for each pair's entire remaining life.
; This file is included inside PrepareRender, not called as a separate routine.
; It prepares the upper sprite in EnemySprite/COLUP1 and the lower sprite in
; NextSprite/NextColor, then rejoins .positionEnemy with the upper X in A.
; Showing two separated enemies per frame lets one TIA player cover four slots
; over two frames. A completely empty phase borrows, avoiding needless flicker.
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
    ; Smaller screen Y is higher. Draw it first even when its slot number is
    ; larger; the lower sprite must leave enough blank rows for repositioning.
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
    ; Signed two's-complement displacement. ReuseMotion/ReuseRemainder turn it
    ; into small horizontal steps while the sprite pixels between enemies are 0.
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
    ; Reverse-index row immediately below the upper sprite's eight-row window.
    ; The kernel swaps pointers/color there, then moves P1 during the gap.
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
