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
EnemyVisual     ds 4
; Inactive: destruction lifetime. Active: bit 7 successful hit, low 7 feedback
; lifetime (gray immunity pulse when bit 7 is clear). Zero means normal color.
; Prototype diagnostics occupy future game-state bytes.
LayoutId        ds 1
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
BeamLeft1       ds 2
BeamLeft2       ds 2
BeamRight0      ds 2
BeamRight1      ds 2
EnemySprite     ds 2
SelectedSlot    ds 1
HudColor        ds 1
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
; HUD buffers live only during display. Logic scratch aliases their storage.
HudScoreLeft    ds 5
HudScoreRight   ds 5
HudStatus1      ds 2
HudStatus2      ds 2
BestAge         ds 1
Temp            ds 1
CurrentButtons = HudScoreLeft
PressedButtons = HudScoreLeft+1
FreeSlot       = HudScoreLeft+2
UsedLanes      = HudScoreLeft+3
CandidateLane  = HudScoreLeft+4
CoordDX        = HudScoreRight
CoordDY        = HudScoreRight+1
DrawableCount  = Temp
BombTargetCount = HudScoreRight+2
MoveStep       = HudScoreRight+3
CombatType     = HudScoreRight+3
GuardStart      ds 8
StackBottom     ds 16
RamEnd = *
    IF RamEnd != $100
        ERR
    ENDIF
