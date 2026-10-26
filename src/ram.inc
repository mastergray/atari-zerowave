; Fixed RAM reservations from IMPLEMENTATION_SPEC.md. No RAM outside $80..$FF.
    SEG.U RAM
    ORG $80
EnemyFlags      ds 4
EnemyRadiusHi   ds 4
EnemyRadiusLo   ds 4
EnemyX          ds 4
EnemyY          ds 4
EnemyPhase      ds 4
EnemyAge        ds 4
EnemyVisual     ds 4
; Prototype diagnostics occupy future game-state bytes.
LayoutId        ds 1
FrameCounter    ds 1
BombCount       ds 1
GameReserved    ds 13
Direction       ds 1
LastDirection   ds 1
PreviousButtons ds 1
BeamEnabled     ds 1
BombCooldown    ds 1
BombTimer       ds 1
BombEvent       ds 1
FramePhase      ds 1
AudioReserved   ds 8
BeamLeft1       ds 2
BeamLeft2       ds 2
BeamRight0      ds 2
BeamRight1      ds 2
EnemySprite     ds 2
SelectedSlot    ds 1
HudColor        ds 1
ArenaColor      ds 1
DisplayPattern  ds 1
RenderReserved  ds 10
CurrentButtons  ds 1
PressedButtons  ds 1
Temp            ds 1
BestAge         ds 1
ScratchReserved ds 12
GuardStart      ds 8
StackBottom     ds 16
RamEnd = *
    IF RamEnd != $100
        ERR
    ENDIF
