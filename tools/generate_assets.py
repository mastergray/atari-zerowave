#!/usr/bin/env python3
"""Generate compact, page-safe TIA graphics from one geometry definition."""
from pathlib import Path
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/generated"
FONT = {
    "T": (7, 2, 2, 2, 2), "E": (7, 4, 6, 4, 7),
    "S": (7, 4, 7, 1, 7), "B": (6, 5, 6, 5, 6),
    "O": (7, 5, 5, 5, 7), "M": (5, 7, 7, 5, 5),
    "F": (7, 4, 6, 4, 4), "I": (7, 2, 2, 2, 7),
    "R": (6, 5, 6, 5, 5), "P": (6, 5, 6, 4, 4),
    "L": (4, 4, 4, 4, 7), "A": (2, 5, 7, 5, 5),
    "Y": (5, 5, 2, 2, 2), "V": (5, 5, 5, 5, 2),
}
DIGITS = [(7, 5, 5, 5, 7), (2, 6, 2, 2, 7), (7, 1, 7, 4, 7),
          (7, 1, 7, 1, 7), (5, 5, 7, 1, 1), (7, 4, 7, 1, 7),
          (7, 4, 7, 5, 7), (7, 1, 1, 1, 1), (7, 5, 7, 5, 7),
          (7, 5, 7, 1, 7)]
BURSTS = [
    ("Flash", [0x00, 0x18, 0x3c, 0x7e, 0x7e, 0x3c, 0x18, 0x00]),
    ("Sparks", [0x24, 0x81, 0x5a, 0x3c, 0x3c, 0x5a, 0x81, 0x24]),
    ("Embers", [0x81, 0x00, 0x24, 0x00, 0x00, 0x24, 0x00, 0x81]),
]
SPRITES = [
    ("SpriteTriangle", [0, 0, 0x18, 0x3c, 0x7e, 0xff, 0, 0]),
    ("SpriteFast", [0, 0, 0, 0x18, 0x3c, 0x7e, 0, 0]),
    ("SpriteSquare", [0, 0, 0x7e, 0x42, 0x42, 0x7e, 0, 0]),
    ("SpriteSquareReady", [0, 0, 0x7e, 0x7e, 0x7e, 0x7e, 0, 0]),
    ("SpriteArmor", [0, 0xff, 0x81, 0xa5, 0xa5, 0x81, 0xff, 0]),
    ("SpriteArmorReady", [0, 0xff, 0xff, 0xdb, 0xdb, 0xff, 0xff, 0]),
    ("SpriteDiamond", [0x18, 0x3c, 0x7e, 0xff, 0xff, 0x7e, 0x3c, 0x18]),
] + [("Burst" + name, shape) for name, shape in BURSTS]


def load_config():
    return json.loads((ROOT / "config/tuning.json").read_text())


def load_sounds():
    # Ordered from lowest to highest priority; each segment is
    # [updates, AUDC waveform, AUDF divider, AUDV volume].
    return json.loads((ROOT / "config/audio.json").read_text())["sounds"]


def load_levels():
    return json.loads((ROOT / "config/levels.json").read_text())


def center(lane, radius, tuning):
    angle = lane * math.pi / 4
    return (
        tuning["center_x"] + round(math.sin(angle) * radius * tuning["extent_x"] / tuning["spawn_radius"]),
        tuning["center_y"] - round(math.cos(angle) * radius * tuning["extent_y"] / tuning["spawn_radius"]),
    )


def encode_row(cells):
    """TIA normal-repeat bit ordering, with independent left/right writes."""
    result = [0] * 6
    for column in cells:
        half, cell = divmod(column, 20)
        if cell < 4:
            register, bit = 0, cell + 4
        elif cell < 12:
            register, bit = 1, 11 - cell
        else:
            register, bit = 2, cell - 12
        result[half * 3 + register] |= 1 << bit
    return result


