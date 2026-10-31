; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Sample controls. Clobbers A/X; outputs current/pressed bits and Direction.
; Bit 7 = fire, bit 1 = SELECT, bit 0 = RESET. At most 160 cycles.
; Gameplay emits one BeamEvent per center-to-direction edge.
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

DirectionDecode:
    .byte $ff,0,4,$ff,6,7,5,6,2,1,3,2,$ff,0,4,$ff
