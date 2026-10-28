; Cosmetic lifetimes advance before combat sets new timers. A/X clobbered,
; no scratch, at most four visits and <120 cycles. Coordinates stay fixed.
UpdateBursts:
    SUBROUTINE
    ldx #MAX_ENEMIES-1
.slot:
    lda EnemyVisual,x
    beq .next
    and #$7f
    cmp #1
    bne .dec
    lda #0                ; discard successful-hit flag on feedback expiry
    sta EnemyVisual,x
    beq .next
.dec:
    dec EnemyVisual,x
.next:
    dex
    bpl .slot
    rts

; Four allocated slots, at most two active. Movement is unsigned 8.8 fixed point.
; A/X/Y, CandidateLane, CoordDX/DY, MoveStep clobbered. Two slots: <700 cycles.
MoveEnemies:
    SUBROUTINE
    ldx #0
.slot:
    lda EnemyFlags,x
    bpl .next
    lda MovementEnabled   ; zero freezes movement for debugger fixtures
    beq .position
    lda EnemyFlags,x
    and #TYPE_MASK
    lsr
    lsr
    lsr
    lsr
    tay
    lda TypeSpeed,y
    sta MoveStep
    cpy #(TYPE_DIAMOND >> 4)
    bne .move
    lda EnemyRadiusHi,x
    cmp #DIAMOND_MID_RADIUS
    bcs .move
    lda #DIAMOND_MID_SPEED
    sta MoveStep
    lda EnemyRadiusHi,x
    cmp #DIAMOND_NEAR_RADIUS
    bcs .move
    lda #DIAMOND_NEAR_SPEED
    sta MoveStep
.move:
    lda EnemyRadiusLo,x
    sec
    sbc MoveStep
    sta EnemyRadiusLo,x
    lda EnemyRadiusHi,x
    sbc #0
    bcs .store
    lda #0
    sta EnemyRadiusLo,x
.store:
    sta EnemyRadiusHi,x
.position:
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

; Outputs ActiveCount, DrawableCount, FreeSlot ($ff if full), UsedLanes,
; BombTargetCount.
; Bursts reserve their old slots and count toward the two-object display cap.
; A/X/Y clobbered. At most four slot visits, <250 cycles for this build.
ScanEnemies:
    SUBROUTINE
    lda #0
    sta ActiveCount
    sta DrawableCount
    sta UsedLanes
    sta BombTargetCount
    lda #$ff
    sta FreeSlot
    ldx #MAX_ENEMIES-1
.slot:
    lda EnemyFlags,x
    bmi .active
    lda EnemyVisual,x
    beq .free
    inc DrawableCount
    jmp .next
.free:
    stx FreeSlot
    jmp .next
.active:
    inc ActiveCount
    inc DrawableCount
    and #$40
    beq .lane
    inc BombTargetCount
.lane:
    lda EnemyFlags,x
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
    lda DrawableCount
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
    and #7
    ora LevelTypeOffset   ; level rows each contain eight weighted choices
    tay
    lda LevelTypes,y
    tay
    and #4
    beq .typeReady
    lda SquareTimer
    bne .triangle
    lda BombTargetCount    ; mixed-speed bomb-only arrivals cannot pile up
    bne .triangle
    lda #SQUARE_SPAWN_GAP
    sta SquareTimer
    jmp .typeReady
.triangle:
    ldy #0
.typeReady:
    ldx FreeSlot
    lda TypeHealth,y
    sta EnemyHealth,x
    tya
    asl
    asl
    asl
    asl
    ora #$80
    ora CandidateLane
    sta EnemyFlags,x
    lda #SPAWN_RADIUS
    sta EnemyRadiusHi,x
    lda #0
    sta EnemyRadiusLo,x
    sta EnemyAge,x
    sta EnemyVisual,x
    jsr PositionEnemy
    inc ActiveCount
    inc DrawableCount
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