def beam_rows(lane, tuning):
    rows = [set() for _ in range(tuning["arena_rows"])]
    if lane in (2, 6):
        # Sample quarter radial units to connect all rounded integer positions.
        for quarter in range(tuning["contact_radius"] * 4, tuning["spawn_radius"] * 4 + 1):
            x, y = center(lane, quarter / 4, tuning)
            rows[y].add(x // 4)
    return [encode_row(row) for row in rows]


def ball_beam(lane, tuning):
    """One color-clock ray, moving at most one clock per physical scanline.

    Both motion nibbles for a two-line row share a byte. The high nibble
    positions its second line; the low nibble positions the following row.
    North/south share a stationary stream; opposite diagonals share slopes.
    """
    count = tuning["arena_rows"]
    if lane not in (0, 1, 3, 4, 5, 7):
        return dict(enabled=0, initial_x=80, min_y=80, max_y=80,
                    motion=[0] * count, pixels=[None] * (count * 2))
    slope = {0: 0, 1: -1, 3: 1, 4: 0, 5: -1, 7: 1}[lane]
    slope *= tuning["extent_x"] / tuning["extent_y"]
    positions = [round(tuning["center_x"] + slope * (line / 2 - tuning["center_y"]))
                 for line in range(count * 2 + 1)]
    first, last = sorted(center(lane, r, tuning)[1]
                         for r in (tuning["contact_radius"], tuning["spawn_radius"]))
    steps = [a - b for a, b in zip(positions, positions[1:])]
    assert all(abs(step) <= 1 for step in steps)
    assert all(0 <= x < 160 for x in positions)
    return dict(enabled=1, initial_x=positions[0], min_y=count - 1 - last,
                max_y=count - first,
                motion=[((steps[i] & 15) << 4) | (steps[i + 1] & 15)
                        for i in range(0, count * 2, 2)],
                pixels=[x if first <= line // 2 <= last else None
                        for line, x in enumerate(positions[:-1])])


def bomb_radii(tuning):
    return [round(tuning["bomb_radius"] * (stage + 1) / tuning["bomb_stages"])
            for stage in range(tuning["bomb_stages"])]


def ring_rows(radius, tuning):
    """An outline in the same radial coordinates as enemies and the beam.

    Sampling half-degree steps joins the coarse playfield cells around the rim;
    there is no filled disk or persistent trail from previous ring sizes.
    """
    rows = [set() for _ in range(tuning["arena_rows"])]
    for step in range(720):
        x, y = center(step / 90, radius, tuning)
        rows[y].add(x // 4)
    return [encode_row(row) for row in rows]


def byte_lines(label, data, alignment=None):
    result = [f"    align {alignment}" ] if alignment else []
    if label:
        result.append(label + ":")
    for start in range(0, len(data), 16):
        result.append("    .byte " + ",".join(f"${value:02x}" for value in data[start:start + 16]))
    return "\n".join(result) + "\n"


def hud_rows():
    rows = []
    for y in range(24):
        cells = set()
        if 6 <= y < 16:
            font_y = (y - 6) // 2
            for text, offset in (("TEST", 2), ("BOMB", 22)):
                for index, char in enumerate(text):
                    bits = FONT[char][font_y]
                    for x in range(3):
                        if bits & (4 >> x):
                            cells.add(offset + index * 4 + x)
        rows.append(encode_row(cells))
    return rows


def generate():
    tuning = load_config()
    fixtures = json.loads((ROOT / "config/fixtures.json").read_text())
    assert tuning["arena_rows"] == 80, "The timed kernel requires 80 logical rows"
    assert (tuning["center_x"], tuning["center_y"]) == (80, 40), "The turret kernel uses a fixed center"
    assert 0 < tuning["bomb_radius"] <= tuning["spawn_radius"]
    animation_frames = tuning["bomb_stages"] * tuning["bomb_stage_frames"]
    assert 0 < tuning["bomb_stages"] <= 8
    assert tuning["bomb_stage_frames"] >= 2 and tuning["bomb_stage_frames"] % 2 == 0
    assert 0 < tuning["bomb_sound_frames"] <= min(15, animation_frames)
    assert animation_frames < tuning["bomb_cooldown"] <= 255
    assert len(tuning["beam_colors"]) == 8
    assert all(0 <= c <= 255 and c & 15 == 14 for c in tuning["beam_colors"])
    assert 1 <= tuning["beam_fade_start"] <= 15
    assert 1 <= tuning["start_hp"] <= 5
    assert 0 < tuning["square_spawn_gap"] <= 255
    assert tuning["enemy_burst_stage_frames"] >= 2 and tuning["enemy_burst_stage_frames"] % 2 == 0
    assert len(tuning["enemy_burst_colors"]) == len(BURSTS)
    assert all(0 <= color <= 255 for color in tuning["enemy_burst_colors"])
    burst_frames = len(BURSTS) * tuning["enemy_burst_stage_frames"]
    assert burst_frames < 128, "Burst and live feedback share a seven-bit lifetime"
    kinds = {kind["id"]: kind for kind in tuning["enemy_types"]}
    assert set(kinds) == {0, 1, 2, 4, 5}
    assert 0 < tuning["hit_flash_frames"] < 128 and 0 < tuning["immune_flash_frames"] < 128
    assert tuning["immune_flash_frames"] % 6 == 0, "Three even stages preserve both draw phases"
    assert tuning["player_hit_stage_frames"] > 0 and tuning["player_hit_colors"]
    assert all(0 <= color <= 255 for color in tuning["player_hit_colors"])
    player_hit_frames = tuning["player_hit_stage_frames"] * len(tuning["player_hit_colors"])
    assert player_hit_frames < 256
    assert 0 < tuning["beam_sound_frames"] <= 15
    assert tuning["contact_radius"] < tuning["diamond_near_radius"] < tuning["diamond_mid_radius"] < tuning["spawn_radius"]
    assert kinds[2]["speed"] < tuning["diamond_mid_speed"] < tuning["diamond_near_speed"] < kinds[1]["speed"] <= 255
    assert kinds[0]["health"] == kinds[1]["health"] == kinds[4]["health"] == 1
    assert kinds[5]["health"] == 2 and 1 < kinds[2]["health"] <= 15
    assert all(kind["speed"] < kinds[1]["speed"] for kind in kinds.values() if kind["id"] != 1)
    for kind in kinds.values():
        assert 0 < kind["speed"] <= 255 and 0 < kind["score"] <= 99
        assert kind["weapons"] == (2 if kind["id"] & 4 else 3 if kind["id"] == 2 else 1)
        assert kind["damage"] == (2 if kind["id"] == 1 else 1)
        assert 0 <= kind["color"] <= 255 and 0 <= kind["sprite"] < 7
    radii = bomb_radii(tuning)
    assert radii == sorted(set(radii)) and radii[0] > 0
    OUT.mkdir(parents=True, exist_ok=True)
    constants = ["; Generated; edit config/tuning.json instead."]
    for name in ("bomb_cooldown", "bomb_sound_frames", "bomb_radius", "arena_rows", "beam_fade_start",
                 "spawn_radius", "contact_radius", "start_hp",
                 "square_spawn_gap", "enemy_burst_stage_frames",
                 "beam_sound_frames", "hit_flash_frames", "immune_flash_frames",
                 "diamond_mid_radius", "diamond_near_radius", "diamond_mid_speed", "diamond_near_speed"):
        constants.append(f"{name.upper()} = {tuning[name]}")
    constants.append(f"BOMB_ANIMATION_FRAMES = {animation_frames}")
    constants.append(f"ENEMY_BURST_FRAMES = {burst_frames}")
    constants.append(f"PLAYER_HIT_FRAMES = {player_hit_frames}")
    for name, value in tuning["colors"].items():
        constants.append(f"COLOR_{name.upper()} = ${value:02x}")
    constants.append(f"FIXTURE_COUNT = {len(fixtures)}")
    level_config = load_levels()
    levels = level_config["levels"]
    assert 1 <= len(levels) <= 9  # BCD levels 01..09 index these rows directly
    assert 1 <= level_config["break_frames"] <= 255
    for level in levels:
        assert 1 <= level["cap"] <= 4 and 1 <= level["quota"] <= 255
        assert 1 <= level["spawn_interval"] <= 255
        assert len(level["types"]) == 8 and set(level["types"]) <= set(kinds)
    constants.append(f"LEVEL_COUNT = {len(levels)}")
    constants.append(f"LEVEL_BREAK_FRAMES = {level_config['break_frames']}")
    level_tables = [byte_lines(label, [level[key] for level in levels])
                    for label, key in (("LevelCap", "cap"), ("LevelQuota", "quota"), ("LevelInterval", "spawn_interval"))]
    level_tables.append(byte_lines("LevelTypes", [kind for level in levels for kind in level["types"]]))
    (OUT / "levels.inc").write_text("".join(level_tables))
    sounds = load_sounds()
    assert [s["name"] for s in sounds] == ["bomb", "immune", "hit", "kill", "player_hit", "death"]
    samples = [(0, 0, 0)]  # zero index is silence
    offsets, lengths = [0], [0]
    for sound_id, sound in enumerate(sounds, 1):
        sequence = []
        for frames, control, frequency, volume in sound["segments"]:
            assert all(isinstance(v, int) for v in (frames, control, frequency, volume))
            assert frames > 0 and 0 <= control <= 15 and 0 <= frequency <= 31 and 1 <= volume <= 15
            sequence.extend([(control, frequency, volume)] * frames)
        assert 0 < len(sequence) <= 255
        offsets.append(len(samples) - 1)
        lengths.append(len(sequence))
        samples.extend(reversed(sequence))  # timer counts down
        constants.append(f"SFX_{sound['name'].upper()} = {sound_id}")
    assert len(samples) <= 256, "Audio tables use one-byte indices"
    assert lengths[1] == tuning["bomb_sound_frames"]
    audio = ["; Generated from config/audio.json; one sample per game update.\n",
             byte_lines("SoundOffset", offsets), byte_lines("SoundLength", lengths)]
    for index, name in enumerate(("Control", "Frequency", "Volume")):
        audio.append(byte_lines("Sound" + name, [sample[index] for sample in samples]))
    (OUT / "audio.inc").write_text("".join(audio))
    (OUT / "tuning.inc").write_text("\n".join(constants) + "\n")
    type_tables = []
    for label, key in (("TypeHealth", "health"), ("TypeSpeed", "speed"), ("TypeDamage", "damage"),
                       ("TypeWeapons", "weapons"), ("TypeScore", "score"), ("TypeColor", "color"),
                       ("TypeSprite", "sprite")):
        values = [kinds.get(i, kinds[0])[key] for i in range(8)]
        if key == "score":
            values = [int(str(v), 16) for v in values]
        type_tables.append(byte_lines(label, values))
    (OUT / "enemy_types.inc").write_text("".join(type_tables))

    patterns = [beam_rows(lane, tuning) for lane in range(9)]
    beam_streams = len({tuple(row[plane] for row in rows) for rows in patterns for plane in (1, 2, 3, 4)})
    patterns.extend(ring_rows(radius, tuning) for radius in radii)
    ball_patterns = [ball_beam(lane, tuning) for lane in range(len(patterns))]
    streams = {}
    references = []
    # Rays are confined to columns 9..31: left PF0 and right PF2 stay zero.
    for rows in patterns:
        assert all(row[0] == row[5] == 0 for row in rows)
        labels = []
        for plane in (1, 2, 3, 4):
            values = tuple(row[plane] for row in rows)
            if values not in streams:
                streams[values] = f"PlayfieldStream{len(streams)}"
            labels.append(streams[values])
        references.append(labels)
    playfield_streams = len(streams)
    motion_labels = []
    for ball in ball_patterns:
        values = tuple(ball["motion"])
        if values not in streams:
            streams[values] = f"BeamMotionStream{len(streams)}"
        motion_labels.append(streams[values])
    render = ["; Bank 0 display setup tables; pointers refer to bank 1 data.\n"]
    immune_stages = [0] + [(tuning["immune_flash_frames"] - timer) // (tuning["immune_flash_frames"] // 3)
                           for timer in range(1, tuning["immune_flash_frames"] + 1)]
    render.append(byte_lines("ImmuneColorByTimer", [
        (tuning["colors"]["immune"], tuning["colors"]["immune_accent"], tuning["colors"]["immune"])[stage]
        for stage in immune_stages]))
    render.append(byte_lines("ImmuneOffsetByTimer", [(254, 2, 0)[stage] for stage in immune_stages]))
    render.append(byte_lines("PlayerHitColorByTimer", [tuning["colors"]["background"]] + [
        tuning["player_hit_colors"][(player_hit_frames - timer) // tuning["player_hit_stage_frames"]]
        for timer in range(1, player_hit_frames + 1)]))
    stages = [0] + [(burst_frames - timer) // tuning["enemy_burst_stage_frames"]
                    for timer in range(1, burst_frames + 1)]
    render.append(byte_lines("BurstSpriteByTimer", [7 + stage for stage in stages]))
    render.append(byte_lines("BurstColorByTimer", [tuning["enemy_burst_colors"][stage] for stage in stages]))
    # Timer counts down. Zero is neutral; 16..13 select the smallest ring, etc.
    render.append(byte_lines("BombPatternByTimer", [8] + [
        9 + (animation_frames - timer) // tuning["bomb_stage_frames"]
        for timer in range(1, animation_frames + 1)]))
    for plane, name in enumerate(("Left1", "Left2", "Right0", "Right1")):
        for operator, suffix in (("<", "Lo"), (">", "Hi")):
            render.append(f"Pattern{name}{suffix}:\n    .byte " + ",".join(operator + labels[plane] for labels in references) + "\n")
    for name, key in (("BallKernelByPattern", "enabled"), ("BallInitialX", "initial_x"),
                      ("BallMinY", "min_y"), ("BallMaxY", "max_y")):
        render.append(byte_lines(name, [ball[key] for ball in ball_patterns]))
    for operator, suffix in (("<", "Lo"), (">", "Hi")):
        render.append(f"BallMotion{suffix}:\n    .byte " + ",".join(operator + label for label in motion_labels) + "\n")
        render.append(f"Graphic{suffix}:\n    .byte " + ",".join(operator + name for name, _ in SPRITES) + "\n")
    setup = render
    render = ["; Bank 1 page-safe graphics. Each sprite window has eight rows.\n"]
    # Three 80-byte streams fit in a 256-byte page, preserving five-cycle
    # indirect loads while reclaiming the old 128-byte alignment gaps.
    for index, (values, label) in enumerate(streams.items()):
        render.append(byte_lines(label, values[::-1], 256 if index % 3 == 0 else None))
    turret = [0] * tuning["arena_rows"]
    turret[38:42] = [0x18, 0x3c, 0x7e, 0x3c]
    render.append(byte_lines("TurretRows", turret[::-1], 128))
    for index, (name, shape) in enumerate(SPRITES):
        assert len(shape) == 8
        # Two padded shapes per page, at 80..87 and 168..175. Pointer low is
        # label offset + EnemyY + 6; an 80-row read stays on-page for Y=0..76.
        render.append(byte_lines(name, [0] * 80 + shape[::-1], 256 if index % 2 == 0 else None))
        if index % 2:
            render.append(byte_lines("", [0] * 80))
    hud = hud_rows()
    render.append("    IF DISPLAY_TEST\n")
    for plane in range(6):
        render.append(byte_lines(f"HudPlane{plane}", [row[plane] for row in hud], 32))
    render.append("    ELSE\n")
    setup.append("    IF DISPLAY_TEST = 0\n")
    setup.append(byte_lines("DigitOffsets", [digit * 5 for digit in range(10)]))
    setup.append(byte_lines("DigitLeft", [bits << 5 for glyph in DIGITS for bits in glyph]))
    setup.append(byte_lines("DigitRight", [int(f"{bits:03b}"[::-1], 2) for glyph in DIGITS for bits in glyph]))
    health = [encode_row({24 + i * 3 for i in range(count)}) for count in range(6)]
    for plane in (1, 2):
        setup.append(byte_lines(f"HealthMask{plane}", [row[plane + 3] for row in health]))
    for plane in (1, 2):
        for operator, suffix in (("<", "Lo"), (">", "Hi")):
            setup.append(f"HudStatus{plane}{suffix}:\n    .byte " +
                          ",".join(f"{operator}HudText{mode}Left{plane}" for mode in range(3)) + "\n")
    setup.append("    ENDIF\n")
    (OUT / "render_tables.inc").write_text("".join(setup))
    for mode, word in enumerate(("FIRE", "PLAY", "OVER", "BOMB")):
        rows = [encode_row({4 + i * 4 + bit for i, char in enumerate(word)
                            for bit in range(3) if FONT[char][y] & (4 >> bit)}) for y in range(5)]
        for plane in (1, 2):
            label = f"HudText{mode}Left{plane}" if mode < 3 else f"BombHud{plane}"
            render.append(byte_lines(label, [row[plane] for row in rows], 8))
    level_label = [encode_row({4 + i * 4 + bit for i, char in enumerate("LV")
                              for bit in range(3) if FONT[char][y] & (4 >> bit)})[1] for y in range(5)]
    render.append(byte_lines("LevelLabel", level_label, 8))
    for name, shift in (("LevelDigitTens", 0), ("LevelDigitOnes", 4)):
        render.append(byte_lines(name, [int(f"{bits:03b}"[::-1], 2) << shift
                                       for glyph in DIGITS for bits in glyph], 64))
    render.append("    ENDIF\n")
    (OUT / "graphics.inc").write_text("".join(render))

    fixture_data = {f"Fixture{field}{slot}": [] for slot in range(2) for field in ("Flags", "Radius", "X", "Y")}
    for fixture in fixtures:
        assert 1 <= len(fixture["enemies"]) <= 2
        for slot in range(2):
            enemy = fixture["enemies"][slot] if slot < len(fixture["enemies"]) else None
            if enemy:
                assert 0 <= enemy["lane"] < 8 and 8 < enemy["radius"] <= 63
                x, y = center(enemy["lane"], enemy["radius"], tuning)
                values = (0x80 | (0x40 if enemy["kind"] == "square" else 0) | enemy["lane"], enemy["radius"], x - 4, y - 2)
            else:
                values = (0, 0, 76, 38)
            for field, value in zip(("Flags", "Radius", "X", "Y"), values):
                fixture_data[f"Fixture{field}{slot}"].append(value)
    # Beam palette belongs to bank 0: game logic selects a shot hue (legacy release hue in diagnostics).
    (OUT / "fixtures.inc").write_text(byte_lines("BeamColors", tuning["beam_colors"]) +
                                      "".join(byte_lines(name, values) for name, values in fixture_data.items()))
    movement = []
    for name, lane, axis, origin in (("RadiusXCardinal", 2, 0, tuning["center_x"]),
                                    ("RadiusYCardinal", 4, 1, tuning["center_y"]),
                                    ("RadiusXDiagonal", 3, 0, tuning["center_x"]),
                                    ("RadiusYDiagonal", 3, 1, tuning["center_y"])):
        movement.append(byte_lines(name, [center(lane, radius, tuning)[axis] - origin
                                         for radius in range(tuning["spawn_radius"] + 1)]))
    (OUT / "movement.inc").write_text("".join(movement))
    manifest = {"unique_beam_streams": beam_streams, "unique_playfield_streams": playfield_streams,
                "unique_raster_streams": len(streams), "ball_patterns": ball_patterns,
                "bomb_radii": radii, "bomb_animation_frames": animation_frames,
                "patterns": patterns, "fixtures": fixtures, "tuning": tuning, "levels": level_config}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    stamp = hashlib.sha256(json.dumps([tuning, fixtures, sounds, level_config], sort_keys=True).encode()).hexdigest()
    (OUT / "assets.stamp").write_text(stamp + "\n")
    print(f"Generated {len(streams)} shared raster streams, {len(radii)} rings, and {len(fixtures)} display fixtures.")


if __name__ == "__main__":
    generate()
