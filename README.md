# L1J Headless

> A headless, native runtime for a behaviorally grounded Lineage 1 world.

```text
L1J Headless
────────────
Behaviorally grounded, headless Native L1 world runtime.

Research method:
Legacy source
→ Behavioral Archaeology
→ Compatibility Contract
→ Native Runtime
→ Differential Replay

Current certified slices:
001 Combat / Death Lifecycle
002 Movement / Collision / Local Navigation
003 Deterministic Cross-Map Portal Transition

Legacy Reference:
Eujenz/182c
```

---

## Project Positioning

This project is **not a rewrite of the L1J server**.

It uses **L1J 1.82** as a behavioral reference and extracts observable gameplay semantics into explicit compatibility contracts. The final runtime operates without the original Java server, original GUI client, login server, or network socket protocol.

```text
Legacy Source (182c)
       ↓
Behavioral Archaeology
       ↓
Canonical Contract
       ↓
Native Runtime
       ↓
Differential Replay
```

---

## Product Vision

The long-term vision is to build a headless Lineage 1 world runtime that executes autonomously without requiring original client or server binaries:

```text
Player Goal
    ↓
Automation Agent (Future)
    ↓
World Observation
    ↓
World Navigation (Future)
    ↓
Local Navigation
    ↓
Movement / Action
    ↓
World State
```

For instance, an automation agent could process high-level goals:
> *"Head to northern Talking Island to hunt monsters. If no targets are found, navigate to Silver Knight Town. Return to town if HP drops below safety threshold."*

The autonomous runtime handles the complete loop:
`Observation` → `Decision` → `Navigation` → `Transition` → `Movement` → `Combat` → `Loot` → `Return`.

*(Note: This represents the long-term vision. Not all features are currently implemented.)*

---

## Architecture

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

- **Local Navigation**: Resolves same-map movement, static obstacle avoidance, and canonical 8-direction pathfinding.
- **Cross-Map Transition**: Evaluates spatial triggers (portals, stairs, teleports) and executes atomic state handoffs between discrete map topologies.
- **World Route Planning (Future)**: Composes cross-map transitions and local A* segments into end-to-end multi-map routes.
- **Wire Codec (`native_engine/codec.py`)**: Serves strictly as a wire serialization compatibility primitive for conformance testing (e.g. Scenario 001 packet layout validation). It is not a live network socket stack or client protocol server.

For further architectural details, see [Architecture Overview](docs/architecture.md).

---

## Methodology: Behavioral Archaeology

Observable behaviors are verified through an empirical, contract-driven pipeline:

```text
Legacy Observation
        ↓
Canonical Contract
        ↓
Native Implementation
        ↓
Differential Replay
```

All data and behavioral assumptions are assigned explicit provenance tiers:
- **`LEGACY_OBSERVED`**: Empirically measured from instrumented legacy execution traces.
- **`DERIVED_CANONICAL`**: Normalized from legacy data schemas into standardized contracts.
- **`CONTROLLED_SUBSTITUTION`**: Deterministic modern primitives replacing unmanaged legacy behavior (e.g. seeded RNG).
- **`MODERN_DESIGN`**: Modern architectural additions (e.g. server-side collision validation, domain event streams).
- **`INFERRED`**: Inferred behavior pending empirical confirmation.
- **`UNKNOWN`**: Unverified edge case behavior.

> **Key Rule**: Legacy implementation ≠ Compatibility contract; Modern design ≠ Legacy fact.
> **Coverage Rule**: Behavioral Coverage ≠ Full Game Coverage. Passing a slice certifies conformance for that slice's defined scope, not whole-game parity.

For details on the research methodology, see [Methodology Documentation](docs/methodology.md).

---

## Current Status & Certified Milestones

| Scenario | Scope | Conformance Status | Specification |
| :--- | :--- | :--- | :--- |
| **001** | Combat / Death Lifecycle | **Certified** | [Spec](docs/scenario_001_specification.md) |
| **002** | Movement / Collision / Local Navigation | **Certified** | [Spec](docs/scenario_002_specification.md) |
| **003** | Deterministic Cross-Map Portal Transition | **Certified** | [Spec](docs/scenario_003_specification.md) |

### Scenario Breakdown

