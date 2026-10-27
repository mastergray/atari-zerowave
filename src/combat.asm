; Each slot resolves bomb, then beam, then contact. Slots are independent; mode
; transitions happen after all slots, so all kills/contacts count on a death frame.
; A/X clobbered, no scratch; two active slots <400 cycles including BCD awards.
ResolveCombat:
    SUBROUTINE
    ldx #0
.slot:
    lda EnemyFlags,x
    bpl .next
    lda BombEvent
    beq .beam
    lda EnemyRadiusHi,x
    cmp #BOMB_RADIUS
    bcc .kill
    bne .beam
    lda EnemyRadiusLo,x
    beq .kill
.beam:
    lda BeamEnabled
    beq .contact
    lda EnemyFlags,x
    and #$40
    bne .contact
    lda EnemyFlags,x
    and #7
    cmp Direction
    beq .kill
.contact:
    lda EnemyRadiusHi,x
    cmp #CONTACT_RADIUS
    bcc .touch
    bne .next
    lda EnemyRadiusLo,x
    bne .next
.touch:
    lda #0
    sta EnemyFlags,x
    lda Health
    beq .next
    dec Health
    jmp .next
.kill:
    lda EnemyFlags,x
    and #$40
    beq .triangle
    lda #$25
    bne .award
.triangle:
    lda #$10
.award:
    jsr AwardScore
    lda #0
    sta EnemyFlags,x
.next:
    inx
    cpx #MAX_ENEMIES
    bne .slot
    rts

; A=packed-BCD award ($10 or $25). Saturates at 9999. X/Y preserved, <50 cycles.
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
