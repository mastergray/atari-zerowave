; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Wave settings come from config/levels.json through generated levels.inc.
; Difficulty rows choose enemy mix, spawn interval and active cap. The displayed
; BCD level, growing kill quota and repeating background palette are independent
; of that row, so later waves can reuse the last mix without freezing progress.
; A separate late_spawn setting shortens the delay from level 10 onward, after
; two waves with the hexagon. Compare the displayed level before choosing delay.
; From level 20, late_mix selects a ninth type row with a reinforced triangle;
; cap and delay still use the established settings, independent of this row.

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
    ; Eight type entries per row form a weighted selection table. Repeated IDs
    ; are intentional; a random 0..7 is combined with this aligned row offset.
    asl
    asl
    asl
    ldx LevelNumber
    cpx #LATE_MIX_LEVEL
    bcc .mix
    lda #LATE_MIX_OFFSET
.mix:
    sta LevelTypeOffset
    jsr CalculateQuota
    sta KillsRemaining
    lda LevelNumber
    cmp #LATE_SPAWN_LEVEL
    lda LevelInterval,y
    bcc .interval         ; LDA preserves carry from the packed-BCD level comparison
    lda #LATE_SPAWN_INTERVAL
.interval:
    sta SpawnInterval
    ; The generator validates every cap as 1..4; TrySpawn also enforces the
    ; validated display ceiling. Avoid duplicating that check in scarce ROM.
    lda LevelCap,y
    sta ActiveCap
    rts

; Start a wave without resetting score, HP, RNG or the consumed input state.
; The contiguous 32-byte clear removes slots, feedback and cached render state;
; ClearWeapons then removes any old attack/fade before the next visible frame.
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
; This compact arithmetic assumes quota step=4 and the cap is reached by BCD 19;
; the asset generator checks those assumptions before writing tuning constants.
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
