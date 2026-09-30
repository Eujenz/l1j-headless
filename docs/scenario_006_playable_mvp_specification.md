# Scenario 006: Playable MVP Specification

---

## 1. Objective

Deliver the first **Headless Playable MVP** for L1J Headless by composing certified subsystems (Scenario 001 through 005) into an interactive, deterministic, end-to-end player game loop:
```text
Start / Status Display
        ↓
Select Hunting Area
        ↓
World-Level Route Planning (BFS)
        ↓
Local Navigation & Physical Movement (A*)
        ↓
Cross-Map Portal Transition (Real Map 0 -> Real Map 1)
        ↓
Arrive at Hunting Area
        ↓
Encounter Monster
        ↓
Turn-Based Combat (Canonical Hit & Damage)
        ↓
Monster Death & EXP Mutation
        ↓
Continue Hunting / Return / Quit
```

This vertical slice proves that the Headless Native Runtime is human-playable and machine-drivable without live game servers, GUIs, or network protocols.

---

## 2. Scope & Boundaries

### Included Scope
- Minimal `GameSession` orchestrator managing player session lifecycle.
- Real canonical map navigation across Map 0 (Talking Island Surface) and Map 1 (Talking Island Dungeon 1F).
- Two predefined hunting destinations:
  - `map0_field`: Map 0 Hunting Ground at `(32475, 32854)` (local same-map route)
  - `map1_dungeon`: Map 1 Dungeon Hunting Ground at `(32671, 32804)` (cross-map route via `portal_ti_to_tid1`)
- Deterministic monster encounters (`Goblin` on Map 0, `Skeleton` on Map 1).
- Turn-based combat reusing `CanonicalCombat` (`HitFigure` and `DmgSystem`) and `NativeRng`.
- Interactive CLI entrypoint (`mvp.py`) with support for a non-interactive `--demo` mode.
- Non-interactive regression replay (`mvp_replay.py`) emitting `mvp_trace.jsonl`.

### Excluded Scope (Non-Goals)
- No full character progression or level curves.
- No equipment management, inventory loot pickup, or weight systems.
- No magic, spells, MP, or class skills.
- No NPC dialogs, shops, quests, or trading.
- No real-time tick loop, async timers, or background threads.
- No database persistence or save files (pure in-memory session).
- No web frontend, GUI, or socket networking.

---

## 3. Existing Certified Primitives Reused

The Playable MVP strictly orchestrates existing certified primitives:
1. **Combat & Damage (Scenario 001)**: `CanonicalCombat.resolve_hit`, `calculate_damage`, HP mutation, `MonsterDied`, `ExperienceGranted`.
2. **Step Physics & Collision (Scenario 002)**: `can_move`, `MovementEngine`, authentic directional bitmasks (`0x01` East, `0x02` North).
3. **Cross-Map Transition (Scenario 003)**: `portal_ti_to_tid1`, `TransitionEngine.trigger_transition`, atomic world state mutation.
4. **Real Map Geometry (Scenario 004)**: `WorldMapGrid` backed by decoded legacy `.data` grids for Map 0 and Map 1 with 2-byte truncation padding.
5. **Multi-Map Route Planning (Scenario 005)**: `WorldRoutePlanner` (BFS), `WorldRouteExecutor`, two-level planning.

---

## 4. Player State

