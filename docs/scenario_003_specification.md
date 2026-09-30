# Scenario 003: Deterministic Portal Cross-Map Transition Specification

## 1. Scope & Objective
Establish the first multi-map vertical slice in the Headless L1 World:
- Real Canonical Transition:
  - `transition_id`: `portal_ti_to_tid1` (from `db/lineage/dungeon.sql` row 2)
  - Source: Map 0 (Talking Island Surface) at (32477, 32851)
  - Target: Map 1 (Talking Island Dungeon 1F) at (32669, 32802, heading 4)
  - Preconditions: `item_id = 0` (zero requirement, deterministic free walk-in portal)
- Synthetic Test Geometries:
  - Map 0 Local Grid: 5x5 bounds containing approach path to portal at (32477, 32851)
  - Map 1 Local Grid: 5x5 bounds containing dungeon landing at (32669, 32802) and destination at (32671, 32804)
- Strict Separation of Concerns:
  - Local Navigation: Local A* pathfinding strictly within current map
  - Transition Engine: Deterministic portal trigger detection and atomic world mutation
  - Planners do not know about portal tables; Transition engines do not plan paths.

## 2. Execution Ordering
1. Phase 1 (Map 0 Local Navigation):
   - Actor at Start_A on Map 0
   - Local A* generates `CmdMove` sequence to portal coordinates (32477, 32851)
   - Step-by-step movement validated by `MovementEngine`
2. Phase 2 (Cross-Map Transition):
   - Actor steps onto portal tile (32477, 32851)
   - Portal trigger resolved by `TransitionEngine`
   - Atomic state mutation:
     - Old map membership removed (Map 0)
     - New map membership registered (Map 1)
     - Coordinates mutated to (32669, 32802, heading 4)
   - Domain events emitted: `PortalTriggered` -> `WorldTransitionCommitted` -> `MapEntered`
3. Phase 3 (Map 1 Local Navigation):
   - Actor on Map 1 landing point
   - Local A* plans path from (32669, 32802) to Final Destination (32671, 32804) on Map 1
   - Step-by-step movement validated by `MovementEngine`
   - Emits `DestinationReached` on final arrival

## 3. Domain Event Model
- `PortalTriggered(entity_id, transition_id, source_map, source_x, source_y)`
- `WorldTransitionCommitted(entity_id, old_map, old_x, old_y, new_map, new_x, new_y, new_heading)`
- `MapEntered(entity_id, map_id, x, y, heading)`
- `DestinationReached(entity_id, target_x, target_y)`
