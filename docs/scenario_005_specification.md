# Scenario 005: Real Multi-Map Route Planning Specification

---

## 1. Objective

Establish the first end-to-end **World Route Planning** vertical slice in the Headless L1 World runtime by composing:
1. **Real Canonical Map Geometry** (Map 0 & Map 1 decoded from legacy `.data`)
2. **Authentic Collision & Local A*** (`WorldMapGrid` & `AStarPlanner`)
3. **Canonical Legacy Portal** (`portal_ti_to_tid1` from `dungeon.sql`)
4. **Deterministic World Transition** (`TransitionEngine` & atomic world state mutation)
5. **Two-Level Route Planning & Execution Architecture** (`WorldRoutePlanner` + `WorldRouteExecutor`)

---

## 2. Scope & Boundaries

### Included Scope
- Two real canonical maps: Map 0 (Talking Island Surface, 512x512) and Map 1 (Talking Island Dungeon 1F, 128x128).
- Canonical portal fixture `portal_ti_to_tid1` (Map 0 -> Map 1).
- Minimal `WorldTransitionProvider` and `TransitionGraph` querying cross-map connectivity.
- `WorldRoutePlanner` calculating discrete multi-map route topology: `[Map 0] -> portal_ti_to_tid1 -> [Map 1]`.
- Two-level route separation:
  - World-level planner resolves inter-map transition topology.
  - Local A* planner resolves intra-map coordinate paths.
- `WorldRouteExecutor` driving:
  1. Map 0 local navigation to portal source `(32477, 32851)`
  2. Portal trigger and atomic cross-map transition to Map 1 `(32669, 32802)`
  3. Map 1 local navigation to destination `(32671, 32804)`
- Deterministic replay and differential verification suite (`scenario_005_replay.py`, `scenario_005_differential.py`).

### Excluded Scope (Non-Goals)
- No global 92-map graph discovery or full world pathfinding.
- No dynamic dungeon discovery, boat schedules, return scrolls, or NPC teleporters.
- No item-cost routing or weighted A* search over the world graph.
- No multi-agent traffic or combat-aware obstacle avoidance.
- No live client protocol packets or GUI client rendering.
- No legacy Java/JVM runtime dependencies.

---

## 3. Existing Architecture & Separation of Concerns

```text
               ┌───────────────────────┐
               │   WorldRoutePlanner   │  <-- Decides map & transition sequence
               └──────────┬────────────┘
                          │ produces WorldRoute
                          ▼
               ┌───────────────────────┐
               │  WorldRouteExecutor   │  <-- Coordinates execution across maps
               └──────────┬────────────┘
         ┌────────────────┴────────────────┐
         ▼                                 ▼
┌──────────────────┐             ┌────────────────────┐
│   AStarPlanner   │             │  TransitionEngine  │
│  (Local Nav A*)  │             │ (Cross-Map Atomic) │
└────────┬─────────┘             └─────────┬──────────┘
         ▼                                 ▼
┌──────────────────┐             ┌────────────────────┐
│  MovementEngine  │             │     World State    │
│  (Step Physics)  │             │ (Map Actors, Grid) │
└──────────────────┘             └────────────────────┘
```

1. **`WorldRoutePlanner` (`MODERN_DESIGN`)**: Resolves world topology (which sequence of maps and transitions to traverse). Does not inspect raw tile bytes or execute movements.
2. **`WorldRouteExecutor` (`MODERN_DESIGN`)**: Orchestrates execution without making routing decisions. Calls local A* on the current map, steps via `MovementEngine`, and triggers `TransitionEngine`.
3. **`AStarPlanner` (`DERIVED_CANONICAL`)**: Computes intra-map heading sequences within a single `WorldMapGrid`. Never plans across map boundaries.
4. **`TransitionEngine` (`LEGACY_OBSERVED`)**: Detects portal coordinates, validates requirements, and executes atomic world state transitions.
5. **`WorldMapGrid` (`LEGACY_OBSERVED`)**: Evaluates authentic tile bitmasks. Keeps static terrain bytes separate from dynamic runtime overlays.

---

## 4. Real Map Fixtures

### Map 0: Talking Island Surface
- **Source**: `Lineage182c/maps/Cache/0.data`
- **Bounds**: $X \in [32256..32767]$, $Y \in [32768..33279]$ ($512 \times 512 = 262,144$ cells)
- **Source File SHA-256**: `9ff8acdbe12e846329bcc4207c8a88dda956ccfc409641a93ecf7cd1b8acd486`
- **Canonical Geometry Digest**: `7fe59f4a4f28fa0c87e69c67506ea578b2860d48e11ef61ffd7b66aef97ff9e5`
- **Format Anomaly**: 2-byte truncation ($W \times H - 2$) safely padded with `0x00`.

