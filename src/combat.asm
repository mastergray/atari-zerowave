; Per slot: bomb event, beam shot event, then surviving contact. All slots
; resolve before mode changes. A/X/Y and CombatType clobbered; two slots <800 cycles.
ResolveCombat:
    SUBROUTINE
    ldx #0
.slot:
    lda EnemyFlags,x
    bmi .active
    jmp .next
.active:
    and #TYPE_MASK
    lsr
    lsr
    lsr
    lsr
    sta CombatType
    tay
    lda BombEvent
    beq .beam
    lda EnemyRadiusHi,x
    cmp #BOMB_RADIUS
    bcc .bombHit
    bne .beam
    lda EnemyRadiusLo,x
    bne .beam
.bombHit:
    lda TypeWeapons,y
    and #VULNERABLE_BOMB
    beq .bombImmune
    jsr HitEnemy
    jmp .beam
.bombImmune:
    jsr ImmuneEnemy
.beam:
    lda EnemyFlags,x
    bpl .next
    lda BeamEvent
    beq .contact
    lda EnemyFlags,x
    and #7
    cmp LastDirection
    bne .contact
    ldy CombatType
    lda TypeWeapons,y
    and #VULNERABLE_BEAM
    beq .beamImmune
    jsr HitEnemy
    jmp .contact
.beamImmune:
    jsr ImmuneEnemy
.contact:
    lda EnemyFlags,x
    bpl .next
    lda EnemyRadiusHi,x
    cmp #CONTACT_RADIUS
    bcc .touch
    bne .next
    lda EnemyRadiusLo,x
    bne .next
.touch:
    ldy CombatType
    lda Health
    sec
    sbc TypeDamage,y
    bcs .health
    lda #0
.health:
    sta Health
    lda #PLAYER_HIT_FRAMES
    sta PlayerHitTimer     ; repeated contacts in this update share one flash
    lda #0
    sta EnemyFlags,x
    sta EnemyHealth,x
    sta EnemyVisual,x
.next:
    inx
    cpx #MAX_ENEMIES
    beq .done
    jmp .slot
.done:
    rts

; X=active slot, CombatType=type index. A/Y clobbered, X preserved. One damage;
; only a zero-health transition awards score and starts the burst. <100 cycles.
HitEnemy:
    SUBROUTINE
    dec EnemyHealth,x
    beq .kill
    lda #($80|HIT_FLASH_FRAMES)
    sta EnemyVisual,x
    rts
.kill:
    ldy CombatType
    lda TypeScore,y
    jsr AwardScore
    lda #0
    sta EnemyFlags,x
    lda #ENEMY_BURST_FRAMES
    sta EnemyVisual,x
    rts

; Cosmetic immunity cue. A clobbered; successful hit flash takes priority. <25 cycles.
ImmuneEnemy:
    SUBROUTINE
    lda EnemyVisual,x
    bmi .done
    lda #IMMUNE_FLASH_FRAMES
    sta EnemyVisual,x
.done:
    rts

; A=packed-BCD award (type award). Saturates at 9999. X/Y preserved, <50 cycles.
AwardScore:
    SUBROUTINE
    sed
    clc
    adc ScoreLo
    sta ScoreLo
    lda ScoreHi
    adc #0
    bcc .store
    lda #$99
    sta ScoreLo
.store:
    sta ScoreHi
    cld
    rts
