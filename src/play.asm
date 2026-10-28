; Fixed variant mix and difficulty for playtesting. Level changes come next.
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
    lda PressedButtons
    and #$80
    beq .quiet
.start:
    jsr StartRun
.quiet:
    jsr ClearWeapons
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
    jsr TrySpawn
.finish:
    lda CurrentButtons
    sta PreviousButtons
    jsr UpdateBeamVisual
    jmp UpdateAudio

; Fresh PLAY state. Preserve sampled input/history; the caller consumes this
; update, so start/reset cannot also attack or spawn. A/X clobbered, <500 cycles.
StartRun:
    SUBROUTINE
    lda #0
    ldx #31
.clearEnemies:
    sta EnemyFlags,x
    dex
    bpl .clearEnemies
    sta ScoreHi
    sta ScoreLo
    sta BombCooldown
    sta BombCount
    sta SquareTimer
    sta ActiveCount
    sta BeamPalette
    sta PlayerHitTimer
    sta EventSoundId
    sta EventSoundTimer
    sta SoundRequest
    lda #START_HP
    sta Health
    lda #ENEMY_CAP
    sta ActiveCap
    lda #1
    sta MovementEnabled
    lda #SPAWN_INTERVAL
    sta SpawnInterval
    sta SpawnTimer
    lda #$a5
    sta RandomState
    lda #MODE_PLAY
    sta GameMode
    jmp ClearWeapons

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
