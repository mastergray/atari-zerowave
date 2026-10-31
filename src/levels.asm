; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; LevelNumber is packed BCD 01..99. Higher numbers reuse the final spawn row;
; the kill quota grows independently until capped.
; A/X/Y clobbered. Preserve score, health, RNG, input history and spawn scratch.
ConfigureLevel:
    SUBROUTINE
    ; Palette index = (decimal level - 1) modulo eight, independent of difficulty.
    ; Ten is two modulo eight, so only the low two bits of the BCD tens matter.
    lda LevelNumber
    lsr
    lsr
    lsr
    and #6
    sta LevelBackground   ; scratch here: leave slot-scan scratch intact
    lda LevelNumber
    and #$0f
    clc
    adc LevelBackground
    sec
    sbc #1
    and #7
    tax
    lda LevelBackgroundColors,x
    sta LevelBackground
    lda LevelNumber
    cmp #(LEVEL_COUNT+1)
    bcc .row
    lda #LEVEL_COUNT
.row:
    sec
    sbc #1
    tay
    asl
    asl
    asl
    sta LevelTypeOffset
    jsr CalculateQuota
    sta KillsRemaining
    lda LevelInterval,y
    sta SpawnInterval
    lda LevelCap,y
    cmp #(VALIDATED_ENEMY_CAP+1)
    bcc .cap
    lda #VALIDATED_ENEMY_CAP
.cap:
    sta ActiveCap
    rts

LoadLevel:
    SUBROUTINE
    jsr ConfigureLevel
    lda SpawnInterval
    sta SpawnTimer
    lda #0
    ldx #31
.clear:
    sta EnemyFlags,x
    dex
    bpl .clear
    sta BombCooldown
    sta SquareTimer
    sta ActiveCount
    sta PlayerHitTimer
    sta EventSoundId
    sta EventSoundTimer
    sta SoundRequest
    lda #MODE_PLAY
    sta GameMode
    jmp ClearWeapons

; A = min(8 + 4 * (decimal level - 1), 64). Preserve X/Y and scratch.
; Cap before conversion: only BCD 10..14 needs the six-value adjustment.
; Shared by level loading and the progress denominator, so the bar stays exact.
CalculateQuota:
    SUBROUTINE
    lda LevelNumber
    cmp #LEVEL_QUOTA_CAP_LEVEL
    bcs .cap
    cmp #$10
    bcc .binary
    sbc #6                ; CMP supplies carry for the BCD-to-binary correction
.binary:
    asl
    asl
    adc #LEVEL_QUOTA_OFFSET ; shifts leave carry clear below the capped level
    rts
.cap:
    lda #LEVEL_QUOTA_CAP
    rts
