# Architecture: Headless Native World Runtime

## 1. System Overview

L1J Headless is a standalone, lightweight simulation engine that executes Lineage 1 world semantics without GUI clients, network sockets, or legacy database engines.

```text
                    Headless L1 World
                           │
             ┌─────────────┴─────────────┐
             │                           │
         World Rules                 Automation (Future)
             │                           │
       ┌─────┴─────┐               Planner / Agent
       │           │
   Map Geometry  Transition
       │           │
       └─────┬─────┘
             ↓
         World State
             ↓
      Text UI / API / Agent (Future)
```

---

## 2. Core Subsystems

### 2.1 Spatial Existence & Map Geometry (`native_engine/map.py`)
- Represents 2D tile topologies using the canonical Lineage 1 bitmask format (`0x01` East Passable, `0x02` North Passable).
- Implements authentic `IsThroughObject` edge evaluation and diagonal clearance logic.
- Independent of client tile rendering and graphic assets.

### 2.2 Movement Arbiter (`native_engine/movement.py`)
- Validates discrete spatial steps in 8 canonical directions (`0` North through `7` North-West).
- Enforces static collision boundaries, tile passability, and out-of-bounds restrictions.
- Emits atomic movement domain events: `MoveAttempted`, `MoveAccepted`, `MoveBlocked`, and `PositionChanged`.

### 2.3 Local Navigation (`native_engine/navigation.py`)
- Executes localized A* pathfinding strictly within a single map grid.
- Uses integer Euclidean-squared distance matching canonical heuristics.
- Generates high-level movement sequences (`CmdMove`) down to the Movement Arbiter without directly mutating actor coordinates.

### 2.4 Cross-Map Transitions (`native_engine/transition.py`)
- Evaluates transition triggers (portals, teleport pads, stairs).
- Executes atomic cross-map mutations:
  - De-registers entity from source map.
  - Updates world spatial registry.
  - Registers entity on target map with landing coordinates and orientation.
- Emits `PortalTriggered`, `WorldTransitionCommitted`, and `MapEntered` lifecycle events.

### 2.5 Combat & Lifecycle (`native_engine/combat.py`, `native_engine/simulator.py`)
- Pure mathematical implementation of canonical HitFigure (0..29 competition roll) and DmgSystem formulas.
- Manages entity death transitions, reward attribution (EXP, Lawful alignment), and drop item transfers.

### 2.6 Wire Codec (`native_engine/codec.py`)
- Serves strictly as a **wire serialization compatibility primitive for conformance testing** (e.g. Scenario 001 packet layout validation).
- Validates binary wire layout (`S_BasePacket` 8-byte alignment) against legacy reference standards.
- **Not** a live client network stack or socket protocol server.

---

## 3. Current Implementation Status vs. Future Modules

```text
Currently Certified & Active:
  Headless World
      ├── World State
      ├── Map Geometry
      ├── Local Navigation (Same-map A*)
      └── Cross-Map Transition (Atomic portal handover)

Planned / Future Modules:
  Automation & Orchestration
      ├── Goal Planner
      ├── World Route Planner (Multi-map route synthesis)
      └── Autonomous Agent Loop
```

---

## 4. Scenario Maturity & Coverage

The scenarios currently certified in this repository represent **targeted vertical slices**, not full game feature parity:
- **Scenario 001**: Combat / Death Lifecycle (single entity pair).
- **Scenario 002**: Spatial Movement, Collision & Local Navigation (synthetic grid).
- **Scenario 003**: Deterministic Cross-Map Portal Transition (Map 0 → Map 1).

Each slice establishes verified behavioral compatibility for its isolated scope.

---

## 5. Decoupling & Independence Guarantees

- **Zero Legacy Java Dependencies**: No JVM invocation, no Java class reflection, no JNI bindings.
- **Zero Database Server Dependencies**: State fixtures and static geometry tables are provided through declarative contracts.
- **Zero Oracle Coupling at Runtime**: The native engine executes autonomously from contracts and never reads oracle traces to make decisions.
- **Strict Separation of Concerns**: Planners do not mutate state; movement arbiters do not plan paths; transition managers do not compute local routes.
