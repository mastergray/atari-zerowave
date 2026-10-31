; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Per slot: bomb event, beam shot event, then surviving contact. Slots count
; down to save loop cycles; all resolve before mode changes. A/X/Y and CombatType clobbered.
ResolveCombat:
    SUBROUTINE
    ldx #MAX_ENEMIES-1
.slot:
    lda EnemyFlags,x
    bpl .next
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
    jsr DamagePlayer
    lda #0
    sta EnemyFlags,x
    sta EnemyHealth,x
    sta EnemyVisual,x
.next:
    dex
    bpl .slot
.done:
    rts

; Contact or hexagon retaliation. Y=type index selects damage. X preserved.
DamagePlayer:
    SUBROUTINE
    lda Health
    sec
    sbc TypeDamage,y
    bcs .health
    lda #0
.health:
    sta Health
    lda #PLAYER_HIT_FRAMES
    sta PlayerHitTimer
    lda #SFX_PLAYER_HIT
    cmp SoundRequest      ; preserve a hexagon cue from any earlier slot
    bcc .done
    sta SoundRequest
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
    lda #SFX_HIT
    jmp RequestSound
.kill:
    ldy CombatType
    lda TypeScore,y
    jsr AwardScore
    lda EnemyFlags,x
    and #7
    ora #$40             ; inactive, with lane retained for burst positioning in VBLANK
    sta EnemyFlags,x
    lda #ENEMY_BURST_FRAMES
    sta EnemyVisual,x
    lda #SFX_KILL
    jmp RequestSound

; Immunity flash; hit flash wins. A/Y clobbered, X preserved. A hexagon is
; immune only to beams, so this path retaliates after a bomb could kill it.
ImmuneEnemy:
    SUBROUTINE
    lda EnemyVisual,x
    bmi .done
    lda #IMMUNE_FLASH_FRAMES
    sta EnemyVisual,x
.done:
    ldy CombatType
    cpy #(TYPE_HEXAGON >> 4)
    bne .ordinary
    lda #SFX_HEX_REJECT
    sta SoundRequest      ; highest combat cue; death is resolved afterward
    jmp DamagePlayer      ; one fresh shot; damage keeps the more specific cue
.ordinary:
    lda #SFX_IMMUNE
    jmp RequestSound

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
    lda KillsRemaining
    beq .done
    dec KillsRemaining
.done:
    rts
