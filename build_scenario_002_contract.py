import json

def build_contract():
    with open('oracle_trace_scenario_002.jsonl', 'r', encoding='utf-8') as f:
        events = [json.loads(line) for line in f]

    header = events[0]
    assert header.get('scenario_id') == '002'

    # Extract map tiles
    map_tiles = []
    tile_dict = {}
    for ev in events:
        if ev.get('record_type') == 'MAP_TILE':
            p = ev['payload']
            map_tiles.append(p)
            tile_dict[(p['x'], p['y'])] = p

    # Extract test cases
    test_cases = []
    for ev in events:
        rec_type = ev.get('record_type')
        if rec_type == 'COLLISION_EVAL':
            p = ev['payload']
            test_cases.append({
                "case_id": p['case_id'],
                "name": ev['name'],
                "type": "COLLISION",
                "x": p['x'],
                "y": p['y'],
                "dir": p['dir'],
                "expected_passable": p['passable'],
                "desc": p['desc']
            })
        elif rec_type == 'NAVIGATION_PATH':
            p = ev['payload']
            test_cases.append({
                "case_id": p['case_id'],
                "name": ev['name'],
                "type": "NAVIGATION",
                "start": p['start'],
                "target": p['target'],
                "expected_found": p['found'],
                "legacy_path": p['steps']
            })

    contract = {
        "contract_schema": "1.0",
        "scenario_id": "002",
        "fixture_version": 1,
        "source": "INSTRUMENTED_LEGACY_REFERENCE + MODERN_DESIGN",
        "scope": "scenario_002",
        "map": {
            "map_id": header['map_id'],
            "loc_x1": header['x1'],
            "loc_y1": header['y1'],
            "width": header['width'],
            "height": header['height'],
            "tiles": map_tiles
        },
        "test_cases": test_cases
    }

    with open('scenario_002_contract.json', 'w', encoding='utf-8') as f:
        json.dump(contract, f, indent=2, ensure_ascii=False)

    print(f"[OK] Generated scenario_002_contract.json with {len(test_cases)} test cases.")

if __name__ == '__main__':
    build_contract()
