; LevelNumber is packed BCD 01..99. Higher numbers reuse the final data row.
; A/X/Y clobbered. Preserve score, health, RNG and sampled input history.
LoadLevel:
    SUBROUTINE
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
    lda LevelQuota,y
    sta KillsRemaining
    lda LevelInterval,y
    sta SpawnInterval
    sta SpawnTimer
    lda LevelCap,y
    cmp #(VALIDATED_ENEMY_CAP+1)
    bcc .cap
    lda #VALIDATED_ENEMY_CAP
.cap:
    sta ActiveCap
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

; Called only after the last live enemy and destruction burst are gone.
EnterLevelBreak:
    SUBROUTINE
    lda LevelNumber
    cmp #$99
    beq .saturated
    sed
    clc
    adc #1
    sta LevelNumber
    cld
.saturated:
    lda #MODE_LEVEL_BREAK
    sta GameMode
    lda #LEVEL_BREAK_FRAMES
    sta SpawnTimer         ; no spawning during the break; reuse its countdown
    jmp ClearWeapons
