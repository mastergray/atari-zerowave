#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 mastergray
# SPDX-License-Identifier: GPL-3.0-only

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
    # The first white destruction flash shares the live hexagon silhouette.
    ("Flash", [0x00, 0x3c, 0x7e, 0xff, 0xff, 0x7e, 0x3c, 0x00]),
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


def load_audio():
    return json.loads((ROOT / "config/audio.json").read_text())


def load_sounds():
    # Ordered from lowest to highest priority; each segment is
    # [updates, AUDC waveform, AUDF divider, AUDV volume].
    return load_audio()["sounds"]


def load_levels():
    return json.loads((ROOT / "config/levels.json").read_text())


def level_quota(number, config=None):
    quota = (load_levels() if config is None else config)["quota"]
    return min(quota["start"] + (number - 1) * quota["step"], quota["cap"])


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


def page_safe_bytes(label, data):
    # Pad only when indexed reads would cross a page, rather than rounding
    # every small font/table to a power-of-two boundary.
    return (f"    IF (<*) > {256 - len(data)}\n    align 256\n    ENDIF\n"
            + byte_lines(label, data))


def packed_tables(tables):
    """Share identical subsequences and overlapping ends of setup tables.

    Entries may be bytes or DASM expressions. Aliases still support the same
    indexed reads, so unpacking adds no instructions to the frame preparation.
    """
    tables = [(name, tuple(values)) for name, values in tables]
    blocks = list(dict.fromkeys(values for _, values in tables))
    def offset(haystack, needle):
        return next((i for i in range(len(haystack) - len(needle) + 1)
                     if haystack[i:i + len(needle)] == needle), None)
    blocks = [block for block in blocks
              if not any(len(other) > len(block) and offset(other, block) is not None
                         for other in blocks)]
    while len(blocks) > 1:
        best = (0, 0, 1)
        for i, left in enumerate(blocks):
            for j, right in enumerate(blocks):
                if i == j:
                    continue
                for size in range(min(len(left), len(right)), best[0], -1):
                    if left[-size:] == right[:size]:
                        best = (size, i, j)
                        break
        size, i, j = best
        joined = blocks[i] + blocks[j][size:]
        blocks = [block for n, block in enumerate(blocks) if n not in (i, j)] + [joined]
    data = blocks[0]
    result = [f"; {sum(len(values) for _, values in tables)} lookup bytes packed into {len(data)}.\n",
              "RenderLookupData:\n"]
    for start in range(0, len(data), 16):
        result.append("    .byte " + ",".join(f"${v:02x}" if isinstance(v, int) else v
                                              for v in data[start:start + 16]) + "\n")
    for name, values in tables:
        index = offset(data, values)
        assert index is not None
        result.append(f"{name} = RenderLookupData+{index}\n")
    return "".join(result)


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


def travel_frames(kind, radius, threshold, tuning):
    """Exact fixed-point time to reach a contact/spacing boundary."""
    definitions = {row["id"]: row for row in tuning["enemy_types"]}
    frames = 0
    while radius > threshold:
        speed = definitions[kind]["speed"]
        if kind == 2:
            if radius // 256 < tuning["diamond_near_radius"]:
                speed = tuning["diamond_near_speed"]
            elif radius // 256 < tuning["diamond_mid_radius"]:
                speed = tuning["diamond_mid_speed"]
        radius -= speed
        frames += 1
    return frames