The player entity reuses [`Actor`](file:///C:/Users/p0282768/Documents/l1j-headless/native_engine/model.py):
- `id`: `10001`
- `name`: `"Traveler"`
- `class_type`: `1` (Knight)
- `level`: `1`
- `hp`: `100`, `max_hp`: `100`
- `str`: `16`, `dex`: `12`, `con`: `14`, `int`: `8`, `wis`: `9`, `cha`: `12`
- `pos`: `Position(x=32477, y=32854, map_id=0)`
- `heading`: `0`
- `equipped_weapon`: `Weapon(item_id=1, name="Short Sword", weapon_type=1, dmg_small=8, dmg_large=8, enchant=0, bless=0)`
- `exp`: `0`
- `lawful`: `0`

---

## 5. Hunting Area Fixtures

```python
@dataclass(frozen=True)
class HuntingArea:
    id: str
    name: str
    map_id: int
    goal_x: int
    goal_y: int
    monster_type: str
```

1. **`map0_field`**:
   - Name: `Talking Island Surface Field`
   - Map: `0`
   - Goal: `(32475, 32854)`
   - Monster: `Goblin`
2. **`map1_dungeon`**:
   - Name: `Talking Island Dungeon 1F`
   - Map: `1`
   - Goal: `(32671, 32804)`
   - Monster: `Skeleton`

---

## 6. Monster Fixtures

```python
@dataclass
class MonsterTemplate:
    id: int
    name: str
    level: int
    hp: int
    ac: int
    exp: int
    size: str
    atk_min: int
    atk_max: int
```

- **`Goblin`**: Level 3, HP 30, AC 10, EXP 20, Size "small", Atk 3..6.
- **`Skeleton`**: Level 5, HP 45, AC 8, EXP 40, Size "small", Atk 5..9.

---

## 7. Encounter Model

- When the player reaches a hunting area or executes `[H] Hunt`:
  1. The area's template is instantiated into an active `Monster` combatant.
  2. Session state transitions to `HUNTING` / `COMBAT`.
  3. The active target is set to the newly spawned monster.

---

## 8. Combat Loop

Combat is strictly turn-based:
1. **Player Turn**:
   - `CanonicalCombat.resolve_hit(player, monster, player.weapon, rng)`
   - On hit: `damage = CanonicalCombat.calculate_damage(...)`, monster HP reduced.
   - If monster HP drops to 0:
     - Monster marked dead (`is_dead = True`).
     - Player awarded monster's EXP reward.
     - Combat ends in `VICTORY`.
2. **Monster Turn (if alive)**:
   - Monster rolls hit against Player's AC (flee formula).
   - On hit: monster deals damage within `[atk_min..atk_max]`, player HP reduced.
   - If player HP drops to 0:
     - Player marked dead.
     - Combat ends in `DEFEAT`.

---

## 9. GameSession Architecture

```text
GameSession
├── world: World (Maps 0 & 1 loaded)
├── player: Actor
├── transition_engine: TransitionEngine
├── transition_provider: StaticTransitionProvider
├── areas: Dict[str, HuntingArea]
├── current_area: Optional[HuntingArea]
├── active_monster: Optional[Monster]
├── state: SessionState (MENU, TRAVELING, HUNTING, COMBAT, DEAD, QUIT)
└── rng: NativeRng
```

Session Methods:
- `get_status() -> dict`: Machine-readable observation dictionary.
- `select_hunting_area(area_id: str) -> Tuple[bool, str, List[DomainEvent]]`: Plans and executes route.
- `hunt() -> Tuple[bool, Optional[Monster], str]`: Triggers encounter at current area.
- `attack() -> Tuple[bool, dict, str]`: Executes single turn of combat.

---

## 10. CLI Boundary & Presentation

- The CLI (`mvp.py`) is strictly a presentation and input adapter.
- Zero business logic in CLI: all state mutations occur through `GameSession`.
- User input commands:
  - Menu: `[1]` Map 0 Field, `[2]` Map 1 Dungeon, `[S]` Status, `[Q]` Quit
  - Hunting: `[A]` Attack, `[H]` Hunt again, `[M]` Choose Hunting Area, `[S]` Status, `[Q]` Quit

---

## 11. Determinism

- All random outcomes (combat hit checks, damage rolls) use `NativeRng(seed)`.
- Given identical inputs and RNG seed, `mvp_replay.py` produces bit-identical event traces and final HP/EXP outcomes across all platforms.

---

## 12. Negative Test Cases

- **N01**: Select non-existent hunting area -> returns `(False, "INVALID_AREA", [])`.
- **N02**: Attempt to hunt while player is dead -> returns `(False, None, "PLAYER_DEAD")`.
- **N03**: Attempt to attack with no active monster -> returns `(False, {}, "NO_ACTIVE_TARGET")`.
- **N04**: Select hunting area while already at target -> zero-length transition, immediate readiness.

---

## 13. Provenance Classification

- **`LEGACY_OBSERVED`**:
  - Map 0 and Map 1 binary terrain grids (`Cache/0.data`, `Cache/1.data`)
  - Directional collision bitmask rules
  - `portal_ti_to_tid1` coordinates and transition trigger
  - Dual-dice hit evaluation (`HitFigure`) and damage formulas (`DmgSystem`)
- **`DERIVED_CANONICAL`**:
  - `Actor` player representation
  - Normalized `TransitionDefinition`
  - Portal approach waypoint sequence
- **`MODERN_DESIGN`**:
  - `GameSession` state machine and API
  - `HuntingArea` fixture schema
  - `MonsterTemplate` fixtures
  - Interactive CLI and demo mode runner
  - Turn-based encounter cycle

---

## 14. Definition of Done

1. Specification and contract frozen and committed.
2. `native_engine/session.py` implemented with `GameSession` and `HuntingArea`.
3. `mvp.py` implemented with interactive and `--demo` execution.
4. `mvp_replay.py` implemented producing `mvp_trace.jsonl`.
5. Automated test suite updated and all 8+ tests passing.
6. Full regression across Scenarios 001-005 passing.
7. README updated with Playable MVP quick-start and demo instructions.
