import json

with open("scenario_007_contract.json", "r", encoding="utf-8") as f:
    contract = json.load(f)

# Player timing
contract["player"]["gfx"] = 61
contract["player"]["gfx_mode"] = 4
contract["player"]["move_speed_ms"] = 640
contract["player"]["attack_speed_ms"] = 880

# Monster timing map from Legacy SQL archaeology
monster_timings = {
    "1": {"gfx": 29, "move_speed_ms": 960, "attack_speed_ms": 1720},
    "2": {"gfx": 30, "move_speed_ms": 640, "attack_speed_ms": 920},
    "3": {"gfx": 31, "move_speed_ms": 800, "attack_speed_ms": 1200},
    "4": {"gfx": 1110, "move_speed_ms": 640, "attack_speed_ms": 840},
    "5": {"gfx": 32, "move_speed_ms": 960, "attack_speed_ms": 1800},
    "6": {"gfx": 49, "move_speed_ms": 1280, "attack_speed_ms": 1920},
    "7": {"gfx": 52, "move_speed_ms": 1640, "attack_speed_ms": 1040},
    "8": {"gfx": 54, "move_speed_ms": 560, "attack_speed_ms": 1480},
    "9": {"gfx": 56, "move_speed_ms": 800, "attack_speed_ms": 1320},
    "12": {"gfx": 94, "move_speed_ms": 800, "attack_speed_ms": 1200},
    "13": {"gfx": 57, "move_speed_ms": 800, "attack_speed_ms": 1200},
    "18": {"gfx": 144, "move_speed_ms": 1280, "attack_speed_ms": 720},
    "55": {"gfx": 1022, "move_speed_ms": 760, "attack_speed_ms": 920},
}

for mid, t in monster_timings.items():
    if mid in contract["canonical_monsters"]:
        contract["canonical_monsters"][mid].update(t)
        contract["canonical_monsters"][mid]["timing_source"] = "LEGACY_ARCHAEOLOGY_SPRITE_FRAME_SQL"

with open("scenario_007_contract.json", "w", encoding="utf-8") as f:
    json.dump(contract, f, indent=2, ensure_ascii=False)

print("scenario_007_contract.json successfully updated with timing specifications.")
