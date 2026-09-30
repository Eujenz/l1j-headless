import json

def build_contract():
    with open('oracle_trace_scenario_001.jsonl', 'r', encoding='utf-8') as f:
        events = [json.loads(line) for line in f]

    header = events[0]
    assert header.get('artifact') == 'L1J_ORACLE_TRACE'

    contract = {
        "contract_schema": "1.0",
        "scenario_id": "001",
        "fixture_version": 3,
        "source": "INSTRUMENTED_LEGACY_REFERENCE",
        "scope": "scenario_001",
        "oracle_status": header.get("oracle_status"),
        "rng_seed": 424242,
        "initial_state": {
            "attacker": {
                "id": 268435456,
                "name": "OracleKnight",
                "class_type": 1,
                "level": 10,
                "hp": 100,
                "max_hp": 100,
                "str": 16,
                "dex": 12,
                "con": 14,
                "int": 8,
                "wis": 9,
                "cha": 12,
                "x": 33430,
                "y": 32810,
                "map_id": 0,
                "heading": 2,
                "auto_pickup": True,
                "weapon": {
                    "item_id": 1,
                    "name": "劍",
                    "type": 1,
                    "dmg_small": 8,
                    "dmg_large": 12,
                    "enchant": 0,
                    "bless": 0
                }
            },
            "target": {
                "id": 10001,
                "name": "哥布林",
                "uid": 3,
                "level": 6,
                "hp": 20,
                "max_hp": 20,
                "mp": 5,
                "ac": 0,
                "exp": 37,
                "size": "small",
                "x": 33431,
                "y": 32810,
                "map_id": 0,
                "heading": 6,
                "inventory": [
                    {
                        "item_id": 5,
                        "name": "金幣",
                        "count": 250
                    }
                ]
            }
        },
        "commands": [],
        "expected_rng": [],
        "expected_state_mutations": [],
        "expected_domain_events": [],
        "expected_inventory": {
            "attacker_gold": 0,
            "ground_drops": [
                {
                    "item_id": 5,
                    "count": 250,
                    "x": 33431,
                    "y": 32809
                }
            ]
        },
        "expected_packets": []
    }

    for ev in events[1:]:
        kind = ev.get("kind")
        event_name = ev.get("event")

        if event_name == "COMMAND":
            contract["commands"].append({
                "tick": ev["tick"],
                "name": ev["name"],
                "payload": ev["payload"]
            })
        elif event_name == "RNG_CONSUMED":
            contract["expected_rng"].append({
                "seq": ev["seq"],
                "tick": ev["tick"],
                "callsite": ev.get("callsite_tag", ev.get("source_method")),
                "source_line": ev.get("source_line"),
                "min": ev["min"],
                "max": ev["max"],
                "result": ev["result"]
            })
        elif event_name in ("STATE_MUTATION", "HIT_EVALUATED", "DAMAGE_CALCULATED", "ENTITY_DIED", "EXP_AWARDED", "ITEM_DROPPED", "INVENTORY_ADDED"):
            contract["expected_state_mutations"].append(ev)
        elif event_name == "PACKET_SERIALIZED":
            contract["expected_packets"].append({
                "seq": ev["seq"],
                "tick": ev["tick"],
                "packet_class": ev["packet_class"],
                "sender_id": ev["sender_id"],
                "len": ev["len"],
                "payload_hex": ev["payload_hex"]
            })

    with open('scenario_001_contract.json', 'w', encoding='utf-8') as out:
        json.dump(contract, out, indent=2, ensure_ascii=False)

    print(f"Contract written: scenario_001_contract.json ({len(contract['commands'])} commands, {len(contract['expected_rng'])} RNGs, {len(contract['expected_packets'])} packets)")

if __name__ == "__main__":
    build_contract()
