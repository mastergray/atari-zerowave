; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; A kernel writes TIA registers while each scanline is being drawn. There is
; no framebuffer to upload: instruction order, page crossings and branch cycles
; determine where pixels appear. Completion-cycle comments count from WSYNC.
; Keep timed loops in place; docs/KERNEL_TIMING.md records their register deadlines.
;
; The arena is 80 logical rows, each repeated for two physical scanlines.
; Y counts down, matching reversed generated tables. Horizontal beams/rings use
; PF0/PF1/PF2; other beams use the one-color-clock ball with per-line motion.
; Gameplay includes reuse_kernel.asm to time-share P1 between two enemies;
; DISPLAY_TEST below keeps the simpler single-enemy diagnostic kernel.

ArenaFrameStart:
    IF DISPLAY_TEST
    ldx #7
SeparatorLoop:
    sta WSYNC
    lda #0
    sta PF0
    sta PF1
    sta PF2
    dex
    bne SeparatorLoop
    ELSE
    ; Entry at cycle 12 of visible line 29. A=0; clear the one-line separator.
    sta PF0
    sta PF1
    sta PF2
    ldx #0
    ENDIF
    lda ArenaColor
    sta COLUPF
    lda #COLOR_BACKGROUND
    IF DISPLAY_TEST
    sta COLUBK
    ENDIF
    sta HMCLR             ; well after blanking HMOVE; players stay stationary
    ; Clear positioning motion before the arena's repeated HMOVE strobes.
    ; The reuse kernel will explicitly supply new P1 motion between enemies.
    sta ENABL
    ldy #ARENA_ROWS-1      ; reverse indexing saves two loop cycles
    lda BallKernel
    beq .playfield
    jmp ThinBeamLoop
.playfield:

    IF DISPLAY_TEST
; Four varying PF streams serve both rays and rings: neither reaches columns
; 0..3 or 32..39. Sprite writes precede their earliest possible pixels.
; X is zero after the separator loop. Reuse it for constant-zero PF writes.
; Completion cycles: PF0=3, PF1=11, GRP1=19, PF2=27, GRP0=34,
; PF0=42, PF1=50, PF2=53. COLUPF stays fixed for the whole arena: the beam
; changes color between frames, with no stripes or scanline color gradient.
; Playfield registers normally repeat across the two screen halves. Rewriting
; them mid-line creates independent halves; a write must be late enough to
; preserve the left pixels yet early enough to supply the right pixels.
    MAC ARENA_SCANLINE
    stx PF0
    lda (BeamLeft1),y
    sta PF1
    lda (EnemySprite),y
    sta GRP1
    lda (BeamLeft2),y
    sta PF2
    lda TurretRows,y
    sta GRP0
    lda (BeamRight0),y
    sta PF0
    lda (BeamRight1),y
    sta PF1
    stx PF2
    ENDM
ArenaLoop:
    sta WSYNC
    ARENA_SCANLINE
    sta WSYNC
    ARENA_SCANLINE
    dey                   ; 55
    bpl ArenaLoop         ; 58; next WSYNC completes at 61
ArenaDone:
    lda #0
    sta ENABL
    lda #2
    sta WSYNC             ; first overscan line
    sta VBLANK
    jmp LogicEntry

; One-clock ball beam. The playfield stays clear; P0/P1 still draw every line.
; HMOVE at cycle 3, then HMBL no earlier than cycle 34 (>24 cycles later).
; Two packed motion nibbles advance the ball on individual physical lines.
ThinBeamLoop:
    sta WSYNC
    sta HMOVE             ; 3
    lda #0
    cpy BeamMinY
    bcc ThinBeamEnableReady
    cpy BeamMaxY
    bcs ThinBeamEnableReady
    lda #2
ThinBeamEnableReady:
    sta ENABL             ; <=20, before the leftmost beam pixel
    lda (EnemySprite),y
    sta GRP1              ; <=28, before the leftmost enemy
    lda TurretRows,y
    sta GRP0              ; <=35
    lda (BeamMotion),y
    sta HMBL              ; high nibble moves the second physical line
    sta WSYNC
    sta HMOVE             ; 3
    lda (EnemySprite),y
    sta GRP1              ; 11
    lda TurretRows,y
    sta GRP0              ; 18
    lda (BeamMotion),y
    asl
    asl
    asl
    asl
    sta HMBL              ; 34; low nibble moves the next row's first line
    dey
    bpl ThinBeamLoop
    jmp ArenaDone
    ELSE
    include "reuse_kernel.asm"
    ENDIF
