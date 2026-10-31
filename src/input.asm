; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Sample controls. Clobbers A/X; outputs current/pressed bits and Direction.
; Bit 7 = fire, bit 1 = SELECT, bit 0 = RESET. At most 160 cycles.
; Gameplay emits one BeamEvent per center-to-direction edge.
; Hardware switches are active low; invert them before edge detection.
; PressedButtons = current AND NOT previous. UpdateGame commits the history
; even outside PLAY, so starting a run or waiting between waves consumes inputs.
SampleInput:
    SUBROUTINE
    lda INPT4
    eor #$80
    and #$80
    sta CurrentButtons
    lda SWCHB
    eor #$ff
    and #3
    ora CurrentButtons
    sta CurrentButtons
    lda PreviousButtons
    eor #$ff
    and CurrentButtons
    sta PressedButtons
    ; Left joystick occupies SWCHA's upper nibble. After inversion/shifting,
    ; bits 0..3 mean up, down, left, right; use all 16 combinations as an index.
    lda SWCHA
    eor #$ff
    lsr
    lsr
    lsr
    lsr
    tax
    lda DirectionDecode,x
    sta Direction
    IF DISPLAY_TEST = 0
    lda #0
    sta BeamEvent
    cpx #0                ; only real center rearms, not opposing switches
    bne .direction
    lda #1
    sta BeamArmed
    rts
.direction:
    lda Direction
    cmp #$ff
    beq .done
    lda BeamArmed
    beq .done
    lda #0
    sta BeamArmed
    lda #1
    sta BeamEvent
    lda Direction
    sta LastDirection     ; latched shot direction, never steered during fade
.done:
    rts
    ELSE
    cmp #$ff
    beq .neutral
    sta LastDirection
    lda #1
    sta BeamEnabled
    rts
    ENDIF
.neutral:
    lda #0
    sta BeamEnabled
    rts

; Clockwise lanes: N=0, NE=1, E=2, SE=3, S=4, SW=5, W=6, NW=7.
; $ff rejects neutral/ambiguous combinations. Even if an opposing combination
; decodes to a lane, it cannot rearm: only the physical zero nibble can do that.
DirectionDecode:
    .byte $ff,0,4,$ff,6,7,5,6,2,1,3,2,$ff,0,4,$ff
