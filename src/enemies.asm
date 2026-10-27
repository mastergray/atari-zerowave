; Four allocated slots, at most two active. Movement is unsigned 8.8 fixed point.
; A/X/Y, CandidateLane, CoordDX/DY clobbered. Two active slots: <550 cycles.
MoveEnemies:
    SUBROUTINE
    ldx #0
.slot:
    lda EnemyFlags,x
    bpl .next
    lda EnemyRadiusLo,x
    sec
    sbc EnemySpeed
    sta EnemyRadiusLo,x
    lda EnemyRadiusHi,x
    sbc #0
    bcs .store
    lda #0
    sta EnemyRadiusLo,x
.store:
    sta EnemyRadiusHi,x
    jsr PositionEnemy
.next:
    inx
    cpx #MAX_ENEMIES
    bne .slot
    rts

; X=slot, radius_hi 0..63. Four shared magnitude tables replace per-lane X/Y
; tables. A/Y and CandidateLane, CoordDX/DY clobbered; X preserved, <180 cycles.
PositionEnemy:
    SUBROUTINE
    lda EnemyFlags,x
    and #7
    sta CandidateLane
    ldy EnemyRadiusHi,x
    and #1
    beq .cardinal
    lda RadiusXDiagonal,y
    sta CoordDX
    lda RadiusYDiagonal,y
    sta CoordDY
    jmp .signs
.cardinal:
    lda CandidateLane
    and #2
    beq .vertical
    lda RadiusXCardinal,y
    sta CoordDX
    lda #0
    sta CoordDY
    beq .signs
.vertical:
    lda RadiusYCardinal,y
    sta CoordDY
    lda #0
    sta CoordDX
.signs:
    lda CandidateLane
    cmp #4
    bcs .left
    lda #76
    clc
    adc CoordDX
    jmp .storeX
.left:
    lda #76
    sec
    sbc CoordDX
.storeX:
    sta EnemyX,x
    lda CandidateLane
    cmp #3
    bcc .up
    cmp #6
    bcs .up
    lda #38
    clc
    adc CoordDY
    jmp .storeY
.up:
    lda #38
    sec
    sbc CoordDY
.storeY:
    sta EnemyY,x
    rts

; Outputs ActiveCount, FreeSlot ($ff if full), UsedLanes. A/X/Y clobbered.
; At most four slot visits, <200 cycles for the two-enemy build.
ScanEnemies:
    SUBROUTINE
    lda #0
    sta ActiveCount
    sta UsedLanes
    lda #$ff
    sta FreeSlot
    ldx #MAX_ENEMIES-1
.slot:
    lda EnemyFlags,x
    bmi .active
    stx FreeSlot
    jmp .next
.active:
    inc ActiveCount
    and #7
    tay
    lda LaneBits,y
    ora UsedLanes
    sta UsedLanes
.next:
    dex
    bpl .slot
    rts

; Uses ScanEnemies outputs. No more than eight lane probes and one spawn.
; A/X/Y, CandidateLane, CoordDX/DY clobbered; <500 cycles including positioning.
TrySpawn:
    SUBROUTINE
    lda SpawnTimer
    bne .done
    lda ActiveCount
    cmp ActiveCap
    bcs .done
    cmp #VALIDATED_ENEMY_CAP
    bcs .done
    lda FreeSlot
    cmp #$ff
    beq .done
    jsr NextRandom
    and #7
    tax
    ldy #8
.lane:
    lda LaneBits,x
    and UsedLanes
    beq .found
    inx
    txa
    and #7
    tax
    dey
    bne .lane
    lda #8
    sta SpawnTimer
    rts
.found:
    stx CandidateLane
    jsr NextRandom
    and #3
    cmp SquareWeight
    bcs .triangle
    lda SquareTimer
    bne .triangle
    lda #SQUARE_SPAWN_GAP
    sta SquareTimer
    lda #$c0
    bne .typeReady
.triangle:
    lda #$80
.typeReady:
    ora CandidateLane
    ldx FreeSlot
    sta EnemyFlags,x
    lda #SPAWN_RADIUS
    sta EnemyRadiusHi,x
    lda #0
    sta EnemyRadiusLo,x
    sta EnemyAge,x
    sta EnemyPhase,x
    sta EnemyVisual,x
    jsr PositionEnemy
    inc ActiveCount
    lda SpawnInterval
    sta SpawnTimer
.done:
    rts

; Nonzero 8-bit maximal LFSR, seed $a5. A clobbered, X/Y preserved, <25 cycles.
NextRandom:
    SUBROUTINE
    lda RandomState
    lsr
    bcc .store
    eor #$b8
.store:
    sta RandomState
    rts

LaneBits:
    .byte 1,2,4,8,16,32,64,128
