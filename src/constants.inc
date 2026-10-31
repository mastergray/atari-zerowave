; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Mode parity is intentional: PLAY and LEVEL_BREAK are odd, so the progress
; bar can test bit 0 to decide whether to draw. Title and game over are even.
MODE_TITLE = 0
MODE_PLAY = 1
MODE_GAME_OVER = 2
MODE_LEVEL_BREAK = 3
MAX_ENEMIES = 4
; Allocated slots are also the tested rendering limit, not just a spawn limit.
VALIDATED_ENEMY_CAP = 4
    IF DISPLAY_TEST
ARENA_START_LINE = 72
    ELSE
ARENA_START_LINE = 70
    ENDIF
; Type constants are already shifted into EnemyFlags bits 4..6. Shift right
; four times to index generated TypeHealth/TypeWeapons/TypeSpeed/etc. tables.
; Bit 6 groups every bomb-only enemy (squares and hexagons) for spawn limits.
TYPE_TRIANGLE = $00
TYPE_FAST = $10
TYPE_DIAMOND = $20
TYPE_SQUARE = $40
TYPE_ARMOR = $50
TYPE_FAST_SQUARE = $60
TYPE_HEXAGON = $70
TYPE_MASK = $70
; TypeWeapons is a bit mask: triangles=1, diamonds=3, squares/hexagons=2.
VULNERABLE_BEAM = 1
VULNERABLE_BOMB = 2
