; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Fixed RAM reservations from IMPLEMENTATION_SPEC.md. No RAM outside $80..$FF.
; The console has only 128 bytes of RAM. SEG.U reserves names/addresses
; without emitting ROM bytes. Arrays are parallel: X selects the same enemy
; in every four-byte array. LoadLevel clears this entire 32-byte slot block.
;
; EnemyFlags while active: %1ttt0lll (type t, clockwise lane l: N=0..NW=7).
; A scored kill instead leaves $40|lane until PrepareFrame positions its burst;
; a bonus clear leaves zero and uses cached X/Y. EnemyVisual keeps either kind
; of inactive slot occupied until its burst ends.
    SEG.U RAM
    ORG $80
EnemyFlags      ds 4
EnemyRadiusHi   ds 4      ; whole lane distance from turret, not screen pixels
EnemyRadiusLo   ds 4      ; fractional distance: 256 units make one whole unit
EnemyX          ds 4      ; cached sprite left edge, in horizontal color clocks
EnemyY          ds 4      ; cached position in logical rows (two scanlines each)
EnemyPhase      ds 4
EnemyHealth = EnemyPhase  ; legacy diagnostic phase is unused in gameplay
EnemyAge        ds 4
; Diagnostic draw ages; gameplay reuses these four bytes for the second draw.
NextSprite = EnemyAge
NextDelta = EnemyAge+2
NextColor = EnemyAge+3
EnemyVisual     ds 4
; Inactive: destruction lifetime. Active: bit 7 successful hit, low 7 feedback
; lifetime (yellow/orange immunity shake when bit 7 is clear). Zero is normal.
; Persistent game/input state follows. The diagnostic build aliases selected
; fields for fixture controls; its meanings must not be assumed in gameplay.
LayoutId        ds 1
LevelNumber = LayoutId  ; packed BCD 01..99 in gameplay, SELECT fixture in diagnostics
FrameCounter    ds 1
BombCount       ds 1
GameMode        ds 1
Health          ds 1
ScoreHi         ds 1      ; packed BCD thousands/hundreds (e.g. $12 for 12xx)
ScoreLo         ds 1      ; packed BCD tens/ones (e.g. $34 completes score 1234)
SpawnTimer      ds 1      ; spawn delay in PLAY; celebration countdown in BREAK
SquareTimer     ds 1      ; shared minimum gap between bomb-only enemy spawns
RandomState     ds 1
ActiveCount     ds 1
ActiveCap       ds 1
MovementEnabled ds 1
SpawnInterval   ds 1
BeamPalette     ds 1
BeamArmed       ds 1      ; only true neutral rearms a shot; holding cannot repeat
Direction       ds 1      ; decoded current lane 0..7, or $ff for no valid direction
LastDirection   ds 1      ; latched shot lane; used for damage, not current input
PreviousButtons ds 1
BeamEnabled     ds 1
BeamEvent = BeamEnabled  ; one-update event in gameplay, held input in diagnostics
BombCooldown    ds 1      ; updates until another fresh button press may bomb
BombTimer       ds 1      ; cosmetic expanding ring, separate from damage event
BombEvent       ds 1      ; one-update pulse, not repeated during the ring
FramePhase      ds 1      ; bit 0 draw pair; renderer also packs diagnostic metadata
HudHealth1      ds 1
HudHealth2      ds 1
AudioReserved   ds 6
ShotSoundTimer = AudioReserved
PlayerHitTimer = AudioReserved+1
EventSoundId = AudioReserved+2
EventSoundTimer = AudioReserved+3
SoundRequest = AudioReserved+4
KillsRemaining = AudioReserved+5
; VBLANK fills these pointers/state for the visible kernels. TIA has no frame
; buffer: each pointed-to row supplies register values as the scanline is drawn.
BeamLeft1       ds 2
BeamLeft2       ds 2
BeamRight0      ds 2
BeamRight1      ds 2
EnemySprite     ds 2
SelectedSlot    ds 1
HudColor        ds 1
LevelBackground = HudColor ; gameplay reuses the diagnostic HUD-ready color byte
ArenaColor      ds 1
DisplayPattern  ds 1
BeamFadeTimer   ds 1
BeamFadeHue     ds 1
BeamDrawDirection ds 1
BeamDrawColor   ds 1
BeamMotion      ds 2
BeamMinY        ds 1
BeamMaxY        ds 1
BallKernel      ds 1
RenderReserved  ds 1
LevelTypeOffset = RenderReserved
; HUD buffers live only during display. Logic scratch aliases their storage.
; Lifetime order: overscan uses input/spawn/combat scratch, commits button
; history, then VBLANK overwrites it with HUD rows. After score rows are drawn,
; PrepareProgress overwrites the right-score rows with the bottom bar masks.
; Never keep a logic temporary here across display preparation.
HudScoreLeft    ds 5
HudScoreRight   ds 5
HudProgress = HudScoreRight ; after score rows finish, five progress PF masks
ProgressQuota = HudProgress+4 ; denominator scratch until final bar masks replace it
HudStatus1      ds 2
HudStatus2      ds 2
BestAge         ds 1
ReuseRow = BestAge
Temp            ds 1
CurrentButtons = HudScoreLeft
PressedButtons = HudScoreLeft+1
FreeSlot       = HudScoreLeft+2
UsedLanes      = HudScoreLeft+3
CandidateLane  = HudScoreLeft+4
ScoreBeforeCombat = HudScoreRight+4 ; combat/scan preserve this until HUD preparation
CoordDX        = HudScoreRight
CoordDY        = HudScoreRight+1
DrawableCount  = Temp
BombTargetCount = HudScoreRight+2
MoveStep       = HudScoreRight+3
CombatType     = HudScoreRight+3
SpawnType = CombatType
FirstDrawX = HudScoreRight
SecondSlot = HudScoreRight+1
GuardStart      ds 8      ; $E8..$EF = $A5 sentinels for stack-overflow checks
StackBottom     ds 16     ; $F0..$FF, mirrored into the CPU's hardware stack page
RamEnd = *
    IF RamEnd != $100
        ERR
    ENDIF
