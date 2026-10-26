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
    if lane != 8:
        # Sample quarter radial units to connect all rounded integer positions.
        for quarter in range(tuning["contact_radius"] * 4, tuning["spawn_radius"] * 4 + 1):
            x, y = center(lane, quarter / 4, tuning)
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
    OUT.mkdir(parents=True, exist_ok=True)
    constants = ["; Generated; edit config/tuning.json instead."]
    for name in ("bomb_cooldown", "bomb_flash", "bomb_radius", "arena_rows"):
        constants.append(f"{name.upper()} = {tuning[name]}")
    for name, value in tuning["colors"].items():
        constants.append(f"COLOR_{name.upper()} = ${value:02x}")
    constants.append(f"FIXTURE_COUNT = {len(fixtures)}")
    (OUT / "tuning.inc").write_text("\n".join(constants) + "\n")

    patterns = [beam_rows(lane, tuning) for lane in range(9)]
    streams = {}
    references = []
    # Rays are confined to columns 9..31: left PF0 and right PF2 stay zero.
    for rows in patterns:
        assert all(row[0] == row[5] == 0 for row in rows)
        labels = []
        for plane in (1, 2, 3, 4):
            values = tuple(row[plane] for row in rows)
            if values not in streams:
                streams[values] = f"BeamStream{len(streams)}"
            labels.append(streams[values])
        references.append(labels)
    render = ["; Generated display data. All indexed loads are page-safe.\n"]
    for plane, name in enumerate(("Left1", "Left2", "Right0", "Right1")):
        for operator, suffix in (("<", "Lo"), (">", "Hi")):
            render.append(f"Beam{name}{suffix}:\n    .byte " + ",".join(operator + labels[plane] for labels in references) + "\n")
    for values, label in streams.items():
        render.append(byte_lines(label, values, 128))
    turret = [0] * tuning["arena_rows"]
    turret[38:42] = [0x18, 0x3c, 0x7e, 0x3c]
    render.append(byte_lines("TurretRows", turret, 128))
    for name, shape in (
        ("Triangle", [0x18, 0x3c, 0x7e, 0xff]),
        ("Square", [0x7e, 0x42, 0x42, 0x7e]),
        ("SquareReady", [0x7e] * 4),
    ):
        render.append(byte_lines("Sprite" + name, [0] * 80 + shape + [0] * 80, 256))
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
    (OUT / "fixtures.inc").write_text("".join(byte_lines(name, values) for name, values in fixture_data.items()))
    manifest = {"unique_beam_streams": len(streams), "patterns": patterns, "fixtures": fixtures, "tuning": tuning}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    stamp = hashlib.sha256((json.dumps(tuning, sort_keys=True) + json.dumps(fixtures, sort_keys=True)).encode()).hexdigest()
    (OUT / "assets.stamp").write_text(stamp + "\n")
    print(f"Generated {len(streams)} shared beam streams and {len(fixtures)} display fixtures.")


if __name__ == "__main__":
    generate()
