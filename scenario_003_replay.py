"""
scenario_003_replay.py - Scenario 003 Cross-Map Transition Replay Verifier.
Validates Local Navigation on Map A -> Portal Trigger -> Cross-Map Transition -> Local Navigation on Map B.
"""
import json
import os
import sys
from dataclasses import dataclass
from typing import List

from native_engine.map import WorldMapGrid
from native_engine.movement import MovementEngine
from native_engine.navigation import AutonomousNavigator
from native_engine.world import World
from native_engine.transition import TransitionEngine, TransitionDefinition
from native_engine.events import DomainEvent

@dataclass
class ReplayActor:
    id: int
    name: str
    map_id: int
    x: int
    y: int
    heading: int

def run_replay(contract_path: str = "scenario_003_contract.json", trace_out: str = "native_trace_003.jsonl"):
    with open(contract_path, "r", encoding="utf-8") as f:
        contract = json.load(f)

    print("=================================================================")
    print("      MODERN REPLAY 003 - CROSS-MAP TRANSITION SIMULATOR")
    print("=================================================================")
    print(f"[CONTRACT LOADED] Scenario: {contract['scenario_id']} (Fixture v{contract['fixture_version']})")
    print(f"                 Scope:    {contract['scope']}")
    print(f"                 Source:   {contract['source']}")

    # 1. Initialize World and Maps
    world = World()
    for mdata in contract["maps"]:
        grid = WorldMapGrid(
            map_id=mdata["map_id"],
            loc_x1=mdata["loc_x1"],
            loc_y1=mdata["loc_y1"],
            width=mdata["width"],
            height=mdata["height"]
        )
        for tile in mdata["tiles"]:
            grid.set_tile(tile["x"], tile["y"], tile["val"])
        world.add_map(grid)

    # 2. Initialize Transition Engine
    transition_engine = TransitionEngine()
    for tdata in contract["transitions"]:
        tdef = TransitionDefinition(
            transition_id=tdata["transition_id"],
            type=tdata["type"],
            source_map=tdata["source_map"],
            source_x=tdata["source_x"],
            source_y=tdata["source_y"],
            target_map=tdata["target_map"],
            target_x=tdata["target_x"],
            target_y=tdata["target_y"],
            target_heading=tdata["target_heading"],
            requirements=tdata.get("requirements", {})
        )
        transition_engine.register_transition(tdef)

    # 3. Add Actor to World
    adata = contract["actor"]
    actor = ReplayActor(
        id=adata["id"],
        name=adata["name"],
        map_id=adata["initial_map"],
        x=adata["initial_x"],
        y=adata["initial_y"],
        heading=adata["initial_heading"]
    )
    world.add_actor(actor, adata["initial_map"])

    trace_records = []
    seq = 0

    # -------------------------------------------------------------
    # PHASE 1: Local Navigation on Map 0 to Portal Trigger
    # -------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> PHASE 1: LOCAL NAVIGATION ON MAP 0 TO PORTAL TRIGGER")
    print("-----------------------------------------------------------------")
    mission = contract["mission"]
    portal_dest = mission["portal"]

    engine_map0 = MovementEngine(world.get_map(0))
    p1_success, p1_events = AutonomousNavigator.goto(
        actor=actor,
        target_x=portal_dest["x"],
        target_y=portal_dest["y"],
        engine=engine_map0,
        start_tick=100
    )

    for ev in p1_events:
        seq += 1
        trace_records.append({
            "seq": seq,
            "tick": ev.tick,
            "channel": "OUTPUT",
            "record_type": "DOMAIN_EVENT",
            "name": ev.__class__.__name__,
            "payload": ev.__dict__
        })

    assert p1_success, "Phase 1: Local navigation to portal failed!"
    assert actor.map_id == 0, f"Expected actor on map 0, got {actor.map_id}"
    assert actor.x == portal_dest["x"] and actor.y == portal_dest["y"], \
        f"Actor stopped at ({actor.x}, {actor.y}), expected portal ({portal_dest['x']}, {portal_dest['y']})"
    print(f"[PASS] Actor arrived at Portal on Map 0: ({actor.x}, {actor.y}) in {len(p1_events)//2} steps.")

    # -------------------------------------------------------------
    # PHASE 2: Cross-Map Portal Transition Resolution & Commitment
    # -------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> PHASE 2: CROSS-MAP PORTAL TRANSITION RESOLUTION")
    print("-----------------------------------------------------------------")
    trans_events = transition_engine.trigger_transition(world, actor.id, tick=200)

    for ev in trans_events:
        seq += 1
        trace_records.append({
            "seq": seq,
            "tick": ev.tick,
            "channel": "OUTPUT",
            "record_type": "DOMAIN_EVENT",
            "name": ev.__class__.__name__,
            "payload": ev.__dict__
        })

    # Validate Event Sequence: PortalTriggered -> WorldTransitionCommitted -> MapEntered
    event_names = [ev.__class__.__name__ for ev in trans_events]
    assert event_names == ["PortalTriggered", "WorldTransitionCommitted", "MapEntered"], \
        f"Unexpected transition event sequence: {event_names}"

    # Audit Atomic State Mutation
    landing = mission["landing"]
    assert actor.map_id == landing["map"], f"Expected actor map {landing['map']}, got {actor.map_id}"
    assert actor.x == landing["x"] and actor.y == landing["y"], \
        f"Expected actor coordinates ({landing['x']}, {landing['y']}), got ({actor.x}, {actor.y})"
    assert actor.heading == landing["heading"], \
        f"Expected actor heading {landing['heading']}, got {actor.heading}"

    # Audit World Spatial Membership
    assert actor.id not in world.map_actors[0], "Actor still registered in old Map 0 membership!"
    assert actor.id in world.map_actors[1], "Actor not registered in new Map 1 membership!"
    print(f"[PASS] Cross-map transition committed atomically:")
    print(f"       Old State: Map 0 ({portal_dest['x']}, {portal_dest['y']})")
    print(f"       New State: Map {actor.map_id} ({actor.x}, {actor.y}, Heading: {actor.heading})")
    print(f"       World Membership verified: Removed from Map 0, Active in Map 1.")

    # -------------------------------------------------------------
    # PHASE 3: Local Navigation on Map 1 to Final Destination
    # -------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> PHASE 3: LOCAL NAVIGATION ON MAP 1 TO FINAL DESTINATION")
    print("-----------------------------------------------------------------")
    final_dest = mission["final_destination"]
    engine_map1 = MovementEngine(world.get_map(1))

    p3_success, p3_events = AutonomousNavigator.goto(
        actor=actor,
        target_x=final_dest["x"],
        target_y=final_dest["y"],
        engine=engine_map1,
        start_tick=300
    )

    for ev in p3_events:
        seq += 1
        trace_records.append({
            "seq": seq,
            "tick": ev.tick,
            "channel": "OUTPUT",
            "record_type": "DOMAIN_EVENT",
            "name": ev.__class__.__name__,
            "payload": ev.__dict__
        })

    assert p3_success, "Phase 3: Local navigation on Map 1 failed!"
    assert actor.map_id == final_dest["map"], f"Expected actor map {final_dest['map']}, got {actor.map_id}"
    assert actor.x == final_dest["x"] and actor.y == final_dest["y"], \
        f"Actor stopped at ({actor.x}, {actor.y}), expected destination ({final_dest['x']}, {final_dest['y']})"

    has_reached = any(ev.__class__.__name__ == 'DestinationReached' for ev in p3_events)
    assert has_reached, "DestinationReached event not emitted in Phase 3!"
    print(f"[PASS] Actor completed mission on Map 1 at Final Destination: ({actor.x}, {actor.y}) in {len(p3_events)//2} steps.")

    # Write Native Trace Output
    with open(trace_out, "w", encoding="utf-8") as f:
        for r in trace_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n[TRACE ARTIFACT] Written {len(trace_records)} native events to {trace_out}")

    print("\n=================================================================")
    print("               FINAL REPLAY CONFORMANCE VERDICT")
    print("=================================================================")
    print("  L1 Map A Local Navigation      PASS")
    print("  L2 Cross-Map World Transition  PASS")
    print("  L3 Map B Local Navigation      PASS")
    print("=================================================================")
    print("               >>>  OVERALL STATUS: PASS  <<<")
    print("=================================================================")

if __name__ == '__main__':
    run_replay()