### Map 1: Talking Island Dungeon 1F
- **Source**: `Lineage182c/maps/Cache/1.data`
- **Bounds**: $X \in [32640..32767]$, $Y \in [32768..32895]$ ($128 \times 128 = 16,384$ cells)
- **Source File SHA-256**: `432b053abf837a28542a97fcc2b1309d6b8305e7dff967a69c32ac08a8a711fd`
- **Canonical Geometry Digest**: `3a8068953f7fbb57fd30bda0a6f63190a7a379a0943bbdb0cc1ccbffc38eb21b`
- **Format Anomaly**: 2-byte truncation ($16,382$ bytes vs $16,384$ cells) safely padded with `0x00`.

---

## 5. Real Transition Fixture

- **Transition ID**: `portal_ti_to_tid1`
- **Archaeological Provenance**: `Lineage182c/db/lineage/dungeon.sql` Row 2:
  `INSERT INTO dungeon VALUES ('2', '32477', '32851', '0', '32669', '32802', '1', '4', '0', '0', '0');`
- **Source Coordinates**: Map 0, `(32477, 32851)`
- **Target Coordinates**: Map 1, `(32669, 32802)`, Heading `4` (South)
- **Preconditions**: `item_id = 0` (free walk-in portal)

### Archaeological Portal Geometry Analysis
- On Map 0, tile `(32477, 32851)` has static byte value `0x20` (Combat Zone, impassable structure base).
- Tile `(32477, 32852)` directly South has static byte value `0x2a` (Combat Zone, `0x02` North Passable, `0x08` North Attack Passable).
- Heading `0` (North) from `(32477, 32852)` is passable into `(32477, 32851)` via authentic Lineage 1 directional bitmask semantics.
- Walking North from `(32477, 32854)` through `(32477, 32853)` and `(32477, 32852)` directly steps onto the portal tile `(32477, 32851)`.

---

## 6. World Graph Model

```text
World Node: Map ID (integer)
World Edge: WorldTransition (TransitionDefinition)
```

The World Graph represents reachability between distinct map topologies:
- `WorldTransitionProvider`: Interface for querying outgoing transitions:
  ```python
  def transitions_from(self, map_id: int) -> List[TransitionDefinition]:
      ...
  ```
- `StaticTransitionProvider`: In-memory provider registering canonical transitions (`portal_ti_to_tid1`).
- Routing Algorithm: Breadth-First Search (BFS) over map nodes. Finds the transition chain connecting `start_map` to `goal_map`.

---

## 7. Local Planner Boundary

- Local path planning is performed strictly within a single `WorldMapGrid`.
- `AStarPlanner.find_path(map_grid, sx, sy, tx, ty)` computes an 8-directional heading sequence.
- Planning across maps directly via local A* is strictly prohibited (non-continuous coordinate spaces).

---

## 8. Transition Boundary

- Transition execution is managed exclusively by `TransitionEngine`.
- Atomic state mutation:
  - Safely unregisters actor from old map spatial container.
  - Registers actor in new map spatial container.
  - Atomically updates `map_id`, `x`, `y`, and `heading`.
- Emits domain events:
  - `PortalTriggered`
  - `WorldTransitionCommitted`
  - `MapEntered`

---

## 9. Static vs Dynamic Map Boundary

- Static terrain bytes (`dense_tiles`) remain pure and immutable.
- Dynamic portal overlay (`WorldMapGrid.set_tile(x, y, 100)`) matches legacy `DungeonTable.gotoDungeon` runtime overlay semantics without modifying canonical base terrain.

---

## 10. World Route Contract

A planned `WorldRoute` contains:
```python
@dataclass
class WorldRoute:
    start_map: int
    goal_map: int
    map_sequence: List[int]
    transitions: List[TransitionDefinition]
    is_valid: bool = True
```

Failure cases emit explicit `RoutePlanningResult`:
- `NO_ROUTE`: No graph connectivity between source and destination maps.
- `SAME_MAP`: Source and destination are on the same map (zero cross-map transitions).
- `INVALID_MAP`: Source or destination map not found in registry.
- `OUT_OF_BOUNDS`: Coordinates outside map dimensions.

