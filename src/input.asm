; Sample controls. Clobbers A/X; outputs current/pressed bits and Direction.
; Bit 7 = fire, bit 1 = SELECT, bit 0 = RESET. At most 100 cycles.
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
    cmp #$ff
    beq .neutral
    sta LastDirection
    lda #1
    sta BeamEnabled
    rts
.neutral:
    lda #0
    sta BeamEnabled
    rts

DirectionDecode:
    .byte $ff,0,4,$ff,6,7,5,6,2,1,3,2,$ff,0,4,$ff
