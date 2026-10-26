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
}


def load_config():
    return json.loads((ROOT / "config/tuning.json").read_text())


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
    radii = bomb_radii(tuning)
    assert radii == sorted(set(radii)) and radii[0] > 0
    OUT.mkdir(parents=True, exist_ok=True)
    constants = ["; Generated; edit config/tuning.json instead."]
    for name in ("bomb_cooldown", "bomb_sound_frames", "bomb_radius", "arena_rows", "beam_fade_start"):
        constants.append(f"{name.upper()} = {tuning[name]}")
    constants.append(f"BOMB_ANIMATION_FRAMES = {animation_frames}")
    for name, value in tuning["colors"].items():
        constants.append(f"COLOR_{name.upper()} = ${value:02x}")
    constants.append(f"FIXTURE_COUNT = {len(fixtures)}")
    (OUT / "tuning.inc").write_text("\n".join(constants) + "\n")

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
    render = ["; Generated display data. All indexed loads are page-safe.\n"]
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
    # Three 80-byte streams fit in a 256-byte page, preserving five-cycle
    # indirect loads while reclaiming the old 128-byte alignment gaps.
    for index, (values, label) in enumerate(streams.items()):
        render.append(byte_lines(label, values[::-1], 256 if index % 3 == 0 else None))
    turret = [0] * tuning["arena_rows"]
    turret[38:42] = [0x18, 0x3c, 0x7e, 0x3c]
    render.append(byte_lines("TurretRows", turret[::-1], 128))
    for name, shape in (
        ("Triangle", [0x18, 0x3c, 0x7e, 0xff]),
        ("Square", [0x7e, 0x42, 0x42, 0x7e]),
        ("SquareReady", [0x7e] * 4),
    ):
        render.append(byte_lines("Sprite" + name, [0] * 80 + shape[::-1] + [0] * 80, 256))
    hud = hud_rows()
    for plane in range(6):
        render.append(byte_lines(f"HudPlane{plane}", [row[plane] for row in hud], 32))
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
    # Beam palette belongs to bank 0: game logic freezes its hue on release.
    (OUT / "fixtures.inc").write_text(byte_lines("BeamColors", tuning["beam_colors"]) +
                                      "".join(byte_lines(name, values) for name, values in fixture_data.items()))
    manifest = {"unique_beam_streams": beam_streams, "unique_playfield_streams": playfield_streams,
                "unique_raster_streams": len(streams), "ball_patterns": ball_patterns,
                "bomb_radii": radii, "bomb_animation_frames": animation_frames,
                "patterns": patterns, "fixtures": fixtures, "tuning": tuning}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    stamp = hashlib.sha256((json.dumps(tuning, sort_keys=True) + json.dumps(fixtures, sort_keys=True)).encode()).hexdigest()
    (OUT / "assets.stamp").write_text(stamp + "\n")
    print(f"Generated {len(streams)} shared raster streams, {len(radii)} rings, and {len(fixtures)} display fixtures.")


if __name__ == "__main__":
    generate()
