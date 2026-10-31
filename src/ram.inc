; SPDX-FileCopyrightText: 2026 mastergray
; SPDX-License-Identifier: GPL-3.0-only

; Fixed RAM reservations from IMPLEMENTATION_SPEC.md. No RAM outside $80..$FF.
    SEG.U RAM
    ORG $80
EnemyFlags      ds 4
EnemyRadiusHi   ds 4
EnemyRadiusLo   ds 4
EnemyX          ds 4
EnemyY          ds 4
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
; Prototype diagnostics occupy future game-state bytes.
LayoutId        ds 1
LevelNumber = LayoutId  ; packed BCD 01..99 in gameplay, SELECT fixture in diagnostics
FrameCounter    ds 1
BombCount       ds 1
GameMode        ds 1
Health          ds 1
ScoreHi         ds 1
ScoreLo         ds 1
SpawnTimer      ds 1
SquareTimer     ds 1
RandomState     ds 1
ActiveCount     ds 1
ActiveCap       ds 1
MovementEnabled ds 1
SpawnInterval   ds 1
BeamPalette     ds 1
BeamArmed       ds 1
Direction       ds 1
LastDirection   ds 1
PreviousButtons ds 1
BeamEnabled     ds 1
BeamEvent = BeamEnabled  ; one-update event in gameplay, held input in diagnostics
BombCooldown    ds 1
BombTimer       ds 1
BombEvent       ds 1
FramePhase      ds 1
HudHealth1      ds 1
HudHealth2      ds 1
AudioReserved   ds 6
ShotSoundTimer = AudioReserved
PlayerHitTimer = AudioReserved+1
EventSoundId = AudioReserved+2
EventSoundTimer = AudioReserved+3
SoundRequest = AudioReserved+4
KillsRemaining = AudioReserved+5
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
GuardStart      ds 8
StackBottom     ds 16
RamEnd = *
    IF RamEnd != $100
        ERR
    ENDIF