def pair_limits(tuning):
    """Conservative bounds: one member stays outside radius 24 through the
    other's approach and full death animation. Fractions use worst endpoints.
    """
    kinds = {row["id"] for row in tuning["enemy_types"]}
    full = tuning["spawn_radius"] * 256
    contact = tuning["contact_radius"] * 256
    safe = tuning["pair_safe_radius"] * 256 - 1
    burst = len(BURSTS) * tuning["enemy_burst_stage_frames"]
    early, late = [], []
    for old in range(8):
        for new in range(8):
            if old not in kinds or new not in kinds:
                early.append(0); late.append(255)
                continue
            early_ok = [r for r in range(64) if
                        travel_frames(old, r * 256 + 255, contact, tuning) + burst <
                        travel_frames(new, full, safe, tuning)]
            late_ok = [r for r in range(64) if
                       travel_frames(new, full, contact, tuning) + burst <
                       travel_frames(old, r * 256, safe, tuning)]
            early.append(max(early_ok, default=-1) + 1)
            late.append(min(late_ok, default=255))
    return early, late


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
    assert set(kinds) == set(range(8))
    assert 0 < tuning["hit_flash_frames"] < 128 and 0 < tuning["immune_flash_frames"] < 128
    assert tuning["immune_flash_frames"] % 6 == 0, "Three even stages preserve both draw phases"
    assert tuning["player_hit_stage_frames"] > 0 and tuning["player_hit_colors"]
    assert all(0 <= color <= 255 for color in tuning["player_hit_colors"])
    player_hit_frames = tuning["player_hit_stage_frames"] * len(tuning["player_hit_colors"])
    assert player_hit_frames < 256
    assert len(tuning["level_background_colors"]) == 8
    assert tuning["level_background_colors"][0] == tuning["colors"]["background"]
    assert all(0 <= color <= 255 and (color & 15) in (0, 2)
               for color in tuning["level_background_colors"]), "Keep level backgrounds dark"
    assert 0 < tuning["beam_sound_frames"] <= 15
    assert tuning["contact_radius"] < tuning["diamond_near_radius"] < tuning["diamond_mid_radius"] < tuning["spawn_radius"]
    assert kinds[2]["speed"] < tuning["diamond_mid_speed"] < tuning["diamond_near_speed"] < kinds[1]["speed"] <= 255
    assert kinds[0]["health"] == kinds[1]["health"] == kinds[4]["health"] == 1
    assert kinds[5]["health"] == 2 and 1 < kinds[2]["health"] <= 15
    assert kinds[6]["health"] == kinds[7]["health"] == 1
    assert kinds[3]["health"] == 2 and kinds[3]["speed"] == kinds[0]["speed"]
    assert kinds[3]["sprite"] == kinds[0]["sprite"] == 0
    assert kinds[4]["speed"] < kinds[6]["speed"] < kinds[1]["speed"]
    assert all(kind["speed"] < kinds[1]["speed"] for kind in kinds.values() if kind["id"] != 1)
    for kind in kinds.values():
        assert 0 < kind["speed"] <= 255 and 0 < kind["score"] <= 99
        assert kind["weapons"] == (2 if kind["id"] & 4 else 3 if kind["id"] == 2 else 1)
        assert kind["damage"] == (2 if kind["id"] == 1 else 1)
        assert 0 <= kind["color"] <= 255 and 0 <= kind["sprite"] <= 7
        assert (kind["sprite"] == 7) == (kind["id"] == 7)
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
    late_spawn = level_config["late_spawn"]
    assert len(levels) < late_spawn["start_level"] <= 99
    assert 1 <= late_spawn["interval"] <= levels[-1]["spawn_interval"]
    constants.extend([f"LATE_SPAWN_LEVEL = ${late_spawn['start_level']:02}",
                      f"LATE_SPAWN_INTERVAL = {late_spawn['interval']}"])
    late_mix = level_config["late_mix"]
    assert late_spawn["start_level"] < late_mix["start_level"] <= 99
    assert len(late_mix["types"]) == 8 and set(late_mix["types"]) <= set(kinds)
    assert 3 in late_mix["types"] and all(3 not in row["types"] for row in levels)
    constants.extend([f"LATE_MIX_LEVEL = ${late_mix['start_level']:02}",
                      f"LATE_MIX_OFFSET = {len(levels) * 8}"])
    reinforced = level_config["reinforced_diamond"]
    assert late_mix["start_level"] < reinforced["start_level"] <= 99
    assert kinds[2]["health"] == 3 and reinforced["health"] == 4
    assert all(kind["health"] < reinforced["health"] for kind in kinds.values())
    assert 0 < reinforced["color"] <= 255 and reinforced["color"] != kinds[2]["color"]
    constants.extend([f"REINFORCED_DIAMOND_LEVEL = ${reinforced['start_level']:02}",
                      f"REINFORCED_DIAMOND_HEALTH = {reinforced['health']}",
                      f"COLOR_REINFORCED_DIAMOND = ${reinforced['color']:02x}"])
    quota = level_config["quota"]
    assert quota["step"] == 4  # two shifts in CalculateQuota
    assert quota["step"] <= quota["start"] <= quota["cap"] <= 255
    capped_level = 1 + (quota["cap"] - quota["start"] + quota["step"] - 1) // quota["step"]
    assert capped_level <= 19  # compact BCD conversion only needs the 10..19 correction
    constants.extend([f"LEVEL_QUOTA_OFFSET = {quota['start'] - quota['step']}",
                      f"LEVEL_QUOTA_CAP = {quota['cap']}",
                      f"LEVEL_QUOTA_CAP_LEVEL = ${capped_level:02}"])
    for level in levels:
        assert 1 <= level["cap"] <= 4
        assert 1 <= level["spawn_interval"] <= 255
        assert len(level["types"]) == 8 and set(level["types"]) <= set(kinds)
    constants.append(f"LEVEL_COUNT = {len(levels)}")
    constants.append(f"LEVEL_BREAK_FRAMES = {level_config['break_frames']}")
    level_tables = [byte_lines(label, [level[key] for level in levels])
                    for label, key in (("LevelCap", "cap"), ("LevelInterval", "spawn_interval"))]
    level_tables.append(byte_lines("LevelTypes", [kind for level in levels for kind in level["types"]]
                                  + late_mix["types"]))
    level_tables.append(byte_lines("LevelBackgroundColors", tuning["level_background_colors"]))
    (OUT / "levels.inc").write_text("".join(level_tables))
    audio_config = load_audio()
    sounds = audio_config["sounds"]
    approach = audio_config["fast_approach"]
    assert set(approach) == {"radius", "control", "frequency_start", "volume_start"}
    assert all(isinstance(value, int) for value in approach.values())
    assert tuning["contact_radius"] < approach["radius"] <= tuning["spawn_radius"]
    assert 0 <= approach["control"] <= 15
    depth = approach["radius"] - tuning["contact_radius"]
    assert 0 <= approach["frequency_start"] <= 31 - depth // 2
    assert 1 <= approach["volume_start"] <= 15 - depth // 8
    for name, value in approach.items():
        constants.append(f"FAST_APPROACH_{name.upper()} = {value}")
    assert [s["name"] for s in sounds] == ["bomb", "immune", "hit", "kill", "heal", "clear", "player_hit", "hex_reject", "death"]
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
    assert lengths[5] == lengths[6] == 32, "Bonus flashes share their 32-update sound envelopes"
    unique_samples = list(dict.fromkeys(samples))
    audio = ["; Generated from config/audio.json; shared, packed register samples.\n",
             byte_lines("SoundOffset", offsets), byte_lines("SoundLength", lengths),
             byte_lines("SoundSample", [unique_samples.index(sample) for sample in samples])]
    audio.append(byte_lines("SoundControlVolume", [(volume << 4) | control
                                                  for control, frequency, volume in unique_samples]))
    audio.append(byte_lines("SoundFrequency", [frequency for control, frequency, volume in unique_samples]))
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
    early, late = pair_limits(tuning)
    horizontal = dict(tuning, pair_safe_radius=36)
    horizontal_early, _ = pair_limits(horizontal)
    type_tables.extend(["    IF DISPLAY_TEST = 0\n", byte_lines("HorizontalEarlyLimit", horizontal_early),
                        byte_lines("PairEarlyLimit", early),
                        byte_lines("PairLateLimit", late), "    ENDIF\n"])
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
    # Separate the two fonts with setup data so neither needs a wasted page
    # tail. Indexed font reads must still stay within one page.
    render.extend(["    IF DISPLAY_TEST = 0\n",
                   page_safe_bytes("DigitLeft", [bits << 5 for glyph in DIGITS for bits in glyph]),
                   "    ENDIF\n"])
    immune_stages = [0] + [(tuning["immune_flash_frames"] - timer) // (tuning["immune_flash_frames"] // 3)
                           for timer in range(1, tuning["immune_flash_frames"] + 1)]
    render.append(byte_lines("ImmuneColorByTimer", [
        (tuning["colors"]["immune"], tuning["colors"]["immune_accent"], tuning["colors"]["immune"])[stage]
        for stage in immune_stages]))
    render.append(byte_lines("ImmuneOffsetByTimer", [(254, 2, 0)[stage] for stage in immune_stages]))
    render.append(byte_lines("PlayerHitColorByTimer", [tuning["colors"]["background"]] + [
        tuning["player_hit_colors"][(player_hit_frames - timer) // tuning["player_hit_stage_frames"]]
        for timer in range(1, player_hit_frames + 1)]))
    render.extend(["    IF DISPLAY_TEST = 0\n",
                   page_safe_bytes("DigitRight", [int(f"{bits:03b}"[::-1], 2) for glyph in DIGITS for bits in glyph]),
                   "    ENDIF\n"])
    stages = [0] + [(burst_frames - timer) // tuning["enemy_burst_stage_frames"]
                    for timer in range(1, burst_frames + 1)]
    lookups = [("BurstSpriteByTimer", [7 + stage for stage in stages]),
               ("BurstColorByTimer", [tuning["enemy_burst_colors"][stage] for stage in stages])]
    # Timer counts down. Zero is neutral; 16..13 select the smallest ring, etc.
    lookups.append(("BombPatternByTimer", [8] + [
        9 + (animation_frames - timer) // tuning["bomb_stage_frames"]
        for timer in range(1, animation_frames + 1)]))
    # Streams pack three per page in both ROMs. Canonicalize equivalent low
    # bytes/page symbols before sharing table subsequences; no fixed bank address.
    stream_names = list(streams.values())
    def stream_address(label, operator):
        index = stream_names.index(label)
        return (index % 3) * 80 if operator == "<" else ">" + stream_names[index - index % 3]
    for plane, name in enumerate(("Left1", "Left2", "Right0", "Right1")):
        for operator, suffix in (("<", "Lo"), (">", "Hi")):
            lookups.append((f"Pattern{name}{suffix}", [stream_address(labels[plane], operator)
                                                      for labels in references]))
    for name, key in (("BallKernelByPattern", "enabled"), ("BallInitialX", "initial_x"),
                      ("BallMinY", "min_y"), ("BallMaxY", "max_y")):
        lookups.append((name, [ball[key] for ball in ball_patterns]))
    for operator, suffix in (("<", "Lo"), (">", "Hi")):
        lookups.append((f"BallMotion{suffix}", [stream_address(label, operator) for label in motion_labels]))
        lookups.append((f"Graphic{suffix}", [(i % 2) * 88 if operator == "<" else ">" + SPRITES[i - i % 2][0]
                                            for i in range(len(SPRITES))]))
    health = [encode_row({24 + i * 3 for i in range(count)}) for count in range(6)]
    for plane in (1, 2):
        lookups.append((f"HealthMask{plane}", [row[plane + 3] for row in health]))
    progress = [encode_row(set(range(4, 4 + step * 4))) for step in range(9)]
    for label, plane in (("ProgressLeft1", 1), ("ProgressLeft2", 2), ("ProgressRight0", 3)):
        lookups.append((label, [row[plane] for row in progress]))
    render.append(packed_tables(lookups))
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
    graphics = render
    render = []
    hud = hud_rows()
    render.append("    IF DISPLAY_TEST\n")
    for plane in range(6):
        render.append(byte_lines(f"HudPlane{plane}", [row[plane] for row in hud], 32))
    render.append("    ELSE\n")
    setup.append("    IF DISPLAY_TEST = 0\n")
    for plane in (1, 2):
        setup.append(f"HudStatus{plane}Lo:\n    .byte " +
                     ",".join(f"<HudText{mode}Left{plane}" for mode in range(3)) + "\n")
    setup.append("    ENDIF\n")
    (OUT / "render_tables.inc").write_text("".join(setup))
    for mode, word in enumerate(("FIRE", "PLAY", "OVER")):
        rows = [encode_row({4 + i * 4 + bit for i, char in enumerate(word)
                            for bit in range(3) if FONT[char][y] & (4 >> bit)}) for y in range(5)]
        for plane in (1, 2):
            label = f"HudText{mode}Left{plane}"
            if mode == 1:
                render.append(f"{label} = HudText0Left{plane}\n")
            else:
                render.append(page_safe_bytes(label, [row[plane] for row in rows]))
    for label in ("HudText0Left2", "HudText2Left1", "HudText2Left2"):
        render.append(f"    IF (>{label}) != (>HudText0Left1)\n        ERR\n    ENDIF\n")
    level_label = [encode_row({4 + i * 4 + bit for i, char in enumerate("LV")
                              for bit in range(3) if FONT[char][y] & (4 >> bit)})[1] for y in range(5)]
    render.append(page_safe_bytes("LevelLabel", level_label))
    render.append("LevelDigitTens = DigitRight\n")
    # LevelDigitOnes lives at $FFAA in each common bank tail, safely on one
    # page and below the $FFF8 hotspots. No labels: this include is used twice.
    shared = [int(f"{bits:03b}"[::-1], 2) << 4 for glyph in DIGITS for bits in glyph]
    for label, plane in (("ProgressLeft1", 1), ("ProgressLeft2", 2), ("ProgressRight0", 3),
                         ("ProgressRight1", 4), ("ProgressRight2", 5)):
        if plane >= 4:
            shared.extend(row[plane] for row in progress)
    shared.extend(digit * 5 for digit in range(10))
    assert len(shared) == 78  # $FFAA..$FFF7, below the cartridge hotspots
    (OUT / "shared_hud.inc").write_text(byte_lines("", shared))
    render.append("    ENDIF\n")
    (OUT / "hud_graphics.inc").write_text("".join(render))
    (OUT / "graphics.inc").write_text("".join(graphics))
    deltas = [i if i < 128 else i - 256 for i in range(256)]
    steps = [max(-7, min(7, value)) for value in deltas]
    (OUT / "reuse_motion.inc").write_text(
        byte_lines("ReuseMotion", [(-step & 15) << 4 for step in steps], 256) +
        byte_lines("ReuseRemainder", [(value - step) & 255 for value, step in zip(deltas, steps)]))

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
                                      "    IF DISPLAY_TEST\n" + "".join(byte_lines(name, values) for name, values in fixture_data.items()) + "    ENDIF\n")
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
    stamp = hashlib.sha256(json.dumps([tuning, fixtures, audio_config, level_config], sort_keys=True).encode()).hexdigest()
    (OUT / "assets.stamp").write_text(stamp + "\n")
    print(f"Generated {len(streams)} shared raster streams, {len(radii)} rings, and {len(fixtures)} display fixtures.")


if __name__ == "__main__":
    generate()
