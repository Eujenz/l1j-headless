# MVP-05: Legacy Player Operation & Configurable Hunting Helper

## 1. Product Positioning & Executive Summary

MVP-05 converges the `l1j-headless` runtime into a **Native Headless L1J 1.82 Player**.
- **Charter**: A real L1J 1.82 player operating without a GUI client or JVM, augmented with a legacy-compatible configurable hunting helper.
- **Key Breakthrough**:
  - Unified all player intents under **Layer 3: Player Operation Model**.
  - Abstracted hunting routines into **Layer 4: Configurable Automation Rules**.
  - Preserved **100% execution equivalence** between human manual operation and automated helper operation.
  - Formally certified closed-loop autonomous cycles (Combat -> Potions -> Low Supply -> Escape Scroll -> Pandora Shop -> Dungeon Portal -> Cross-Map Transition -> Re-entry).

---

## 2. Multi-Profile Long-Running Verification (Scenario 009)

Scenario 009 verified long-running persistent gameplay across three distinct player configurations:

| Metric | `autonomous_default.json` | `conservative_hunt.json` | `aggressive_hunt.json` |
| :--- | :--- | :--- | :--- |
| **Virtual Duration** | 600,000 ms (10.0 min) | 600,000 ms (10.0 min) | 600,000 ms (10.0 min) |
| **Simulation Speed** | ~94x real-time | ~130x real-time | ~60x real-time |
| **Monsters Slain** | 19 | 21 | 19 |
| **Potions Consumed** | 58 | 49 | 31 |
| **Town Visits** | 2 | 1 | 1 |
| **Resupply Cycles** | 1 | 1 | 1 |
| **Adena Earned** | 289 | 269 | 197 |
| **Adena Spent** | 1156 | 1221 | 703 |
| **Net Adena** | -867 | -952 | -506 |
| **Outcome** | **PASS** | **PASS** | **PASS** |

### Key Observations:
1. **Behavioral Variance**: Different potion and emergency thresholds drove markedly different potion consumption rates (58 vs 49 vs 31) and town trip frequencies.
2. **Economic Realism**: Low-level novice characters buying red potions (40 adena each) in early TI Dungeon 1F naturally run at an economic deficit (-867 to -506 net adena). The runtime faithfully reflects this legacy game reality without applying fake profit optimizations.
3. **Closed Loop Integrity**: In all profiles, the player reliably recognized low supplies, escaped to Talking Island Town, purchased items from Pandora, traversed back across Map 0 to the dungeon portal, transitioned into Map 1, and resumed field hunting.

---

## 3. Real-Time Readable Trace

The runtime outputs standard, human-readable player trace events:
```text
[T=4200ms] [PLAYER] SELECT_TARGET: Target #1003 (Skeleton) acquired at (32672, 32804)
[T=4250ms] [PLAYER] ATTACK: Knight one-hand sword swing at Skeleton (Dist=1)
[T=4300ms] [COMBAT] Player deals 8 damage to Skeleton (HP: 22/30)
[T=5170ms] [PLAYER] ATTACK: Knight one-hand sword swing at Skeleton (Dist=1)
[T=6090ms] [PLAYER] USE_ITEM: Item 104 (Red Potion) used | HP 62/100 -> 84/100
[T=6090ms] [PLAYER] ATTACK: Knight one-hand sword swing at Skeleton (Dist=1)
[T=7010ms] [PLAYER] LOOT: Picked up Adena x18 from ground
```

---

## 4. Architectural Verification

- **Path Equivalence**: `tests/test_player_operation.py:test_manual_vs_automation_path_equivalence` proves that manual commands and automated rules invoke identical internal logic.
- **Target Selection Prerequisite**: `tests/test_player_operation.py:test_select_target_operation` proves that attacks cannot proceed without prior target selection.
- **Item Consumption**: All canonical consumables (Red, Orange, Clear, Green/Haste, Bravery, Escape Scroll) function strictly according to L1J 1.82 server source code.
- **No Startup Teleport**: Player begins at contract spawn coordinates `(32477, 32875, Map 0)`, walks 24 steps along the road to the portal, executes `TRANSITION_MAP`, and arrives at TI Dungeon 1F naturally.
- **Unified Clock**: `GameSession`, `HeadlessBot`, `Scheduler`, regeneration timers, and potion cooldowns share a single canonical simulation clock.
- **Player Operation Metrics**: Summary reports exact discrete player operation counts (`MOVE_STEP`, `SELECT_TARGET`, `ATTACK`, `USE_ITEM`, `LOOT`, `BUY_SUPPLY`, `TRANSITION_MAP`).

---

## 5. Official CLI Entrypoint (`mvp.py`)

```bash
# Default: Runs official Headless Player autonomous runtime (10 mins, instant VirtualClock)
python mvp.py

# Custom duration & configuration profile
python mvp.py --config configs/conservative_hunt.json --duration 600000
python mvp.py --config configs/aggressive_hunt.json --duration 600000

# Scaled real-time playback
python mvp.py --speed 5.0

# Legacy compatibility modes (preserved for regression testing)
python mvp.py --demo
python mvp.py --demo --s007
python mvp.py --interactive
```

