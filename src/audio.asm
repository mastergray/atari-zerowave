; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Channel 0 is the independent beam voice. Channel 1 plays one event envelope,
; or a distance-driven fast-triangle warning when no event is playing.
; Higher/equal priority interrupts; lower priority is discarded, never queued.
; A/X/Y clobbered. Once per update, at the start of gameplay VBLANK.
; Idle warning consumes Temp from PrepareApproachAudio before render scratch;
; diagnostics update sound in overscan.
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
    lda SoundSample,y     ; repeated envelope samples share one register triple
    tay
    lda SoundControlVolume,y
    tax                   ; shared sample packs volume high, waveform low
    and #15
    sta AUDC1
    lda SoundFrequency,y
    sta AUDF1
    txa
    lsr
    lsr
    lsr
    lsr
    sta AUDV1
    dec EventSoundTimer
    rts
.silent:
    sta EventSoundId
    lda GameMode
    cmp #MODE_PLAY
    bne .quiet
    lda #FAST_APPROACH_RADIUS
    sec
    sbc Temp
    bcc .quiet            ; no live magenta triangle in the warning zone
    tax                   ; depth into warning zone, before frequency division
    lsr
    clc
    adc #FAST_APPROACH_FREQUENCY_START
    sta AUDF1             ; increasing divider makes the whistle descend
    txa
    lsr
    lsr
    lsr
    clc
    adc #FAST_APPROACH_VOLUME_START
    sta AUDV1             ; grow louder on the final approach
    lda #FAST_APPROACH_CONTROL
    sta AUDC1
    rts
.quiet:
    lda #0
    sta AUDV1
    ENDIF
    rts

    IF DISPLAY_TEST = 0
; Only when both sound request and active envelope are zero. A/X clobbered.
; Temp carries the nearest radius from overscan to the first VBLANK operation;
; beam visual update and sync never touch it. Rendering may then reuse it.
PrepareApproachAudio:
    SUBROUTINE
    lda #(FAST_APPROACH_RADIUS+1)
    sta Temp
    ldx #MAX_ENEMIES-1
.nearest:
    lda EnemyFlags,x
    and #($80 | TYPE_MASK)
    cmp #($80 | TYPE_FAST)
    bne .next
    lda EnemyRadiusHi,x
    cmp Temp
    bcs .next
    sta Temp
.next:
    dex
    bpl .nearest
    rts
    ENDIF

; A=event priority/ID. Coalesce events before selecting a voice, so slot order
; cannot hide damage/death behind a lower-priority cue. X/Y preserved.
RequestSound:
    SUBROUTINE
    cmp SoundRequest
    bcc .done
    sta SoundRequest
.done:
    rts
