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
004 Canonical Real Map Import
005 Real Multi-Map Route Planning
006 Playable MVP (Hunting / Combat / Character State)
007 Multi-Actor Persistent Native World (10-min Virtual Run)
008 Configurable Autonomous Hunting & Town Resupply (30-min Virtual Run)
009 Headless Player MVP Multi-Profile Verification (Closed-Loop Run)

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

## Product Definition & Vision

> **L1J Headless = 一個沒有 Legacy Client / JVM 的 Native L1J 1.82 玩家；唯一額外能力，是玩家可以透過設定把原本手動進行的狩獵操作自動化。**

本專案的核心目標：在不依賴 Legacy Java Server、Legacy Client、JVM、GUI Client、Legacy MySQL Runtime、Live Network Protocol 的情況下，讓 Native Headless Player 以盡可能接近真實 L1J 1.82 玩家操作、邏輯與遊玩體驗的方式進行遊戲。

概念上等同：
```text
Real L1J Player + Legacy-compatible helper / bot configuration
```

而不是 Generic AI Agent，也不是 Game Strategy Optimizer。

---

## Four-Layer Architecture

```text
Legacy L1J Behavior (Eujenz/182c)
        ↓
Native L1J World
        ↓
Headless Player
        ↓
Player Operation (Action Model)
        ↓
Configurable Automation (Helper / Policy)
        ↓
Continuous Gameplay
```

