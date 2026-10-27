; Fixed opening difficulty for the milestone-2 combat prototype. Level changes
; are the next milestone. A/X/Y clobbered, logic scratch only; bounded slot loops.
; The complete update must stay below 2,000 cycles; measured paths are in tests.
UpdateGame:
    SUBROUTINE
    inc FrameCounter
    lda #0
    sta BombEvent
    jsr SampleInput
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
.combat:
    jsr ResolveCombat
    jsr ScanEnemies
    lda Health
    bne .alive
    lda #MODE_GAME_OVER
    sta GameMode
    jsr ClearWeapons
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
    lda #START_HP
    sta Health
    lda #ENEMY_CAP
    sta ActiveCap
    lda #ENEMY_SPEED
    sta EnemySpeed
    lda #SPAWN_INTERVAL
    sta SpawnInterval
    sta SpawnTimer
    lda #SQUARE_WEIGHT
    sta SquareWeight
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
    lda #$ff
    sta BeamDrawDirection
    rts
