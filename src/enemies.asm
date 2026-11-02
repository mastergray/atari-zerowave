; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Four parallel RAM slots hold every enemy and its destruction effect. Each
; live slot follows one of eight fixed lanes toward the turret; its radius is
; authoritative. Screen coordinates are cached later for rendering, not combat.
; A dead slot remains reserved while its burst is visible, so spawning cannot
; erase an explosion or break the display pair's separation guarantees.

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

; Four allocated slots, at most four active. Movement is unsigned 8.8 fixed point.
; A/X/Y and MoveStep clobbered. VBLANK derives coordinates after combat/spawning.
; TypeSpeed is in 1/256 radius units per update: 32 moves 1/8 unit. Diamonds
; substitute faster steps inside the middle/near radii. Subtracting the fraction
; borrows into the whole byte; underflow clamps both bytes to zero.
MoveEnemies:
    SUBROUTINE
    lda MovementEnabled   ; one check covers every slot, including debugger freeze
    beq .done
    ldx #MAX_ENEMIES-1
.slot:
    lda EnemyFlags,x
    bpl .next
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
.next:
    dex
    bpl .slot
.done:
    rts

; X=slot, radius_hi 0..63. Four shared magnitude tables replace per-lane X/Y
; tables. A/Y and CandidateLane, CoordDX/DY clobbered; X preserved, <180 cycles.
; Odd lanes are diagonal. Cardinal lanes use only one axis; lane tests supply
; the signs. The tables account for the arena's unequal horizontal/vertical
; scale, avoiding trigonometry at runtime. (76,38) anchors the sprite at center;
; EnemyY is measured in logical rows, each displayed on two physical scanlines.
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
; Bursts reserve their old slots and count toward the level display cap.
; A/X/Y clobbered. At most four slot visits, <250 cycles for this build.
; UsedLanes is an eight-bit occupancy mask for live enemies; bomb-only types
; are counted separately for their shared cap. Only an inactive slot with no
; visual lifetime is free. The descending scan leaves the lowest free index.
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
; A/X/Y, CandidateLane, SpawnType, UsedLanes, CoordDX/DY clobbered.
; Selection is deliberately bounded to fit overscan. Choose a type and starting
; lane, mask out unsafe lanes, then probe clockwise once. A failed placement
; retries in two updates; it never loops until it finds a random valid position.
TrySpawn:
    SUBROUTINE
    lda SpawnTimer
    bne .done
    lda DrawableCount
    cmp ActiveCap
    bcs .done
    cmp #VALIDATED_ENEMY_CAP
    bcs .done
    lda FreeSlot
    cmp #$ff
    bne .choose
.done:
    rts
.choose:
    jsr NextRandom
    and #7
    sta CandidateLane
    jsr NextRandom
    lsr
    lsr
    lsr
    lsr
    lsr                    ; upper bits keep type selection independent of lane
    ora LevelTypeOffset
    tay
    lda LevelTypes,y
    tay
    ; Bomb-only enemies share a spawn gap and at most half the active cap.
    ; If that family is unavailable, fall back to the basic beam-only triangle.
    and #4
    beq .typeReady
    lda SquareTimer
    bne .triangle
    lda BombTargetCount
    asl                    ; one bomb-only target with two slots, two with four
    cmp ActiveCap
    bcc .typeReady
.triangle:
    ldy #0
.typeReady:
    sty SpawnType
    IF DISPLAY_TEST = 0
    lda ActiveCap
    cmp #3
    bcc .probe
    lda FreeSlot
    and #1
    beq .verticalOnly
    lda SpawnType
    cmp #(TYPE_FAST >> 4)
    beq .partner
.verticalOnly:
    lda UsedLanes
    ora #$44              ; E/W reserved for fast singletons in the odd phase
    sta UsedLanes
.partner:
    ; Slots 0/2 and 1/3 share one displayed frame. XOR 2 finds the other member.
    ; The two P1 draws need a vertical gap for horizontal repositioning; spawn
    ; restrictions preserve that gap through movement and the final burst.
    lda FreeSlot
    eor #2
    tax
    lda EnemyFlags,x
    bmi .livePartner
    lda EnemyVisual,x
    beq .probe
    bne .retry             ; bursts keep their lane and draw reservation
.livePartner:
    and #7
    cmp #2
    beq .horizontalPartner
    cmp #6
    beq .horizontalPartner
    lda EnemyFlags,x
    and #TYPE_MASK
    lsr                    ; old kind * 8 + new kind
    ora SpawnType
    tay
    lda EnemyRadiusHi,x
    cmp PairEarlyLimit,y
    bcc .separate
    cmp PairLateLimit,y
    bcc .retry
.separate:
    ; A partner far out or almost finished can be safe; the middle arrival
    ; window is rejected. Generated bounds include type speed, acceleration and
    ; burst lifetime. Place the new enemy in the opposite vertical half.
    lda EnemyFlags,x
    and #7
    cmp #3
    bcc .upper
    cmp #6
    bcs .upper
    lda #$7c              ; old lower half: allow only N, NE, NW
    bne .restrict
.upper:
    lda #$c7              ; old upper half: allow only SE, S, SW
.restrict:
    ora UsedLanes
    sta UsedLanes
    jmp .probe
.horizontalPartner:
    ; A new vertical partner stays outside radius 36 until this horizontal
    ; enemy and its possible burst finish. Its type-pair bound is stricter than
    ; the usual opposite-half case because this sprite sits at turret height.
    lda EnemyFlags,x
    and #TYPE_MASK
    lsr
    ora SpawnType
    tay
    lda EnemyRadiusHi,x
    cmp HorizontalEarlyLimit,y
    bcs .retry
    lda UsedLanes
    ora #$44
    sta UsedLanes
    ENDIF
.probe:
    ldx CandidateLane
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
.retry:
    lda #2
    sta SpawnTimer
    rts
.found:
    ; Only a successful placement starts the normal delays. Coordinates are
    ; left to PrepareFrame after combat/spawning, keeping logic work bounded.
    stx CandidateLane
    ldy SpawnType
    tya
    and #4
    beq .create
    lda #SQUARE_SPAWN_GAP
    sta SquareTimer
.create:
    ldx FreeSlot
    lda TypeHealth,y
    cpy #(TYPE_DIAMOND >> 4)
    bne .health
    ; The displayed level is packed BCD. CMP supplies one extra HP from level
    ; 25 onward; the diamond keeps the same type, speed, weapons and score.
    lda LevelNumber
    cmp #REINFORCED_DIAMOND_LEVEL
    lda #(REINFORCED_DIAMOND_HEALTH-1)
    adc #0
.health:
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
    sta EnemyVisual,x
    inc ActiveCount
    inc DrawableCount
    lda SpawnInterval
    sta SpawnTimer
    rts

; Nonzero 8-bit maximal LFSR, seed $a5. A clobbered, X/Y preserved, <25 cycles.
; Shift out one bit and apply feedback when it was set. Zero is a stuck state,
; so StartRun seeds a nonzero value. A fixed seed also makes runs reproducible.
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