### Layer 1 — Legacy Evidence
Canonical 參考：[`Eujenz/182c`](https://github.com/Eujenz/182c)。所有遊戲規則、數值、動作時序、掉落率、商店資料均優先從此層取得與驗證。

### Layer 2 — Native L1J World
純 Python / In-Process 忠實表達 L1J 1.82 世界規則：地圖與阻擋 (Map 0/1)、怪物 AI 與刷新、戰鬥計算與武器速度、背包與道具、藥水機制與冷卻、NPC 商店交易、經驗值與等級、死亡與回城、虛擬時間排程。不包含任何玩家個人偏好。

### Layer 3 — Player Operation
定義真實玩家能執行的操作集合（Player Action Model，不是 AI）：
`MOVE`, `ATTACK`, `SELECT_TARGET`, `CAST_SKILL`, `USE_ITEM`, `LOOT`, `TALK_NPC`, `BUY`, `SELL`, `TRAVEL`, `TELEPORT`, `EQUIP`, `UNEQUIP`。

### Layer 4 — Configurable Automation
玩家配置哪些 Player Operation 要由系統自動執行（如參考 `r0ptik/L1J-3.8-launcher` 式經典外掛/輔助工具設定）：
- 喝水規則（HP 門檻、藥水種類、冷卻、優先級）
- 緊急逃脫（危急血量使用回城卷軸）
- 回城補給（低藥水、過重觸發回城、指定商店 NPC、採購目標數量）
- 狩獵目標（獵場地圖、巡邏範圍）

> **Automation ≠ Optimization**：系統不負責尋找最高 EXP、最高利潤或最佳化喝水。玩家配置什麼，Native World 就忠實執行什麼。入不敷出、死亡、虧損皆為完全合法的真實遊戲結果。

For further architectural details, see [Product Direction](docs/architecture/product_direction_headless_player.md) and [Architecture Overview](docs/architecture.md).

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
| **004** | Canonical Real Map Import | **Certified** | [Spec](docs/scenario_004_specification.md) |
| **005** | Real Multi-Map Route Planning | **Certified** | [Spec](docs/scenario_005_specification.md) |
| **006** | Playable MVP (Hunting / Combat / State) | **Certified** | [Spec](docs/scenario_006_playable_mvp_specification.md) |
| **007** | Multi-Actor Persistent Native World | **Certified** | [Spec](docs/scenario_007_specification.md) |
| **008** | Configurable Autonomous Hunting & Town Resupply | **Certified** | [Spec](docs/scenario_008_specification.md) |
| **009** | Headless Player MVP Multi-Profile Verification | **Certified** | [Spec](docs/mvp/mvp_05_headless_player.md) |

### Scenario Breakdown

- **Scenario 007 (Multi-Actor Persistent Native World)**:
  - Multi-actor spatial indexing and collision
  - Autonomous monster roaming and target chasing
  - Natural HP regeneration and virtual temporal scheduler
- **Scenario 008 (Autonomous Resupply Cycle)**:
  - 30-minute persistent autonomous hunting cycle
  - Low supply detection and Escape Scroll return to town
  - Pandora NPC shop interaction and cross-map re-entry
- **Scenario 009 (Headless Player MVP Multi-Profile)**:
  - Layer 3 Player Operation execution with target acquisition gate
  - Layer 4 Configurable Helper rule evaluations across 3 distinct profiles
  - Verified behavioral variance and economic realism in closed loop


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
- **Scenario 004 (Canonical Real Map Import)**:
  - Headerless raw byte grid decoding (`maps/Cache/<map_id>.data`)
  - Resolution of historic 2-byte truncation bug (`W*H - 2` padding)
  - Bit-exact bitmask semantics (`0x01` East, `0x02` North, `0x10` Safety, `0x20` Combat)
  - Full Map 0 Talking Island (512x512 = 262,144 cells) geometry digest match (`7fe59f4a4f28fa0c87e69c67506ea578b2860d48e11ef61ffd7b66aef97ff9e5`)
  - Standalone map import CLI (`tools/import_real_map.py`)
  - Dynamic runtime overlays (`DungeonTable` portals, `DoorInstance` states) decoupled from static terrain
  - Seamless integration into existing Native `WorldMapGrid` and `MovementEngine` without binary coupling
- **Scenario 005 (Real Multi-Map Route Planning)**:
  - End-to-end multi-map pathfinding across Real Map 0 and Real Map 1
  - Topological graph search over world maps (`WorldRoutePlanner` via BFS)
  - Strict two-level separation: WorldRoute topology vs. intra-map coordinate planning (`AStarPlanner`)
  - Execution coordinator (`WorldRouteExecutor`) managing approach, portal trigger, and exit legs
  - Real terrain portal approach on Map 0 to `(32477, 32851)` without synthetic geometries
  - Atomic cross-map state handoff to Map 1 landing `(32669, 32802, heading 4)`
  - Real Map 1 local navigation to destination `(32671, 32804)`
- **Scenario 006 (Playable MVP)**:
  - First end-to-end playable and interactive vertical slice (`GameSession`)
  - Unified loop: Status View -> Hunting Area Selection -> Real World Route Planning -> Real Portal Transition -> Monster Encounter -> Turn-Based Combat -> Monster Death & EXP Mutation
  - Predefined hunting areas on Real Map 0 (`map0_field`) and Real Map 1 (`map1_dungeon`)
  - Deterministic monster templates (`Goblin`, `Skeleton`)
  - Interactive CLI and automated demonstration mode (`python mvp.py --demo`)
  - Deterministic replay verification suite (`python mvp_replay.py`) emitting `mvp_trace.jsonl`

### Conformance Verification Note
- **Scenario 003 Differential Conformance**: `PASS` (100% state and domain event equivalence between Legacy Oracle and Native Engine).
  *Note: This certification applies strictly to the verified behavioral scope of Scenario 003 and does not imply comprehensive feature parity with all L1J 1.82 mechanics.*
- **Scenario 004 Differential Conformance**: `PASS` (100% bit-exact equivalence across all 262,144 cells of Talking Island Map 0 between Legacy Oracle and Native Engine, matching canonical SHA-256 digest `7fe59f4a4f28fa0c87e69c67506ea578b2860d48e11ef61ffd7b66aef97ff9e5`).
- **Scenario 005 Differential Conformance**: `PASS` (100% conformance across L0 Map Integrity, L1 Transition Integrity, L2 World Topology, L3 Real Approach, L4 Atomic Transition Commit, and L5 Real Destination Arrival).
- **Scenario 006 Conformance**: `PASS` (100% deterministic execution of entire playable loop across real maps, portal traversal, and turn-based combat with verified state mutations).
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

Run the certified scenario replays and differential verifiers:

```bash
# Scenario 001: Combat & Death Replay
python scenario_001_replay.py

# Scenario 002: Movement & Collision Replay
python scenario_002_replay.py

# Scenario 003: Cross-Map Transition Replay
python scenario_003_replay.py

# Scenario 003: Differential Conformance against Legacy Oracle
python scenario_003_differential.py

# Scenario 004: Canonical Real Map Import Replay
python scenario_004_replay.py

# Scenario 004: Differential Conformance against Legacy Oracle
python scenario_004_differential.py

# Scenario 005: Real Multi-Map Route Planning Replay
python scenario_005_replay.py

# Scenario 005: Differential Conformance against Legacy Oracle
python scenario_005_differential.py

# Headless Player MVP (MVP-05): Official CLI Entrypoint (default 10 mins)
python mvp.py

# Custom duration & configuration profile
python mvp.py --config configs/conservative_hunt.json --duration 600000

# Scaled real-time playback (e.g. 5x speed)
python mvp.py --speed 5.0

# Headless Player MVP: Run Scenario 009 Multi-Profile Verification
python scenario_009_headless_player_mvp.py --duration 600000

# Historical / Legacy compatibility modes
python mvp.py --demo          # S006 legacy demo
python mvp.py --demo --s007   # S007 legacy demo
python mvp.py --interactive   # Text UI interactive mode
python mvp_replay.py

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
- [x] **Scenario 004**: Canonical Real Map Import
- [x] **Scenario 005**: Real Multi-Map Route Planning
- [x] **Scenario 006**: Playable MVP (Hunting / Combat / Character State)
- [x] **Scenario 007**: Multi-Actor Persistent Native World (10-min Virtual Run)
- [x] **Scenario 008**: Configurable Autonomous Hunting & Town Resupply Cycle (30-min Virtual Run)
- [x] **Scenario 009**: Headless Player MVP Multi-Profile Verification (Closed-Loop Run)
- [x] **MVP-05**: Layer 3 Player Operation Model & Layer 4 Configurable Helper
- [ ] Speed Buff Potions Runtime Action Speed Scaling (Green Potion / Bravery Potion movement & attack frames)
- [ ] Town Warehouse Storage & Weight Economics (Doruru / Elf Warehouse)


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