- **Scenario 001 (Combat & Death)**:
  - Canonical dual-dice hit resolution (`HitFigure`)
  - Weapon damage calculation and blessed bonus (`DmgSystem`)
  - HP mutation, entity death, and death action dispatch
  - EXP award and Lawful alignment adjustment
  - Inventory drop transfer and ground item state
  - Bit-exact Lineage 182 binary packet wire serialization (`S_BasePacket`)
- **Scenario 002 (Movement & Local Navigation)**:
  - Canonical 8-direction delta steps (0..7 clockwise)
  - Authentic tile bitmask evaluation (`0x01` East, `0x02` North)
  - Static wall collision and out-of-bounds rejection
  - Diagonal corner clearance with dual-route disjunction
  - Local A* autonomous navigation (`CmdMove` generation)
- **Scenario 003 (Cross-Map Transition)**:
  - Map A local navigation to portal coordinates
  - Deterministic walk-in portal trigger (`portal_ti_to_tid1`)
  - Atomic cross-map transition (remove from Map 0, enter Map 1 at landing coordinates)
  - Map B local navigation to final destination

### Conformance Verification Note
- **Scenario 003 Differential Conformance**: `PASS` (100% state and domain event equivalence between Legacy Oracle and Native Engine).
  *Note: This certification applies strictly to the verified behavioral scope of Scenario 003 and does not imply comprehensive feature parity with all L1J 1.82 mechanics.*
- **Extraction Source Provenance**: `Eujenz/182c@7eeacbc`. See [Repository Migration Provenance](docs/repository_migration.md).

---

## Repository Relationship

```text
             Eujenz/182c
         Legacy Reference
                 │
                 │ evidence / oracle traces
                 ↓
       Compatibility Contracts
                 │
                 ↓
        Eujenz/l1j-headless
          Native Runtime
```

- **`Eujenz/182c`**: Legacy Reference / Archaeology Source (Java source, database dumps, map archives, oracle generation).
- **`Eujenz/l1j-headless`**: Active Native Runtime repository.

> The Native runtime does **not** depend on the legacy Java server, JVM, or database at execution time.

---

## Quick Start

Run the certified scenario replays and differential verifier:

```bash
# Scenario 001: Combat & Death Replay
python scenario_001_replay.py

# Scenario 002: Movement & Collision Replay
python scenario_002_replay.py

# Scenario 003: Cross-Map Transition Replay
python scenario_003_replay.py

# Scenario 003: Differential Conformance against Legacy Oracle
python scenario_003_differential.py

# Run all test suites
python -m unittest discover tests
```

---

## Development Rules

1. **Strict Cadence**: Small Vertical Slice → Evidence → Contract → Native Implementation → Differential Replay → Freeze.
2. **Do not overbuild**: Implement only what the active slice requires.
3. **Do not infer undocumented behavior as fact**: Flag unknown behavior as `INFERRED`.
4. **Do not rewrite Legacy history**: Keep `182c` untouched as immutable archaeological evidence.
5. **Do not feed oracle traces into Native runtime**: Oracles are used solely for differential verification after the fact.
6. **Do not attempt to implement an entire MMORPG at once**.

---

## Roadmap

- [x] **Scenario 001**: Combat / Death Lifecycle
- [x] **Scenario 002**: Movement / Collision / Local Navigation
- [x] **Scenario 003**: Cross-Map Portal Transition
- [ ] **Scenario 004**: Canonical Real Map Import *(Planned)*
- [ ] Multi-Actor World Simulation
- [ ] NPC & Object Interaction
- [ ] Items & Equipment Systems
- [ ] Spells & Skills
- [ ] Quests & Game Progression
- [ ] Economy & Trading
- [ ] Persistent World State
- [ ] Autonomous Goal Planner / Agent
- [ ] Text UI / CLI & Developer API

---

## Non-Goals

The following are explicitly non-goals for this project:
- Full original GUI client emulation
- Login server implementation
- Full network protocol compatibility / live client serving
- MMORPG server replacement
- Complete AOI (Area of Interest) replication
- Full legacy MySQL database compatibility
- Full 1.82 feature parity

---

## Legacy Reference

The behavioral reference repository is:

> [**`Eujenz/182c`**](https://github.com/Eujenz/182c)

The Native runtime does not embed or require the Legacy Java server. Compatibility artifacts and oracle traces are derived from explicitly identified Legacy source/data and are labeled with provenance.

---

## License

No project license has currently been declared.

The project is intended for research and educational experimentation. Users are responsible for determining the rights applicable to any legacy source or game data they use.
