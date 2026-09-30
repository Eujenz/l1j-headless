"""
build_scenario_003_contract.py - Generate Scenario 003 Machine-Readable Contract.
"""
import json

def build_contract():
    # Map 0 local synthetic grid (5x5 around 32474, 32848)
    # Portal at (32477, 32851)
    map0_tiles = []
    for dy in range(5):
        for dx in range(5):
            x = 32474 + dx
            y = 32848 + dy
            # Standard passable tile (east=1, north=2 -> 3)
            # Portal tile at (32477, 32851) has value 100
            val = 100 if (x == 32477 and y == 32851) else 3
            map0_tiles.append({"x": x, "y": y, "val": val})

    # Map 1 local synthetic grid (5x5 around 32667, 32800)
    # Landing at (32669, 32802), Final Dest at (32671, 32804)
    map1_tiles = []
    for dy in range(5):
        for dx in range(5):
            x = 32667 + dx
            y = 32800 + dy
            map1_tiles.append({"x": x, "y": y, "val": 3})

    contract = {
        "contract_schema": "1.0",
        "scenario_id": "003",
        "fixture_version": 1,
        "source": "INSTRUMENTED_LEGACY_REFERENCE + MODERN_DESIGN",
        "scope": "scenario_003_deterministic_portal",
        "maps": [
            {
                "map_id": 0,
                "name": "Talking_Island_Surface_Synthetic",
                "loc_x1": 32474,
                "loc_y1": 32848,
                "width": 5,
                "height": 5,
                "tiles": map0_tiles
            },
            {
                "map_id": 1,
                "name": "Talking_Island_Dungeon_1F_Synthetic",
                "loc_x1": 32667,
                "loc_y1": 32800,
                "width": 5,
                "height": 5,
                "tiles": map1_tiles
            }
        ],
        "transitions": [
            {
                "transition_id": "portal_ti_to_tid1",
                "type": "PORTAL",
                "source_map": 0,
                "source_x": 32477,
                "source_y": 32851,
                "target_map": 1,
                "target_x": 32669,
                "target_y": 32802,
                "target_heading": 4,
                "requirements": {"item_id": 0}
            }
        ],
        "actor": {
            "id": 10001,
            "name": "CrossMapTraveler",
            "initial_map": 0,
            "initial_x": 32474,
            "initial_y": 32849,
            "initial_heading": 2
        },
        "mission": {
            "start": {"map": 0, "x": 32474, "y": 32849},
            "portal": {"map": 0, "x": 32477, "y": 32851},
            "landing": {"map": 1, "x": 32669, "y": 32802, "heading": 4},
            "final_destination": {"map": 1, "x": 32671, "y": 32804}
        },
        "expected_phases": [
            {
                "phase": 1,
                "description": "Local Navigation on Map 0 to Portal Trigger",
                "expected_end_map": 0,
                "expected_end_pos": [32477, 32851]
            },
            {
                "phase": 2,
                "description": "Cross-Map Portal Transition Committed",
                "expected_transition_id": "portal_ti_to_tid1",
                "expected_new_map": 1,
                "expected_landing_pos": [32669, 32802],
                "expected_heading": 4
            },
            {
                "phase": 3,
                "description": "Local Navigation on Map 1 to Final Destination",
                "expected_final_map": 1,
                "expected_final_pos": [32671, 32804],
                "destination_reached": True
            }
        ]
    }

    with open("scenario_003_contract.json", "w", encoding="utf-8") as f:
        json.dump(contract, f, indent=2, ensure_ascii=False)

    print("[OK] Generated scenario_003_contract.json successfully.")

if __name__ == '__main__':
    build_contract()
