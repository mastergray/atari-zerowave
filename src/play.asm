; Table-driven levels, with the three-enemy display ceiling.
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
    dec SpawnTimer
    bne .quiet
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
    jsr ResolveCombat
    jsr ScanEnemies
    lda Health
    bne .alive
    lda #MODE_GAME_OVER
    sta GameMode
    jsr ClearWeapons
    lda #SFX_DEATH
    jsr RequestSound
    jmp .finish
.alive:
    lda KillsRemaining
    bne .spawn
    lda DrawableCount
    bne .finish
    jsr EnterLevelBreak
    jmp .finish
.spawn:
    jsr TrySpawn
.finish:
    lda CurrentButtons
    sta PreviousButtons
    jsr UpdateBeamVisual
    jmp UpdateAudio

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
