; Channel 0 is the independent beam voice. Channel 1 plays one event envelope.
; Higher/equal priority interrupts; lower priority is discarded, never queued.
; A/X/Y clobbered, no scratch. Called once per update, including game over.
UpdateAudio:
    SUBROUTINE
    lda #4
    sta AUDC0
    lda #8
    sta AUDF0
    IF DISPLAY_TEST
    lda BeamEnabled
    asl
    ELSE
    lda BeamEvent
    beq .shotDecay
    lda #BEAM_SOUND_FRAMES
    sta ShotSoundTimer
.shotDecay:
    lda ShotSoundTimer
    beq .shotVolume
    dec ShotSoundTimer
.shotVolume:
    ENDIF
    sta AUDV0
    IF DISPLAY_TEST
    ; Preserve the diagnostic ROM's original beam/bomb sound experiment.
    lda #8
    sta AUDC1
    sta AUDF1
    lda BombTimer
    sec
    sbc #(BOMB_ANIMATION_FRAMES-BOMB_SOUND_FRAMES)
    bcs .bombVolume
    lda #0
.bombVolume:
    sta AUDV1
    ELSE
    lda SoundRequest
    beq .continue
    ldy EventSoundTimer
    beq .accept
    cmp EventSoundId
    bcc .continue
.accept:
    sta EventSoundId
    tax
    lda SoundLength,x
    sta EventSoundTimer
.continue:
    lda EventSoundTimer
    beq .silent
    ldx EventSoundId
    clc
    adc SoundOffset,x
    tay
    lda SoundControl,y
    sta AUDC1
    lda SoundFrequency,y
    sta AUDF1
    lda SoundVolume,y
    sta AUDV1
    dec EventSoundTimer
    rts
.silent:
    sta EventSoundId
    sta AUDV1
    ENDIF
    rts

; A=event priority/ID. Coalesce events before selecting a voice, so slot order
; cannot hide damage/death behind a lower-priority cue. X/Y preserved.
RequestSound:
    SUBROUTINE
    cmp SoundRequest
    bcc .done
    sta SoundRequest
.done:
    rts