---

## 11. Execution Model (`WorldRouteExecutor`)

1. **Validation**: Verify actor is at start position and map matches `route.start_map`.
2. **Leg 1 (Map 0 Local Approach)**:
   - Local A* plans path from start `(32477, 32854)` to portal source `(32477, 32851)`.
   - `MovementEngine` validates and executes each `CmdMove`.
3. **Cross-Map Transition**:
   - Actor steps onto `(32477, 32851)`.
   - `TransitionEngine.trigger_transition` fires `portal_ti_to_tid1`.
   - Actor state atomically becomes Map 1, `(32669, 32802)`, heading `4`.
4. **Leg 2 (Map 1 Local Arrival)**:
   - Local A* plans path from landing `(32669, 32802)` to goal `(32671, 32804)`.
   - `MovementEngine` validates and executes each `CmdMove`.
   - Emits `DestinationReached`.

---

## 12. Differential Strategy

Legacy 1.82 has no unified `WorldRoutePlanner` class; route planning is a modern orchestration primitive. Therefore, differential verification certifies:
- **Level 0 (Map Integrity)**: Map 0 and Map 1 metadata and canonical geometry digests match 100%.
- **Level 1 (Transition Integrity)**: Transition definition matches legacy `dungeon.sql` row 2.
- **Level 2 (World Route Topology)**: Planner correctly identifies map sequence `[0, 1]` and transition `portal_ti_to_tid1`.
- **Level 3 (Map 0 Approach Conformance)**: Local navigation on real terrain reaches portal tile without collisions.
- **Level 4 (Cross-Map State Conformance)**: Atomic mutation matches legacy `DungeonTable` landing coordinates `(32669, 32802, 4)`.
- **Level 5 (Map 1 Exit Conformance)**: Local navigation on real Map 1 terrain reaches goal `(32671, 32804)`.

---

## 13. Test Matrix

| ID | Description | Expected Result |
| :--- | :--- | :--- |
| **T01** | Real Map 0 Import | $512 \times 512$, Digest `7fe59f...` verified |
| **T02** | Real Map 1 Import | $128 \times 128$, Digest `3a8068...` verified |
| **T03** | Transition Graph Load | `portal_ti_to_tid1` registered with provenance |
| **T04** | World Route Planning (0 -> 1) | Map sequence `[0, 1]`, 1 transition |
| **T05** | Map 0 Real Terrain A* to Portal | Path `[0, 0, 0]` found |
| **T06** | Portal Trigger & Execution | Actor moves Map 0 -> Map 1 at `(32669, 32802)` |
| **T07** | Map 1 Real Terrain A* to Goal | Path `[2, 3, 4]` found |
| **T08** | Full Multi-Map Route Execution | Reaches Goal `(32671, 32804)` with all events |
| **T09** | Deterministic Replay | 100% bit-exact replay across runs |
| **F01** | Disconnected Map Query | `NO_ROUTE` error returned |
| **F02** | Out-of-Bounds Destination | `OUT_OF_BOUNDS` error returned |
| **F03** | Unreachable Portal on Terrain | Local planning fails gracefully |
| **F04** | Unreachable Goal on Target Map | Local planning fails gracefully |

---

## 14. Provenance Classification

- **`LEGACY_OBSERVED`**:
  - Raw map byte grids for Map 0 and Map 1 (`Cache/0.data`, `Cache/1.data`)
  - 2-byte truncation bug handling
  - Bitmask passability semantics (`0x01` East, `0x02` North)
  - Portal table schema and row 2 values in `dungeon.sql`
  - Atomic landing state `(32669, 32802, 4)`
- **`DERIVED_CANONICAL`**:
  - `CanonicalMapDefinition` representation
  - Normalized `TransitionDefinition`
  - Dual-phase approach and landing sequence
- **`MODERN_DESIGN`**:
  - `WorldRoutePlanner` (multi-map BFS topological routing)
  - `WorldRouteExecutor` (two-level execution coordinator)
  - `TransitionProvider` and `MapRegistry` interfaces
  - `WorldRoutePlanned` domain event

---

## 15. Definition of Done
1. Specification frozen and committed.
2. Real Map 1 imported via canonical decoder and verified.
3. Transition graph and provider abstractions implemented.
4. WorldRoutePlanner and WorldRouteExecutor implemented cleanly.
5. Scenario 005 replay and differential verifier implemented and certified.
6. Full regression across Scenarios 001-005 passing.
