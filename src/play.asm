; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Table-driven levels, with the four-enemy display ceiling.
; A/X/Y clobbered, logic scratch only; bounded slot loops.
; The complete update must stay below 2,000 cycles; measured paths are in tests.
UpdateGame:
    SUBROUTINE
    inc FrameCounter
    lda #0
    sta BombEvent
    sta SoundRequest
    jsr SampleInput
    jsr UpdateBursts       ; advance old effects, including during game over
    lda PlayerHitTimer
    beq .playerFlashDone
    dec PlayerHitTimer
.playerFlashDone:
    lda PressedButtons
    and #1
    bne .start
    lda GameMode
    cmp #MODE_PLAY
    beq .play
    cmp #MODE_LEVEL_BREAK
    beq .levelBreak
    lda PressedButtons
    and #$80
    beq .quiet
.start:
    jsr StartRun
.quiet:
    jsr ClearWeapons
    jmp .finish
.levelBreak:
    lda SpawnTimer
    bne .countdown
    lda PlayerHitTimer
    bne .quiet            ; finish damage feedback before the yellow celebration
    jsr ClearEnemyBonus
    inx                   ; clear loop exits with X=$ff
    stx ActiveCount
    lda #LEVEL_BREAK_FRAMES
    sta SpawnTimer
    lda #SFX_CLEAR
    sta SoundRequest      ; no combat requests during the celebration
    bne .quiet
.countdown:
    dec SpawnTimer
    bne .quiet
    lda KillsRemaining
    bne .load             ; debugger loader: positive quota loads without advancing
    lda LevelNumber
    cmp #$99
    beq .load
    sed
    clc
    adc #1
    sta LevelNumber
    cld
.load:
    jsr LoadLevel          ; consume this update; no attack/spawn at the boundary
    jmp .finish
.play:
    lda BombCooldown
    beq .cooldownDone
    dec BombCooldown
.cooldownDone:
    lda BombTimer
    beq .bombDone
    dec BombTimer
.bombDone:
    lda SpawnTimer
    beq .spawnDone
    dec SpawnTimer
.spawnDone:
    lda SquareTimer
    beq .squareDone
    dec SquareTimer
.squareDone:
    jsr MoveEnemies
    lda PressedButtons
    and #$80
    beq .combat
    lda BombCooldown
    bne .combat
    lda #BOMB_COOLDOWN
    sta BombCooldown
    lda #BOMB_ANIMATION_FRAMES
    sta BombTimer
    lda #1
    sta BombEvent
    inc BombCount
    lda #SFX_BOMB
    sta SoundRequest
.combat:
    lda ScoreHi
    sta ScoreBeforeCombat
    jsr ResolveCombat
    lda Health
    bne .alive
    jsr ScanEnemies
    lda #MODE_GAME_OVER
    sta GameMode
    jsr ClearWeapons
    lda #SFX_DEATH
    jsr RequestSound
    jmp .finish
.alive:
    ; Award once after all hits/contacts, independent of slot order. Full health
    ; clears survivors; fatal contacts win. Four kills cannot span 1000 points.
    lda ScoreHi
    eor ScoreBeforeCombat
    and #$f0
    beq .noRecovery
    lda Health
    cmp #START_HP
    bcc .heal
    jsr ClearEnemyBonus
    lda #SFX_CLEAR
    bne .bonusCue
.heal:
    inc Health
    lda #SFX_HEAL
.bonusCue:
    jsr RequestSound
.noRecovery:
    jsr ScanEnemies        ; scan survivors/bursts after any full-health clear
    lda KillsRemaining
    bne .spawn
    sta SpawnTimer        ; show the full bar before clearing on the next update
    lda #MODE_LEVEL_BREAK
    sta GameMode
    bne .finish
.spawn:
    jsr TrySpawn
.finish:
    lda CurrentButtons
    sta PreviousButtons
    IF DISPLAY_TEST = 0
    lda SoundRequest
    ora EventSoundTimer
    bne .audioReady
    jsr PrepareApproachAudio ; idle voice only; preserve nearest radius until VBLANK
.audioReady:
    ENDIF
    jmp UpdateBeamVisual  ; audio runs at the start of the following VBLANK

; Full-health milestone or wave completion: ignore armor/immunity, no score.
; Milestones count quota progress; completion already has a zero quota.
; Freeze bursts at last displayed positions, preserve old bursts, defer due spawn.
; A/X clobbered, returns X=$ff; no scratch. Cached coordinates bound the update.
ClearEnemyBonus:
    SUBROUTINE
    lda SpawnInterval
    sta SpawnTimer
    ldx #MAX_ENEMIES-1
.slot:
    lda EnemyFlags,x
    bpl .next
    lda #0
    sta EnemyFlags,x
    sta EnemyHealth,x
    lda #ENEMY_BURST_FRAMES
    sta EnemyVisual,x
    lda KillsRemaining
    beq .next
    dec KillsRemaining
.next:
    dex
    bpl .slot
    rts

; Fresh PLAY state. Preserve sampled input/history; the caller consumes this
; update, so start/reset cannot also attack or spawn. A/X/Y clobbered, <500 cycles.
StartRun:
    SUBROUTINE
    lda #0
    sta ScoreHi
    sta ScoreLo
    sta BombCount
    sta BeamPalette
    lda #START_HP
    sta Health
    lda #1
    sta MovementEnabled
    sta LevelNumber
    lda #$a5
    sta RandomState
    jmp LoadLevel

; Stop attacks and afterglow for ready, reset, or game-over. A clobbered, <40 cycles.
ClearWeapons:
    lda #0
    sta BeamEnabled
    sta BeamFadeTimer
    sta BeamDrawColor
    sta BombTimer
    sta BombEvent
    sta ShotSoundTimer
    lda #$ff
    sta BeamDrawDirection
    rts
